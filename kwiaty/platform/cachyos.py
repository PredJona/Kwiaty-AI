"""Implementación de PlatformAdapter específica para CachyOS / Arch Linux.

Lee directamente las interfaces del kernel (/proc, os-release) de manera determinista,
sin subprocesos inseguros y sin dependencias externas.
"""

from __future__ import annotations
import os
import platform
from typing import Dict
from kwiaty.platform.base import PlatformAdapter, MemoryMetrics, SystemStatusInfo


class CachyOSAdapter(PlatformAdapter):
    """Adaptador de plataforma optimizado para CachyOS Linux."""

    def __init__(self, proc_dir: str = "/proc", os_release_path: str = "/etc/os-release"):
        self._proc_dir = proc_dir
        self._os_release_path = os_release_path

    @property
    def platform_id(self) -> str:
        return "cachyos"

    def get_memory_info(self) -> MemoryMetrics:
        """Lee y analiza /proc/meminfo con precisión de bytes."""
        meminfo_path = os.path.join(self._proc_dir, "meminfo")
        data: Dict[str, int] = {}

        try:
            with open(meminfo_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        # El formato de /proc/meminfo suele ser 'MemTotal:       16283728 kB'
                        val_parts = parts[1].strip().split()
                        if val_parts:
                            try:
                                kb_val = int(val_parts[0])
                                data[key] = kb_val * 1024  # Convertir a bytes
                            except ValueError:
                                continue
        except OSError as exc:
            raise RuntimeError(f"Error al leer métricas de memoria en {meminfo_path}: {exc}") from exc

        total = data.get("MemTotal", 0)
        available = data.get("MemAvailable", 0)
        free = data.get("MemFree", 0)

        # Si MemAvailable no está disponible, aproximar con free + buffers + cached
        if available == 0:
            buffers = data.get("Buffers", 0)
            cached = data.get("Cached", 0)
            available = free + buffers + cached

        used = max(0, total - available)

        return MemoryMetrics(
            total_bytes=total,
            available_bytes=available,
            used_bytes=used,
            free_bytes=free,
        )

    def _read_os_release(self) -> Dict[str, str]:
        """Lee y parsea pares clave=valor de /etc/os-release."""
        info: Dict[str, str] = {}
        if not os.path.isfile(self._os_release_path):
            return {"NAME": "Linux", "ID": "linux"}

        try:
            with open(self._os_release_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        # Quitar comillas si existen
                        v = v.strip().strip('"').strip("'")
                        info[k.strip()] = v
        except OSError:
            pass

        return info

    def _read_uptime(self) -> float:
        """Lee los segundos de actividad desde /proc/uptime."""
        uptime_path = os.path.join(self._proc_dir, "uptime")
        try:
            with open(uptime_path, "r", encoding="utf-8") as f:
                line = f.readline().strip()
                if line:
                    return float(line.split()[0])
        except (OSError, ValueError):
            pass
        return 0.0

    def get_system_status(self) -> SystemStatusInfo:
        """Construye un diagnóstico consolidado de CachyOS."""
        os_info = self._read_os_release()
        uname_res = platform.uname()

        try:
            load_avg = os.getloadavg()
        except OSError:
            load_avg = (0.0, 0.0, 0.0)

        memory_metrics = self.get_memory_info()

        return SystemStatusInfo(
            os_name=os_info.get("PRETTY_NAME", os_info.get("NAME", "CachyOS Linux")),
            os_id=os_info.get("ID", "cachyos"),
            kernel_release=uname_res.release,
            architecture=uname_res.machine,
            hostname=uname_res.node,
            uptime_seconds=self._read_uptime(),
            load_avg_1m=round(load_avg[0], 2),
            load_avg_5m=round(load_avg[1], 2),
            load_avg_15m=round(load_avg[2], 2),
            memory=memory_metrics,
        )
