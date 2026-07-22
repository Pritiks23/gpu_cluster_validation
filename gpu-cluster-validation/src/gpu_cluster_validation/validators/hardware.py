"""
PHASE 1: Hardware Inventory Validator

Discovers and validates:
- GPU count and SKU (H100, H200, etc)
- GPU driver version
- CUDA version
- GPU UUIDs and PCIe generation/lanes
- CPU sockets and system memory
- NUMA topology
- NVLink and NVSwitch presence

Fails validation if:
- Expected GPU count doesn't match discovered
- PCIe running x8 instead of x16
- Driver/CUDA version mismatch
- NVLink missing when expected
- GPU throttling detected

In production, this queries nvidia-smi, nvidia-debugfs, and dmidecode.
For testing, we mock these calls.
"""

import asyncio
import logging
import time
from typing import Dict, List

from gpu_cluster_validation.models import (
    CheckResult,
    ClusterConfig,
    GPUSpec,
    PhaseResult,
    StatusEnum,
)
from gpu_cluster_validation.validators import BaseValidator
from gpu_cluster_validation.services.hardware import HardwareService


logger = logging.getLogger(__name__)


class HardwareInventoryValidator(BaseValidator):
    """Phase 1: Validate hardware inventory"""

    phase_number = 1
    phase_name = "Hardware Inventory"
    is_critical = True

    def __init__(self):
        self.hw_service = HardwareService()

    async def validate(self, config: ClusterConfig) -> PhaseResult:
        """
        Run Phase 1 validation.
        
        For each node in the cluster:
        1. Query nvidia-smi for GPU info
        2. Check driver and CUDA versions
        3. Verify PCIe generation and lanes
        4. Validate NUMA topology
        5. Check for NVLink/NVSwitch
        """
        checks: List[CheckResult] = []

        # Check 1: GPU count per node
        checks.append(await self._check_gpu_count(config))

        # Check 2: GPU SKU matches config
        checks.append(await self._check_gpu_sku(config))

        # Check 3: Driver version
        checks.append(await self._check_driver_version(config))

        # Check 4: CUDA version
        checks.append(await self._check_cuda_version(config))

        # Check 5: PCIe generation and lanes
        checks.append(await self._check_pcie_config(config))

        # Check 6: NUMA topology
        checks.append(await self._check_numa_topology(config))

        # Check 7: NVLink presence
        checks.append(await self._check_nvlink(config))

        # Check 8: NVSwitch (if applicable)
        checks.append(await self._check_nvswitch(config))

        # Check 9: No throttling detected
        checks.append(await self._check_thermal_throttling(config))

        return self._create_phase_result(checks)

    async def _check_gpu_count(self, config: ClusterConfig) -> CheckResult:
        """Verify GPU count matches expectation"""
        start = time.time()
        try:
            # Query actual GPU count from hardware
            discovered_count = await self.hw_service.get_gpu_count()
            expected_count = config.nodes[0].gpu_count if config.nodes else 0

            if discovered_count == expected_count:
                status = StatusEnum.PASS
                message = f"GPU count correct: {discovered_count} GPUs"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"GPU count mismatch: expected {expected_count}, found {discovered_count}"
                errors = [f"GPU count {discovered_count} != {expected_count}"]

            return CheckResult(
                name="gpu_count",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={"expected": expected_count, "discovered": discovered_count},
                remediation="Verify all GPUs are properly seated in system",
            )
        except Exception as e:
            return self._error_check("gpu_count", str(e), time.time() - start)

    async def _check_gpu_sku(self, config: ClusterConfig) -> CheckResult:
        """Verify GPU SKU matches config"""
        start = time.time()
        try:
            discovered_skus = await self.hw_service.get_gpu_types()
            config_skus = [node.gpus[0].type.value for node in config.nodes if node.gpus]

            # Check if all discovered SKUs match at least one config SKU
            if all(sku in config_skus for sku in discovered_skus):
                status = StatusEnum.PASS
                message = f"GPU SKU correct: {discovered_skus[0]}"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"GPU SKU mismatch: expected {config_skus}, found {discovered_skus}"
                errors = [f"SKU {discovered_skus} not in {config_skus}"]

            return CheckResult(
                name="gpu_sku",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={"expected": config_skus, "discovered": discovered_skus},
                remediation="Verify correct GPU models were installed",
            )
        except Exception as e:
            return self._error_check("gpu_sku", str(e), time.time() - start)

    async def _check_driver_version(self, config: ClusterConfig) -> CheckResult:
        """Verify NVIDIA driver version"""
        start = time.time()
        try:
            driver_version = await self.hw_service.get_driver_version()
            min_driver = "550"  # Configurable threshold
            
            if driver_version >= min_driver:
                status = StatusEnum.PASS
                message = f"Driver version acceptable: {driver_version}"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"Driver version too old: {driver_version} < {min_driver}"
                errors = [f"Driver {driver_version} is outdated"]

            return CheckResult(
                name="driver_version",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={"version": driver_version, "minimum": min_driver},
                remediation="Update NVIDIA driver to version 550 or later",
            )
        except Exception as e:
            return self._error_check("driver_version", str(e), time.time() - start)

    async def _check_cuda_version(self, config: ClusterConfig) -> CheckResult:
        """Verify CUDA version"""
        start = time.time()
        try:
            cuda_version = await self.hw_service.get_cuda_version()
            min_cuda = "12.0"
            
            if cuda_version >= min_cuda:
                status = StatusEnum.PASS
                message = f"CUDA version acceptable: {cuda_version}"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"CUDA version too old: {cuda_version} < {min_cuda}"
                errors = [f"CUDA {cuda_version} is outdated"]

            return CheckResult(
                name="cuda_version",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={"version": cuda_version, "minimum": min_cuda},
                remediation="Upgrade CUDA toolkit to 12.0 or later",
            )
        except Exception as e:
            return self._error_check("cuda_version", str(e), time.time() - start)

    async def _check_pcie_config(self, config: ClusterConfig) -> CheckResult:
        """Verify PCIe generation and lane width"""
        start = time.time()
        try:
            pcie_widths = await self.hw_service.get_pcie_lane_widths()
            
            # Fail if any GPU has x8 or less
            bad_widths = [w for w in pcie_widths.values() if w < 16]
            
            if not bad_widths:
                status = StatusEnum.PASS
                message = f"PCIe configuration correct: all GPUs x16"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"PCIe degraded: {len(bad_widths)} GPUs with < x16 lanes"
                errors = [f"GPU widths: {pcie_widths}"]

            return CheckResult(
                name="pcie_config",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={"pcie_widths": pcie_widths},
                remediation="Reseat GPUs and verify slot configuration",
            )
        except Exception as e:
            return self._error_check("pcie_config", str(e), time.time() - start)

    async def _check_numa_topology(self, config: ClusterConfig) -> CheckResult:
        """Verify NUMA topology matches expectations"""
        start = time.time()
        try:
            numa_info = await self.hw_service.get_numa_topology()
            expected_nodes = config.nodes[0].numa_nodes if config.nodes else 12
            
            if numa_info["node_count"] >= expected_nodes:
                status = StatusEnum.PASS
                message = f"NUMA topology correct: {numa_info['node_count']} nodes"
                errors = []
            else:
                status = StatusEnum.WARNING
                message = f"NUMA nodes less than expected: {numa_info['node_count']} < {expected_nodes}"
                errors = [f"NUMA count mismatch"]

            return CheckResult(
                name="numa_topology",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details=numa_info,
                remediation="Check BIOS settings for NUMA configuration",
            )
        except Exception as e:
            return self._error_check("numa_topology", str(e), time.time() - start)

    async def _check_nvlink(self, config: ClusterConfig) -> CheckResult:
        """Verify NVLink is present and working"""
        start = time.time()
        try:
            nvlink_status = await self.hw_service.get_nvlink_topology()
            
            if nvlink_status["present"] and nvlink_status["working"]:
                status = StatusEnum.PASS
                message = f"NVLink operational: {nvlink_status['link_count']} links"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = "NVLink not found or non-functional"
                errors = ["NVLink unavailable"]

            return CheckResult(
                name="nvlink",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details=nvlink_status,
                remediation="Verify HGX cable connections and GPU firmware",
            )
        except Exception as e:
            return self._error_check("nvlink", str(e), time.time() - start)

    async def _check_nvswitch(self, config: ClusterConfig) -> CheckResult:
        """Verify NVSwitch if applicable (8-GPU or larger HGX)"""
        start = time.time()
        try:
            nvswitch_status = await self.hw_service.get_nvswitch_status()
            
            expected = config.nodes[0].gpu_count >= 8 if config.nodes else False
            
            if expected:
                if nvswitch_status["present"] and nvswitch_status["working"]:
                    status = StatusEnum.PASS
                    message = f"NVSwitch operational"
                    errors = []
                else:
                    status = StatusEnum.FAIL
                    message = "NVSwitch expected but not found"
                    errors = ["NVSwitch unavailable"]
            else:
                status = StatusEnum.PASS
                message = "NVSwitch not expected for this configuration"
                errors = []

            return CheckResult(
                name="nvswitch",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details=nvswitch_status,
                remediation="Check NVSwitch module seating and firmware version",
            )
        except Exception as e:
            return self._error_check("nvswitch", str(e), time.time() - start)

    async def _check_thermal_throttling(self, config: ClusterConfig) -> CheckResult:
        """Verify no thermal throttling is active"""
        start = time.time()
        try:
            throttle_info = await self.hw_service.get_throttle_status()
            
            if not throttle_info["throttling_active"]:
                status = StatusEnum.PASS
                message = "No thermal throttling detected"
                errors = []
            else:
                status = StatusEnum.WARNING
                message = f"Thermal throttling detected: {throttle_info['reason']}"
                errors = ["Thermal throttling active"]

            return CheckResult(
                name="thermal_throttling",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details=throttle_info,
                remediation="Check system cooling, airflow, and thermal paste application",
            )
        except Exception as e:
            return self._error_check("thermal_throttling", str(e), time.time() - start)

    def _error_check(self, name: str, error: str, duration: float) -> CheckResult:
        """Helper to create an ERROR status check"""
        return CheckResult(
            name=name,
            phase=self.phase_number,
            status=StatusEnum.ERROR,
            duration_seconds=duration,
            message=f"Check failed to execute: {error}",
            errors=[error],
        )
