"""Presentador de resultados en terminal para la CLI de Kwiaty.

Formatea resultados estructurados de las herramientas y respuestas del
Orchestrator para una experiencia limpia y legible (RF-CLI-01, RF-CLI-07, Sec. 11.2).
"""

from __future__ import annotations
import json
from typing import Any, Dict
from kwiaty.core.orchestrator import OrchestratorResult
from kwiaty.core.intent_router import RouteType


class CliPresenter:
    """Formateador visual de respuestas en consola."""

    @staticmethod
    def render_json(result: OrchestratorResult) -> str:
        """Serializa el resultado completo del Orchestrator a JSON."""
        payload: Dict[str, Any] = {
            "success": result.success,
            "route": result.route.value,
            "message": result.message,
        }
        if result.tool_result:
            payload["tool_result"] = {
                "success": result.tool_result.success,
                "data": result.tool_result.data,
                "error": result.tool_result.error,
                "execution_time_ms": result.tool_result.execution_time_ms,
            }
        if result.permission_decision:
            payload["security"] = {
                "risk_level": result.permission_decision.risk_level.value,
                "status": result.permission_decision.status.value,
                "reason": result.permission_decision.reason,
            }
        if result.audit_entry:
            payload["audit"] = {
                "timestamp": result.audit_entry.timestamp,
                "authorized": result.audit_entry.authorized,
                "action": result.audit_entry.action,
            }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    @staticmethod
    def render_normal(result: OrchestratorResult) -> str:
        """Formatea el resultado de manera humana, concisa y elegante."""
        if not result.success:
            return f"❌ {result.message}"

        # Si el resultado proviene de una herramienta de diagnóstico
        if result.tool_result and result.tool_result.success:
            data = result.tool_result.data

            # 1. Caso kwiaty.system.status
            if "kernel_release" in data and "memory" in data:
                mem = data["memory"]
                load = data.get("load_average", {})
                lines = [
                    "╭────────────────── Estado del Sistema (CachyOS) ──────────────────╮",
                    f"│  Sistema:     {data.get('os_name', 'Linux')} ({data.get('architecture', 'x86_64')})",
                    f"│  Kernel:      {data.get('kernel_release', 'N/A')}",
                    f"│  Equipo:      {data.get('hostname', 'N/A')}",
                    f"│  Uptime:      {data.get('uptime_human', 'N/A')}",
                    f"│  Carga (CPU): {load.get('1m', 0.0)} (1m), {load.get('5m', 0.0)} (5m), {load.get('15m', 0.0)} (15m)",
                    f"│  Memoria RAM: {mem.get('used_gb', 0.0)} GB / {mem.get('total_gb', 0.0)} GB ({mem.get('used_percent', 0.0)}%)",
                    "╰──────────────────────────────────────────────────────────────────╯",
                ]
                return "\n".join(lines)

            # 2. Caso kwiaty.system.ram_usage
            if "total_gb" in data and "used_gb" in data and "available_gb" in data:
                pct = data.get("used_percent", 0.0)
                used_gb = data.get("used_gb", 0.0)
                total_gb = data.get("total_gb", 0.0)
                avail_gb = data.get("available_gb", 0.0)
                free_mb = data.get("free_mb", 0.0)

                lines = [
                    f"Uso de RAM: {used_gb} GB de {total_gb} GB ({pct}%)",
                    f"  • Disponible: {avail_gb} GB",
                    f"  • Libre inmediata: {free_mb} MB",
                ]
                return "\n".join(lines)

            if "logical_cpus" in data and "used_percent" in data:
                return (
                    f"Uso de CPU: {data['used_percent']}% "
                    f"({data['logical_cpus']} CPU lógicas)"
                )

            if "total_bytes" in data and "free_bytes" in data and "path" in data:
                gib = 1024 ** 3
                return "\n".join(
                    [
                        f"Almacenamiento ({data['path']}): {data['used_percent']}% usado",
                        f"  • Usado: {round(data['used_bytes'] / gib, 2)} GiB",
                        f"  • Libre: {round(data['free_bytes'] / gib, 2)} GiB",
                    ]
                )

            if "processes" in data and "sort_by" in data:
                criterion = "CPU" if data["sort_by"] == "cpu" else "memoria"
                lines = [f"Procesos con mayor uso de {criterion}:"]
                for process in data["processes"]:
                    memory_mib = round(process["memory_bytes"] / (1024 ** 2), 1)
                    lines.append(
                        f"  • PID {process['pid']} {process['name']}: "
                        f"CPU {process['cpu_percent']}%, RAM {memory_mib} MiB"
                    )
                if not data["processes"]:
                    lines.append("  • No se encontraron procesos legibles.")
                return "\n".join(lines)

            # Caso genérico estructurado
            return json.dumps(data, indent=2, ensure_ascii=False)

        # Si es un mensaje del modelo o informativo
        if result.route == RouteType.LLM_REASONING:
            return f"ℹ️ {result.message}"

        return result.message
