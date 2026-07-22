"""
VALIDATORS: Phase-specific validation logic

This package contains validators for each of the 6 validation phases:
- Phase 1: Hardware Inventory (GPU SKU, driver versions, NUMA topology)
- Phase 2: Fabric Topology (InfiniBand switch discovery)
- Phase 3: Fabric Health (CRC errors, link flaps, disabled ports)
- Phase 4: Performance (RDMA bandwidth/latency benchmarks)
- Phase 5: GPU Communication (NCCL, GPUDirect RDMA)
- Phase 6: Final Report (not a "validator" - handled separately)

Each validator:
- Inherits from BaseValidator
- Can run standalone or as part of the pipeline
- Can be tested with mocked hardware
- Returns PhaseResult with detailed check results
"""

import logging
from abc import ABC, abstractmethod
from typing import List

from gpu_cluster_validation.models import (
    ClusterConfig,
    CheckResult,
    PhaseResult,
    StatusEnum,
)


logger = logging.getLogger(__name__)


class BaseValidator(ABC):
    """
    Abstract base class for all validators.
    
    Subclasses implement the validation logic for their phase.
    """

    phase_number: int = 0
    phase_name: str = "Unknown"
    is_critical: bool = True  # If fails, stop pipeline?

    @abstractmethod
    async def validate(self, config: ClusterConfig) -> PhaseResult:
        """
        Run validation for this phase.
        
        Args:
            config: Cluster configuration
            
        Returns:
            PhaseResult with all checks and overall status
        """
        pass

    def _create_phase_result(self, checks: List[CheckResult]) -> PhaseResult:
        """Helper: convert check results into phase result"""
        # Determine overall phase status
        has_fail = any(c.status == StatusEnum.FAIL for c in checks)
        has_error = any(c.status == StatusEnum.ERROR for c in checks)

        if has_error:
            status = StatusEnum.ERROR
        elif has_fail:
            status = StatusEnum.FAIL
        else:
            status = StatusEnum.PASS

        return PhaseResult(
            phase=self.phase_number,
            name=self.phase_name,
            status=status,
            checks=checks,
            duration_seconds=sum(c.duration_seconds for c in checks),
        )


# Import all validators
from gpu_cluster_validation.validators.hardware import HardwareInventoryValidator
from gpu_cluster_validation.validators.fabric_topology import FabricTopologyValidator
from gpu_cluster_validation.validators.fabric_health import FabricHealthValidator
from gpu_cluster_validation.validators.performance import PerformanceValidator
from gpu_cluster_validation.validators.gpu_communication import GPUCommunicationValidator

__all__ = [
    "BaseValidator",
    "HardwareInventoryValidator",
    "FabricTopologyValidator",
    "FabricHealthValidator",
    "PerformanceValidator",
    "GPUCommunicationValidator",
]
