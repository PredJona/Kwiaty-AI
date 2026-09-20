"""Enrutador neutral de proveedores de modelos para Kwiaty."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from kwiaty.providers.contracts import ModelProvider


@dataclass(frozen=True)
class ModelResponse:
    """Resultado normalizado que el Core recibe de un proveedor."""

    content: str
    success: bool = True
    provider_name: str = "unknown"
    error: str | None = None
    is_offline_notice: bool = False


class ModelRouter:
    """Invoca un proveedor sin exponer sus detalles al resto del Core."""

    def __init__(self, provider: ModelProvider):
        self._provider = provider

    def is_available(self) -> bool:
        """Indica si tanto el servidor como el modelo están disponibles."""
        status = self._provider.status()
        return status.server_available and status.model_available

    def generate(
        self,
        prompt: str,
        context: Mapping[str, Any] | None = None,
    ) -> ModelResponse:
        """Genera texto o retorna un aviso controlado de indisponibilidad."""
        status = self._provider.status()
        if not status.server_available or not status.model_available:
            detail = status.detail or "El modelo local no está disponible."
            return ModelResponse(
                content=detail,
                success=False,
                provider_name=self._provider.provider_name,
                error=detail,
                is_offline_notice=True,
            )

        response = self._provider.generate(prompt, context)
        content = response.content or response.error or "El modelo local no respondió."
        return ModelResponse(
            content=content,
            success=response.success,
            provider_name=response.provider_name,
            error=response.error,
            is_offline_notice=not response.success,
        )
