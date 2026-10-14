"""Linha de comando da skill csv-eda-notebook.

Uso:
    python scripts/gerar_eda.py dados.csv -o analise.ipynb [--alvo coluna] [--titulo "..."]

Códigos de saída: 0 ok · 1 erro de entrada · 2 uso incorreto (argparse) ·
3 notebook gerado, mas a execução falhou · 4 notebook gerado sem execução por
falta de nbclient/nbformat/ipykernel.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import codigo, notebook
from .apoio import chave_normalizada, limpar_dados
from .codigo import Opcoes, plano_limpeza, selecionar_colunas
from .loader import CATEGORICA, NUMERICA, ErroLeitura, avisos_do_perfil, carregar_csv, perfilar
from .notebook import Execucao
from .resumo import resumo_markdown

SAIDA_OK = 0
SAIDA_ERRO_ENTRADA = 1
SAIDA_EXECUCAO_FALHOU = 3
SAIDA_SEM_KERNEL = 4
REQUISITOS = Path(__file__).resolve().parents[2] / "requirements.txt"
LIMITE_CLASSES_ALVO = 20


class ErroEntrada(ValueError):
    """Argumento inválido (ex.: --alvo que não existe), com mensagem em pt-BR."""


@dataclass
class Resultado:
    """O que `gerar` produziu."""

    caminho: Path
    codigo: int
    mensagem: str                    # linha "Execução: ..." sem o prefixo
    avisos: list[str] = field(default_factory=list)
    resumo: str = ""
    execucao: Execucao | None = None


def _inteiro_positivo(texto: str) -> int:
    valor = int(texto)
    if valor < 1:
        raise argparse.ArgumentTypeError("precisa ser 1 ou mais")
    return valor


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gerar_eda.py",
        description="Gera um notebook Jupyter de análise exploratória a partir de um CSV.",
    )
    parser.add_argument("csv", help="Arquivo CSV/TSV (também .csv.gz, .csv.zip, .bz2, .xz).")
    parser.add_argument("-o", "--saida", help="Notebook a criar. Padrão: <nome-do-csv>_eda.ipynb")
    parser.add_argument("--titulo", help="Título do cabeçalho do notebook.")
    parser.add_argument("--alvo", help="Variável de interesse: gera uma seção com a relação dela "
                                       "com as demais colunas.")
    parser.add_argument("--sep", "--separador", dest="sep",
                        help="Separador: ',', ';', '|' ou tab (\\t). Detectado por padrão.")
    parser.add_argument("--encoding", help="Encoding (utf-8, cp1252, latin-1...). Detectado por padrão.")
    parser.add_argument("--decimal", choices=[".", ","],
                        help="Separador decimal do arquivo. Detectado por padrão.")
    parser.add_argument("--max-graficos", type=_inteiro_positivo, default=6,
                        help="Máximo de numéricas nos gráficos de distribuição (padrão: 6).")
    parser.add_argument("--nao-executar", action="store_true",
                        help="Salva o notebook sem rodar as células (mais rápido).")
    return parser


def _saida_padrao(csv: Path) -> Path:
    """dados.csv.zip -> dados_eda.ipynb, na pasta do CSV."""
    nome = csv.name
    for sufixos in ((".gz", ".zip", ".bz2", ".xz"), (".csv", ".tsv", ".txt")):
        sufixo = next((s for s in sufixos if nome.lower().endswith(s)), "")
        nome = nome[: len(nome) - len(sufixo)]
    return csv.with_name(f"{nome}_eda.ipynb")


def _resolver_alvo(alvo: str, colunas: list[str]) -> str:
    """Nome exato, ou o único que coincide ignorando caixa, acentos e espaços."""
    if alvo in colunas:
        return alvo
    iguais = [c for c in colunas if chave_normalizada(c) == chave_normalizada(alvo)]
    if len(iguais) == 1:
        return iguais[0]
    if iguais:
        raise ErroEntrada(f"--alvo {alvo!r} é ambíguo: coincide com "
                          f"{', '.join(repr(c) for c in iguais)}. Use o nome exato.")
    parecidas = difflib.get_close_matches(alvo, colunas, n=3, cutoff=0.5)
    sugestao = f" Você quis dizer: {', '.join(repr(c) for c in parecidas)}?" if parecidas else ""
    disponiveis = ", ".join(repr(c) for c in colunas[:30]) + (" ..." if len(colunas) > 30 else "")
    raise ErroEntrada(f"A coluna {alvo!r} não existe.{sugestao} Colunas: {disponiveis}")


def _validar_alvo(alvo: str, perfil) -> None:
    info = next(c for c in perfil if c.nome == alvo)
    if info.identificador:
        raise ErroEntrada(f"A coluna {alvo!r} é um identificador e não pode ser variável de interesse.")
    if info.tipo not in (NUMERICA, CATEGORICA):
        tipo = "data" if info.tipo == "data" else "texto livre"
        raise ErroEntrada(f"A coluna {alvo!r} é {tipo} e não pode ser variável de interesse; "
                          "escolha uma coluna numérica ou categórica.")
    if info.nao_nulos == 0:
        raise ErroEntrada(f"A coluna {alvo!r} está vazia; não há o que comparar.")
    if info.n_unicos < 2:
        raise ErroEntrada(f"A coluna {alvo!r} tem um único valor; não há o que comparar.")
    if info.tipo == CATEGORICA and info.n_unicos > LIMITE_CLASSES_ALVO:
        raise ErroEntrada(f"A coluna {alvo!r} tem {info.n_unicos} categorias; a variável de "
                          f"interesse categórica pode ter no máximo {LIMITE_CLASSES_ALVO}.")


def gerar(csv, saida=None, titulo=None, alvo=None, separador=None, encoding=None, decimal=None,
          max_graficos: int = 6, executar_notebook: bool = True) -> Resultado:
    """Gera (e por padrão executa) o notebook. Lança ErroLeitura, ErroEntrada ou FileNotFoundError."""
    csv = Path(csv).expanduser()
    caminho_saida = Path(saida).expanduser() if saida else _saida_padrao(csv)
    if caminho_saida.is_dir():
        caminho_saida = caminho_saida / _saida_padrao(csv).name
    if caminho_saida.suffix.lower() != ".ipynb":
        raise ErroEntrada(f"A saída precisa ser um arquivo .ipynb: {caminho_saida}")
    arquivo_no_caminho = next((pasta for pasta in caminho_saida.parents if pasta.is_file()), None)
    if arquivo_no_caminho:
        raise ErroEntrada(f"A pasta de saída {arquivo_no_caminho} é um arquivo, não uma pasta.")
    if caminho_saida.resolve() == csv.resolve():
        raise ErroEntrada(f"A saída não pode ser o próprio CSV: {caminho_saida}")
    leitura = carregar_csv(csv, separador, encoding, decimal)
    df_bruto = leitura.df
    if alvo is not None:
        alvo = _resolver_alvo(alvo, list(df_bruto.columns))

    perfil_bruto = perfilar(df_bruto)
    avisos = list(leitura.avisos) + avisos_do_perfil(df_bruto, perfil_bruto)
    dica = "," if leitura.parametros.get("decimal") == "," or leitura.separador == ";" else None
    plano = plano_limpeza(df_bruto, perfil_bruto, dica)
    df, registro = limpar_dados(df_bruto, plano)
    # Do registro da limpeza, só vira aviso o que perdeu ou removeu dados.
    avisos += [linha for linha in registro if "→ ausente" in linha or "duplicata" in linha
               or "idêntica" in linha]
    perfil = perfilar(df, tipos={c.nome: c.tipo for c in perfil_bruto})
    if alvo is not None:
        _validar_alvo(alvo, perfil)

    opcoes = Opcoes(
        caminho_csv=csv.resolve(),
        saida=caminho_saida,
        titulo=titulo or f"Análise exploratória — {csv.name}",
        leitura_parametros=leitura.parametros,
        alvo=alvo,
        max_numericas_grafico=max_graficos,
        avisos_leitura=list(leitura.avisos),
    )
    selecao = selecionar_colunas(df, perfil, opcoes)
    resumo = resumo_markdown(df, perfil, selecao, csv.name, alvo, avisos)
    # Chamadas pelo módulo (codigo.*, notebook.*) para aceitarem monkeypatch nos testes.
    celulas = codigo.gerar_celulas(df, perfil, opcoes, resumo, plano, selecao)
    caminho = notebook.salvar(notebook.construir_notebook(celulas, opcoes.titulo), caminho_saida)

    execucao = None
    if not executar_notebook:
        codigo_saida, mensagem = SAIDA_OK, "não executado: --nao-executar"
    elif faltando := notebook.dependencias_execucao():
        codigo_saida = SAIDA_SEM_KERNEL
        mensagem = (f"não executado: falta {', '.join(faltando)}. Instale com: "
                    f"pip install -r {REQUISITOS} (o notebook foi salvo sem resultados)")
    else:
        execucao = notebook.executar(caminho)
        mensagem = execucao.mensagem
        if execucao.ok:
            codigo_saida = SAIDA_OK
        else:
            codigo_saida = SAIDA_SEM_KERNEL if execucao.sem_kernel else SAIDA_EXECUCAO_FALHOU
    return Resultado(caminho, codigo_saida, mensagem, avisos, resumo, execucao)


def _saida_utf8() -> None:
    """Console do Windows: sem isso, acentos e símbolos podem derrubar o print."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    _saida_utf8()
    args = construir_parser().parse_args(argv)
    try:
        resultado = gerar(
            csv=args.csv,
            saida=args.saida,
            titulo=args.titulo,
            alvo=args.alvo,
            separador=args.sep,
            encoding=args.encoding,
            decimal=args.decimal,
            max_graficos=args.max_graficos,
            executar_notebook=not args.nao_executar,
        )
    except (OSError, ErroLeitura, ErroEntrada) as erro:  # OSError: CSV inexistente, sem permissão, pasta inválida
        print(f"Erro: {erro}", file=sys.stderr)
        return SAIDA_ERRO_ENTRADA

    print(f"Notebook gerado em: {resultado.caminho.resolve()}")
    print(f"Execução: {resultado.mensagem}")
    if resultado.avisos:
        print("Avisos:")
        for aviso in resultado.avisos:
            print(f"- {aviso}")
    print("---")
    print(resultado.resumo)
    return resultado.codigo
