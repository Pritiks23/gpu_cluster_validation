"""
MODELS: Cluster configuration and validation result schemas

This module defines the data structures used throughout the validation pipeline.
All cluster configuration (from YAML) and all validation results are modeled here
using Pydantic for type safety and automatic validation.

Think of this as the "contract" between what we read from config files and what
the validators expect to work with.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StatusEnum(str, Enum):
    """Validation result status"""
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


class GPUType(str, Enum):
    """Supported GPU SKUs"""
    H100 = "H100"
    H200 = "H200"
    L40S = "L40S"
    A100 = "A100"
    A6000 = "A6000"
    UNKNOWN = "UNKNOWN"


# ==================== Configuration Models ====================

class GPUSpec(BaseModel):
    """Single GPU specification"""
    index: int = Field(..., description="GPU index (0-7)")
    type: GPUType = Field(default=GPUType.UNKNOWN, description="GPU SKU")
    memory_gb: int = Field(default=80, description="GPU memory in GB")
    compute_capability: str = Field(default="8.0", description="CUDA compute capability")
    uuid: Optional[str] = Field(default=None, description="GPU UUID")
    pcie_gen: str = Field(default="5", description="PCIe generation (e.g., '5')")
    pcie_lanes: int = Field(default=16, description="PCIe lane width")


class NodeConfig(BaseModel):
    """Single compute node configuration"""
    name: str = Field(..., description="Node hostname/identifier")
    gpu_count: int = Field(default=8, description="Number of GPUs on node")
    gpus: List[GPUSpec] = Field(default_factory=list, description="Detailed GPU specs")
    cpu_sockets: int = Field(default=2, description="Number of CPU sockets")
    memory_gb: int = Field(default=1024, description="Total system memory in GB")
    numa_nodes: int = Field(default=12, description="NUMA nodes present")
    ib_port: str = Field(default="1", description="Primary InfiniBand port")
    nvlink_topology: str = Field(default="full_mesh", description="NVLink connection type")
    role: str = Field(default="compute", description="Node role (compute/storage/mgmt)")


class FabricConfig(BaseModel):
    """InfiniBand fabric configuration"""
    switch_type: str = Field(default="mellanox_sb", description="Switch SKU")
    hca_type: str = Field(default="mellanox_cx7", description="Host channel adapter SKU")
    expected_link_width: str = Field(default="8x", description="Expected link width")
    expected_link_speed: str = Field(default="400g", description="Expected link speed")
    topology: str = Field(default="fat_tree", description="Expected topology (fat_tree/torus/etc)")


class SLASpec(BaseModel):
    """Performance SLA thresholds"""
    rdma_bandwidth_gbs: float = Field(default=200.0, description="Min RDMA throughput (GB/s)")
    rdma_latency_us: float = Field(default=5.0, description="Max RDMA latency (µs)")
    nccl_allreduce_throughput_gbs: float = Field(default=180.0, description="Min AllReduce throughput")


class ClusterConfig(BaseModel):
    """Complete cluster configuration"""
    cluster_name: str = Field(..., description="Cluster identifier")
    deployment_date: datetime = Field(default_factory=datetime.now, description="When hardware arrived")
    nodes: List[NodeConfig] = Field(..., description="List of compute nodes")
    fabric: FabricConfig = Field(default_factory=FabricConfig, description="Fabric configuration")
    sla: SLASpec = Field(default_factory=SLASpec, description="Performance SLAs")
    tags: Dict[str, str] = Field(default_factory=dict, description="Arbitrary metadata tags")


# ==================== Validation Result Models ====================

class CheckResult(BaseModel):
    """Result of a single validation check"""
    name: str = Field(..., description="Check name (e.g., 'gpu_inventory')")
    phase: int = Field(..., description="Validation phase (1-6)")
    status: StatusEnum = Field(..., description="PASS/FAIL/WARNING/ERROR")
    duration_seconds: float = Field(default=0.0, description="Execution time")
    message: str = Field(default="", description="Human-readable result message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Raw check data")
    errors: List[str] = Field(default_factory=list, description="Failure reasons")
    remediation: Optional[str] = Field(default=None, description="How to fix if failed")


class PhaseResult(BaseModel):
    """Result of a validation phase"""
    phase: int = Field(..., description="Phase number (1-6)")
    name: str = Field(..., description="Phase name (e.g., 'Hardware Inventory')")
    status: StatusEnum = Field(..., description="Overall phase status")
    duration_seconds: float = Field(default=0.0, description="Total phase duration")
    checks: List[CheckResult] = Field(default_factory=list, description="Individual check results")

    @property
    def failed_checks(self) -> List[CheckResult]:
        """Returns all failed checks in this phase"""
        return [c for c in self.checks if c.status == StatusEnum.FAIL]

    @property
    def check_count(self) -> int:
        """Total number of checks in this phase"""
        return len(self.checks)

    @property
    def pass_count(self) -> int:
        """Number of passing checks"""
        return len([c for c in self.checks if c.status == StatusEnum.PASS])


class ValidationReport(BaseModel):
    """Complete validation report - output artifact"""
    cluster_name: str = Field(..., description="Cluster being validated")
    timestamp: datetime = Field(default_factory=datetime.now, description="When validation ran")
    overall_status: StatusEnum = Field(..., description="PASS/FAIL verdict")
    health_score: float = Field(default=0.0, description="0-100 health percentage")
    phases: List[PhaseResult] = Field(default_factory=list, description="All phase results")
    duration_seconds: float = Field(default=0.0, description="Total validation time")
    deployment_ready: bool = Field(default=False, description="Safe to enable for customers?")
    recommendations: List[str] = Field(default_factory=list, description="Operator guidance")

    @property
    def failed_phases(self) -> List[PhaseResult]:
        """Returns all failed phases"""
        return [p for p in self.phases if p.status == StatusEnum.FAIL]

    @property
    def total_checks(self) -> int:
        """Count all checks across all phases"""
        return sum(p.check_count for p in self.phases)

    @property
    def total_pass(self) -> int:
        """Count all passing checks"""
        return sum(p.pass_count for p in self.phases)

    def calculate_health_score(self) -> None:
        """Updates health_score based on pass ratio"""
        if self.total_checks == 0:
            self.health_score = 0.0
        else:
            self.health_score = (self.total_pass / self.total_checks) * 100


# ==================== Utility Models ====================

@dataclass
class HardwareInventory:
    """Discovered hardware state (used during Phase 1)"""
    gpu_count: int
    gpu_types: Dict[int, str]  # {gpu_index: 'H100', ...}
    driver_version: str
    cuda_version: str
    cpu_sockets: int
    memory_gb: int
    nvlink_present: bool
    nvswitch_present: bool
    pcie_gens: Dict[int, str]  # {gpu_index: '5', ...}
    pcie_lanes: Dict[int, int]  # {gpu_index: 16, ...}
    numa_topology: Dict[str, Any]


@dataclass
class FabricTopology:
    """Discovered fabric state (used during Phase 2)"""
    leaf_switches: List[str]
    spine_switches: List[str]
    nodes_connected: List[str]
    nodes_disconnected: List[str]
    link_state: Dict[str, str]  # {link_id: 'ACTIVE'/'DOWN',...}
    link_width: Dict[str, str]  # {link_id: '8x',...}
    link_speed: Dict[str, str]  # {link_id: '400g',...}


@dataclass
class PerformanceMetrics:
    """Measured performance (used during Phases 4-5)"""
    rdma_bandwidth_gbs: float
    rdma_latency_us: float
    nccl_allreduce_gbs: float
    gpu_p2p_bandwidth_gbs: float
    nvlink_bandwidth_gbs: float
