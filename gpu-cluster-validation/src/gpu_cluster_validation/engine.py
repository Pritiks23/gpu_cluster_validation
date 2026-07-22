"""
ENGINE: Main validation orchestration

This module contains the ValidationEngine - the core coordinator that:
1. Loads cluster configuration from YAML
2. Executes all 6 phases of validation in sequence
3. Collects results from each phase
4. Aggregates into final report with PASS/FAIL decision

Think of this as the "conductor" - it doesn't do the actual validation,
but it knows the order and coordinates all the validators.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import List

from gpu_cluster_validation.models import ClusterConfig, StatusEnum, ValidationReport, PhaseResult
from gpu_cluster_validation.validators import (
    HardwareInventoryValidator,
    FabricTopologyValidator,
    FabricHealthValidator,
    PerformanceValidator,
    GPUCommunicationValidator,
)


logger = logging.getLogger(__name__)


class ValidationEngine:
    """
    Main validation orchestrator.
    
    Runs all 6 phases in sequence:
    - Phase 1: Hardware inventory and driver/firmware checks
    - Phase 2: InfiniBand fabric topology discovery
    - Phase 3: Fabric health (CRC, symbol errors, flapping)
    - Phase 4: Performance benchmarks (RDMA BW/latency)
    - Phase 5: GPU communication (NCCL, P2P, GPUDirect RDMA)
    - Phase 6: Final report generation
    """

    def __init__(self, cluster_config: ClusterConfig):
        """
        Initialize engine with cluster configuration.
        
        Args:
            cluster_config: Parsed ClusterConfig from YAML
        """
        self.cluster_config = cluster_config
        self.report = ValidationReport(
            cluster_name=cluster_config.cluster_name,
            overall_status=StatusEnum.PASS,
        )
        self.start_time = None
        self.validators = [
            HardwareInventoryValidator(),
            FabricTopologyValidator(),
            FabricHealthValidator(),
            PerformanceValidator(),
            GPUCommunicationValidator(),
        ]

    async def run_all_phases(self) -> ValidationReport:
        """
        Execute all 6 validation phases.
        
        Returns:
            ValidationReport with complete results and PASS/FAIL decision
        """
        self.start_time = time.time()
        logger.info(f"Starting validation for cluster: {self.cluster_config.cluster_name}")

        # Phase 1-5: Run validators
        for validator in self.validators:
            try:
                logger.info(f"Running {validator.__class__.__name__}...")
                phase_result = await validator.validate(self.cluster_config)
                self.report.phases.append(phase_result)

                # Early exit on critical failures
                if phase_result.status == StatusEnum.FAIL and validator.is_critical:
                    logger.error(f"Phase {phase_result.phase} failed critically. Stopping pipeline.")
                    break

            except Exception as e:
                logger.exception(f"Validator {validator.__class__.__name__} crashed: {e}")
                # Create error phase result
                phase_result = PhaseResult(
                    phase=validator.phase_number,
                    name=validator.phase_name,
                    status=StatusEnum.ERROR,
                    checks=[],
                )
                self.report.phases.append(phase_result)

        # Calculate overall status and health score
        self._finalize_report()

        # Log summary
        elapsed = time.time() - self.start_time
        self.report.duration_seconds = elapsed
        logger.info(
            f"Validation complete. Status: {self.report.overall_status} "
            f"({self.report.health_score:.1f}% health). Duration: {elapsed:.1f}s"
        )

        return self.report

    def _finalize_report(self) -> None:
        """
        Determine overall status and generate recommendations.
        
        Rules:
        - PASS: All phases PASS
        - FAIL: Any critical phase FAIL
        - WARNING: Non-critical failures or warnings
        """
        # Check for any failures
        failed_phases = [p for p in self.report.phases if p.status == StatusEnum.FAIL]
        error_phases = [p for p in self.report.phases if p.status == StatusEnum.ERROR]

        if error_phases:
            self.report.overall_status = StatusEnum.ERROR
            for phase in error_phases:
                self.report.recommendations.append(
                    f"Phase {phase.phase} ({phase.name}) encountered unexpected error. "
                    f"Check logs and retry."
                )

        elif failed_phases:
            self.report.overall_status = StatusEnum.FAIL
            for phase in failed_phases:
                failed_checks = phase.failed_checks
                for check in failed_checks:
                    if check.remediation:
                        self.report.recommendations.append(
                            f"[Phase {phase.phase}] {check.name}: {check.remediation}"
                        )

        else:
            self.report.overall_status = StatusEnum.PASS
            self.report.deployment_ready = True
            self.report.recommendations.append("All validations passed. Cluster ready for deployment.")

        # Calculate health score
        self.report.calculate_health_score()

    def get_exit_code(self) -> int:
        """
        Return shell exit code suitable for CI/CD.
        
        Returns:
            0 if PASS, 1 if FAIL, 2 if ERROR
        """
        if self.report.overall_status == StatusEnum.PASS:
            return 0
        elif self.report.overall_status == StatusEnum.FAIL:
            return 1
        else:  # ERROR
            return 2


async def run_validation(config_path: str) -> ValidationReport:
    """
    Convenience function: load config and run full validation.
    
    Args:
        config_path: Path to cluster.yaml file
        
    Returns:
        ValidationReport with results
    """
    import yaml

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    # Load YAML config
    with open(config_file) as f:
        config_dict = yaml.safe_load(f)

    # Parse into Pydantic model with validation
    cluster_config = ClusterConfig(**config_dict["cluster"])

    # Run validation pipeline
    engine = ValidationEngine(cluster_config)
    return await engine.run_all_phases()
