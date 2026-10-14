"""Skill csv-eda-notebook: análise exploratória de CSV com geração de notebook Jupyter.

Uso como biblioteca (com a pasta scripts/ no sys.path):
    from eda import gerar
    resultado = gerar("dados.csv", alvo="churn")
    print(resultado.caminho, resultado.codigo, resultado.mensagem)
"""

from .cli import ErroEntrada, Resultado, gerar, main
from .codigo import Opcoes, gerar_celulas, selecionar_colunas
from .loader import ErroLeitura, carregar_csv, perfilar

__all__ = [
    "gerar",
    "main",
    "carregar_csv",
    "perfilar",
    "Opcoes",
    "gerar_celulas",
    "selecionar_colunas",
    "Resultado",
    "ErroLeitura",
    "ErroEntrada",
]
