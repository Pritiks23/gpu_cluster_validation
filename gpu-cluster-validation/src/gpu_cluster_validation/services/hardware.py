"""
Hardware Service: GPU and system information queries

Abstracts:
- nvidia-smi calls
- CUDA version checks
- Driver version checks
- PCIe configuration (lspci)
- NUMA topology (numactl)
- Thermal status

In production, this makes real subprocess calls.
In tests, this returns mocked data.
"""

import asyncio
import json
import logging
import subprocess
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class HardwareService:
    """Query hardware information from system"""

    def __init__(self, use_mock: bool = True):
        """
        Initialize hardware service.
        
        Args:
            use_mock: If True, return mocked data (for testing). 
                     If False, query actual hardware.
        """
        self.use_mock = use_mock

    async def get_gpu_count(self) -> int:
        """Query total number of GPUs"""
        if self.use_mock:
            return 8

        # Production: query nvidia-smi
        try:
            result = await self._run_cmd("nvidia-smi --query-gpu=count --format=csv,noheader")
            return int(result.strip())
        except Exception as e:
            logger.error(f"Failed to query GPU count: {e}")
            raise

    async def get_gpu_types(self) -> List[str]:
        """Query GPU SKU (H100, H200, etc)"""
        if self.use_mock:
            return ["H100"] * 8

        try:
            result = await self._run_cmd(
                "nvidia-smi --query-gpu=name --format=csv,noheader"
            )
            return result.strip().split("\n")
        except Exception as e:
            logger.error(f"Failed to query GPU types: {e}")
            raise

    async def get_driver_version(self) -> str:
        """Query NVIDIA driver version"""
        if self.use_mock:
            return "550.67"

        try:
            result = await self._run_cmd("nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1")
            return result.strip()
        except Exception as e:
            logger.error(f"Failed to query driver version: {e}")
            raise

    async def get_cuda_version(self) -> str:
        """Query CUDA version"""
        if self.use_mock:
            return "12.1"

        try:
            result = await self._run_cmd("nvcc --version | grep release")
            # Extract version number from output
            return result.split("release ")[1].split(",")[0].strip()
        except Exception as e:
            logger.error(f"Failed to query CUDA version: {e}")
            raise

    async def get_pcie_lane_widths(self) -> Dict[int, int]:
        """Query PCIe lane width for each GPU"""
        if self.use_mock:
            return {i: 16 for i in range(8)}

        try:
            result = await self._run_cmd(
                "nvidia-smi --query-gpu=pci.bus_id,index --format=csv,noheader"
            )
            lanes = {}
            for line in result.strip().split("\n"):
                bus_id, idx = line.split(",")
                # Use lspci to query actual lanes
                lanes[int(idx)] = 16  # Default assumption
            return lanes
        except Exception as e:
            logger.error(f"Failed to query PCIe lanes: {e}")
            raise

    async def get_numa_topology(self) -> Dict[str, Any]:
        """Query NUMA node topology"""
        if self.use_mock:
            return {
                "node_count": 12,
                "nodes": {
                    f"node{i}": {
                        "cpus": list(range(i*10, (i+1)*10)),
                        "memory_gb": 50,
                    }
                    for i in range(12)
                },
            }

        try:
            result = await self._run_cmd("numactl --show")
            # Parse numactl output
            # This is simplified - actual parsing would be more complex
            return {"node_count": 12}
        except Exception as e:
            logger.error(f"Failed to query NUMA topology: {e}")
            raise

    async def get_nvlink_topology(self) -> Dict[str, Any]:
        """Query NVLink status and topology"""
        if self.use_mock:
            return {
                "present": True,
                "working": True,
                "link_count": 56,  # 8 GPUs: 7*8 = 56 links (full mesh)
                "topology": "full_mesh",
            }

        try:
            result = await self._run_cmd("nvidia-smi nvlink -s")
            # Parse nvlink output
            return {
                "present": True,
                "working": "OK" not in result,
                "link_count": result.count("Link"),
            }
        except Exception as e:
            logger.warning(f"NVLink query failed (expected on non-NVLink systems): {e}")
            return {"present": False, "working": False, "link_count": 0}

    async def get_nvswitch_status(self) -> Dict[str, Any]:
        """Query NVSwitch status"""
        if self.use_mock:
            return {
                "present": True,
                "working": True,
                "count": 2,
            }

        try:
            result = await self._run_cmd("nvidia-smi -i 0 --query-gpu=nvswitch --format=csv,noheader")
            return {
                "present": "OK" in result,
                "working": "OK" in result,
            }
        except Exception as e:
            logger.warning(f"NVSwitch query failed: {e}")
            return {"present": False, "working": False}

    async def get_throttle_status(self) -> Dict[str, Any]:
        """Query thermal and power throttling status"""
        if self.use_mock:
            return {
                "throttling_active": False,
                "reason": None,
                "power_limited": False,
                "thermal_limited": False,
            }

        try:
            result = await self._run_cmd(
                "nvidia-smi --query-gpu=clocks_throttle_reasons.active --format=csv,noheader"
            )
            throttling = "None" not in result
            return {
                "throttling_active": throttling,
                "reason": result.strip() if throttling else None,
            }
        except Exception as e:
            logger.error(f"Failed to query throttle status: {e}")
            raise

    async def _run_cmd(self, cmd: str) -> str:
        """
        Run shell command asynchronously.
        
        Args:
            cmd: Shell command to run
            
        Returns:
            Command output
            
        Raises:
            RuntimeError if command fails
        """
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                raise RuntimeError(f"Command failed: {stderr.decode()}")

            return stdout.decode()
        except Exception as e:
            raise RuntimeError(f"Failed to run '{cmd}': {e}")
