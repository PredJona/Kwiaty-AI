"""Gestor de permisos y políticas de seguridad de Kwiaty.

Aplica de forma determinista las políticas R0, R1, R2, R3 y RX de manera
completamente desacoplada e independiente del LLM.
"""

from __future__ import annotations
from typing import Optional, Dict, Any
from kwiaty.security.risk import (
    RiskLevel,
    DecisionStatus,
    PermissionDecision,
    PermissionDeniedError,
)


class PermissionManager:
    """Evalúa y autoriza operaciones según la matriz de riesgo oficial."""

    def __init__(self, allow_r1_auto: bool = True):
        self._allow_r1_auto = allow_r1_auto

    def calculate_effective_risk(
        self,
        tool_inherent_risk: RiskLevel,
        claimed_risk: Optional[RiskLevel] = None,
    ) -> RiskLevel:
        """Calcula el riesgo efectivo garantizando que el modelo NUNCA pueda disminuir el riesgo.

        Principio P-04 / RF-SEC-08: El riesgo es intrínseco a la herramienta y sus parámetros.
        Si un modelo o solicitante declara un riesgo menor al inherente, prevalece el mayor.
        """
        if claimed_risk is None:
            return tool_inherent_risk

        if tool_inherent_risk.is_stricter_than(claimed_risk):
            # El modelo o solicitante intenta disminuir el riesgo -> ignorar y forzar el inherente
            return tool_inherent_risk

        return claimed_risk

    def evaluate(
        self,
        tool_name: str,
        tool_inherent_risk: RiskLevel,
        claimed_risk: Optional[RiskLevel] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> PermissionDecision:
        """Evalúa si una acción sobre una tool puede ejecutarse y qué autorización requiere."""
        effective_risk = self.calculate_effective_risk(tool_inherent_risk, claimed_risk)

        if effective_risk == RiskLevel.RX:
            return PermissionDecision(
                status=DecisionStatus.DENIED,
                risk_level=RiskLevel.RX,
                reason=f"Operación prohibida '{tool_name}' clasificada como RX. Rechazada incondicionalmente.",
                requires_prompt=False,
            )

        if effective_risk == RiskLevel.R0:
            return PermissionDecision(
                status=DecisionStatus.ALLOWED,
                risk_level=RiskLevel.R0,
                reason=f"Acción de lectura segura '{tool_name}' (R0). Aprobada automáticamente.",
                requires_prompt=False,
            )

        if effective_risk == RiskLevel.R1:
            if self._allow_r1_auto:
                return PermissionDecision(
                    status=DecisionStatus.ALLOWED,
                    risk_level=RiskLevel.R1,
                    reason=f"Acción reversible '{tool_name}' (R1). Aprobada automáticamente con registro auditable.",
                    requires_prompt=False,
                )
            return PermissionDecision(
                status=DecisionStatus.NEEDS_CONFIRMATION,
                risk_level=RiskLevel.R1,
                reason=f"Acción reversible '{tool_name}' (R1) en modo estricto. Requiere confirmación.",
                requires_prompt=True,
            )

        if effective_risk == RiskLevel.R2:
            return PermissionDecision(
                status=DecisionStatus.NEEDS_CONFIRMATION,
                risk_level=RiskLevel.R2,
                reason=f"Acción de modificación '{tool_name}' (R2). Requiere confirmación explícita del usuario.",
                requires_prompt=True,
            )

        if effective_risk == RiskLevel.R3:
            return PermissionDecision(
                status=DecisionStatus.NEEDS_AUTHENTICATION,
                risk_level=RiskLevel.R3,
                reason=f"Acción crítica/destructiva '{tool_name}' (R3). Requiere confirmación reforzada y autenticación del SO.",
                requires_prompt=True,
            )

        # Caso por defecto si se agregara un nivel no previsto
        return PermissionDecision(
            status=DecisionStatus.DENIED,
            risk_level=effective_risk,
            reason=f"Acción '{tool_name}' no autorizada por nivel de riesgo desconocido.",
            requires_prompt=False,
        )

    def enforce_r0_or_raise(self, tool_name: str, tool_inherent_risk: RiskLevel) -> PermissionDecision:
        """Valida que una acción sea estrictamente R0 para el incremento de Fase 1.

        Lanza PermissionDeniedError si no es R0.
        """
        decision = self.evaluate(tool_name, tool_inherent_risk)
        if decision.status != DecisionStatus.ALLOWED:
            raise PermissionDeniedError(
                f"Acceso denegado a '{tool_name}': {decision.reason}",
                risk_level=decision.risk_level,
            )
        return decision
