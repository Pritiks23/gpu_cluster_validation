"""
SERVICES: External system integrations

This package contains service classes that encapsulate all interactions
with external systems:

- HardwareService: GPU and system queries (nvidia-smi, dmidecode, lspci)
- FabricService: InfiniBand diagnostics (ibstatus, ibnetdiscover, ibdiagnet)
- PerformanceService: RDMA benchmarks (ib_write_bw, ib_write_lat)
- NCCLService: GPU communication tests

Each service has a production implementation and a mock for testing.
The validators never directly call system commands - they use these services.
This makes testing and mocking much easier.
"""
