"""Pruebas de integración para la CLI de Kwiaty."""

import io
import json
import sys
import unittest
from kwiaty.cli.main import main


class TestCliIntegration(unittest.TestCase):

    def run_cli(self, args):
        captured_out = io.StringIO()
        captured_err = io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        try:
            sys.stdout = captured_out
            sys.stderr = captured_err
            code = main(args)
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
        return code, captured_out.getvalue(), captured_err.getvalue()

    def test_cli_status(self):
        """kwiaty status retorna 0 y muestra resumen de CachyOS."""
        code, out, err = self.run_cli(["status"])
        self.assertEqual(code, 0)
        self.assertIn("Estado del Sistema (CachyOS)", out)
        self.assertIn("Kernel:", out)
        self.assertIn("Memoria RAM:", out)

    def test_cli_status_json(self):
        """kwiaty status --json emite JSON válido."""
        code, out, err = self.run_cli(["status", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["success"])
        self.assertIn("tool_result", data)
        self.assertEqual(data["security"]["risk_level"], "R0")

    def test_cli_ram_query(self):
        """kwiaty 'cuánta RAM estoy usando' responde con datos deterministas."""
        code, out, err = self.run_cli(["cuánta RAM estoy usando"])
        self.assertEqual(code, 0)
        self.assertIn("Uso de RAM:", out)
        self.assertIn("Disponible:", out)

    def test_cli_tools_list(self):
        """kwiaty tools list muestra las tools R0 registradas."""
        code, out, err = self.run_cli(["tools", "list"])
        self.assertEqual(code, 0)
        self.assertIn("kwiaty.system.status", out)
        self.assertIn("kwiaty.system.ram_usage", out)

    def test_cli_audit_list(self):
        """kwiaty audit list muestra registros de auditoría recientes."""
        code, out, err = self.run_cli(["audit", "list"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
