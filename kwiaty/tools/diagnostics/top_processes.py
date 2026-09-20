"""Tool R0 para listar procesos con mayor consumo."""

from __future__ import annotations

import time
from typing import Any, Dict

from kwiaty.platform.base import PlatformAdapter
from kwiaty.security.risk import RiskLevel
from kwiaty.tools.contracts import ToolMetadata, ToolParameter, ToolResult


class TopProcessesTool:
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="kwiaty.system.top_processes",
            domain="diagnostics",
            description="Lista procesos con mayor uso de CPU o memoria.",
            parameters=(
                ToolParameter(
                    "sort_by",
                    "str",
                    "Criterio de orden: 'cpu' o 'memory'.",
                    required=False,
                    default="memory",
                ),
                ToolParameter(
                    "limit",
                    "int",
                    "Cantidad de procesos, entre 1 y 20.",
                    required=False,
                    default=5,
                ),
            ),
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
        sort_by = params.get("sort_by", "memory")
        limit = params.get("limit", 5)
        if sort_by not in ("cpu", "memory"):
            return self._invalid_result(start, "sort_by debe ser 'cpu' o 'memory'.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            return self._invalid_result(start, "limit debe estar entre 1 y 20.")

        try:
            processes = platform_adapter.get_top_processes(
                sort_by=sort_by,
                limit=limit,
            )
            data = {
                "sort_by": sort_by,
                "processes": [
                    {
                        "pid": process.pid,
                        "name": process.name,
                        "cpu_percent": process.cpu_percent,
                        "memory_bytes": process.memory_bytes,
                    }
                    for process in processes
                ],
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
                error=f"Error al obtener procesos: {exc}",
                execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
            )

    @staticmethod
    def _invalid_result(start: float, message: str) -> ToolResult:
        return ToolResult(
            success=False,
            data={},
            error=message,
            execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
        )
