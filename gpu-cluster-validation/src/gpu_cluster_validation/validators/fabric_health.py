"""
PHASE 3: Fabric Health Validator

Runs ibdiagnet and analyzes for:
- CRC errors (corrupted packets)
- Symbol errors (signal integrity issues)
- Link flaps (port up/down cycling)
- Disabled ports (quarantined by subnet manager)
- Cable failures (historical error counters)
- Port congestion (packet loss from queue overflow)

Fails validation if:
- Any CRC errors detected
- Symbol error rate exceeds threshold
- Ports flapping
- Ports disabled
- High error accumulation
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
from gpu_cluster_validation.services.fabric import FabricService


logger = logging.getLogger(__name__)


class FabricHealthValidator(BaseValidator):
    """Phase 3: Validate fabric health and error conditions"""

    phase_number = 3
    phase_name = "Fabric Health"
    is_critical = True

    def __init__(self):
        self.fabric_service = FabricService()

    async def validate(self, config: ClusterConfig) -> PhaseResult:
        """Run Phase 3 validation: diagnose fabric health"""
        checks: List[CheckResult] = []

        # Check 1: CRC errors
        checks.append(await self._check_crc_errors(config))

        # Check 2: Symbol errors
        checks.append(await self._check_symbol_errors(config))

        # Check 3: Link flaps
        checks.append(await self._check_link_flaps(config))

        # Check 4: Disabled ports
        checks.append(await self._check_disabled_ports(config))

        # Check 5: Error accumulation
        checks.append(await self._check_error_counters(config))

        # Check 6: Port congestion
        checks.append(await self._check_congestion(config))

        return self._create_phase_result(checks)

    async def _check_crc_errors(self, config: ClusterConfig) -> CheckResult:
        """
        Check for packet CRC errors.
        
        CRC errors indicate:
        - Bad cables
        - Failing transceivers
        - Electrical noise
        
        Even 1 CRC error is a sign of hardware issues.
        """
        start = time.time()
        try:
            crc_info = await self.fabric_service.get_crc_errors()
            
            error_count = crc_info["total_errors"]
            error_ports = crc_info["error_ports"]
            
            if error_count == 0:
                status = StatusEnum.PASS
                message = "No CRC errors detected"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"{error_count} CRC errors on {len(error_ports)} ports"
                errors = [f"CRC errors: {error_ports}"]

            return CheckResult(
                name="crc_errors",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "total_errors": error_count,
                    "affected_ports": error_ports,
                },
                remediation="Replace cables and transceivers on affected ports. Reseat connections.",
            )
        except Exception as e:
            return self._error_check("crc_errors", str(e), time.time() - start)

    async def _check_symbol_errors(self, config: ClusterConfig) -> CheckResult:
        """
        Check for symbol errors.
        
        Symbol errors indicate:
        - Poor signal quality
        - Multipath interference
        - Weak optical signal
        
        Thresholds:
        - < 100 errors per hour = acceptable for Ethernet
        - < 1 error per hour = expected for good optics
        """
        start = time.time()
        try:
            symbol_info = await self.fabric_service.get_symbol_errors()
            
            error_rate = symbol_info["errors_per_hour"]
            high_error_ports = symbol_info["ports_with_high_errors"]
            
            if error_rate < 1:
                status = StatusEnum.PASS
                message = f"Symbol errors minimal: {error_rate:.2f} errors/hour"
                errors = []
            elif error_rate < 100:
                status = StatusEnum.WARNING
                message = f"Symbol error rate elevated: {error_rate:.2f} errors/hour"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"Symbol errors excessive: {error_rate:.2f} errors/hour"
                errors = [f"Ports: {high_error_ports}"]

            return CheckResult(
                name="symbol_errors",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "errors_per_hour": error_rate,
                    "affected_ports": high_error_ports,
                },
                remediation="Check optical power levels. Inspect and clean transceiver connectors.",
            )
        except Exception as e:
            return self._error_check("symbol_errors", str(e), time.time() - start)

    async def _check_link_flaps(self, config: ClusterConfig) -> CheckResult:
        """
        Check for link flapping (port cycling up/down).
        
        Indicates:
        - Flaky cables
        - Intermittent connection issues
        - Incompatible modules
        
        Even 1 flap is suspicious.
        """
        start = time.time()
        try:
            flap_info = await self.fabric_service.get_link_flaps()
            
            flap_count = flap_info["total_flaps"]
            flapping_ports = flap_info["flapping_ports"]
            
            if flap_count == 0:
                status = StatusEnum.PASS
                message = "No link flaps detected"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"{flap_count} link flaps on {len(flapping_ports)} ports"
                errors = [f"Flapping ports: {flapping_ports}"]

            return CheckResult(
                name="link_flaps",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "total_flaps": flap_count,
                    "affected_ports": flapping_ports,
                },
                remediation="Reseat or replace cables and transceivers. Check firmware compatibility.",
            )
        except Exception as e:
            return self._error_check("link_flaps", str(e), time.time() - start)

    async def _check_disabled_ports(self, config: ClusterConfig) -> CheckResult:
        """
        Check for disabled or quarantined ports.
        
        Ports are disabled by subnet manager when:
        - Repeated errors detected
        - Exceeds error threshold
        - Manual administrative action
        """
        start = time.time()
        try:
            port_info = await self.fabric_service.get_port_status()
            
            disabled_ports = [p for p in port_info["ports"] if p["state"] == "DISABLED"]
            
            if not disabled_ports:
                status = StatusEnum.PASS
                message = f"All {len(port_info['ports'])} ports enabled"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"{len(disabled_ports)} ports disabled"
                errors = [[p["name"] for p in disabled_ports]]

            return CheckResult(
                name="disabled_ports",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "total_ports": len(port_info["ports"]),
                    "disabled_ports": [p["name"] for p in disabled_ports],
                },
                remediation="Check why subnet manager disabled ports. Fix underlying issues and re-enable.",
            )
        except Exception as e:
            return self._error_check("disabled_ports", str(e), time.time() - start)

    async def _check_error_counters(self, config: ClusterConfig) -> CheckResult:
        """
        Check cumulative hardware error counters.
        
        Accumulation indicates:
        - Slow cable/transceiver failure
        - Environmental stress (heat, EMI)
        - Marginal connections
        """
        start = time.time()
        try:
            counter_info = await self.fabric_service.get_error_counters()
            
            high_error_ports = counter_info["high_error_ports"]
            max_count = counter_info["max_error_count"]
            
            if max_count < 100:
                status = StatusEnum.PASS
                message = "Error counters within acceptable range"
                errors = []
            elif max_count < 1000:
                status = StatusEnum.WARNING
                message = f"Error counters elevated (max: {max_count})"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"Error counters excessive (max: {max_count})"
                errors = [f"High-error ports: {high_error_ports}"]

            return CheckResult(
                name="error_counters",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "max_error_count": max_count,
                    "high_error_ports": high_error_ports,
                },
                remediation="Plan cable/transceiver replacement for ports with high error counts.",
            )
        except Exception as e:
            return self._error_check("error_counters", str(e), time.time() - start)

    async def _check_congestion(self, config: ClusterConfig) -> CheckResult:
        """
        Check for port congestion (queue overflow, packet loss).
        
        Indicates:
        - Oversubscribed fabric
        - Workload imbalance
        - Underprovisioned links
        """
        start = time.time()
        try:
            congestion_info = await self.fabric_service.get_congestion_metrics()
            
            congested_ports = congestion_info["congested_ports"]
            max_loss = congestion_info["max_packet_loss_rate"]
            
            if max_loss < 0.1:  # < 0.1% loss
                status = StatusEnum.PASS
                message = "No port congestion detected"
                errors = []
            elif max_loss < 1.0:  # < 1% loss
                status = StatusEnum.WARNING
                message = f"Mild congestion detected (max loss: {max_loss:.2f}%)"
                errors = []
            else:
                status = StatusEnum.FAIL
                message = f"Significant congestion (max loss: {max_loss:.2f}%)"
                errors = [f"Congested ports: {congested_ports}"]

            return CheckResult(
                name="congestion",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={
                    "max_packet_loss_rate": max_loss,
                    "congested_ports": congested_ports,
                },
                remediation="Review traffic patterns. Consider rebalancing workloads or fabric topology.",
            )
        except Exception as e:
            return self._error_check("congestion", str(e), time.time() - start)

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
