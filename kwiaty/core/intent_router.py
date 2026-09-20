"""Intent Router de Kwiaty.

Distingue órdenes deterministas directas de solicitudes que requieren
razonamiento o planificación por parte de un modelo (RF-CORE-02, Principio P-03).
"""

from __future__ import annotations
import re
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class RouteType(str, Enum):
    DETERMINISTIC_TOOL = "DETERMINISTIC_TOOL"  # Ruta rápida directa a una herramienta
    LLM_REASONING = "LLM_REASONING"            # Requiere procesamiento por el modelo
    UNKNOWN = "UNKNOWN"                        # Petición no interpretable


@dataclass(frozen=True)
class IntentResolution:
    """Resultado del enrutamiento de intención."""
    route_type: RouteType
    tool_name: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    raw_query: str = ""
    confidence: float = 1.0


class IntentRouter:
    """Enrutador de intenciones basado en patrones deterministas y reglas de menor inteligencia."""

    def __init__(self):
        # Normalizaciones y patrones deterministas para Fase 1
        self._status_patterns = [
            r"^status$",
            r"^kwiaty status$",
            r"^estado$",
            r"^diagnostico$",
            r"^diagnóstico$",
            r"^como esta el sistema\??$",
            r"^cómo está el sistema\??$",
            r"^resumen del sistema$",
        ]

        self._ram_patterns = [
            r"^cu[aá]nta ram estoy usando\??$",
            r"^cu[aá]nta ram uso\??$",
            r"^uso de ram$",
            r"^memoria ram$",
            r"^cu[aá]nta memoria estoy usando\??$",
            r"^cu[aá]nta memoria uso\??$",
            r"^ram$",
            r"^memoria$",
        ]

        self._cpu_patterns = [
            r"^cpu$",
            r"^uso de cpu$",
            r"^consumo de cpu$",
        ]

        self._disk_patterns = [
            r"^disco$",
            r"^uso de disco$",
            r"^espacio en disco$",
            r"^almacenamiento$",
        ]

        self._process_memory_patterns = [
            r"^procesos que m[aá]s memoria usan$",
            r"^procesos por memoria$",
        ]

        self._process_cpu_patterns = [
            r"^procesos que m[aá]s cpu usan$",
            r"^procesos por cpu$",
        ]

    def _normalize(self, text: str) -> str:
        """Normaliza texto para comparación básica."""
        cleaned = text.strip().lower()
        # Eliminar signos de puntuación iniciales y finales
        cleaned = re.sub(r"^[¡¿\s]+|[!?\s]+$", "", cleaned)
        return cleaned

    def resolve(self, query: str) -> IntentResolution:
        """Analiza la consulta y decide la ruta óptima de procesamiento."""
        cleaned = self._normalize(query)

        # 1. Comprobación de patrones de estado general
        for pat in self._status_patterns:
            if re.match(pat, cleaned):
                return IntentResolution(
                    route_type=RouteType.DETERMINISTIC_TOOL,
                    tool_name="kwiaty.system.status",
                    parameters={},
                    raw_query=query,
                    confidence=1.0,
                )

        # 2. Comprobación de patrones de memoria RAM
        for pat in self._ram_patterns:
            if re.match(pat, cleaned):
                return IntentResolution(
                    route_type=RouteType.DETERMINISTIC_TOOL,
                    tool_name="kwiaty.system.ram_usage",
                    parameters={},
                    raw_query=query,
                    confidence=1.0,
                )

        for pat in self._cpu_patterns:
            if re.match(pat, cleaned):
                return IntentResolution(
                    route_type=RouteType.DETERMINISTIC_TOOL,
                    tool_name="kwiaty.system.cpu_usage",
                    parameters={},
                    raw_query=query,
                    confidence=1.0,
                )

        for pat in self._disk_patterns:
            if re.match(pat, cleaned):
                return IntentResolution(
                    route_type=RouteType.DETERMINISTIC_TOOL,
                    tool_name="kwiaty.system.disk_usage",
                    parameters={"path": "/"},
                    raw_query=query,
                    confidence=1.0,
                )

        for pat in self._process_memory_patterns:
            if re.match(pat, cleaned):
                return IntentResolution(
                    route_type=RouteType.DETERMINISTIC_TOOL,
                    tool_name="kwiaty.system.top_processes",
                    parameters={"sort_by": "memory", "limit": 5},
                    raw_query=query,
                    confidence=1.0,
                )

        for pat in self._process_cpu_patterns:
            if re.match(pat, cleaned):
                return IntentResolution(
                    route_type=RouteType.DETERMINISTIC_TOOL,
                    tool_name="kwiaty.system.top_processes",
                    parameters={"sort_by": "cpu", "limit": 5},
                    raw_query=query,
                    confidence=1.0,
                )

        # Si no hay coincidencia determinista, se delega al LLM (para fases posteriores)
        return IntentResolution(
            route_type=RouteType.LLM_REASONING,
            tool_name=None,
            parameters={},
            raw_query=query,
            confidence=0.5,
        )
