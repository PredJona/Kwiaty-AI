"""Contrato base de Platform Adapter.

Aísla las operaciones dependientes del sistema operativo para que el Core
de Kwiaty permanezca completamente portable y agnóstico a la plataforma.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CpuMetrics:
    """Uso agregado de CPU durante un intervalo de muestreo."""

    used_percent: float
    logical_cpus: int


@dataclass(frozen=True)
class DiskMetrics:
    """Uso estructurado de un sistema de archivos."""

    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float


@dataclass(frozen=True)
class ProcessMetrics:
    """Consumo observado de un proceso durante el muestreo."""

    pid: int
    name: str
    cpu_percent: float
    memory_bytes: int


@dataclass(frozen=True)
class MemoryMetrics:
    """Métricas estandarizadas de memoria RAM."""
    total_bytes: int
    available_bytes: int
    used_bytes: int
    free_bytes: int

    @property
    def total_mb(self) -> float:
        return round(self.total_bytes / (1024 * 1024), 2)

    @property
    def used_mb(self) -> float:
        return round(self.used_bytes / (1024 * 1024), 2)

    @property
    def available_mb(self) -> float:
        return round(self.available_bytes / (1024 * 1024), 2)

    @property
    def total_gb(self) -> float:
        return round(self.total_bytes / (1024 * 1024 * 1024), 2)

    @property
    def used_gb(self) -> float:
        return round(self.used_bytes / (1024 * 1024 * 1024), 2)

    @property
    def available_gb(self) -> float:
        return round(self.available_bytes / (1024 * 1024 * 1024), 2)

    @property
    def used_percent(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return round((self.used_bytes / self.total_bytes) * 100.0, 1)


@dataclass(frozen=True)
class SystemStatusInfo:
    """Información consolidada de estado del sistema operativo."""
    os_name: str
    os_id: str
    kernel_release: str
    architecture: str
    hostname: str
    uptime_seconds: float
    load_avg_1m: float
    load_avg_5m: float
    load_avg_15m: float
    memory: MemoryMetrics


@runtime_checkable
class PlatformAdapter(Protocol):
    """Protocolo que debe implementar cualquier adaptador de sistema operativo."""

    @property
    def platform_id(self) -> str:
        """Identificador de la plataforma (ej. 'cachyos', 'generic_linux')."""
        ...

    def get_memory_info(self) -> MemoryMetrics:
        """Obtiene métricas precisas del uso de memoria RAM."""
        ...

    def get_system_status(self) -> SystemStatusInfo:
        """Obtiene un diagnóstico general del estado del sistema."""
        ...

    def get_cpu_info(self, sample_interval: float = 0.1) -> CpuMetrics:
        """Muestrea el uso agregado de CPU."""
        ...

    def get_disk_info(self, path: str = "/") -> DiskMetrics:
        """Obtiene uso del sistema de archivos que contiene una ruta."""
        ...

    def get_top_processes(
        self,
        sort_by: str = "memory",
        limit: int = 5,
        sample_interval: float = 0.1,
    ) -> list[ProcessMetrics]:
        """Lista procesos ordenados por CPU o memoria observada."""
        ...
