"""Contratos neutrales para proveedores de modelos."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True)
class ProviderStatus:
    """Disponibilidad normalizada de un proveedor y su modelo."""

    server_available: bool
    model_available: bool
    detail: str = ""


@dataclass(frozen=True)
class ProviderResponse:
    """Respuesta de texto normalizada de un proveedor."""

    success: bool
    content: str
    provider_name: str
    error: str | None = None


@runtime_checkable
class ModelProvider(Protocol):
    """Operaciones que el Core puede solicitar a cualquier proveedor."""

    provider_name: str

    def status(self) -> ProviderStatus:
        """Comprueba la disponibilidad del servidor y modelo configurado."""
        ...

    def generate(
        self,
        prompt: str,
        context: Mapping[str, Any] | None = None,
    ) -> ProviderResponse:
        """Genera una respuesta de texto sin ejecutar capacidades externas."""
        ...


@dataclass(frozen=True)
class UnavailableProvider:
    """Proveedor normalizado para una configuración local no utilizable."""

    provider_name: str
    detail: str

    def status(self) -> ProviderStatus:
        return ProviderStatus(False, False, self.detail)

    def generate(
        self,
        prompt: str,
        context: Mapping[str, Any] | None = None,
    ) -> ProviderResponse:
        return ProviderResponse(False, "", self.provider_name, self.detail)
