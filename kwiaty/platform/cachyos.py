"""Implementación de PlatformAdapter específica para CachyOS / Arch Linux.

Lee directamente las interfaces del kernel (/proc, os-release) de manera determinista,
sin subprocesos inseguros y sin dependencias externas.
"""

from __future__ import annotations
import os
import platform
import shutil
import time
from typing import Callable, Dict

from kwiaty.platform.base import (
    CpuMetrics,
    DiskMetrics,
    MemoryMetrics,
    PlatformAdapter,
    ProcessMetrics,
    SystemStatusInfo,
)


class CachyOSAdapter(PlatformAdapter):
    """Adaptador de plataforma optimizado para CachyOS Linux."""

    def __init__(
        self,
        proc_dir: str = "/proc",
        os_release_path: str = "/etc/os-release",
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self._proc_dir = proc_dir
        self._os_release_path = os_release_path
        self._sleep_fn = sleep_fn

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

    def get_cpu_info(self, sample_interval: float = 0.1) -> CpuMetrics:
        """Calcula el uso agregado de CPU a partir de dos muestras de /proc/stat."""
        first_total, first_idle = self._read_cpu_times()
        self._sleep_fn(sample_interval)
        second_total, second_idle = self._read_cpu_times()

        total_delta = second_total - first_total
        idle_delta = second_idle - first_idle
        if total_delta <= 0:
            used_percent = 0.0
        else:
            used_percent = 100.0 * (total_delta - idle_delta) / total_delta
            used_percent = min(100.0, max(0.0, used_percent))

        return CpuMetrics(
            used_percent=round(used_percent, 1),
            logical_cpus=os.cpu_count() or 1,
        )

    def _read_cpu_times(self) -> tuple[int, int]:
        stat_path = os.path.join(self._proc_dir, "stat")
        try:
            with open(stat_path, "r", encoding="utf-8") as stat_file:
                fields = stat_file.readline().split()
            if not fields or fields[0] != "cpu" or len(fields) < 5:
                raise ValueError("línea agregada de CPU ausente")
            values = [int(value) for value in fields[1:]]
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"Error al leer métricas de CPU en {stat_path}: {exc}") from exc

        # guest y guest_nice ya están incluidos en user y nice en /proc/stat.
        total = sum(values[:8])
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return total, idle

    def get_disk_info(self, path: str = "/") -> DiskMetrics:
        """Obtiene capacidad y uso del sistema de archivos de una ruta."""
        usage = shutil.disk_usage(path)
        used_percent = 0.0 if usage[0] == 0 else (usage[1] / usage[0]) * 100.0
        return DiskMetrics(
            path=path,
            total_bytes=usage[0],
            used_bytes=usage[1],
            free_bytes=usage[2],
            used_percent=round(used_percent, 1),
        )

    def get_top_processes(
        self,
        sort_by: str = "memory",
        limit: int = 5,
        sample_interval: float = 0.1,
    ) -> list[ProcessMetrics]:
        """Muestrea procesos y los ordena por uso de CPU o memoria residente."""
        if sort_by not in ("cpu", "memory"):
            raise ValueError("sort_by debe ser 'cpu' o 'memory'.")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit debe ser un entero positivo.")

        first_total, _ = self._read_cpu_times()
        first_snapshot = self._read_process_snapshot()
        self._sleep_fn(sample_interval)
        second_total, _ = self._read_cpu_times()
        second_snapshot = self._read_process_snapshot()

        total_delta = second_total - first_total
        logical_cpus = os.cpu_count() or 1
        processes = []
        for pid, second in second_snapshot.items():
            first = first_snapshot.get(pid)
            if first is None:
                cpu_percent = 0.0
            elif total_delta <= 0:
                cpu_percent = 0.0
            else:
                ticks_delta = max(0, second[0] - first[0])
                cpu_percent = ticks_delta / total_delta * logical_cpus * 100.0

            processes.append(
                ProcessMetrics(
                    pid=pid,
                    name=second[1],
                    cpu_percent=round(cpu_percent, 1),
                    memory_bytes=second[2],
                )
            )

        key = (
            (lambda process: (process.cpu_percent, process.memory_bytes))
            if sort_by == "cpu"
            else (lambda process: (process.memory_bytes, process.cpu_percent))
        )
        processes.sort(key=key, reverse=True)
        return processes[:limit]

    def _read_process_snapshot(self) -> Dict[int, tuple[int, str, int]]:
        snapshot: Dict[int, tuple[int, str, int]] = {}
        try:
            entries = list(os.scandir(self._proc_dir))
        except OSError as exc:
            raise RuntimeError(
                f"Error al enumerar procesos en {self._proc_dir}: {exc}"
            ) from exc

        for entry in entries:
            if not entry.name.isdigit() or not entry.is_dir(follow_symlinks=False):
                continue
            pid = int(entry.name)
            try:
                ticks = self._read_process_ticks(entry.path)
                name = self._read_process_name(entry.path)
                memory_bytes = self._read_process_memory(entry.path)
            except (OSError, ValueError):
                continue
            snapshot[pid] = (ticks, name, memory_bytes)
        return snapshot

    @staticmethod
    def _read_process_ticks(process_dir: str) -> int:
        with open(os.path.join(process_dir, "stat"), "r", encoding="utf-8") as file:
            line = file.readline().strip()
        close_paren = line.rfind(")")
        if close_paren < 0:
            raise ValueError("stat de proceso malformado")
        fields = line[close_paren + 1 :].split()
        if len(fields) <= 12:
            raise ValueError("stat de proceso incompleto")
        return int(fields[11]) + int(fields[12])

    @staticmethod
    def _read_process_name(process_dir: str) -> str:
        with open(os.path.join(process_dir, "comm"), "r", encoding="utf-8") as file:
            name = file.readline().strip()
        if not name:
            raise ValueError("nombre de proceso vacío")
        return name

    @staticmethod
    def _read_process_memory(process_dir: str) -> int:
        with open(os.path.join(process_dir, "status"), "r", encoding="utf-8") as file:
            for line in file:
                if line.startswith("VmRSS:"):
                    fields = line.split()
                    if len(fields) < 2:
                        raise ValueError("VmRSS malformado")
                    return int(fields[1]) * 1024
        return 0

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
