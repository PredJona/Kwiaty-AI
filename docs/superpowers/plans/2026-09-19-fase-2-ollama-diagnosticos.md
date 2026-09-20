# Kwiaty Fase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conectar Kwiaty de forma segura con Ollama local mediante `ModelRouter` y añadir diagnósticos R0 de CPU, almacenamiento y procesos sin romper el modo determinista.

**Architecture:** Un contrato de proveedor normaliza estado y generación, mientras `OllamaProvider` encapsula HTTP local y `ModelRouter` conserva la única dependencia del Core. El adaptador CachyOS obtiene hechos desde `/proc` y `shutil`; tools R0 separadas los exponen a través del flujo existente de validación, permisos y auditoría.

**Tech Stack:** Python 3.10+, biblioteca estándar (`urllib`, `json`, `ipaddress`, `shutil`, `/proc`), pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-19-fase-2-ollama-diagnosticos-design.md`

## Global Constraints

- No implementar GUI, memoria, automatizaciones, web ni cloud.
- El LLM nunca ejecuta shell ni tools directamente y su salida siempre se trata como texto.
- Solo se permite Ollama mediante HTTP a `localhost` o direcciones loopback.
- Las rutas deterministas no consultan Ollama y continúan disponibles cuando falla.
- Toda tool nueva es R0, offline y atraviesa `PermissionManager` y auditoría.
- No añadir dependencias de ejecución; pytest es dependencia opcional de desarrollo.
- Escribir y ejecutar cada prueba fallida antes del cambio de producción correspondiente.

## Review Focus

- Una URL Ollama remota, con credenciales o esquema distinto de HTTP se rechaza antes de realizar E/S; lo cubre la Tarea 1.
- Configuración sin modelo y respuestas Ollama vacías/malformadas generan indisponibilidad controlada; lo cubren las Tareas 1 y 2.
- Un texto del modelo con sintaxis de shell o tool call nunca dispara el registro de tools; lo cubre la Tarea 2.
- Procesos que desaparecen, `/proc` incompleto y deltas de CPU cero no rompen el diagnóstico; lo cubre la Tarea 3.
- Límites de procesos inválidos y criterios desconocidos se rechazan antes de llegar al adaptador; lo cubre la Tarea 4.

---

### Task 1: Contrato de proveedor y cliente Ollama local

**Files:**
- Create: `kwiaty/providers/__init__.py`
- Create: `kwiaty/providers/contracts.py`
- Create: `kwiaty/providers/ollama.py`
- Create: `tests/unit/test_ollama_provider.py`

**Interfaces:**
- Consumes: variables `KWIATY_OLLAMA_URL`, `KWIATY_OLLAMA_MODEL`, `KWIATY_OLLAMA_TIMEOUT`.
- Produces: `ProviderStatus(server_available: bool, model_available: bool, detail: str)`, `ProviderResponse(success: bool, content: str, provider_name: str, error: str | None)`, protocolo `ModelProvider.status() -> ProviderStatus`, `ModelProvider.generate(prompt: str, context: Mapping[str, Any] | None) -> ProviderResponse`, y `OllamaProvider.from_env(...)`.

- [ ] **Step 1: Escribir pruebas fallidas de configuración segura**

```python
class TestOllamaConfiguration(unittest.TestCase):
    def test_accepts_loopback_defaults(self):
        provider = OllamaProvider(base_url="http://127.0.0.1:11434", model="qwen2.5:7b", timeout=5)
        self.assertEqual(provider.provider_name, "ollama")

    def test_rejects_non_local_or_credentialed_urls(self):
        for url in ("https://example.com", "http://192.168.1.10:11434", "http://user:pass@localhost:11434"):
            with self.subTest(url=url), self.assertRaises(OllamaConfigurationError):
                OllamaProvider(base_url=url, model="qwen2.5:7b", timeout=5)

    def test_requires_non_empty_model_and_positive_timeout(self):
        with self.assertRaises(OllamaConfigurationError):
            OllamaProvider(base_url="http://localhost:11434", model="", timeout=5)
        with self.assertRaises(OllamaConfigurationError):
            OllamaProvider(base_url="http://localhost:11434", model="qwen2.5:7b", timeout=0)
```

- [ ] **Step 2: Ejecutar RED de configuración**

Run: `python -m unittest tests.unit.test_ollama_provider.TestOllamaConfiguration -v`
Expected: FAIL por ausencia de `kwiaty.providers.ollama`.

- [ ] **Step 3: Implementar contratos y validación mínima**

```python
@dataclass(frozen=True)
class ProviderStatus:
    server_available: bool
    model_available: bool
    detail: str = ""

@dataclass(frozen=True)
class ProviderResponse:
    success: bool
    content: str
    provider_name: str
    error: str | None = None

@runtime_checkable
class ModelProvider(Protocol):
    provider_name: str
    def status(self) -> ProviderStatus: ...
    def generate(self, prompt: str, context: Mapping[str, Any] | None = None) -> ProviderResponse: ...
```

En `OllamaProvider.__init__`, usar `urlsplit`, exigir `scheme == "http"`, ausencia de usuario/contraseña, hostname resoluble sintácticamente como `localhost` o `ip_address(host).is_loopback`, modelo no vacío y timeout finito mayor que cero. Normalizar `base_url` sin `/` final.

- [ ] **Step 4: Ejecutar GREEN de configuración**

Run: `python -m unittest tests.unit.test_ollama_provider.TestOllamaConfiguration -v`
Expected: PASS.

- [ ] **Step 5: Escribir pruebas fallidas del estado y generación HTTP**

Crear un `FakeTransport` que devuelva bytes JSON o lance `TimeoutError`, `URLError` y `HTTPError`. Probar comportamientos, no llamadas al fake:

```python
def test_status_distinguishes_server_and_exact_model(self):
    provider = make_provider({"models": [{"name": "qwen2.5:7b", "model": "qwen2.5:7b"}]})
    self.assertEqual(provider.status(), ProviderStatus(True, True, ""))

def test_status_reports_missing_model(self):
    status = make_provider({"models": [{"name": "llama3:8b"}]}).status()
    self.assertTrue(status.server_available)
    self.assertFalse(status.model_available)
    self.assertIn("qwen2.5:7b", status.detail)

def test_generate_returns_only_response_text(self):
    response = make_provider({"response": "respuesta local"}).generate("hola", {"session_id": "s1"})
    self.assertEqual(response, ProviderResponse(True, "respuesta local", "ollama", None))

def test_transport_and_payload_failures_are_normalized(self):
    for failure in (TimeoutError(), URLError("offline"), ValueError("json")):
        response = make_failing_provider(failure).generate("hola")
        self.assertFalse(response.success)
        self.assertEqual(response.provider_name, "ollama")
        self.assertTrue(response.error)

def test_empty_or_non_text_response_is_rejected(self):
    for payload in ({}, {"response": 4}, {"response": ""}):
        self.assertFalse(make_provider(payload).generate("hola").success)
```

- [ ] **Step 6: Ejecutar RED del transporte**

Run: `python -m unittest tests.unit.test_ollama_provider -v`
Expected: FAIL porque `status` y `generate` aún no realizan ni normalizan HTTP.

- [ ] **Step 7: Implementar transporte HTTP y normalización**

Implementar un transporte inyectable con firma `request(method, url, payload, timeout) -> bytes`. El transporte real usa `urllib.request` con un handler que rechaza redirecciones. `status()` hace `GET /api/tags`, valida `models` como lista y compara `name`/`model` exactamente. `generate()` compone un prompt de texto con contexto JSON estable, envía `{"model": self.model, "prompt": full_prompt, "stream": False}` a `/api/generate` y valida un `response` no vacío. Capturar timeout, errores URL/HTTP, decodificación y esquema con mensajes controlados.

- [ ] **Step 8: Ejecutar GREEN y suite completa**

Run: `python -m unittest tests.unit.test_ollama_provider -v && python -m unittest discover -v`
Expected: nuevas pruebas y 31 pruebas existentes PASS.

- [ ] **Step 9: Commit**

```bash
git add kwiaty/providers tests/unit/test_ollama_provider.py
git commit -m "feat: añadir proveedor Ollama local seguro"
```

### Task 2: Integrar el proveedor mediante ModelRouter sin tool calling

**Files:**
- Modify: `kwiaty/core/model_router.py`
- Modify: `kwiaty/core/orchestrator.py`
- Modify: `kwiaty/core/__init__.py`
- Modify: `tests/unit/test_orchestrator.py`
- Create: `tests/unit/test_model_router.py`

**Interfaces:**
- Consumes: `ModelProvider`, `ProviderStatus`, `ProviderResponse`, `OllamaProvider.from_env()`.
- Produces: `ModelResponse(content: str, success: bool, provider_name: str, error: str | None, is_offline_notice: bool)` y `ModelRouter(provider: ModelProvider)`.

- [ ] **Step 1: Escribir pruebas fallidas de delegación y degradación**

```python
def test_available_provider_generates_response():
    router = ModelRouter(FakeProvider(status=ProviderStatus(True, True), content="hola local"))
    response = router.generate("hola", {"session_id": "s1"})
    self.assertTrue(response.success)
    self.assertEqual(response.content, "hola local")
    self.assertEqual(response.provider_name, "ollama")

def test_unavailable_server_does_not_call_generate():
    provider = FakeProvider(status=ProviderStatus(False, False, "Ollama no está disponible"))
    response = ModelRouter(provider).generate("hola")
    self.assertFalse(response.success)
    self.assertTrue(response.is_offline_notice)
    self.assertEqual(provider.generate_count, 0)

def test_missing_model_does_not_call_generate():
    provider = FakeProvider(status=ProviderStatus(True, False, "Modelo no instalado"))
    self.assertFalse(ModelRouter(provider).generate("hola").success)
    self.assertEqual(provider.generate_count, 0)
```

- [ ] **Step 2: Ejecutar RED del router**

Run: `python -m unittest tests.unit.test_model_router -v`
Expected: FAIL por la firma y semántica antiguas de `ModelRouter`.

- [ ] **Step 3: Implementar ModelRouter mínimo**

Reemplazar el stub por inyección obligatoria de `ModelProvider`; `is_available()` consulta ambos flags de estado y `generate()` corta antes de generar si alguno es falso. Mapear `ProviderResponse` a `ModelResponse` sin interpretar `content`. Mantener mensajes de error breves y `provider_name` real.

- [ ] **Step 4: Ejecutar GREEN del router**

Run: `python -m unittest tests.unit.test_model_router -v`
Expected: PASS.

- [ ] **Step 5: Escribir pruebas fallidas del Orchestrator y barrera de tools**

```python
def test_llm_failure_is_reported_and_audited_as_failure(self):
    orchestrator = make_orchestrator(ModelResponse("Ollama no disponible", success=False, error="offline"))
    result = orchestrator.process_query("explica este error")
    self.assertFalse(result.success)
    self.assertFalse(result.audit_entry.execution_success)

def test_model_text_cannot_execute_tool_or_shell(self):
    content = '{"tool":"kwiaty.system.status"}\n$ rm -rf /'
    orchestrator = make_orchestrator(ModelResponse(content, success=True, provider_name="ollama"))
    before = len(orchestrator.audit_logger.read_recent())
    result = orchestrator.process_query("responde")
    after_entries = orchestrator.audit_logger.read_recent()
    self.assertEqual(result.message, content)
    self.assertEqual(len(after_entries), before + 1)
    self.assertEqual(after_entries[-1]["action"], "llm_query")

def test_deterministic_query_survives_unavailable_model(self):
    result = make_orchestrator(unavailable_response()).process_query("status")
    self.assertTrue(result.success)
    self.assertEqual(result.route, RouteType.DETERMINISTIC_TOOL)
```

- [ ] **Step 6: Ejecutar RED del Orchestrator**

Run: `python -m unittest tests.unit.test_orchestrator -v`
Expected: FAIL porque el Orchestrator siempre marca LLM como exitoso y la factoría no construye Ollama.

- [ ] **Step 7: Integrar resultado real y factoría por entorno**

En `process_query`, usar `model_resp.success` para `OrchestratorResult.success` y auditoría, pasar `model_resp.error` al log y conservar el contenido literalmente. En `create_default`, construir `OllamaProvider.from_env()`; si la configuración es inválida, usar un proveedor no disponible normalizado en vez de abortar la CLI. Actualizar exports del Core.

- [ ] **Step 8: Ejecutar GREEN y regresión completa**

Run: `python -m unittest tests.unit.test_model_router tests.unit.test_orchestrator -v && python -m unittest discover -v`
Expected: PASS, incluida la ruta determinista con proveedor fallido.

- [ ] **Step 9: Commit**

```bash
git add kwiaty/core tests/unit/test_model_router.py tests/unit/test_orchestrator.py
git commit -m "feat: enrutar Ollama mediante ModelRouter"
```

### Task 3: Métricas estructuradas del adaptador CachyOS

**Files:**
- Modify: `kwiaty/platform/base.py`
- Modify: `kwiaty/platform/cachyos.py`
- Modify: `tests/unit/test_cachyos_adapter.py`

**Interfaces:**
- Produces: `CpuMetrics(used_percent, logical_cpus)`, `DiskMetrics(path, total_bytes, used_bytes, free_bytes, used_percent)`, `ProcessMetrics(pid, name, cpu_percent, memory_bytes)`, y métodos `get_cpu_info(sample_interval=0.1)`, `get_disk_info(path="/")`, `get_top_processes(sort_by="memory", limit=5, sample_interval=0.1)`.

- [ ] **Step 1: Escribir pruebas fallidas de CPU y disco**

Con un `/proc/stat` temporal y un sleeper inyectado que sustituye el contenido entre muestras:

```python
def test_cpu_usage_uses_two_proc_stat_samples(self):
    # primera: total=100, idle=60; segunda: total=200, idle=100
    metrics = adapter.get_cpu_info(sample_interval=0)
    self.assertEqual(metrics.used_percent, 60.0)

def test_cpu_zero_delta_returns_zero(self):
    self.assertEqual(adapter.get_cpu_info(sample_interval=0).used_percent, 0.0)

def test_disk_usage_returns_structured_bytes(self):
    with patch("kwiaty.platform.cachyos.shutil.disk_usage", return_value=(1000, 400, 600)):
        self.assertEqual(adapter.get_disk_info("/tmp"), DiskMetrics("/tmp", 1000, 400, 600, 40.0))
```

- [ ] **Step 2: Ejecutar RED de CPU/disco**

Run: `python -m unittest tests.unit.test_cachyos_adapter.TestCachyOSAdapter -v`
Expected: FAIL por ausencia de métricas y métodos.

- [ ] **Step 3: Implementar CPU y disco**

Parsear la línea agregada `cpu` de `/proc/stat`; total es la suma de campos y idle es `idle + iowait`. Calcular `100 * (delta_total - delta_idle) / delta_total`, acotar a `[0, 100]` y redondear a una decimal. Inyectar `sleep_fn` en el constructor para pruebas. Para disco, envolver `shutil.disk_usage(path)` y proteger división por cero.

- [ ] **Step 4: Ejecutar GREEN de CPU/disco**

Run: `python -m unittest tests.unit.test_cachyos_adapter.TestCachyOSAdapter -v`
Expected: PASS.

- [ ] **Step 5: Escribir pruebas fallidas de procesos**

Crear fixtures `/proc/<pid>/stat`, `/proc/<pid>/comm` y `/proc/<pid>/status` para dos muestras. Incluir nombre con espacios/paréntesis, un PID que desaparece y un archivo malformado.

```python
def test_top_processes_orders_by_memory_and_limits(self):
    result = adapter.get_top_processes(sort_by="memory", limit=1, sample_interval=0)
    self.assertEqual([(p.pid, p.name) for p in result], [(22, "worker")])

def test_top_processes_orders_by_cpu_from_sample_delta(self):
    result = adapter.get_top_processes(sort_by="cpu", limit=2, sample_interval=0)
    self.assertGreaterEqual(result[0].cpu_percent, result[1].cpu_percent)

def test_disappearing_or_malformed_process_is_skipped(self):
    self.assertEqual([p.pid for p in adapter.get_top_processes(limit=5, sample_interval=0)], [22])
```

- [ ] **Step 6: Ejecutar RED de procesos**

Run: `python -m unittest tests.unit.test_cachyos_adapter.TestCachyOSAdapter -v`
Expected: FAIL por ausencia de `get_top_processes`.

- [ ] **Step 7: Implementar lectura robusta de procesos**

Enumerar directorios PID numéricos. Parsear `stat` separando por el último `)` y sumar `utime + stime`; leer `VmRSS` de `status` en KiB y convertir a bytes. Tomar dos snapshots para CPU y usar el delta total del sistema; calcular porcentaje por proceso como `delta_ticks / delta_total * logical_cpus * 100`. Omitir por PID los `OSError`, `ValueError` y datos incompletos. Validar internamente `sort_by` y `limit` también en el adaptador.

- [ ] **Step 8: Ejecutar GREEN y suite completa**

Run: `python -m unittest tests.unit.test_cachyos_adapter -v && python -m unittest discover -v`
Expected: PASS sin subprocesos ni comandos externos.

- [ ] **Step 9: Commit**

```bash
git add kwiaty/platform tests/unit/test_cachyos_adapter.py
git commit -m "feat: obtener métricas R0 desde CachyOS"
```

### Task 4: Tools R0, intenciones y salida CLI

**Files:**
- Create: `kwiaty/tools/diagnostics/cpu_usage.py`
- Create: `kwiaty/tools/diagnostics/disk_usage.py`
- Create: `kwiaty/tools/diagnostics/top_processes.py`
- Modify: `kwiaty/tools/diagnostics/__init__.py`
- Modify: `kwiaty/core/intent_router.py`
- Modify: `kwiaty/core/orchestrator.py`
- Modify: `kwiaty/cli/presenter.py`
- Create: `tests/unit/test_diagnostic_tools.py`
- Modify: `tests/unit/test_intent_router.py`
- Modify: `tests/unit/test_orchestrator.py`
- Modify: `tests/integration/test_cli.py`

**Interfaces:**
- Consumes: los tres métodos nuevos de `PlatformAdapter`.
- Produces: tools `kwiaty.system.cpu_usage`, `kwiaty.system.disk_usage`, `kwiaty.system.top_processes`; rutas directas para `cpu`, `disco` y `procesos`.

- [ ] **Step 1: Escribir pruebas fallidas de contratos y resultados de tools**

```python
def test_cpu_tool_is_r0_and_returns_facts(self):
    result = CpuUsageTool().execute({}, FakeAdapter())
    self.assertTrue(result.success)
    self.assertEqual(result.data, {"used_percent": 37.5, "logical_cpus": 8})
    self.assertEqual(CpuUsageTool().metadata.risk_level, RiskLevel.R0)

def test_disk_tool_defaults_to_root(self):
    params = ToolRegistry().validate_parameters(DiskUsageTool(), {})
    self.assertEqual(params, {"path": "/"})

def test_process_tool_rejects_bad_criterion_and_limit(self):
    tool = TopProcessesTool()
    self.assertFalse(tool.execute({"sort_by": "io", "limit": 5}, FakeAdapter()).success)
    self.assertFalse(tool.execute({"sort_by": "cpu", "limit": 0}, FakeAdapter()).success)
```

- [ ] **Step 2: Ejecutar RED de tools**

Run: `python -m unittest tests.unit.test_diagnostic_tools -v`
Expected: FAIL porque no existen las tres tools.

- [ ] **Step 3: Implementar tools mínimas y exports**

Cada tool mide tiempo con `perf_counter`, llama un único método del adaptador, devuelve diccionarios con bytes/porcentajes/PID/nombre y normaliza excepciones a `ToolResult(success=False, data={}, error=...)`. `DiskUsageTool` declara `path` opcional `/`; `TopProcessesTool` declara `sort_by` opcional `memory` y `limit` opcional `5`, y aplica rango `1..20` antes de consultar el adaptador.

- [ ] **Step 4: Ejecutar GREEN de tools**

Run: `python -m unittest tests.unit.test_diagnostic_tools -v`
Expected: PASS.

- [ ] **Step 5: Escribir pruebas fallidas de rutas, registro, permiso y CLI**

```python
def test_new_diagnostic_queries_are_deterministic(self):
    cases = {
        "uso de cpu": ("kwiaty.system.cpu_usage", {}),
        "espacio en disco": ("kwiaty.system.disk_usage", {"path": "/"}),
        "procesos que más memoria usan": ("kwiaty.system.top_processes", {"sort_by": "memory", "limit": 5}),
        "procesos que más cpu usan": ("kwiaty.system.top_processes", {"sort_by": "cpu", "limit": 5}),
    }
    for query, expected in cases.items():
        result = IntentRouter().resolve(query)
        self.assertEqual((result.tool_name, result.parameters), expected)

def test_default_registry_contains_new_r0_tools(self):
    tools = {m.name: m for m in Orchestrator.create_default().tool_registry.list_tools()}
    for name in ("kwiaty.system.cpu_usage", "kwiaty.system.disk_usage", "kwiaty.system.top_processes"):
        self.assertEqual(tools[name].risk_level, RiskLevel.R0)
```

En integración, ejecutar las frases anteriores y afirmar código `0` y etiquetas `Uso de CPU`, `Almacenamiento` y `Procesos`.

- [ ] **Step 6: Ejecutar RED de integración**

Run: `python -m unittest tests.unit.test_intent_router tests.unit.test_orchestrator tests.integration.test_cli -v`
Expected: FAIL por rutas, registro y presentación ausentes.

- [ ] **Step 7: Registrar, enrutar y presentar**

Añadir patrones deterministas estrechos antes del fallback LLM. Registrar las tres tools en `create_default`. En `CliPresenter`, detectar las claves distintivas y mostrar unidades claras; para procesos, una línea por PID con CPU y memoria MiB. No añadir subcomandos ni ejecución desde salida LLM.

- [ ] **Step 8: Ejecutar GREEN y suite completa**

Run: `python -m unittest tests.unit.test_diagnostic_tools tests.unit.test_intent_router tests.unit.test_orchestrator tests.integration.test_cli -v && python -m unittest discover -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add kwiaty/tools/diagnostics kwiaty/core kwiaty/cli/presenter.py tests
git commit -m "feat: ampliar diagnósticos R0"
```

### Task 5: pytest, CI, documentación y verificación final

**Files:**
- Modify: `pyproject.toml`
- Create: `.github/workflows/tests.yml`
- Modify: `README.md`

**Interfaces:**
- Produces: extra instalable `dev`, workflow reproducible y guía operativa de Fase 2.

- [ ] **Step 1: Añadir configuración de desarrollo**

Agregar a `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = ["pytest>=8,<9"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

- [ ] **Step 2: Crear GitHub Actions**

```yaml
name: tests
on:
  push:
  pull_request:
jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
          cache: pip
      - run: python -m pip install --upgrade pip
      - run: python -m pip install -e ".[dev]"
      - run: python -m pytest
```

- [ ] **Step 3: Verificar el workflow estructuralmente**

Run: `python -c "import pathlib; p=pathlib.Path('.github/workflows/tests.yml'); assert p.is_file() and 'python -m pytest' in p.read_text()"`
Expected: exit 0. Esta comprobación solo valida que el artefacto invoca la suite; GitHub validará el workflow real.

- [ ] **Step 4: Actualizar README**

Documentar: Python 3.10+, entorno virtual, `pip install -e ".[dev]"`, `ollama serve`, ejemplo `ollama pull qwen2.5:7b`, las tres variables, aviso de que el modelo no tiene tools/shell, ejemplos de CPU/disco/procesos y `python -m pytest`/pruebas por archivo. Explicar que sin Ollama o modelo solo falla la consulta conversacional.

- [ ] **Step 5: Instalar dependencias de desarrollo y ejecutar pytest**

Run: `python -m pip install -e ".[dev]"`
Expected: instalación exit 0.

Run: `python -m pytest`
Expected: todas las pruebas PASS, sin requerir Ollama ni red durante la suite.

- [ ] **Step 6: Ejecutar verificaciones adicionales**

Run: `python -m unittest discover -v`
Expected: todas las pruebas PASS.

Run: `python -m compileall -q kwiaty tests`
Expected: exit 0.

Run: `git diff --check`
Expected: exit 0.

- [ ] **Step 7: Revisar requisitos contra la especificación**

Confirmar manualmente en el diff: proveedor fuera del Core; host local obligatorio; timeout y errores normalizados; ausencia de `subprocess` en proveedor/tools; salida LLM tratada como texto; rutas deterministas independientes; tres tools R0 registradas; README y workflow presentes.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .github/workflows/tests.yml README.md
git commit -m "ci: ejecutar pytest y documentar fase 2"
```

- [ ] **Step 9: Inspección final**

Run: `git status --short && git log --oneline -6`
Expected: árbol limpio y commits separados para proveedor, router, diagnósticos y CI/documentación.
