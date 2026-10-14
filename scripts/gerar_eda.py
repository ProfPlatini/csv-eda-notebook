#!/usr/bin/env python3
"""Ponto de entrada da skill csv-eda-notebook.

Gera um notebook Jupyter (.ipynb) com a análise exploratória de um CSV:

    python scripts/gerar_eda.py dados.csv -o analise.ipynb
"""

import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent

if sys.version_info < (3, 10):
    sys.exit(f"Erro: a skill precisa de Python 3.10 ou mais novo (este é {sys.version.split()[0]}).")

for _modulo in ("pandas", "numpy", "matplotlib", "seaborn"):
    try:
        __import__(_modulo)
    except ImportError:
        sys.exit(f"Erro: Dependência ausente: {_modulo}. "
                 f"Instale com: pip install -r {PASTA.parent / 'requirements.txt'}")

sys.path.insert(0, str(PASTA))

from eda.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
