"""Permite invocar kwiaty como módulo: python -m kwiaty."""

import sys
from kwiaty.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
