"""Modelo de riesgos y permisos de Kwiaty.

Define los niveles de riesgo R0, R1, R2, R3 y RX según la especificación,
así como las estructuras inmutables de decisión de permisos.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    """Niveles de riesgo del sistema de seguridad Kwiaty.

    - R0: Lectura segura. Consulta de estado y métricas. Ejecución automática.
    - R1: Acción reversible. Modificaciones menores con registro en auditoría.
    - R2: Modificación relevante. Requiere explicación y confirmación del usuario.
    - R3: Crítica o destructiva. Requiere confirmación reforzada y autenticación del SO (polkit/sudo).
    - RX: Prohibida. Acciones destructivas masivas o evasión de controles. Rechazo tajante.
    """
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    RX = "RX"

    @property
    def rank(self) -> int:
        """Valor ordinal de severidad de riesgo para comparaciones."""
        ordering = {
            RiskLevel.R0: 0,
            RiskLevel.R1: 1,
            RiskLevel.R2: 2,
            RiskLevel.R3: 3,
            RiskLevel.RX: 99,
        }
        return ordering[self]

    def is_stricter_than(self, other: RiskLevel) -> bool:
        return self.rank > other.rank


class DecisionStatus(str, Enum):
    """Estado de la decisión de seguridad emitida por el PermissionManager."""
    ALLOWED = "ALLOWED"                          # Permitida de forma automática
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"    # Requiere confirmación explícita (R2)
    NEEDS_AUTHENTICATION = "NEEDS_AUTHENTICATION" # Requiere auth del SO (R3)
    DENIED = "DENIED"                            # Rechazada incondicionalmente (RX)


@dataclass(frozen=True)
class PermissionDecision:
    """Resultado inmutable de la evaluación de seguridad de una acción."""
    status: DecisionStatus
    risk_level: RiskLevel
    reason: str
    requires_prompt: bool = False

    @property
    def is_allowed(self) -> bool:
        return self.status == DecisionStatus.ALLOWED

    @property
    def is_denied(self) -> bool:
        return self.status == DecisionStatus.DENIED


class SecurityViolationError(Exception):
    """Lanzada cuando una operación viola las restricciones de seguridad."""
    def __init__(self, message: str, risk_level: RiskLevel):
        super().__init__(message)
        self.risk_level = risk_level


class PermissionDeniedError(SecurityViolationError):
    """Lanzada cuando una acción es denegada por política o clasificada como RX."""
    pass
