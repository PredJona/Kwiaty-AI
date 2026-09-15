"""Gestor de contexto (Context Manager) para Kwiaty.

En la Fase 1 funciona como un stub mínimo, preparando la arquitectura
para integrar sesión y memoria relevante en fases posteriores (Principio P-06).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ConversationSession:
    session_id: str = "default_session"
    history: List[Dict[str, Any]] = field(default_factory=list)


class ContextManager:
    """Administra el contexto mínimo para peticiones."""

    def __init__(self):
        self._current_session = ConversationSession()

    def get_minimal_context(self, query: str) -> Dict[str, Any]:
        """Retorna el contexto mínimo requerido para una consulta."""
        return {
            "session_id": self._current_session.session_id,
            "query": query,
        }

    def record_turn(self, role: str, content: str) -> None:
        """Registra un turno en el historial en memoria de la sesión actual."""
        self._current_session.history.append({"role": role, "content": content})
