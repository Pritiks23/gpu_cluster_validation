# Development Guide

This guide explains how to work with the GPU Cluster Validation Suite codebase.

## Architecture Overview

```
src/gpu_cluster_validation/
├── models.py           # Pydantic data models (config + results)
├── engine.py           # Orchestration engine (runs 5 phases)
├── validators/         # Phase-specific validators
│   ├── hardware.py     # Phase 1: Hardware inventory
│   ├── fabric_topology.py  # Phase 2: Fabric discovery
│   ├── fabric_health.py    # Phase 3: Error detection
│   ├── performance.py      # Phase 4: Benchmarks
│   └── gpu_communication.py # Phase 5: NCCL & P2P
├── services/           # External system integrations
│   ├── hardware.py     # nvidia-smi wrapper
│   ├── fabric.py       # IB diagnostics wrapper
│   ├── performance.py  # RDMA benchmarks wrapper
│   └── nccl.py         # GPU communication wrapper
├── cli/
│   └── main.py         # Click-based CLI
└── reports/
    └── generator.py    # HTML report generation
```

## Data Flow

```
1. User runs CLI
   └→ cli/main.py --cluster config.yaml
   
2. Load and validate YAML config
   └→ models.ClusterConfig (Pydantic validation)
   
3. Create ValidationEngine
   └→ engine.ValidationEngine(config)
   
4. Run all 5 phases in sequence
   └→ For each validator:
       ├ Load config
       ├ Call service layer (mocked or real)
       ├ Run checks
       ├ Collect results into CheckResult list
       └→ Return PhaseResult
   
5. Aggregate all phase results
   └→ ValidationReport
   
6. Generate HTML report
   └→ reports/generator.py
   
7. Return exit code and print summary
```

## Adding a New Validation Check

### Step 1: Create check method in validator

```python
# In src/gpu_cluster_validation/validators/hardware.py

async def _check_my_new_check(self, config: ClusterConfig) -> CheckResult:
    """Validate something new"""
    start = time.time()
    try:
        result = await self.hw_service.get_my_data()
        
        if result["ok"]:
            status = StatusEnum.PASS
            message = "All good"
            errors = []
        else:
            status = StatusEnum.FAIL
            message = "Problem detected"
            errors = [result["error"]]
        
        return CheckResult(
            name="my_check",
            phase=self.phase_number,
            status=status,
            duration_seconds=time.time() - start,
            message=message,
            errors=errors,
            details=result,
            remediation="How to fix this issue",
        )
    except Exception as e:
        return self._error_check("my_check", str(e), time.time() - start)
```

### Step 2: Call it from validate()

```python
async def validate(self, config: ClusterConfig) -> PhaseResult:
    checks: List[CheckResult] = []
    
    # ... existing checks ...
    
    # Add your new check
    checks.append(await self._check_my_new_check(config))
    
    return self._create_phase_result(checks)
```

### Step 3: Add service method (if needed)

```python
# In src/gpu_cluster_validation/services/hardware.py

async def get_my_data(self) -> Dict[str, Any]:
    """Query my new data"""
    if self.use_mock:
        return {"ok": True, "data": "mocked"}
    
    # Production: query actual hardware
    raise NotImplementedError()
```

### Step 4: Add test

```python
# In tests/test_validators.py

class TestMyNewCheck:
    @pytest.mark.asyncio
    async def test_my_check(self, sample_cluster_config):
        validator = HardwareInventoryValidator()
        result = await validator.validate(sample_cluster_config)
        
        my_check = next(
            (c for c in result.checks if c.name == "my_check"),
            None
        )
        assert my_check is not None
        assert my_check.status == StatusEnum.PASS
```

## Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test
pytest tests/test_validators.py::TestHardwareInventoryValidator::test_gpu_count_pass -v

# Run async tests
pytest tests/ -v -m asyncio
```

## Running Validation Locally

```bash
# With mocked hardware (no GPU/IB required)
make validate

# In Docker
make validate-docker

# With debug logging
make validate-debug
```

## Code Style

We enforce:
- **Black** for formatting
- **Ruff** for linting
- **MyPy** for type checking

```bash
make lint    # Check code quality
make format  # Auto-fix formatting
```

## Production Deployment

### Docker Build & Push

```bash
make docker-build
make docker-push
```

### Kubernetes Deployment

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: gpu-cluster-validation
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: validator
            image: registry.company.com/gpu-cluster-validation:latest
            args:
            - --cluster
            - /config/cluster.yaml
            - --output
            - /reports
            volumeMounts:
            - name: config
              mountPath: /config
            - name: reports
              mountPath: /reports
          volumes:
          - name: config
            configMap:
              name: cluster-config
          - name: reports
            emptyDir: {}
          restartPolicy: OnFailure
```

## Integration with CI/CD

The validation suite is designed for CI/CD integration:

```bash
#!/bin/bash
# ci-validate.sh

gpu-cluster-validate --cluster config/cluster.yaml --output reports/
EXIT_CODE=$?

# Exit code usage:
# 0 = PASS (cluster ready)
# 1 = FAIL (cluster not ready)
# 2 = ERROR (tool misconfiguration)

if [ $EXIT_CODE -eq 0 ]; then
    echo "Cluster PASSED validation. Ready for deployment."
    exit 0
else
    echo "Cluster validation FAILED. Review reports/"
    exit 1
fi
```

## Debugging

### Enable debug logging

```bash
gpu-cluster-validate --cluster config.yaml --log-level DEBUG
```

### Mock vs Real Hardware

All service classes have `use_mock` parameter:

```python
# Production: real hardware queries
service = HardwareService(use_mock=False)

# Testing: mocked responses
service = HardwareService(use_mock=True)
```

### Inspecting Results

Check intermediate JSON report:

```bash
cat reports/validation_report_*.json | python -m json.tool
```

## Common Issues

### Import Errors

```bash
# Reinstall in development mode
pip install -e ".[dev]"
```

### Async Test Failures

Ensure `pytest-asyncio` is installed:

```bash
pip install pytest-asyncio
```

### Mock Data Mismatches

Review service implementations in `src/gpu_cluster_validation/services/` -
ensure mock data matches what validators expect.

## Questions?

Contact: infrastructure-team@company.com

Or review:
- Architecture in this file
- Model definitions in `src/gpu_cluster_validation/models.py`
- Validator examples in `src/gpu_cluster_validation/validators/`
