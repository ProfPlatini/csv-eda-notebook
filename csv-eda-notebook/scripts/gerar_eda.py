#!/usr/bin/env python3
"""Ponto de entrada da skill csv-eda-notebook.

Gera um notebook Jupyter (.ipynb) com a análise exploratória de um CSV.

    python scripts/gerar_eda.py dados.csv -o analise.ipynb
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eda.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
