"""Registro central de herramientas (Tool Registry / Tool Manager).

Gestiona el ciclo de vida, descubrimiento, metadatos y validación de
parámetros antes de la ejecución de cualquier herramienta (RF-TOOL-01 a RF-TOOL-04).
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from kwiaty.tools.contracts import Tool, ToolMetadata


class ToolRegistryError(Exception):
    """Error base del registro de herramientas."""
    pass


class ToolNotFoundError(ToolRegistryError):
    """Lanzada cuando se solicita una herramienta inexistente (RF-TOOL-04)."""
    def __init__(self, tool_name: str):
        super().__init__(f"Herramienta no registrada: '{tool_name}'")
        self.tool_name = tool_name


class InvalidParametersError(ToolRegistryError):
    """Lanzada cuando los parámetros proporcionados no cumplen el contrato de la herramienta (RF-TOOL-03)."""
    pass


class ToolRegistry:
    """Registro y validador de herramientas del sistema."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Registra una nueva herramienta en el sistema."""
        meta = tool.metadata
        if not meta.name:
            raise ToolRegistryError("La herramienta debe declarar un nombre no vacío.")
        if meta.name in self._tools:
            raise ToolRegistryError(f"La herramienta '{meta.name}' ya se encuentra registrada.")
        self._tools[meta.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Obtiene una herramienta por su nombre, o None si no existe."""
        return self._tools.get(name)

    def get_or_raise(self, name: str) -> Tool:
        """Obtiene una herramienta o lanza ToolNotFoundError (RF-TOOL-04)."""
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(name)
        return tool

    def list_tools(self) -> List[ToolMetadata]:
        """Retorna los metadatos de todas las herramientas registradas."""
        return [tool.metadata for tool in self._tools.values()]

    def validate_parameters(self, tool: Tool, params: Dict[str, Any]) -> Dict[str, Any]:
        """Valida y normaliza los parámetros para una herramienta dada (RF-TOOL-03)."""
        meta = tool.metadata
        validated: Dict[str, Any] = {}

        # Mapeo de tipos permitidos
        type_checks = {
            "str": str,
            "int": int,
            "float": (int, float),
            "bool": bool,
            "list": list,
            "dict": dict,
        }

        # Validar cada parámetro declarado
        for p in meta.parameters:
            if p.name in params:
                val = params[p.name]
                expected_type = type_checks.get(p.type_name)
                if expected_type and not isinstance(val, expected_type):
                    raise InvalidParametersError(
                        f"El parámetro '{p.name}' para '{meta.name}' debe ser de tipo '{p.type_name}', "
                        f"pero se recibió '{type(val).__name__}'."
                    )
                validated[p.name] = val
            elif p.required:
                raise InvalidParametersError(
                    f"Falta el parámetro requerido '{p.name}' para ejecutar la herramienta '{meta.name}'."
                )
            else:
                validated[p.name] = p.default

        # Detectar parámetros sobrantes no esperados
        expected_names = {p.name for p in meta.parameters}
        unexpected_keys = set(params.keys()) - expected_names
        if unexpected_keys:
            raise InvalidParametersError(
                f"Parámetros no reconocidos para '{meta.name}': {', '.join(sorted(unexpected_keys))}"
            )

        return validated
