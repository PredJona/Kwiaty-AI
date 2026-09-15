"""Enrutador de modelos (Model Router) de Kwiaty.

Desacopla el Core de cualquier modelo o proveedor de IA específico (Principio P-01 / RF-AI-02).
En la Fase 1, implementa un proveedor desconectado/stub que permite verificar
que el Core sigue funcionando de forma determinista sin Ollama (RF-AI-04 / RF-OFF-02).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ModelResponse:
    content: str
    tool_calls: tuple = ()
    is_offline_notice: bool = False
    provider_name: str = "offline_stub"


class ModelRouter:
    """Administra la selección e invocación de proveedores de modelos de lenguaje."""

    def __init__(self, default_provider: str = "ollama"):
        self._default_provider = default_provider

    def is_available(self) -> bool:
        """Indica si existe un modelo de IA disponible actualmente."""
        # En la Fase 1 deliberadamente no se conecta a Ollama
        return False

    def generate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> ModelResponse:
        """Emite una respuesta de modelo o avisa de la indisponibilidad de IA."""
        return ModelResponse(
            content=(
                "El subsistema LLM (Ollama) no está activo en este incremento funcional (Fase 1). "
                "Kwiaty está operando en modo puramente determinista y local. "
                "Puede consultar operaciones directas como 'kwiaty status' o 'cuánta RAM estoy usando'."
            ),
            is_offline_notice=True,
            provider_name="offline_stub",
        )
