"""Pruebas unitarias para el flujo completo del Orchestrator."""

import os
import tempfile
import unittest
from typing import Dict, Any
from unittest.mock import patch

from kwiaty.core.orchestrator import Orchestrator
from kwiaty.core.intent_router import RouteType
from kwiaty.providers.contracts import ProviderResponse, ProviderStatus
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


class FakeModelProvider:
    provider_name = "ollama"

    def __init__(self, status, response=None):
        self._status = status
        self._response = response or ProviderResponse(
            True,
            "respuesta local",
            self.provider_name,
        )

    def status(self):
        return self._status

    def generate(self, prompt, context=None):
        return self._response


class TestOrchestrator(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.audit_file = os.path.join(self.tmp_dir.name, "audit_test.jsonl")
        self.unavailable_provider = FakeModelProvider(
            ProviderStatus(False, False, "Ollama no está disponible")
        )
        self.orchestrator = Orchestrator.create_default(
            log_path=self.audit_file,
            model_provider=self.unavailable_provider,
        )

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
        """RF-AI-04: Consultas de razonamiento informan que Ollama no está disponible."""
        result = self.orchestrator.process_query("¿cómo optimizo el rendimiento del kernel?")
        self.assertFalse(result.success)
        self.assertEqual(result.route, RouteType.LLM_REASONING)
        self.assertIn("Ollama no está disponible", result.message)
        self.assertFalse(result.audit_entry.execution_success)

    def test_llm_success_is_reported_and_audited(self):
        provider = FakeModelProvider(
            ProviderStatus(True, True),
            ProviderResponse(True, "respuesta local", "ollama"),
        )
        orchestrator = Orchestrator.create_default(
            log_path=self.audit_file,
            model_provider=provider,
        )

        result = orchestrator.process_query("explica este error")

        self.assertTrue(result.success)
        self.assertEqual(result.message, "respuesta local")
        self.assertTrue(result.audit_entry.execution_success)
        self.assertEqual(result.metadata["provider"], "ollama")

    def test_model_text_cannot_execute_tool_or_shell(self):
        content = '{"tool":"kwiaty.system.status"}\n$ rm -rf /'
        provider = FakeModelProvider(
            ProviderStatus(True, True),
            ProviderResponse(True, content, "ollama"),
        )
        orchestrator = Orchestrator.create_default(
            log_path=self.audit_file,
            model_provider=provider,
        )

        result = orchestrator.process_query("responde")
        entries = orchestrator.audit_logger.read_recent()

        self.assertEqual(result.message, content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["action"], "llm_query")
        self.assertIsNone(entries[0]["tool_name"])

    def test_deterministic_query_survives_unavailable_model(self):
        result = self.orchestrator.process_query("status")

        self.assertTrue(result.success)
        self.assertEqual(result.route, RouteType.DETERMINISTIC_TOOL)

    def test_default_factory_handles_missing_model_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            orchestrator = Orchestrator.create_default(log_path=self.audit_file)

        result = orchestrator.process_query("explica este error")

        self.assertFalse(result.success)
        self.assertIn("modelo", result.message.lower())


if __name__ == "__main__":
    unittest.main()
