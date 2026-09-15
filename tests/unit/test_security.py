"""Pruebas unitarias para el modelo de riesgos y PermissionManager."""

import unittest
from kwiaty.security.risk import (
    RiskLevel,
    DecisionStatus,
    PermissionDeniedError,
)
from kwiaty.security.permission_manager import PermissionManager


class TestRiskAndPermissions(unittest.TestCase):

    def setUp(self):
        self.pm = PermissionManager()

    def test_risk_level_ordering(self):
        """Verifica que los niveles de riesgo sigan la jerarquía R0 < R1 < R2 < R3 < RX."""
        self.assertTrue(RiskLevel.R1.is_stricter_than(RiskLevel.R0))
        self.assertTrue(RiskLevel.R2.is_stricter_than(RiskLevel.R1))
        self.assertTrue(RiskLevel.R3.is_stricter_than(RiskLevel.R2))
        self.assertTrue(RiskLevel.RX.is_stricter_than(RiskLevel.R3))
        self.assertFalse(RiskLevel.R0.is_stricter_than(RiskLevel.R1))

    def test_r0_allowed_automatically(self):
        """RF-SEC-03: R0 debe autorizarse automáticamente."""
        decision = self.pm.evaluate("test_tool", RiskLevel.R0)
        self.assertEqual(decision.status, DecisionStatus.ALLOWED)
        self.assertEqual(decision.risk_level, RiskLevel.R0)
        self.assertFalse(decision.requires_prompt)

    def test_r1_allowed_automatically(self):
        """RF-SEC-04: R1 puede ejecutarse automáticamente con registro."""
        decision = self.pm.evaluate("test_tool", RiskLevel.R1)
        self.assertEqual(decision.status, DecisionStatus.ALLOWED)
        self.assertEqual(decision.risk_level, RiskLevel.R1)

    def test_r2_requires_confirmation(self):
        """RF-SEC-05: R2 requiere confirmación explícita."""
        decision = self.pm.evaluate("test_tool", RiskLevel.R2)
        self.assertEqual(decision.status, DecisionStatus.NEEDS_CONFIRMATION)
        self.assertTrue(decision.requires_prompt)

    def test_r3_requires_authentication(self):
        """RF-SEC-06: R3 requiere confirmación reforzada y autenticación del SO."""
        decision = self.pm.evaluate("test_tool", RiskLevel.R3)
        self.assertEqual(decision.status, DecisionStatus.NEEDS_AUTHENTICATION)
        self.assertTrue(decision.requires_prompt)

    def test_rx_denied_strictly(self):
        """RF-SEC-07: RX se rechaza incondicionalmente."""
        decision = self.pm.evaluate("malicious_tool", RiskLevel.RX)
        self.assertEqual(decision.status, DecisionStatus.DENIED)
        self.assertEqual(decision.risk_level, RiskLevel.RX)

    def test_model_cannot_downgrade_risk(self):
        """RF-SEC-08 / Principio P-04: El modelo nunca puede reducir el riesgo de una operación."""
        # La tool es intrínsecamente R2, pero el modelo afirma que es R0
        decision = self.pm.evaluate(
            tool_name="sensitive_tool",
            tool_inherent_risk=RiskLevel.R2,
            claimed_risk=RiskLevel.R0,
        )
        self.assertEqual(decision.risk_level, RiskLevel.R2)
        self.assertEqual(decision.status, DecisionStatus.NEEDS_CONFIRMATION)

        # Si el modelo intenta clamar R0 para una tool RX
        decision_rx = self.pm.evaluate(
            tool_name="rm_rf",
            tool_inherent_risk=RiskLevel.RX,
            claimed_risk=RiskLevel.R0,
        )
        self.assertEqual(decision_rx.risk_level, RiskLevel.RX)
        self.assertEqual(decision_rx.status, DecisionStatus.DENIED)

    def test_enforce_r0_or_raise(self):
        """Verifica enforce_r0_or_raise para operaciones exclusivas de lectura."""
        decision = self.pm.enforce_r0_or_raise("safe_tool", RiskLevel.R0)
        self.assertEqual(decision.status, DecisionStatus.ALLOWED)

        with self.assertRaises(PermissionDeniedError):
            self.pm.enforce_r0_or_raise("dangerous_tool", RiskLevel.R2)

        with self.assertRaises(PermissionDeniedError):
            self.pm.enforce_r0_or_raise("banned_tool", RiskLevel.RX)


if __name__ == "__main__":
    unittest.main()
