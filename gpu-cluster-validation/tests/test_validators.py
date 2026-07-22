"""
Test suite for validators.

Tests all validators with mocked hardware. This allows the test suite to run
on any machine without requiring actual GPUs or InfiniBand hardware.
"""

import asyncio
import pytest

from gpu_cluster_validation.models import (
    ClusterConfig,
    NodeConfig,
    GPUSpec,
    GPUType,
    FabricConfig,
    SLASpec,
    StatusEnum,
)
from gpu_cluster_validation.validators import (
    HardwareInventoryValidator,
    FabricTopologyValidator,
    FabricHealthValidator,
    PerformanceValidator,
    GPUCommunicationValidator,
)


@pytest.fixture
def sample_cluster_config():
    """Create a sample cluster config for testing"""
    return ClusterConfig(
        cluster_name="test-cluster",
        nodes=[
            NodeConfig(
                name=f"gpu-node-{i:03d}",
                gpu_count=8,
                cpus=2,
                memory_gb=1024,
                numa_nodes=12,
                ib_port="1",
                gpus=[
                    GPUSpec(
                        index=j,
                        type=GPUType.H100,
                        memory_gb=80,
                        pcie_gen="5",
                        pcie_lanes=16,
                    )
                    for j in range(8)
                ],
            )
            for i in range(8)
        ],
        fabric=FabricConfig(),
        sla=SLASpec(),
    )


class TestHardwareInventoryValidator:
    """Test Phase 1: Hardware Inventory"""

    @pytest.mark.asyncio
    async def test_gpu_count_pass(self, sample_cluster_config):
        """Test GPU count validation passes"""
        validator = HardwareInventoryValidator()
        result = await validator.validate(sample_cluster_config)

        assert result.phase == 1
        assert result.status == StatusEnum.PASS
        assert len(result.checks) > 0

        # Check that gpu_count check exists and passed
        gpu_count_check = next(
            (c for c in result.checks if c.name == "gpu_count"), None
        )
        assert gpu_count_check is not None
        assert gpu_count_check.status == StatusEnum.PASS

    @pytest.mark.asyncio
    async def test_gpu_sku_check(self, sample_cluster_config):
        """Test GPU SKU validation"""
        validator = HardwareInventoryValidator()
        result = await validator.validate(sample_cluster_config)

        sku_check = next((c for c in result.checks if c.name == "gpu_sku"), None)
        assert sku_check is not None

    @pytest.mark.asyncio
    async def test_driver_version_check(self, sample_cluster_config):
        """Test driver version validation"""
        validator = HardwareInventoryValidator()
        result = await validator.validate(sample_cluster_config)

        driver_check = next(
            (c for c in result.checks if c.name == "driver_version"), None
        )
        assert driver_check is not None
        assert driver_check.status == StatusEnum.PASS


class TestFabricTopologyValidator:
    """Test Phase 2: Fabric Topology"""

    @pytest.mark.asyncio
    async def test_fabric_discovery(self, sample_cluster_config):
        """Test fabric discovery succeeds"""
        validator = FabricTopologyValidator()
        result = await validator.validate(sample_cluster_config)

        assert result.phase == 2
        assert result.status == StatusEnum.PASS

        discovery_check = next(
            (c for c in result.checks if c.name == "fabric_discovery"), None
        )
        assert discovery_check is not None
        assert discovery_check.status == StatusEnum.PASS

    @pytest.mark.asyncio
    async def test_node_connectivity(self, sample_cluster_config):
        """Test all nodes are connected"""
        validator = FabricTopologyValidator()
        result = await validator.validate(sample_cluster_config)

        conn_check = next(
            (c for c in result.checks if c.name == "node_connectivity"), None
        )
        assert conn_check is not None


class TestFabricHealthValidator:
    """Test Phase 3: Fabric Health"""

    @pytest.mark.asyncio
    async def test_no_crc_errors(self, sample_cluster_config):
        """Test CRC error detection"""
        validator = FabricHealthValidator()
        result = await validator.validate(sample_cluster_config)

        assert result.phase == 3
        # In mocked mode, should have no errors
        assert result.status == StatusEnum.PASS

    @pytest.mark.asyncio
    async def test_all_health_checks_run(self, sample_cluster_config):
        """Test all health checks are executed"""
        validator = FabricHealthValidator()
        result = await validator.validate(sample_cluster_config)

        check_names = {c.name for c in result.checks}
        expected = {
            "crc_errors",
            "symbol_errors",
            "link_flaps",
            "disabled_ports",
            "error_counters",
            "congestion",
        }
        assert expected.issubset(check_names)


class TestPerformanceValidator:
    """Test Phase 4: Performance"""

    @pytest.mark.asyncio
    async def test_bandwidth_measurement(self, sample_cluster_config):
        """Test RDMA bandwidth check"""
        validator = PerformanceValidator()
        result = await validator.validate(sample_cluster_config)

        assert result.phase == 4
        # In mocked mode with good defaults, should pass
        assert result.status == StatusEnum.PASS

    @pytest.mark.asyncio
    async def test_latency_measurement(self, sample_cluster_config):
        """Test latency check"""
        validator = PerformanceValidator()
        result = await validator.validate(sample_cluster_config)

        latency_check = next(
            (c for c in result.checks if c.name == "rdma_latency"), None
        )
        assert latency_check is not None


class TestGPUCommunicationValidator:
    """Test Phase 5: GPU Communication"""

    @pytest.mark.asyncio
    async def test_nccl_init(self, sample_cluster_config):
        """Test NCCL initialization check"""
        validator = GPUCommunicationValidator()
        result = await validator.validate(sample_cluster_config)

        assert result.phase == 5
        assert result.status == StatusEnum.PASS

        nccl_check = next(
            (c for c in result.checks if c.name == "nccl_init"), None
        )
        assert nccl_check is not None
        assert nccl_check.status == StatusEnum.PASS

    @pytest.mark.asyncio
    async def test_gpu_p2p_check(self, sample_cluster_config):
        """Test GPU P2P communication check"""
        validator = GPUCommunicationValidator()
        result = await validator.validate(sample_cluster_config)

        p2p_check = next(
            (c for c in result.checks if c.name == "gpu_p2p"), None
        )
        assert p2p_check is not None


class TestValidationPipeline:
    """Test complete validation pipeline"""

    @pytest.mark.asyncio
    async def test_full_pipeline(self, sample_cluster_config):
        """Test all validators run in sequence"""
        from gpu_cluster_validation.engine import ValidationEngine

        engine = ValidationEngine(sample_cluster_config)
        report = await engine.run_all_phases()

        # Check overall report
        assert report.cluster_name == "test-cluster"
        assert report.overall_status == StatusEnum.PASS
        assert len(report.phases) == 5

        # Check all phases ran
        phase_nums = {p.phase for p in report.phases}
        assert phase_nums == {1, 2, 3, 4, 5}

        # Check health score calculated
        assert report.health_score > 0
        assert report.health_score <= 100

    @pytest.mark.asyncio
    async def test_exit_code_on_pass(self, sample_cluster_config):
        """Test exit code returns 0 on PASS"""
        from gpu_cluster_validation.engine import ValidationEngine

        engine = ValidationEngine(sample_cluster_config)
        report = await engine.run_all_phases()

        assert engine.get_exit_code() == 0
