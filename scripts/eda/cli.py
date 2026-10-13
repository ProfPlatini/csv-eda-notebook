"""Linha de comando da skill csv-eda-notebook.

Uso:
    python scripts/gerar_eda.py dados.csv -o analise.ipynb [--alvo coluna] [--titulo "..."]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .codigo import Opcoes, gerar_celulas
from .loader import carregar_csv, perfilar
from .notebook import construir_notebook, executar, salvar
from .resumo import resumo_markdown


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gerar_eda.py",
        description="Gera um notebook Jupyter de análise exploratória a partir de um CSV.",
    )
    parser.add_argument("csv", help="Caminho do arquivo CSV a analisar.")
    parser.add_argument(
        "-o", "--saida",
        help="Arquivo .ipynb a ser criado. Padrão: <nome-do-csv>_eda.ipynb",
    )
    parser.add_argument("--titulo", help="Título usado no cabeçalho do notebook.")
    parser.add_argument(
        "--alvo",
        help="Coluna de interesse (variável alvo). Gera uma seção extra com a relação dela "
             "com as demais variáveis.",
    )
    parser.add_argument("--sep", "--separador", dest="sep",
                        help="Separador do CSV. Detectado automaticamente por padrão.")
    parser.add_argument("--encoding", help="Encoding do CSV. Detectado automaticamente por padrão.")
    parser.add_argument("--max-graficos", type=int, default=6,
                        help="Máximo de variáveis numéricas nos gráficos (padrão: 6).")
    parser.add_argument("--nao-executar", action="store_true",
                        help="Salva o notebook sem rodar as células (mais rápido).")
    return parser


def gerar(csv: str | Path, saida: str | Path | None = None, titulo: str | None = None,
          alvo: str | None = None, separador: str | None = None,
          encoding: str | None = None, max_graficos: int = 6,
          executar_notebook: bool = True) -> tuple[Path, str]:
    """Gera o notebook e devolve (caminho, mensagem)."""
    df, sep_detectado, enc_detectado = carregar_csv(csv, separador, encoding)
    if df.empty:
        raise ValueError(f"O arquivo {csv} não contém nenhuma linha de dados.")

    perfil = perfilar(df)
    caminho_saida = Path(saida) if saida else Path(csv).with_name(
        Path(csv).stem + "_eda.ipynb")
    titulo_final = titulo or f"Análise exploratória — {Path(csv).name}"

    opcoes = Opcoes(
        caminho_csv=Path(csv).resolve(),
        saida=caminho_saida,
        titulo=titulo_final,
        separador=sep_detectado,
        encoding=enc_detectado,
        alvo=alvo,
        max_numericas_grafico=max_graficos,
    )

    resumo = resumo_markdown(df, perfil, Path(csv).name, alvo)
    celulas = gerar_celulas(df, perfil, opcoes, resumo)
    caminho = salvar(construir_notebook(celulas, titulo_final), caminho_saida)

    if executar_notebook:
        _, mensagem = executar(caminho)
    else:
        mensagem = "Notebook salvo sem execução (use --nao-executar foi solicitado)."
    return caminho, mensagem


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    try:
        caminho, mensagem = gerar(
            csv=args.csv,
            saida=args.saida,
            titulo=args.titulo,
            alvo=args.alvo,
            separador=args.sep,
            encoding=args.encoding,
            max_graficos=args.max_graficos,
            executar_notebook=not args.nao_executar,
        )
    except (FileNotFoundError, ValueError, PermissionError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1

    print(f"Notebook gerado em: {caminho.resolve()}")
    print(mensagem)
    return 0
