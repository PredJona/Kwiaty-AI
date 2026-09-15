"""Herramienta R0 para diagnóstico general del sistema."""

from __future__ import annotations
import time
from typing import Any, Dict
from kwiaty.platform.base import PlatformAdapter
from kwiaty.security.risk import RiskLevel
from kwiaty.tools.contracts import Tool, ToolMetadata, ToolResult


class SystemStatusTool(Tool):
    """Diagnóstico consolidado del estado de CachyOS y hardware (RF-DIAG-01)."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="kwiaty.system.status",
            domain="diagnostics",
            description="Obtiene un resumen estructurado del estado del sistema operativo, kernel, carga y memoria.",
            parameters=(),
            risk_level=RiskLevel.R0,
            requires_network=False,
            requires_privileges=False,
            offline_available=True,
            supported_platforms=("cachyos", "linux"),
        )

    def _format_uptime(self, seconds: float) -> str:
        """Formatea segundos en una cadena legible (horas, minutos)."""
        sec = int(seconds)
        days, sec = divmod(sec, 86400)
        hours, sec = divmod(sec, 3600)
        minutes, sec = divmod(sec, 60)
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0 or days > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        return " ".join(parts)

    def execute(self, params: Dict[str, Any], platform_adapter: PlatformAdapter) -> ToolResult:
        start_time = time.perf_counter()
        try:
            status_info = platform_adapter.get_system_status()
            data = {
                "os_name": status_info.os_name,
                "os_id": status_info.os_id,
                "kernel_release": status_info.kernel_release,
                "architecture": status_info.architecture,
                "hostname": status_info.hostname,
                "uptime_seconds": status_info.uptime_seconds,
                "uptime_human": self._format_uptime(status_info.uptime_seconds),
                "load_average": {
                    "1m": status_info.load_avg_1m,
                    "5m": status_info.load_avg_5m,
                    "15m": status_info.load_avg_15m,
                },
                "memory": {
                    "total_gb": status_info.memory.total_gb,
                    "used_gb": status_info.memory.used_gb,
                    "available_gb": status_info.memory.available_gb,
                    "used_percent": status_info.memory.used_percent,
                },
            }
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return ToolResult(
                success=True,
                data=data,
                execution_time_ms=round(elapsed, 2),
                metadata={"platform": platform_adapter.platform_id},
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return ToolResult(
                success=False,
                data={},
                error=f"Error al obtener estado del sistema: {exc}",
                execution_time_ms=round(elapsed, 2),
            )
