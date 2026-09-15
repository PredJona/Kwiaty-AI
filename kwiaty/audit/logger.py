"""Sistema de registro de auditoría y trazabilidad para Kwiaty.

Registra todas las acciones ejecutadas por herramientas, verificando autorización,
éxito/fallo y omitiendo secretos detectados (RF-AUD-01 a RF-AUD-05, Principio P-10).
"""

from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from kwiaty.security.risk import RiskLevel


SENSITIVE_PATTERNS = {
    "password", "passwd", "token", "secret", "key", "apikey",
    "api_key", "authorization", "auth", "credential", "cookie", "private"
}


def sanitize_data(data: Any) -> Any:
    """Sanitiza diccionarios y colecciones para no almacenar secretos en logs (RF-AUD-05)."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(pattern in k.lower() for pattern in SENSITIVE_PATTERNS):
                sanitized[k] = "[REDACTED_SECRET]"
            else:
                sanitized[k] = sanitize_data(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    return data


@dataclass(frozen=True)
class AuditEntry:
    """Entrada inmutable del log de auditoría."""
    timestamp: str
    action: str
    tool_name: Optional[str]
    parameters: Dict[str, Any]
    risk_level: str
    authorized: bool
    execution_success: bool
    duration_ms: float
    error_message: Optional[str] = None


class AuditLogger:
    """Registrador de auditoría en formato JSON Lines (JSONL)."""

    def __init__(self, log_file_path: Optional[str] = None):
        if log_file_path is None:
            home = os.path.expanduser("~")
            log_dir = os.path.join(home, ".local", "share", "kwiaty")
            log_file_path = os.path.join(log_dir, "audit.jsonl")

        self._log_file_path = log_file_path
        self._ensure_log_dir()

    @property
    def log_file_path(self) -> str:
        return self._log_file_path

    def _ensure_log_dir(self) -> None:
        """Crea el directorio de logs si no existe."""
        log_dir = os.path.dirname(self._log_file_path)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except OSError:
                pass

    def log(
        self,
        action: str,
        tool_name: Optional[str],
        parameters: Dict[str, Any],
        risk_level: RiskLevel,
        authorized: bool,
        execution_success: bool,
        duration_ms: float,
        error_message: Optional[str] = None,
    ) -> AuditEntry:
        """Registra una acción en el archivo de auditoría JSONL."""
        now_utc = datetime.now(timezone.utc).isoformat()
        clean_params = sanitize_data(parameters)

        entry = AuditEntry(
            timestamp=now_utc,
            action=action,
            tool_name=tool_name,
            parameters=clean_params,
            risk_level=risk_level.value,
            authorized=authorized,
            execution_success=execution_success,
            duration_ms=round(duration_ms, 2),
            error_message=error_message,
        )

        try:
            self._ensure_log_dir()
            with open(self._log_file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        except OSError:
            # La auditoría no debe romper el asistente si el filesystem falla temporalmente
            pass

        return entry

    def read_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Lee las entradas más recientes del archivo de auditoría."""
        if not os.path.exists(self._log_file_path):
            return []

        entries: List[Dict[str, Any]] = []
        try:
            with open(self._log_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            return []

        return entries[-limit:]
