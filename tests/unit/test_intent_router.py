"""Pruebas unitarias para IntentRouter."""

import unittest
from kwiaty.core.intent_router import IntentRouter, RouteType


class TestIntentRouter(unittest.TestCase):

    def setUp(self):
        self.router = IntentRouter()

    def test_status_deterministic_matches(self):
        """RF-CORE-02: Mapeo de solicitudes de estado a ruta determinista sin LLM."""
        queries = [
            "status",
            "kwiaty status",
            "estado",
            "diagnóstico",
            "diagnostico",
            "¿cómo está el sistema?",
            "resumen del sistema",
        ]
        for q in queries:
            resolution = self.router.resolve(q)
            self.assertEqual(
                resolution.route_type,
                RouteType.DETERMINISTIC_TOOL,
                f"Falló al clasificar '{q}'"
            )
            self.assertEqual(resolution.tool_name, "kwiaty.system.status")

    def test_ram_deterministic_matches(self):
        """RF-CORE-02 / RF-SYS-04: Mapeo de consultas de RAM a ruta determinista."""
        queries = [
            "cuánta RAM estoy usando",
            "cuanta ram estoy usando",
            "¿cuánta ram uso?",
            "uso de ram",
            "memoria ram",
            "ram",
            "memoria",
        ]
        for q in queries:
            resolution = self.router.resolve(q)
            self.assertEqual(
                resolution.route_type,
                RouteType.DETERMINISTIC_TOOL,
                f"Falló al clasificar '{q}'"
            )
            self.assertEqual(resolution.tool_name, "kwiaty.system.ram_usage")

    def test_unrecognized_query_delegates_to_llm(self):
        """Consultas complejas o no reconocidas se delegan a la ruta de razonamiento."""
        complex_queries = [
            "¿por qué falló el contenedor de base de datos?",
            "analiza los últimos errores del kernel",
            "ayúdame a escribir un script bash",
        ]
        for q in complex_queries:
            resolution = self.router.resolve(q)
            self.assertEqual(resolution.route_type, RouteType.LLM_REASONING)
            self.assertIsNone(resolution.tool_name)

    def test_new_diagnostic_queries_are_deterministic(self):
        cases = {
            "uso de cpu": ("kwiaty.system.cpu_usage", {}),
            "espacio en disco": ("kwiaty.system.disk_usage", {"path": "/"}),
            "procesos que más memoria usan": (
                "kwiaty.system.top_processes",
                {"sort_by": "memory", "limit": 5},
            ),
            "procesos que más cpu usan": (
                "kwiaty.system.top_processes",
                {"sort_by": "cpu", "limit": 5},
            ),
        }

        for query, expected in cases.items():
            with self.subTest(query=query):
                result = self.router.resolve(query)
                self.assertEqual(result.route_type, RouteType.DETERMINISTIC_TOOL)
                self.assertEqual((result.tool_name, result.parameters), expected)


if __name__ == "__main__":
    unittest.main()
