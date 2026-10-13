"""Skill csv-eda-notebook: análise exploratória de CSV com geração de notebook Jupyter.

Uso como biblioteca:
    from eda import gerar
    caminho, mensagem = gerar("dados.csv", alvo="churn")
"""

from .cli import gerar, main
from .codigo import Opcoes, gerar_celulas, selecionar_colunas
from .loader import carregar_csv, perfilar

__all__ = [
    "gerar",
    "main",
    "Opcoes",
    "gerar_celulas",
    "selecionar_colunas",
    "carregar_csv",
    "perfilar",
]
