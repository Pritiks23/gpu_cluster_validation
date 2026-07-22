"""
PHASE 4: Performance Validator

Runs RDMA performance benchmarks:
- ib_write_bw: Measures peak RDMA bandwidth between nodes
- ib_write_lat: Measures round-trip latency

Validates against SLA thresholds:
- Bandwidth: default 200 GB/s minimum (H100 NVLink capable)
- Latency: default < 5 µs (InfiniBand expectation)

Fails validation if performance is below threshold.
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
from gpu_cluster_validation.services.performance import PerformanceService


logger = logging.getLogger(__name__)


class PerformanceValidator(BaseValidator):
    """Phase 4: Validate fabric performance"""

    phase_number = 4
    phase_name = "Performance Benchmarks"
    is_critical = False  # Performance issues don't block, but flag for investigation

    def __init__(self):
        self.perf_service = PerformanceService()

    async def validate(self, config: ClusterConfig) -> PhaseResult:
        """Run Phase 4 validation: measure and validate performance"""
        checks: List[CheckResult] = []

        # Check 1: RDMA bandwidth
        checks.append(await self._check_bandwidth(config))

        # Check 2: RDMA latency
        checks.append(await self._check_latency(config))

        # Check 3: Bandwidth consistency across node pairs
        checks.append(await self._check_bandwidth_variance(config))

        # Check 4: Latency consistency
        checks.append(await self._check_latency_variance(config))

        return self._create_phase_result(checks)

    async def _check_bandwidth(self, config: ClusterConfig) -> CheckResult:
        """
        Benchmark RDMA bandwidth.
        
        Runs ib_write_bw between first two nodes and measures:
        - Peak throughput (GB/s)
        - Sustained throughput (over time)
        
        Default threshold: 200 GB/s (supports H100 training)
        """
        start = time.time()
        try:
            bw_results = await self.perf_service.measure_rdma_bandwidth()
            
            measured_bw = bw_results["peak_bw_gbs"]
            threshold = config.sla.rdma_bandwidth_gbs
            
            if measured_bw >= threshold:
                status = StatusEnum.PASS
                message = f"RDMA bandwidth acceptable: {measured_bw:.1f} GB/s"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"RDMA bandwidth below SLA: {measured_bw:.1f} GB/s < {threshold:.1f} GB/s"
                errors = [f"Bandwidth {measured_bw:.1f} GB/s < {threshold:.1f} GB/s"]

            return CheckResult(
                name="rdma_bandwidth",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "peak_bw_gbs": measured_bw,
                    "sustained_bw_gbs": bw_results.get("sustained_bw_gbs", 0),
                    "threshold_gbs": threshold,
                    "test_duration_sec": bw_results.get("test_duration_sec", 0),
                },
                remediation="Check for driver version compatibility, fabric congestion, or MTU mismatch",
            )
        except Exception as e:
            return self._error_check("rdma_bandwidth", str(e), time.time() - start)

    async def _check_latency(self, config: ClusterConfig) -> CheckResult:
        """
        Benchmark RDMA latency.
        
        Runs ib_write_lat and measures round-trip latency in microseconds.
        
        Default threshold: 5 µs (low-latency NVLink expectation)
        """
        start = time.time()
        try:
            lat_results = await self.perf_service.measure_rdma_latency()
            
            measured_lat = lat_results["rtt_latency_us"]
            threshold = config.sla.rdma_latency_us
            
            if measured_lat <= threshold:
                status = StatusEnum.PASS
                message = f"RDMA latency acceptable: {measured_lat:.2f} µs"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"RDMA latency above SLA: {measured_lat:.2f} µs > {threshold:.2f} µs"
                errors = [f"Latency {measured_lat:.2f} µs > {threshold:.2f} µs"]

            return CheckResult(
                name="rdma_latency",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "rtt_latency_us": measured_lat,
                    "min_latency_us": lat_results.get("min_latency_us", 0),
                    "max_latency_us": lat_results.get("max_latency_us", 0),
                    "threshold_us": threshold,
                },
                remediation="Check CPU pinning, NUMA configuration, and InfiniBand priority levels",
            )
        except Exception as e:
            return self._error_check("rdma_latency", str(e), time.time() - start)

    async def _check_bandwidth_variance(self, config: ClusterConfig) -> CheckResult:
        """
        Verify bandwidth consistency across all node pairs.
        
        High variance indicates:
        - Topology imbalance
        - Congested paths
        - Asymmetric link quality
        
        Threshold: < 10% variance
        """
        start = time.time()
        try:
            variance_info = await self.perf_service.measure_bandwidth_variance()
            
            variance_pct = variance_info["variance_percent"]
            node_pairs = variance_info["node_pairs_tested"]
            outliers = variance_info["outlier_pairs"]
            
            if variance_pct < 10:
                status = StatusEnum.PASS
                message = f"Bandwidth variance acceptable: {variance_pct:.1f}% across {node_pairs} pairs"
                errors = []
            else:
                status = StatusEnum.WARNING
                message = f"Bandwidth variance elevated: {variance_pct:.1f}%"
                errors = [f"Outlier pairs: {outliers}"]

            return CheckResult(
                name="bandwidth_variance",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "variance_percent": variance_pct,
                    "node_pairs": node_pairs,
                    "outliers": outliers,
                },
                remediation="Investigate outlier node pairs for topology/cabling issues",
            )
        except Exception as e:
            return self._error_check("bandwidth_variance", str(e), time.time() - start)

    async def _check_latency_variance(self, config: ClusterConfig) -> CheckResult:
        """
        Verify latency consistency across all node pairs.
        
        High variance indicates:
        - Congestion on certain paths
        - NUMA distance effects
        
        Threshold: < 20% variance
        """
        start = time.time()
        try:
            variance_info = await self.perf_service.measure_latency_variance()
            
            variance_pct = variance_info["variance_percent"]
            node_pairs = variance_info["node_pairs_tested"]
            
            if variance_pct < 20:
                status = StatusEnum.PASS
                message = f"Latency variance acceptable: {variance_pct:.1f}% across {node_pairs} pairs"
                errors = []
            else:
                status = StatusEnum.WARNING
                message = f"Latency variance elevated: {variance_pct:.1f}%"
                errors = []

            return CheckResult(
                name="latency_variance",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "variance_percent": variance_pct,
                    "node_pairs": node_pairs,
                },
                remediation="Review fabric topology for imbalanced paths",
            )
        except Exception as e:
            return self._error_check("latency_variance", str(e), time.time() - start)

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
