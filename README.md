# Kwiaty (Fase 2)

Asistente local-first para CachyOS con Core modular, herramientas estructuradas
y conversación local opcional mediante Ollama.

## Principios

- **Kwiaty ≠ modelo:** el Core depende de `ModelRouter`, no de un modelo concreto.
- **LLM sin acceso al sistema:** Ollama recibe texto y contexto mínimo; nunca
  recibe shell, callbacks ni definiciones ejecutables de tools.
- **Seguridad independiente:** toda tool pasa por `PermissionManager` y conserva
  su nivel `R0`, `R1`, `R2`, `R3` o `RX`.
- **Degradación local:** si Ollama o el modelo faltan, las consultas
  deterministas de diagnóstico siguen funcionando.

Esta fase no incluye GUI, memoria persistente, automatizaciones, web ni cloud.

## Requisitos

- Python 3.10 o posterior.
- Linux; CachyOS es la plataforma soportada oficialmente.
- Ollama local solo para consultas conversacionales.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Para desarrollar y ejecutar las pruebas:

```bash
python -m pip install -e ".[dev]"
```

## Configuración de Ollama

Instala Ollama por el mecanismo recomendado para tu sistema y arranca el
servidor local:

```bash
ollama serve
```

En otra terminal, descarga el modelo que quieras usar. El modelo exacto no está
fijado por la arquitectura; este es un ejemplo:

```bash
ollama pull qwen2.5:7b
```

Configura Kwiaty:

```bash
export KWIATY_OLLAMA_MODEL="qwen2.5:7b"
export KWIATY_OLLAMA_URL="http://127.0.0.1:11434"
export KWIATY_OLLAMA_TIMEOUT="30"
```

| Variable | Valor predeterminado | Uso |
| --- | --- | --- |
| `KWIATY_OLLAMA_MODEL` | sin valor | Nombre exacto de un modelo instalado. |
| `KWIATY_OLLAMA_URL` | `http://127.0.0.1:11434` | API local de Ollama. |
| `KWIATY_OLLAMA_TIMEOUT` | `30` | Timeout positivo en segundos. |

Por seguridad, `KWIATY_OLLAMA_URL` solo acepta HTTP sobre `localhost` o una
dirección IP de loopback. No acepta credenciales, hosts remotos ni servicios
cloud.

Kwiaty comprueba que el servidor responda y que el modelo configurado aparezca
en `/api/tags` antes de generar. Si cualquiera falla, la consulta conversacional
termina con un aviso controlado; comandos como `status`, RAM, CPU, disco y
procesos permanecen disponibles.

## Uso

Diagnósticos deterministas R0, sin cargar el modelo:

```bash
python -m kwiaty status
python -m kwiaty "cuánta RAM estoy usando"
python -m kwiaty "uso de cpu"
python -m kwiaty "espacio en disco"
python -m kwiaty "procesos que más memoria usan"
python -m kwiaty "procesos que más cpu usan"
```

Consulta conversacional mediante Ollama:

```bash
python -m kwiaty "explícame qué significa load average"
```

Inspección administrativa:

```bash
python -m kwiaty tools list
python -m kwiaty audit list -n 5
python -m kwiaty status --json
```

La respuesta generada por Ollama se presenta literalmente como texto. Aunque
contenga un comando o una aparente llamada a una tool, Kwiaty no la ejecuta.

## Pruebas

Suite completa con pytest, igual que GitHub Actions:

```bash
python -m pytest
```

Subconjuntos relevantes:

```bash
python -m pytest tests/unit/test_ollama_provider.py
python -m pytest tests/unit/test_model_router.py
python -m pytest tests/unit/test_diagnostic_tools.py
python -m pytest tests/integration/test_cli.py
```

Las pruebas usan transportes y fixtures locales; no requieren un servidor
Ollama real ni conexión a Internet.
