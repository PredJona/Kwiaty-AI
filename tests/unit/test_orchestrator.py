"""Pruebas unitarias para el flujo completo del Orchestrator."""

import os
import tempfile
import unittest
from typing import Dict, Any

from kwiaty.core.orchestrator import Orchestrator
from kwiaty.core.intent_router import RouteType
from kwiaty.security.risk import RiskLevel, DecisionStatus
from kwiaty.tools.contracts import Tool, ToolMetadata, ToolResult
from kwiaty.platform.base import PlatformAdapter


class MockRxTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="mock.prohibited.rm_root",
            domain="system",
            description="Herramienta RX de prueba que debe ser bloqueada.",
            parameters=(),
            risk_level=RiskLevel.RX,
        )

    def execute(self, params: Dict[str, Any], platform_adapter: PlatformAdapter) -> ToolResult:
        return ToolResult(success=True, data={"destroyed": True})


class TestOrchestrator(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.audit_file = os.path.join(self.tmp_dir.name, "audit_test.jsonl")
        self.orchestrator = Orchestrator.create_default(log_path=self.audit_file)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_status_flow(self):
        """Flujo completo de 'status' (CLI -> Orchestrator -> Tool R0 -> Adapter -> Audit)."""
        result = self.orchestrator.process_query("status")

        self.assertTrue(result.success)
        self.assertEqual(result.route, RouteType.DETERMINISTIC_TOOL)
        self.assertIsNotNone(result.tool_result)
        self.assertTrue(result.tool_result.success)
        self.assertIn("kernel_release", result.tool_result.data)

        # Verificar decisión de seguridad R0
        self.assertIsNotNone(result.permission_decision)
        self.assertEqual(result.permission_decision.status, DecisionStatus.ALLOWED)
        self.assertEqual(result.permission_decision.risk_level, RiskLevel.R0)

        # Verificar auditoría
        self.assertIsNotNone(result.audit_entry)
        self.assertTrue(result.audit_entry.authorized)
        self.assertTrue(result.audit_entry.execution_success)

        # Verificar que se escribió en disco
        recent = self.orchestrator.audit_logger.read_recent()
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["action"], "tool_executed")

    def test_ram_flow(self):
        """Flujo completo para consulta determinista de RAM."""
        result = self.orchestrator.process_query("cuánta RAM estoy usando")

        self.assertTrue(result.success)
        self.assertEqual(result.route, RouteType.DETERMINISTIC_TOOL)
        self.assertIn("used_gb", result.tool_result.data)
        self.assertIn("total_gb", result.tool_result.data)

    def test_rx_tool_blocked(self):
        """RF-SEC-07: Una herramienta RX debe ser rechazada incondicionalmente."""
        self.orchestrator.tool_registry.register(MockRxTool())

        result = self.orchestrator.execute_tool("mock.prohibited.rm_root")

        self.assertFalse(result.success)
        self.assertIsNotNone(result.permission_decision)
        self.assertEqual(result.permission_decision.status, DecisionStatus.DENIED)
        self.assertEqual(result.permission_decision.risk_level, RiskLevel.RX)

        # Auditoría debe reflejar que NO fue autorizada
        self.assertIsNotNone(result.audit_entry)
        self.assertFalse(result.audit_entry.authorized)
        self.assertFalse(result.audit_entry.execution_success)

    def test_unregistered_tool_fails_safely(self):
        """RF-TOOL-04: Intentar ejecutar tool no registrada falla limpiamente."""
        result = self.orchestrator.execute_tool("phantom.tool")
        self.assertFalse(result.success)
        self.assertIn("Herramienta no registrada", result.message)

    def test_llm_reasoning_route_offline_notice(self):
        """RF-AI-04: Consultas de razonamiento informan el modo offline de la Fase 1."""
        result = self.orchestrator.process_query("¿cómo optimizo el rendimiento del kernel?")
        self.assertTrue(result.success)
        self.assertEqual(result.route, RouteType.LLM_REASONING)
        self.assertIn("El subsistema LLM (Ollama) no está activo", result.message)


if __name__ == "__main__":
    unittest.main()
