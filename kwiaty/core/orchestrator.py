"""Orchestrator central de Kwiaty.

Coordina el ciclo de vida completo de cada petición:
Intent Router -> Context Manager -> Model Router / Tool Manager ->
Permission Manager -> Platform Adapter -> Audit Logger (Sección 4 y 5 de la especificación).
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from kwiaty.audit.logger import AuditLogger, AuditEntry
from kwiaty.core.context_manager import ContextManager
from kwiaty.core.intent_router import IntentRouter, RouteType, IntentResolution
from kwiaty.core.model_router import ModelRouter, ModelResponse
from kwiaty.platform.base import PlatformAdapter
from kwiaty.platform.cachyos import CachyOSAdapter
from kwiaty.security.permission_manager import PermissionManager
from kwiaty.security.risk import RiskLevel, PermissionDecision, DecisionStatus
from kwiaty.tools.contracts import ToolResult
from kwiaty.tools.diagnostics.ram_usage import RamUsageTool
from kwiaty.tools.diagnostics.system_status import SystemStatusTool
from kwiaty.tools.registry import ToolRegistry, ToolNotFoundError, InvalidParametersError


@dataclass(frozen=True)
class OrchestratorResult:
    """Resultado unificado de una petición procesada por el Orchestrator."""
    success: bool
    route: RouteType
    message: str
    tool_result: Optional[ToolResult] = None
    permission_decision: Optional[PermissionDecision] = None
    audit_entry: Optional[AuditEntry] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Orchestrator:
    """Orquestador modular de Kwiaty."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        permission_manager: PermissionManager,
        platform_adapter: PlatformAdapter,
        intent_router: IntentRouter,
        audit_logger: AuditLogger,
        model_router: ModelRouter,
        context_manager: ContextManager,
    ):
        self._tool_registry = tool_registry
        self._permission_manager = permission_manager
        self._platform_adapter = platform_adapter
        self._intent_router = intent_router
        self._audit_logger = audit_logger
        self._model_router = model_router
        self._context_manager = context_manager

    @property
    def platform_adapter(self) -> PlatformAdapter:
        return self._platform_adapter

    @property
    def tool_registry(self) -> ToolRegistry:
        return self._tool_registry

    @property
    def permission_manager(self) -> PermissionManager:
        return self._permission_manager

    @property
    def audit_logger(self) -> AuditLogger:
        return self._audit_logger

    def process_query(self, query: str) -> OrchestratorResult:
        """Procesa una consulta de usuario desde cualquier interfaz (CLI o GUI)."""
        resolution: IntentResolution = self._intent_router.resolve(query)

        if resolution.route_type == RouteType.DETERMINISTIC_TOOL and resolution.tool_name:
            return self.execute_tool(resolution.tool_name, resolution.parameters)

        if resolution.route_type == RouteType.LLM_REASONING:
            context = self._context_manager.get_minimal_context(query)
            model_resp: ModelResponse = self._model_router.generate(query, context)

            audit_entry = self._audit_logger.log(
                action="llm_query",
                tool_name=None,
                parameters={"query": query},
                risk_level=RiskLevel.R0,
                authorized=True,
                execution_success=True,
                duration_ms=0.0,
            )

            return OrchestratorResult(
                success=True,
                route=RouteType.LLM_REASONING,
                message=model_resp.content,
                audit_entry=audit_entry,
                metadata={"provider": model_resp.provider_name},
            )

        return OrchestratorResult(
            success=False,
            route=RouteType.UNKNOWN,
            message=f"No se pudo determinar una acción para: '{query}'",
        )

    def execute_tool(self, tool_name: str, params: Optional[Dict[str, Any]] = None) -> OrchestratorResult:
        """Flujo estricto de ejecución de una herramienta a través del Permission Manager."""
        if params is None:
            params = {}

        # 1. Obtener la herramienta del registro
        try:
            tool = self._tool_registry.get_or_raise(tool_name)
        except ToolNotFoundError as err:
            audit_entry = self._audit_logger.log(
                action="tool_call_failed",
                tool_name=tool_name,
                parameters=params,
                risk_level=RiskLevel.RX,
                authorized=False,
                execution_success=False,
                duration_ms=0.0,
                error_message=str(err),
            )
            return OrchestratorResult(
                success=False,
                route=RouteType.DETERMINISTIC_TOOL,
                message=str(err),
                audit_entry=audit_entry,
            )

        # 2. Validar parámetros según el contrato
        try:
            validated_params = self._tool_registry.validate_parameters(tool, params)
        except InvalidParametersError as err:
            audit_entry = self._audit_logger.log(
                action="tool_validation_failed",
                tool_name=tool_name,
                parameters=params,
                risk_level=tool.metadata.risk_level,
                authorized=False,
                execution_success=False,
                duration_ms=0.0,
                error_message=str(err),
            )
            return OrchestratorResult(
                success=False,
                route=RouteType.DETERMINISTIC_TOOL,
                message=f"Error en parámetros: {err}",
                audit_entry=audit_entry,
            )

        # 3. Evaluación de seguridad OBLIGATORIA (RF-SEC-01)
        decision = self._permission_manager.evaluate(
            tool_name=tool.metadata.name,
            tool_inherent_risk=tool.metadata.risk_level,
        )

        if decision.status != DecisionStatus.ALLOWED:
            audit_entry = self._audit_logger.log(
                action="tool_permission_denied",
                tool_name=tool_name,
                parameters=validated_params,
                risk_level=decision.risk_level,
                authorized=False,
                execution_success=False,
                duration_ms=0.0,
                error_message=decision.reason,
            )
            return OrchestratorResult(
                success=False,
                route=RouteType.DETERMINISTIC_TOOL,
                message=f"Acción bloqueada: {decision.reason}",
                permission_decision=decision,
                audit_entry=audit_entry,
            )

        # 4. Ejecución a través del Platform Adapter
        start_exec = time.perf_counter()
        tool_result: ToolResult = tool.execute(validated_params, self._platform_adapter)
        elapsed_ms = (time.perf_counter() - start_exec) * 1000.0

        # 5. Registro obligatorio de auditoría (RF-AUD-01 a RF-AUD-03)
        audit_entry = self._audit_logger.log(
            action="tool_executed",
            tool_name=tool_name,
            parameters=validated_params,
            risk_level=decision.risk_level,
            authorized=True,
            execution_success=tool_result.success,
            duration_ms=elapsed_ms,
            error_message=tool_result.error,
        )

        return OrchestratorResult(
            success=tool_result.success,
            route=RouteType.DETERMINISTIC_TOOL,
            message="Herramienta ejecutada con éxito." if tool_result.success else f"Error: {tool_result.error}",
            tool_result=tool_result,
            permission_decision=decision,
            audit_entry=audit_entry,
        )

    @classmethod
    def create_default(cls, log_path: Optional[str] = None) -> Orchestrator:
        """Crea una instancia estándar del Orchestrator con los componentes oficiales de Fase 1."""
        platform_adapter = CachyOSAdapter()
        permission_manager = PermissionManager()
        audit_logger = AuditLogger(log_file_path=log_path)
        intent_router = IntentRouter()
        model_router = ModelRouter()
        context_manager = ContextManager()

        registry = ToolRegistry()
        # Registrar tools diagnósticas R0 aprobadas para la Fase 1
        registry.register(SystemStatusTool())
        registry.register(RamUsageTool())

        return cls(
            tool_registry=registry,
            permission_manager=permission_manager,
            platform_adapter=platform_adapter,
            intent_router=intent_router,
            audit_logger=audit_logger,
            model_router=model_router,
            context_manager=context_manager,
        )
