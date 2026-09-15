"""Submódulo de Platform Adapters."""

from kwiaty.platform.base import PlatformAdapter, MemoryMetrics, SystemStatusInfo
from kwiaty.platform.cachyos import CachyOSAdapter

__all__ = [
    "PlatformAdapter",
    "MemoryMetrics",
    "SystemStatusInfo",
    "CachyOSAdapter",
]
