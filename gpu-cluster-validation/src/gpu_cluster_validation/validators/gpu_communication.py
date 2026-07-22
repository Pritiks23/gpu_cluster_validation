"""
PHASE 5: GPU Communication Validator

Validates:
- NCCL (NVIDIA Collective Communications Library) initialization
- NCCL topology discovery
- AllReduce collective operation (core training primitive)
- GPU-to-GPU P2P communication
- GPUDirect RDMA (GPU ↔ GPU over network without CPU copy)
- NVLink bandwidth between GPUs

These validations ensure that distributed training workloads
can execute correctly across the cluster.
"""

import logging
import time
from typing import Dict, List

from gpu_cluster_validation.models import (
    CheckResult,
    ClusterConfig,
    PhaseResult,
    StatusEnum,
)
from gpu_cluster_validation.validators import BaseValidator
from gpu_cluster_validation.services.nccl import NCCLService


logger = logging.getLogger(__name__)


class GPUCommunicationValidator(BaseValidator):
    """Phase 5: Validate GPU communication and NCCL"""

    phase_number = 5
    phase_name = "GPU Communication"
    is_critical = True  # Training won't work without this

    def __init__(self):
        self.nccl_service = NCCLService()

    async def validate(self, config: ClusterConfig) -> PhaseResult:
        """Run Phase 5 validation: GPU communication and NCCL"""
        checks: List[CheckResult] = []

        # Check 1: NCCL initialization
        checks.append(await self._check_nccl_init(config))

        # Check 2: NCCL topology
        checks.append(await self._check_nccl_topology(config))

        # Check 3: AllReduce collective
        checks.append(await self._check_allreduce(config))

        # Check 4: GPU-to-GPU P2P
        checks.append(await self._check_p2p_communication(config))

        # Check 5: GPUDirect RDMA
        checks.append(await self._check_gpudirect_rdma(config))

        # Check 6: NVLink bandwidth
        checks.append(await self._check_nvlink_bandwidth(config))

        return self._create_phase_result(checks)

    async def _check_nccl_init(self, config: ClusterConfig) -> CheckResult:
        """
        Verify NCCL can initialize across cluster.
        
        NCCL needs to:
        1. Discover all GPUs
        2. Discover all nodes
        3. Determine optimal collective algorithm
        4. Establish connections
        """
        start = time.time()
        try:
            init_result = await self.nccl_service.test_nccl_init()
            
            if init_result["success"]:
                status = StatusEnum.PASS
                message = f"NCCL initialized successfully across {init_result['node_count']} nodes"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"NCCL initialization failed: {init_result['error']}"
                errors = [init_result["error"]]

            return CheckResult(
                name="nccl_init",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "success": init_result["success"],
                    "node_count": init_result.get("node_count", 0),
                    "gpu_count": init_result.get("gpu_count", 0),
                    "nccl_version": init_result.get("nccl_version", "unknown"),
                },
                remediation="Check NCCL library installation, network configuration, and SSH keys for passwordless access",
            )
        except Exception as e:
            return self._error_check("nccl_init", str(e), time.time() - start)

    async def _check_nccl_topology(self, config: ClusterConfig) -> CheckResult:
        """
        Verify NCCL topology discovery.
        
        NCCL discovers the communication graph and determines:
        - Which GPUs can reach which other GPUs
        - Optimal paths for collectives
        - Ring vs tree topologies
        """
        start = time.time()
        try:
            topo_result = await self.nccl_service.get_nccl_topology()
            
            expected_gpus = sum(node.gpu_count for node in config.nodes)
            discovered_gpus = topo_result["total_gpus"]
            
            if discovered_gpus == expected_gpus:
                status = StatusEnum.PASS
                message = f"NCCL topology correct: {discovered_gpus} GPUs"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"NCCL topology mismatch: expected {expected_gpus}, found {discovered_gpus}"
                errors = [f"GPU count mismatch"]

            return CheckResult(
                name="nccl_topology",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "expected_gpus": expected_gpus,
                    "discovered_gpus": discovered_gpus,
                    "topology_type": topo_result.get("topology_type", "unknown"),
                },
                remediation="Verify all GPUs are discoverable via nvidia-smi on all nodes",
            )
        except Exception as e:
            return self._error_check("nccl_topology", str(e), time.time() - start)

    async def _check_allreduce(self, config: ClusterConfig) -> CheckResult:
        """
        Test AllReduce collective operation.
        
        AllReduce is the core primitive for:
        - Gradient synchronization in training
        - Model averaging
        - Parameter updates
        
        Measures throughput and compares against SLA.
        """
        start = time.time()
        try:
            allreduce_result = await self.nccl_service.benchmark_allreduce()
            
            throughput = allreduce_result["throughput_gbs"]
            threshold = config.sla.nccl_allreduce_throughput_gbs
            
            if throughput >= threshold:
                status = StatusEnum.PASS
                message = f"AllReduce throughput acceptable: {throughput:.1f} GB/s"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"AllReduce throughput below SLA: {throughput:.1f} GB/s < {threshold:.1f} GB/s"
                errors = [f"AllReduce throughput {throughput:.1f} GB/s < {threshold:.1f} GB/s"]

            return CheckResult(
                name="allreduce",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "throughput_gbs": throughput,
                    "threshold_gbs": threshold,
                    "latency_us": allreduce_result.get("latency_us", 0),
                    "algorithm": allreduce_result.get("algorithm", "unknown"),
                },
                remediation="Check network latency, MTU settings, and fabric congestion",
            )
        except Exception as e:
            return self._error_check("allreduce", str(e), time.time() - start)

    async def _check_p2p_communication(self, config: ClusterConfig) -> CheckResult:
        """
        Test GPU-to-GPU P2P communication.
        
        GPU-to-GPU P2P is used for:
        - Direct GPU memory access on same node (via NVLink)
        - Cross-node GPU sends/receives
        
        Failure indicates:
        - GPUs can't see each other
        - NVLink not functioning
        - PCIe configuration issue
        """
        start = time.time()
        try:
            p2p_result = await self.nccl_service.test_gpu_p2p()
            
            if p2p_result["all_pairs_working"]:
                status = StatusEnum.PASS
                message = f"GPU P2P communication working: {p2p_result['working_pairs']}/{p2p_result['total_pairs']} pairs"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"GPU P2P communication broken: {p2p_result['broken_pairs']} pairs failing"
                errors = [f"Failed pairs: {p2p_result['failed_pair_details']}"]

            return CheckResult(
                name="gpu_p2p",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "working_pairs": p2p_result["working_pairs"],
                    "total_pairs": p2p_result["total_pairs"],
                    "broken_pairs": p2p_result["broken_pairs"],
                },
                remediation="Verify GPU PCIe configuration and NVLink cabling",
            )
        except Exception as e:
            return self._error_check("gpu_p2p", str(e), time.time() - start)

    async def _check_gpudirect_rdma(self, config: ClusterConfig) -> CheckResult:
        """
        Test GPUDirect RDMA capability.
        
        GPUDirect RDMA enables:
        - GPU memory direct access from NIC (no CPU copy)
        - Lower latency for inter-node communication
        - Higher throughput
        
        Optional but highly recommended for training clusters.
        """
        start = time.time()
        try:
            gpudirect_result = await self.nccl_service.test_gpudirect_rdma()
            
            if gpudirect_result["available"]:
                if gpudirect_result["working"]:
                    status = StatusEnum.PASS
                    message = "GPUDirect RDMA enabled and functional"
                    errors = []
                else:
                    status = StatusEnum.FAIL
                    message = "GPUDirect RDMA available but not working"
                    errors = ["GPUDirect RDMA initialization failed"]
            else:
                status = StatusEnum.WARNING
                message = "GPUDirect RDMA not available (performance may be limited)"
                errors = []

            return CheckResult(
                name="gpudirect_rdma",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "available": gpudirect_result["available"],
                    "working": gpudirect_result.get("working", False),
                    "capability": gpudirect_result.get("capability", "unknown"),
                },
                remediation="Enable GPUDirect RDMA in driver settings for better performance",
            )
        except Exception as e:
            return self._error_check("gpudirect_rdma", str(e), time.time() - start)

    async def _check_nvlink_bandwidth(self, config: ClusterConfig) -> CheckResult:
        """
        Measure NVLink bandwidth between GPUs on same node.
        
        NVLink provides:
        - 400+ GB/s per link (H100)
        - Full mesh connectivity (8 GPUs → 7*8 = 56 links)
        - Critical for large model training
        """
        start = time.time()
        try:
            nvlink_result = await self.nccl_service.measure_nvlink_bandwidth()
            
            avg_bandwidth = nvlink_result["avg_bandwidth_gbs"]
            min_bandwidth = nvlink_result["min_bandwidth_gbs"]
            
            # H100 NVLink: ~400 GB/s bidirectional per link
            threshold = 350  # Allow some margin
            
            if min_bandwidth >= threshold:
                status = StatusEnum.PASS
                message = f"NVLink bandwidth excellent: avg {avg_bandwidth:.1f} GB/s"
                errors = []
            else:
                status = StatusEnum.WARNING
                message = f"NVLink bandwidth degraded: min {min_bandwidth:.1f} GB/s < {threshold:.1f} GB/s"
                errors = []

            return CheckResult(
                name="nvlink_bandwidth",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "avg_bandwidth_gbs": avg_bandwidth,
                    "min_bandwidth_gbs": min_bandwidth,
                    "link_count": nvlink_result.get("link_count", 0),
                },
                remediation="Check NVLink cable connections and ensure full mesh topology",
            )
        except Exception as e:
            return self._error_check("nvlink_bandwidth", str(e), time.time() - start)

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
