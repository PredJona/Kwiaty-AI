# Kwiaty Fase 2: Ollama local y diagnósticos R0

## Objetivo

Conectar Kwiaty con un servidor Ollama exclusivamente local mediante el
`ModelRouter`, manteniendo al Core independiente del proveedor y preservando
las rutas deterministas cuando el modelo no esté disponible. Ampliar el
diagnóstico R0 con CPU, almacenamiento y procesos de mayor consumo.

Esta fase no incluye GUI, memoria persistente, automatizaciones, acceso web,
cloud, servicios de systemd ni lectura de journal.

## Requisitos cubiertos

- `RF-AI-01`: Ollama es el proveedor local principal.
- `RF-AI-02`: el Core consume un contrato genérico de proveedor.
- `RF-AI-03`: se comprueban servidor y modelo configurado.
- `RF-AI-04`, `RNF-AVAIL-02` y `AC-09`: un fallo de Ollama no afecta las tools
  deterministas.
- `RF-TOOL-05`: los diagnósticos devuelven resultados estructurados.
- `RF-TOOL-06`, `RF-TERM-07` y `P-02`: el modelo no recibe shell ni capacidad
  de ejecutar tools.
- `RF-SYS-02`, `RF-SYS-03`, `RF-SYS-05`, `RF-DIAG-02` y `RF-DIAG-03`: se
  consultan CPU, almacenamiento y procesos de mayor consumo.
- `RF-SEC-01` y `RF-SEC-03`: las nuevas tools son R0 y pasan por el
  `PermissionManager`.
- `RF-OFF-01`, `RF-OFF-03` y `RF-OFF-05`: las capacidades deterministas
  permanecen locales y no dependen de red externa.

## Arquitectura

### Contrato de proveedor

Un protocolo de proveedor define las operaciones que necesita `ModelRouter`:
comprobar el estado y generar texto. El Core solo conoce ese protocolo y los
resultados normalizados; no importa paquetes, endpoints ni excepciones de
Ollama.

El resultado de estado distingue:

- servidor accesible;
- modelo configurado disponible;
- detalle de indisponibilidad apto para mostrar al usuario.

El resultado de generación incluye contenido, nombre del proveedor, éxito y
un error normalizado cuando corresponda. No contiene callbacks ni solicitudes
ejecutables.

### OllamaProvider

`OllamaProvider` reside fuera de `kwiaty/core` y usa HTTP con la biblioteca
estándar de Python. Esto evita una dependencia de ejecución adicional y hace
explícitos los límites de red y tiempo.

Configuración:

- `KWIATY_OLLAMA_URL`, por defecto `http://127.0.0.1:11434`;
- `KWIATY_OLLAMA_MODEL`, requerido para generar y documentado con un valor de
  ejemplo, sin fijar en código una decisión pendiente de la especificación;
- `KWIATY_OLLAMA_TIMEOUT`, por defecto `30` segundos y validado como número
  positivo.

Solo se aceptan URLs HTTP cuyo host sea `localhost` o una dirección IP de
loopback. No se siguen redirecciones fuera de ese límite. Una URL no local se
rechaza al construir la configuración.

Operaciones HTTP:

- `GET /api/tags` comprueba el servidor y obtiene los modelos instalados;
- la coincidencia del modelo acepta el nombre exacto devuelto por Ollama;
- `POST /api/generate` envía `model`, `prompt` y `stream: false`;
- la respuesta solo se acepta si es JSON válido con un campo `response` de
  texto.

Los errores de timeout, conexión, HTTP, JSON y esquema se convierten en
resultados normalizados. No se propagan trazas ni excepciones de transporte a
la interfaz.

### ModelRouter y Orchestrator

`ModelRouter` recibe el proveedor por inyección y `create_default` construye el
proveedor Ollama a partir del entorno. El router comprueba disponibilidad antes
de generar y devuelve un aviso controlado si falta el servidor o el modelo.

El `Orchestrator` mantiene la ruta actual:

1. `IntentRouter` intenta una ruta determinista.
2. Solo una intención de razonamiento consulta al `ModelRouter`.
3. El contenido del modelo se presenta como texto y nunca se interpreta como
   llamada a tool, comando o instrucción de seguridad.
4. El éxito y la auditoría de la consulta reflejan el resultado real del
   proveedor.

No se envían esquemas de tools a Ollama y no existe bucle de tool calling en
esta fase.

## Diagnósticos R0

El `PlatformAdapter` se amplía con contratos estructurados para:

- porcentaje de CPU total calculado a partir de dos muestras de `/proc/stat`;
- uso del sistema de archivos indicado mediante `shutil.disk_usage`;
- lista limitada de procesos ordenada por consumo de memoria o CPU, obtenida
  desde `/proc` sin ejecutar comandos.

El adaptador controla archivos que desaparecen durante una lectura de
procesos, datos incompletos y permisos insuficientes. Un proceso ilegible se
omite; un fallo de la operación completa produce un `ToolResult` fallido.

Se incorporan tres tools independientes:

- `kwiaty.system.cpu_usage`, sin parámetros;
- `kwiaty.system.disk_usage`, con ruta opcional cuyo valor por defecto es `/`;
- `kwiaty.system.top_processes`, con criterio `cpu` o `memory` y límite
  acotado.

Todas declaran riesgo R0, disponibilidad offline y plataformas Linux/CachyOS.
Sus resultados contienen hechos y unidades explícitas; no recomiendan ni
ejecutan correcciones.

`IntentRouter` reconocerá frases directas de CPU, disco y procesos. Las
consultas ambiguas o explicativas siguen la ruta LLM.

## Seguridad

- Ningún módulo del proveedor importa o invoca `subprocess`, shell, registro
  de tools ni `PermissionManager`.
- La respuesta de Ollama es texto no confiable y no puede iniciar acciones.
- Las tools deterministas conservan el flujo obligatorio de registro,
  validación, permisos y auditoría.
- El transporte de Ollama no permite hosts remotos, HTTPS externo ni
  redirecciones fuera de loopback.
- No se registran prompts completos adicionales ni secretos en el proveedor.

## Experiencia de error

La interfaz distingue mensajes breves para:

- Ollama no accesible;
- modelo configurado no instalado;
- tiempo de espera agotado;
- respuesta inválida del servidor.

Un error LLM produce un resultado no exitoso en esa consulta. A continuación,
una consulta determinista puede ejecutarse normalmente en el mismo proceso.

## Pruebas

Las pruebas se escriben antes de cada cambio de producción y se ejecutan con
`pytest`, conservando compatibilidad con las pruebas `unittest` existentes.

Cobertura requerida:

- configuración local válida y rechazo de URLs remotas o timeouts inválidos;
- servidor disponible, modelo presente y modelo ausente;
- generación correcta y errores de timeout, conexión, HTTP, JSON y esquema;
- inyección de proveedor y degradación del `ModelRouter`;
- semántica de éxito y auditoría del `Orchestrator`;
- prueba que demuestra que una respuesta con sintaxis de tool o shell sigue
  siendo texto sin ejecución;
- CPU, disco y procesos mediante fixtures deterministas;
- metadatos, validación, permisos, rutas de intención y presentación CLI;
- regresión: status y RAM funcionan con un proveedor Ollama fallido.

GitHub Actions ejecutará en cada `push` y `pull_request`:

1. checkout;
2. instalación de una versión compatible de Python;
3. instalación editable con dependencias de desarrollo;
4. `python -m pytest`.

La suite no requiere un servidor Ollama real ni acceso de red.

## Documentación

El README incluirá:

- creación de entorno virtual e instalación;
- instalación para desarrollo con pytest;
- arranque local de Ollama y descarga manual del modelo elegido;
- variables de entorno y valores por defecto;
- comandos CLI deterministas y consulta conversacional;
- comandos para ejecutar la suite completa y subconjuntos relevantes;
- comportamiento esperado cuando Ollama o el modelo no están disponibles.

## Fuera de alcance

No se implementan GUI, memoria persistente, automatizaciones, web, cloud,
tool calling del LLM, shell executor, servicios, journal, acciones correctivas
ni selección de varios modelos.
