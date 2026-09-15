"""Pruebas unitarias para ToolRegistry y contratos de herramientas."""

import unittest
from typing import Dict, Any
from kwiaty.security.risk import RiskLevel
from kwiaty.tools.contracts import (
    Tool,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)
from kwiaty.tools.registry import (
    ToolRegistry,
    ToolNotFoundError,
    InvalidParametersError,
    ToolRegistryError,
)
from kwiaty.platform.base import PlatformAdapter


class MockSimpleTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="mock.simple",
            domain="system",
            description="Herramienta mock para pruebas.",
            parameters=(
                ToolParameter("param_str", "str", "Parámetro de texto", required=True),
                ToolParameter("param_int", "int", "Parámetro numérico", required=False, default=42),
            ),
            risk_level=RiskLevel.R0,
        )

    def execute(self, params: Dict[str, Any], platform_adapter: PlatformAdapter) -> ToolResult:
        return ToolResult(success=True, data={"echo": params})


class TestToolRegistry(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.tool = MockSimpleTool()

    def test_register_and_get(self):
        """RF-TOOL-01: Mantener registro de herramientas disponibles."""
        self.registry.register(self.tool)
        retrieved = self.registry.get("mock.simple")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.metadata.name, "mock.simple")

    def test_duplicate_registration_rejected(self):
        """Rechazar registro con el mismo nombre."""
        self.registry.register(self.tool)
        with self.assertRaises(ToolRegistryError):
            self.registry.register(self.tool)

    def test_get_or_raise_unregistered(self):
        """RF-TOOL-04: Rechazar herramientas inexistentes."""
        with self.assertRaises(ToolNotFoundError):
            self.registry.get_or_raise("non_existent_tool")

    def test_validate_parameters_success(self):
        """RF-TOOL-03: Validar parámetros requeridos y aplicar valores por defecto."""
        self.registry.register(self.tool)
        validated = self.registry.validate_parameters(
            self.tool,
            {"param_str": "test_value"}
        )
        self.assertEqual(validated["param_str"], "test_value")
        self.assertEqual(validated["param_int"], 42)  # Valor por defecto

    def test_validate_parameters_missing_required(self):
        """RF-TOOL-03: Fallar si falta un parámetro requerido."""
        self.registry.register(self.tool)
        with self.assertRaises(InvalidParametersError):
            self.registry.validate_parameters(self.tool, {})

    def test_validate_parameters_wrong_type(self):
        """RF-TOOL-03: Fallar si el tipo de dato es incompatible."""
        self.registry.register(self.tool)
        with self.assertRaises(InvalidParametersError):
            self.registry.validate_parameters(self.tool, {"param_str": 12345})

    def test_validate_parameters_unexpected_keys(self):
        """Rechazar parámetros no declarados."""
        self.registry.register(self.tool)
        with self.assertRaises(InvalidParametersError):
            self.registry.validate_parameters(
                self.tool,
                {"param_str": "valid", "extra_bad": "malicious"}
            )


if __name__ == "__main__":
    unittest.main()
