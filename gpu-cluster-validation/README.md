# GPU Cluster Acceptance & Validation Suite

**Status:** Production-ready internal tool  
**Owner:** AI Infrastructure / Deployment Engineering  
**Purpose:** Automated validation of GPU cluster hardware and fabric before customer workloads

## Overview

This tool automates the acceptance testing workflow when new GPU hardware (e.g., NVIDIA HGX racks) arrives at a data center.

**What it does:**
- Discovers and validates GPU inventory and configuration
- Verifies high-speed interconnect (InfiniBand) fabric health
- Detects wiring, topology, and link errors
- Measures RDMA and GPU performance
- Validates NCCL communication across GPUs
- Generates compliance report with PASS/FAIL decision

**Who uses it:**
- Deployment engineers accepting new hardware
- Infrastructure ops validating cluster readiness
- CI/CD pipelines gating production enablement

## Quickstart

```bash
# 1. Install dependencies
pip install -e .

# 2. Configure your cluster
cp config/cluster.example.yaml config/cluster.yaml
# Edit config/cluster.yaml with your hardware details

# 3. Run full validation pipeline
gpu-cluster-validate --cluster config/cluster.yaml --output reports/

# 4. View HTML report
open reports/validation_report.html
```

## Validation Pipeline

### Phase 1: Hardware Inventory
Collects GPU, CPU, memory, NUMA, NVLink, NVSwitch configuration.  
**Fails if:** GPU missing, PCIe x8, driver mismatch, missing NVLink

### Phase 2: Fabric Topology
Discovers InfiniBand switch topology and node connectivity.  
**Fails if:** switch unreachable, node disconnected, unexpected topology

### Phase 3: Fabric Health
Scans for CRC errors, symbol errors, cable failures, port congestion.  
**Fails if:** errors detected, ports disabled, flapping links

### Phase 4: Performance Benchmarks
Measures RDMA bandwidth and latency between nodes.  
**Fails if:** below configurable SLA thresholds

### Phase 5: GPU Communication
Validates NCCL collective operations and GPUDirect RDMA.  
**Fails if:** NCCL init fails, AllReduce degraded, P2P blocked

### Phase 6: Final Report
Generates `validation_report.html` with PASS/FAIL verdict, topology diagrams, and remediation guidance.

## Architecture

```
gpu-cluster-validation/
├── src/
│   ├── validators/         # Phase-specific validation logic
│   ├── checks/             # Individual health checks (plugin-style)
│   ├── models/             # Data models (Pydantic)
│   ├── services/           # External integrations (HW APIs, Prometheus)
│   ├── reports/            # Report generation
│   └── cli/                # Command-line interface
├── config/                 # YAML cluster definitions
├── tests/                  # Pytest test suite
├── docker/                 # Dockerfile & compose
└── docs/                   # Architecture & runbooks
```

## For Developers

```bash
# Run tests (mocked hardware)
pytest tests/ -v

# Run with debug logging
gpu-cluster-validate --log-level DEBUG

# Generate test report
pytest --cov=src tests/ --cov-report=html
```

## Production Deployment

See `docker/README.md` for containerization and Kubernetes integration.

## Configuration

All cluster details (node names, GPU SKUs, fabric topology) are defined in YAML:

```yaml
cluster:
  name: "us-west-2a-hgx"
  nodes:
    - name: "gpu-node-001"
      gpus: 8
      gpu_type: "H100"
      ib_port: "1"
```

See `config/cluster.example.yaml` for full schema.

## Extensibility

To add a custom validation check:

1. Create `src/checks/my_check.py`
2. Inherit from `BaseCheck`
3. Register in `src/validators/__init__.py`

Checks execute in parallel. Failures are collected and reported.

## Metrics & Observability

- Prometheus metrics exported on `/metrics`
- Structured JSON logging (stdlib + structlog)
- All validation timings and results recorded
- Integration with Datadog/CloudWatch via logs

## Exit Codes

- `0` — All validations PASSED
- `1` — Validation FAILED (cluster not ready)
- `2` — Validation ERROR (tool misconfiguration)

Suitable for CI/CD gates: `gpu-cluster-validate ... || exit $?`

---


