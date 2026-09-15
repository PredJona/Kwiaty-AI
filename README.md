# Kwiaty (v1)

Asistente personal local-first para CachyOS con arquitectura modular y herramientas estructuradas.

## Principios
* **Kwiaty ≠ Qwen**: El Core no depende directamente del modelo de lenguaje ni del sistema operativo.
* **LLM sin acceso directo al SO**: Toda operación de sistema pasa por `PermissionManager` y herramientas estructuradas.
* **Seguridad independiente del modelo**: Niveles `R0`, `R1`, `R2`, `R3`, `RX`. El modelo nunca puede reducir el riesgo de una operación.
* **Local-first y determinista**: Funciona sin internet y sin LLM para operaciones deterministas de diagnóstico y sistema.

## Uso (Fase 1)
```bash
# Estado general del sistema
python3 -m kwiaty status

# Consulta determinista de memoria RAM
python3 -m kwiaty "cuánta RAM estoy usando"
```
