"""Punto de entrada principal para la interfaz de línea de comandos (CLI) de Kwiaty.

Permite consultar el estado del sistema, invocar consultas deterministas en lenguaje
natural o inspeccionar herramientas y auditoría (RF-CLI-01 a RF-CLI-07).
"""

from __future__ import annotations
import sys
import json
from typing import List, Optional

from kwiaty import __version__
from kwiaty.cli.presenter import CliPresenter
from kwiaty.core.orchestrator import Orchestrator


HELP_TEXT = f"""Kwiaty AI v{__version__} - Asistente local-first modular para CachyOS

Uso:
  kwiaty status [--json]
  kwiaty tools [list] [--json]
  kwiaty audit [list] [-n LÍMITE] [--json]
  kwiaty "<consulta en lenguaje natural>" [--json]
  kwiaty -v | --version
  kwiaty -h | --help

Ejemplos:
  kwiaty status
  kwiaty "cuánta RAM estoy usando"
  kwiaty "cómo está el sistema"
  kwiaty tools list
  kwiaty audit list -n 5
"""


def parse_cli_args(args: List[str]):
    """Parsea argumentos de la CLI soportando subcomandos estructurados y lenguaje natural."""
    clean_args = list(args)
    json_mode = False
    if "--json" in clean_args:
        json_mode = True
        clean_args.remove("--json")

    if not clean_args:
        return {"action": "help", "json": json_mode}

    # Version
    if clean_args[0] in ("-v", "--version"):
        return {"action": "version", "json": json_mode}

    # Help
    if clean_args[0] in ("-h", "--help"):
        return {"action": "help", "json": json_mode}

    first_arg = clean_args[0].lower()

    # Subcomando: status
    if first_arg == "status":
        return {"action": "status", "json": json_mode}

    # Subcomando: tools
    if first_arg == "tools":
        subaction = "list"
        if len(clean_args) > 1 and clean_args[1] in ("list",):
            subaction = clean_args[1]
        return {"action": "tools", "subaction": subaction, "json": json_mode}

    # Subcomando: audit
    if first_arg == "audit":
        subaction = "list"
        limit = 10
        idx = 1
        while idx < len(clean_args):
            tok = clean_args[idx]
            if tok in ("-n", "--limit") and idx + 1 < len(clean_args):
                try:
                    limit = int(clean_args[idx + 1])
                except ValueError:
                    pass
                idx += 2
            elif tok in ("list",):
                subaction = tok
                idx += 1
            else:
                idx += 1
        return {"action": "audit", "subaction": subaction, "limit": limit, "json": json_mode}

    # Lenguaje natural (ej. 'cuánta RAM estoy usando' o palabras separadas)
    query = " ".join(clean_args)
    return {"action": "query", "query": query, "json": json_mode}


def main(args: Optional[List[str]] = None) -> int:
    """Función principal de ejecución."""
    if args is None:
        args = sys.argv[1:]

    parsed = parse_cli_args(args)
    action = parsed.get("action")
    json_mode = parsed.get("json", False)

    if action == "help":
        print(HELP_TEXT.strip())
        return 0

    if action == "version":
        print(f"kwiaty v{__version__}")
        return 0

    orchestrator = Orchestrator.create_default()

    # 1. Comando status
    if action == "status":
        result = orchestrator.execute_tool("kwiaty.system.status")
        if json_mode:
            print(CliPresenter.render_json(result))
        else:
            print(CliPresenter.render_normal(result))
        return 0 if result.success else 1

    # 2. Comando tools
    if action == "tools":
        tools_meta = orchestrator.tool_registry.list_tools()
        if json_mode:
            data = [
                {
                    "name": t.name,
                    "domain": t.domain,
                    "description": t.description,
                    "risk_level": t.risk_level.value,
                    "offline_available": t.offline_available,
                }
                for t in tools_meta
            ]
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"Herramientas registradas ({len(tools_meta)}):")
            for t in tools_meta:
                print(f"  • [{t.risk_level.value}] {t.name}: {t.description}")
        return 0

    # 3. Comando audit
    if action == "audit":
        limit = parsed.get("limit", 10)
        entries = orchestrator.audit_logger.read_recent(limit=limit)
        if json_mode:
            print(json.dumps(entries, indent=2, ensure_ascii=False))
        else:
            if not entries:
                print("No hay registros de auditoría recientes.")
            else:
                print(f"Últimos {len(entries)} registros de auditoría:")
                for e in entries:
                    status_str = "OK" if e.get("execution_success") else "FAIL"
                    print(
                        f"  [{e.get('timestamp')}] {e.get('action')} - "
                        f"tool={e.get('tool_name')} risk={e.get('risk_level')} status={status_str}"
                    )
        return 0

    # 4. Consulta en lenguaje natural
    if action == "query":
        query = parsed.get("query", "")
        result = orchestrator.process_query(query)
        if json_mode:
            print(CliPresenter.render_json(result))
        else:
            print(CliPresenter.render_normal(result))
        return 0 if result.success else 1

    print(HELP_TEXT.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
