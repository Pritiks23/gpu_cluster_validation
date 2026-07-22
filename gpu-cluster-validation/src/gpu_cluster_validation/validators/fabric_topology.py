"""
PHASE 2: Fabric Topology Validator

Discovers and validates InfiniBand fabric:
- Runs ibnetdiscover to discover all switches and nodes
- Builds topology tree (Rack → Leaf Switches → Spine Switches → Compute Nodes)
- Verifies all expected nodes are present
- Detects disconnected switches
- Verifies topology matches expected structure (fat-tree, torus, etc)

Fails validation if:
- Node unreachable
- Switch unreachable
- Unexpected topology deviation
- Missing expected nodes
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


class FabricTopologyValidator(BaseValidator):
    """Phase 2: Validate fabric topology"""

    phase_number = 2
    phase_name = "Fabric Topology"
    is_critical = True

    def __init__(self):
        self.fabric_service = FabricService()

    async def validate(self, config: ClusterConfig) -> PhaseResult:
        """Run Phase 2 validation: discover and verify fabric topology"""
        checks: List[CheckResult] = []

        # Check 1: Discover fabric
        checks.append(await self._check_fabric_discovery(config))

        # Check 2: Verify all nodes reachable
        checks.append(await self._check_node_connectivity(config))

        # Check 3: Verify all switches reachable
        checks.append(await self._check_switch_connectivity(config))

        # Check 4: Validate topology structure
        checks.append(await self._check_topology_structure(config))

        # Check 5: Verify link state on all ports
        checks.append(await self._check_link_states(config))

        return self._create_phase_result(checks)

    async def _check_fabric_discovery(self, config: ClusterConfig) -> CheckResult:
        """Run ibnetdiscover and verify fabric is discoverable"""
        start = time.time()
        try:
            topology = await self.fabric_service.discover_topology()
            
            if topology and topology["discovery_success"]:
                status = StatusEnum.PASS
                message = f"Fabric discovered successfully. {len(topology['nodes'])} nodes, {len(topology['switches'])} switches"
                errors = []
                details = {
                    "node_count": len(topology["nodes"]),
                    "switch_count": len(topology["switches"]),
                    "discovery_time_ms": topology.get("discovery_time_ms", 0),
                }
            else:
                status = StatusEnum.FAIL
                message = "Fabric discovery failed"
                errors = ["ibnetdiscover returned no results"]
                details = {}

            return CheckResult(
                name="fabric_discovery",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details=details,
                remediation="Check InfiniBand manager is running and fabric is powered",
            )
        except Exception as e:
            return self._error_check("fabric_discovery", str(e), time.time() - start)

    async def _check_node_connectivity(self, config: ClusterConfig) -> CheckResult:
        """Verify all expected nodes are reachable"""
        start = time.time()
        try:
            expected_nodes = set(n.name for n in config.nodes)
            connected_nodes = await self.fabric_service.get_connected_nodes()
            
            missing_nodes = expected_nodes - set(connected_nodes)
            extra_nodes = set(connected_nodes) - expected_nodes
            
            if not missing_nodes:
                status = StatusEnum.PASS
                message = f"All {len(connected_nodes)} expected nodes connected"
                errors = []
                details = {"missing": [], "extra": list(extra_nodes)}
            else:
                status = StatusEnum.FAIL
                message = f"{len(missing_nodes)} nodes not reachable"
                errors = [f"Missing nodes: {missing_nodes}"]
                details = {"missing": list(missing_nodes), "extra": list(extra_nodes)}

            return CheckResult(
                name="node_connectivity",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details=details,
                remediation="Check node network cables and verify hosts are powered/booted",
            )
        except Exception as e:
            return self._error_check("node_connectivity", str(e), time.time() - start)

    async def _check_switch_connectivity(self, config: ClusterConfig) -> CheckResult:
        """Verify fabric switches are reachable"""
        start = time.time()
        try:
            switch_info = await self.fabric_service.get_switch_status()
            
            dead_switches = [s for s in switch_info["switches"] if not s["reachable"]]
            
            if not dead_switches:
                status = StatusEnum.PASS
                message = f"All {len(switch_info['switches'])} switches reachable"
                errors = []
                details = {"total": len(switch_info["switches"]), "reachable": len(switch_info["switches"])}
            else:
                status = StatusEnum.FAIL
                message = f"{len(dead_switches)} switches unreachable"
                errors = [f"Unreachable switches: {[s['name'] for s in dead_switches]}"]
                details = {"dead_switches": [s["name"] for s in dead_switches]}

            return CheckResult(
                name="switch_connectivity",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details=details,
                remediation="Check fabric switch power, fans, and network connectivity",
            )
        except Exception as e:
            return self._error_check("switch_connectivity", str(e), time.time() - start)

    async def _check_topology_structure(self, config: ClusterConfig) -> CheckResult:
        """Validate topology matches expected structure"""
        start = time.time()
        try:
            topology = await self.fabric_service.get_topology_structure()
            expected_type = config.fabric.topology
            
            # Simple check: does discovered topology match config?
            if topology["type"] == expected_type or expected_type == "auto":
                status = StatusEnum.PASS
                message = f"Topology structure correct: {topology['type']}"
                errors = []
            else:
                status = StatusEnum.WARNING
                message = f"Topology mismatch: expected {expected_type}, found {topology['type']}"
                errors = [f"Topology {topology['type']} != {expected_type}"]

            return CheckResult(
                name="topology_structure",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details={"expected": expected_type, "discovered": topology["type"]},
                remediation="Verify fabric cabling matches expected topology diagram",
            )
        except Exception as e:
            return self._error_check("topology_structure", str(e), time.time() - start)

    async def _check_link_states(self, config: ClusterConfig) -> CheckResult:
        """Verify all fabric links are up and active"""
        start = time.time()
        try:
            link_info = await self.fabric_service.get_link_states()
            
            down_links = [l for l in link_info["links"] if l["state"] != "ACTIVE"]
            
            if not down_links:
                status = StatusEnum.PASS
                message = f"All {len(link_info['links'])} fabric links active"
                errors = []
                details = {"total_links": len(link_info["links"]), "active": len(link_info["links"])}
            else:
                status = StatusEnum.FAIL
                message = f"{len(down_links)} fabric links not active"
                errors = [f"Down links: {[l['name'] for l in down_links]}"]
                details = {"down_links": [l["name"] for l in down_links]}

            return CheckResult(
                name="link_states",
                phase=self.phase_number,
                status=status,
                duration_seconds=time.time() - start,
                message=message,
                errors=errors,
                details=details,
                remediation="Check cable connections, transceiver status, and port configuration",
            )
        except Exception as e:
            return self._error_check("link_states", str(e), time.time() - start)

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
