"""Tool R0 para muestrear uso agregado de CPU."""

from __future__ import annotations

import time
from typing import Any, Dict

from kwiaty.platform.base import PlatformAdapter
from kwiaty.security.risk import RiskLevel
from kwiaty.tools.contracts import ToolMetadata, ToolResult


class CpuUsageTool:
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="kwiaty.system.cpu_usage",
            domain="diagnostics",
            description="Muestrea el porcentaje agregado de uso de CPU.",
            parameters=(),
            risk_level=RiskLevel.R0,
            offline_available=True,
            supported_platforms=("cachyos", "linux"),
        )

    def execute(
        self,
        params: Dict[str, Any],
        platform_adapter: PlatformAdapter,
    ) -> ToolResult:
        start = time.perf_counter()
        try:
            metrics = platform_adapter.get_cpu_info()
            data = {
                "used_percent": metrics.used_percent,
                "logical_cpus": metrics.logical_cpus,
            }
            return ToolResult(
                success=True,
                data=data,
                metadata={"platform": platform_adapter.platform_id},
                execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                data={},
                error=f"Error al obtener uso de CPU: {exc}",
                execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
            )
