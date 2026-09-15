"""Contratos formales del sistema de herramientas de Kwiaty.

Define ToolMetadata, ToolParameter, ToolResult y el protocolo Tool según
los requisitos RF-TOOL-01 a RF-TOOL-08 y la sección 7.1 de la especificación.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, Tuple, runtime_checkable
from kwiaty.platform.base import PlatformAdapter
from kwiaty.security.risk import RiskLevel


@dataclass(frozen=True)
class ToolParameter:
    """Especificación de un parámetro aceptado por una herramienta."""
    name: str
    type_name: str  # 'str', 'int', 'float', 'bool', 'list', 'dict'
    description: str
    required: bool = True
    default: Any = None


@dataclass(frozen=True)
class ToolMetadata:
    """Metadatos inmutables y obligatorios de una herramienta (Sec. 7.1)."""
    name: str
    domain: str  # 'system', 'diagnostics', 'terminal', 'development', etc.
    description: str
    parameters: Tuple[ToolParameter, ...]
    risk_level: RiskLevel
    requires_network: bool = False
    requires_privileges: bool = False
    offline_available: bool = True
    supported_platforms: Tuple[str, ...] = ("cachyos", "linux")


@dataclass(frozen=True)
class ToolResult:
    """Resultado estructurado retornado por toda herramienta (Sec. 7.4 / RF-TOOL-05)."""
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0


@runtime_checkable
class Tool(Protocol):
    """Protocolo formal que debe satisfacer toda herramienta en Kwiaty."""

    @property
    def metadata(self) -> ToolMetadata:
        """Metadatos declarados de la herramienta."""
        ...

    def execute(self, params: Dict[str, Any], platform_adapter: PlatformAdapter) -> ToolResult:
        """Ejecuta la herramienta con los parámetros validados y el adaptador de plataforma."""
        ...
