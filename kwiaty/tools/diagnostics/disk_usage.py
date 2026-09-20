"""Tool R0 para consultar almacenamiento disponible."""

from __future__ import annotations

import time
from typing import Any, Dict

from kwiaty.platform.base import PlatformAdapter
from kwiaty.security.risk import RiskLevel
from kwiaty.tools.contracts import ToolMetadata, ToolParameter, ToolResult


class DiskUsageTool:
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="kwiaty.system.disk_usage",
            domain="diagnostics",
            description="Obtiene capacidad, uso y espacio libre de una ruta.",
            parameters=(
                ToolParameter(
                    "path",
                    "str",
                    "Ruta cuyo sistema de archivos se consultará.",
                    required=False,
                    default="/",
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
        try:
            metrics = platform_adapter.get_disk_info(params.get("path", "/"))
            data = {
                "path": metrics.path,
                "total_bytes": metrics.total_bytes,
                "used_bytes": metrics.used_bytes,
                "free_bytes": metrics.free_bytes,
                "used_percent": metrics.used_percent,
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
                error=f"Error al obtener almacenamiento: {exc}",
                execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
            )
