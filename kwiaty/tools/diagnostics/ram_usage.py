"""Herramienta R0 para diagnóstico específico de memoria RAM."""

from __future__ import annotations
import time
from typing import Any, Dict
from kwiaty.platform.base import PlatformAdapter
from kwiaty.security.risk import RiskLevel
from kwiaty.tools.contracts import Tool, ToolMetadata, ToolResult


class RamUsageTool(Tool):
    """Diagnóstico detallado del consumo de memoria RAM (RF-SYS-04)."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="kwiaty.system.ram_usage",
            domain="diagnostics",
            description="Obtiene métricas detalladas de memoria RAM utilizada, libre y disponible.",
            parameters=(),
            risk_level=RiskLevel.R0,
            requires_network=False,
            requires_privileges=False,
            offline_available=True,
            supported_platforms=("cachyos", "linux"),
        )

    def execute(self, params: Dict[str, Any], platform_adapter: PlatformAdapter) -> ToolResult:
        start_time = time.perf_counter()
        try:
            mem = platform_adapter.get_memory_info()
            data = {
                "total_mb": mem.total_mb,
                "used_mb": mem.used_mb,
                "available_mb": mem.available_mb,
                "free_mb": round(mem.free_bytes / (1024 * 1024), 2),
                "total_gb": mem.total_gb,
                "used_gb": mem.used_gb,
                "available_gb": mem.available_gb,
                "used_percent": mem.used_percent,
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
                error=f"Error al obtener métricas de RAM: {exc}",
                execution_time_ms=round(elapsed, 2),
            )
