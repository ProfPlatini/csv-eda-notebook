"""Geração das células do notebook de análise exploratória.

O notebook é montado *a partir do conteúdo real do CSV*: as células citam os
nomes das colunas que existem, mostram apenas as análises que fazem sentido
para os tipos detectados e nunca inventam variáveis. Todo nome de coluna entra
no código com repr(), então aspas, barras e acentos não quebram as células.
"""

from __future__ import annotations

import os
import re
import textwrap
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path, PurePath

import numpy as np
import pandas as pd

from . import apoio
from .apoio import (
    chave_normalizada,
    checar_qualidade,
    converter_datas,
    detectar_decimal,
    eta_quadrado,
    v_de_cramer,
)
from .loader import CATEGORICA, DATA, NUMERICA, TEXTO, ColunaInfo, perfilar
from .resumo import MIN_GRUPO_TAXA, NOME_PERIODO, md_codigo

MAX_NUMERICAS_GRAFICO = 6
MAX_CATEGORICAS_GRAFICO = 4
MAX_CATEGORICAS_AGRUPAR = 8
MAX_COLUNAS_DESCRIBE = 25
MAX_CORRELACAO = 15
MAX_FREQUENCIAS = 12
MAX_TEXTO = 4
MAX_DATAS = 2
MAX_PARES = 3
LIMITE_CATEGORIAS_GRAFICO = 20
LIMITE_CATEGORIAS_AGRUPAR = 8
MIN_GRUPO = 5           # registros mínimos para um grupo entrar nas comparações
MIN_CORRELACAO = 10     # linhas mínimas para calcular uma correlação
NOMES_SEPARADOR = {",": "vírgula", ";": "ponto e vírgula", "\t": "tabulação", "|": "barra vertical"}
ROTULOS_TIPO = {NUMERICA: "numérica", CATEGORICA: "categórica", DATA: "data", TEXTO: "texto livre"}


@dataclass
class Opcoes:
    """Parâmetros que controlam o notebook gerado."""

    caminho_csv: Path
    saida: Path
    titulo: str = "Análise exploratória de dados"
    leitura_parametros: dict = field(default_factory=dict)
    alvo: str | None = None
    max_numericas_grafico: int = MAX_NUMERICAS_GRAFICO
    max_categoricas_grafico: int = MAX_CATEGORICAS_GRAFICO
    avisos_leitura: list[str] = field(default_factory=list)


@dataclass
class Selecao:
    """Colunas escolhidas para cada bloco de análise."""

    numericas: list[str] = field(default_factory=list)            # histogramas e boxplots
    numericas_describe: list[str] = field(default_factory=list)
    numericas_correlacao: list[str] = field(default_factory=list)
    categorias: list[str] = field(default_factory=list)           # tabelas de frequência
    categorias_barra: list[str] = field(default_factory=list)
    categorias_agrupar: list[str] = field(default_factory=list)   # 2 a 8 grupos
    texto: list[str] = field(default_factory=list)
    datas: list[str] = field(default_factory=list)
    combos_num_cat: list[tuple[str, str]] = field(default_factory=list)  # (categoria, numérica)
    combos_cat_cat: list[tuple[str, str]] = field(default_factory=list)
    serie_temporal: list[str] = field(default_factory=list)
    para_numerico: list[str] = field(default_factory=list)        # numéricas que estão como texto
    binarias: list[str] = field(default_factory=list)
    regras: dict[str, str] = field(default_factory=dict)          # periodicidade por coluna de data
    alvo: str | None = None
    alvo_classes: bool = False        # True: alvo binário/categórico; False: numérico
    classe_positiva: object = None
    alvo_categorias: list[str] = field(default_factory=list)
    alvo_numericas: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Escolha das colunas
# --------------------------------------------------------------------------- #

def _regra_resample(datas: pd.Series) -> str:
    """Periodicidade da série temporal conforme o período coberto."""
    dias = (datas.max() - datas.min()).days
    if dias <= 45:
        return "D"
    if dias <= 200:
        return "W"
    if dias <= 1200:
        return "MS"
    if dias <= 4000:
        return "QS"
    return "YS"


def _classe_positiva(serie: pd.Series):
    """Classe cuja taxa é comparada entre os grupos.

    Com duas classes: 1, True, sim/yes/s; sem nenhuma delas, a menos frequente.
    Com mais: a menos frequente entre as que têm ao menos MIN_GRUPO_TAXA
    registros (uma grafia rara como "sudeste" não serve) ou, se nenhuma tem, a
    mais frequente.
    """
    contagem = serie.value_counts()
    if len(contagem) == 2:
        for valor in contagem.index:
            if chave_normalizada(valor) in {"1", "1.0", "true", "sim", "s", "yes", "y"}:
                return _nativo(valor)
    else:
        grandes = contagem[contagem >= MIN_GRUPO_TAXA]
        contagem = grandes if len(grandes) else contagem.head(1)
    menor = sorted(contagem.items(), key=lambda item: (item[1], str(item[0])))[0][0]
    return _nativo(menor)


def _nativo(valor):
    """Converte escalares do numpy em tipos do Python (para o repr ficar limpo)."""
    return valor.item() if isinstance(valor, np.generic) else valor


def _melhores_pares(candidatos: list[tuple[float, str, str]], limite: int) -> list[tuple[str, str]]:
    """Os pares de maior pontuação, cada coluna aparecendo no máximo duas vezes."""
    usos: Counter = Counter()
    escolhidos = []
    for _, a, b in sorted(candidatos, key=lambda c: -c[0]):
        if usos[a] < 2 and usos[b] < 2:
            escolhidos.append((a, b))
            usos.update([a, b])
        if len(escolhidos) == limite:
            break
    return escolhidos


def selecionar_colunas(df: pd.DataFrame, perfil: list[ColunaInfo], opcoes: Opcoes) -> Selecao:
    """Decide quais colunas entram em cada bloco de análise (df já limpo)."""
    sel = Selecao()
    uteis = [c for c in perfil if c.nao_nulos > 0 and not c.identificador]
    numericas = [c for c in uteis if c.tipo == NUMERICA]
    continuas = [c for c in numericas if c.n_unicos > 2]    # nem binária nem constante
    categoricas = [c for c in uteis if c.tipo == CATEGORICA]

    sel.binarias = [c.nome for c in numericas if c.binaria]
    # Variáveis com muitos valores distintos primeiro: são as que mais rendem em histograma.
    por_variedade = sorted(continuas, key=lambda c: (c.n_unicos <= 20, -c.nao_nulos))
    sel.numericas = [c.nome for c in por_variedade[: opcoes.max_numericas_grafico]]
    sel.numericas_describe = [c.nome for c in numericas if not c.binaria][:MAX_COLUNAS_DESCRIBE]
    sel.numericas_correlacao = [
        c.nome for c in continuas + [c for c in numericas if c.binaria] if c.nao_nulos >= MIN_CORRELACAO
    ][:MAX_CORRELACAO]
    sel.para_numerico = [c.nome for c in numericas if not pd.api.types.is_numeric_dtype(df[c.nome])]

    sel.categorias = ([c.nome for c in categoricas] + sel.binarias)[:MAX_FREQUENCIAS]
    poucas = [c for c in categoricas if 2 <= c.n_unicos <= LIMITE_CATEGORIAS_GRAFICO]
    poucas.sort(key=lambda c: (c.n_unicos > 8, -c.nao_nulos))
    sel.categorias_barra = ([c.nome for c in poucas] + sel.binarias)[: opcoes.max_categoricas_grafico]
    agrupaveis = [c for c in categoricas if 2 <= c.n_unicos <= LIMITE_CATEGORIAS_AGRUPAR]
    agrupaveis.sort(key=lambda c: -c.nao_nulos)
    sel.categorias_agrupar = [c.nome for c in agrupaveis][:MAX_CATEGORICAS_AGRUPAR]
    sel.texto = [c.nome for c in uteis if c.tipo == TEXTO][:MAX_TEXTO]

    for info in (c for c in uteis if c.tipo == DATA):
        datas = df[info.nome]
        if not pd.api.types.is_datetime64_any_dtype(datas):
            if not info.formato_data:
                continue
            datas = converter_datas(datas, info.formato_data)
        datas = datas.dropna()
        if len(datas) >= 10 and datas.nunique() >= 5 and len(sel.datas) < MAX_DATAS:
            sel.datas.append(info.nome)
            sel.regras[info.nome] = _regra_resample(datas)

    # Numérica x categoria: pares em que os grupos mais diferem (eta²).
    nomes_continuas = [c.nome for c in continuas]
    candidatos = [(eta, cat, num) for cat in sel.categorias_agrupar for num in nomes_continuas
                  if (eta := eta_quadrado(df, cat, num)) is not None]
    sel.combos_num_cat = _melhores_pares(candidatos, MAX_PARES)
    # Categoria x categoria: o par mais associado (V de Cramér).
    candidatos = [(v, a, b) for i, a in enumerate(sel.categorias_agrupar)
                  for b in sel.categorias_agrupar[i + 1:] if (v := v_de_cramer(df, a, b)) is not None]
    sel.combos_cat_cat = _melhores_pares(candidatos, 1)

    alvo = opcoes.alvo
    principais = [c.nome for c in por_variedade]
    if alvo in principais:  # o alvo numérico aparece primeiro na série temporal
        principais.remove(alvo)
        principais.insert(0, alvo)
    sel.serie_temporal = principais[:3]
    if alvo:
        _selecionar_alvo(df, perfil, sel, alvo, nomes_continuas)
    return sel


def _selecionar_alvo(df, perfil, sel: Selecao, alvo: str, continuas: list[str]) -> None:
    info = next(c for c in perfil if c.nome == alvo)
    sel.alvo = alvo
    sel.alvo_classes = info.tipo == CATEGORICA or info.binaria
    outras_categorias = [c for c in sel.categorias_agrupar if c != alvo]
    outras_numericas = [c for c in continuas if c != alvo]
    if sel.alvo_classes:
        sel.classe_positiva = _classe_positiva(df[alvo])
        pontuadas = [(v, c) for c in outras_categorias if (v := v_de_cramer(df, alvo, c)) is not None]
        sel.alvo_categorias = [c for _, c in sorted(pontuadas, key=lambda p: -p[0])][:2]
        pontuadas = [(e, c) for c in outras_numericas if (e := eta_quadrado(df, alvo, c)) is not None]
        sel.alvo_numericas = [c for _, c in sorted(pontuadas, key=lambda p: -p[0])][:3]
    else:
        pontuadas = [(e, c) for c in outras_categorias if (e := eta_quadrado(df, c, alvo)) is not None]
        sel.alvo_categorias = [c for _, c in sorted(pontuadas, key=lambda p: -p[0])][:2]
        sel.alvo_numericas = [c for c in sel.numericas_correlacao if c != alvo]


# --------------------------------------------------------------------------- #
# Plano de limpeza
# --------------------------------------------------------------------------- #

def coluna_identificadora(df: pd.DataFrame, perfil: list[ColunaInfo]) -> str | None:
    """Nome de uma coluna que identifica os registros, ignorando linhas repetidas.

    Se o id só se repete em linhas idênticas por inteiro, as repetições são o
    mesmo registro gravado duas vezes, e o id continua valendo como chave.
    """
    distintas = df.drop_duplicates()
    if len(distintas) < len(df):
        perfil = perfilar(distintas, tipos={c.nome: c.tipo for c in perfil})
    return next((c.nome for c in perfil if c.identificador), None)


def plano_limpeza(df: pd.DataFrame, perfil: list[ColunaInfo], dica_decimal: str | None = None) -> dict:
    """Plano aplicado por `limpar_dados`, gravado literalmente no notebook."""
    numericas = {c.nome: detectar_decimal(df[c.nome], dica_decimal) for c in perfil
                 if c.tipo == NUMERICA and not pd.api.types.is_numeric_dtype(df[c.nome])}
    datas = {c.nome: c.formato_data for c in perfil if c.tipo == DATA and c.formato_data}
    texto = [c.nome for c in perfil if c.nome not in numericas and c.nome not in datas
             and (pd.api.types.is_object_dtype(df[c.nome]) or pd.api.types.is_string_dtype(df[c.nome]))]
    return {"texto": texto, "numericas": numericas, "datas": datas,
            "remover_duplicadas": coluna_identificadora(df, perfil) is not None}


# --------------------------------------------------------------------------- #
# Utilitários de texto do código gerado
# --------------------------------------------------------------------------- #

def _literal(valor) -> str:
    """repr de listas e dicionários, quebrando em várias linhas quando ficam longos."""
    texto = repr(valor)
    if len(texto) <= 88 or not isinstance(valor, (list, dict)):
        return texto
    if isinstance(valor, list):
        return "[\n" + "".join(f"    {item!r},\n" for item in valor) + "]"
    return "{\n" + "".join(f"    {chave!r}: {item!r},\n" for chave, item in valor.items()) + "}"


def _codigo(modelo: str, **valores) -> str:
    """Troca <<NOME>> pelos valores (evita escapar as chaves do código gerado).

    Numa passada só: um valor que contenha "<<OUTRO>>" não é substituído de novo.
    """
    texto = textwrap.dedent(modelo).strip()
    return re.sub(r"<<([A-Z_]+)>>", lambda m: valores.get(m.group(1), m.group(0)), texto)


def _caminho_relativo(opcoes: Opcoes) -> str:
    """Caminho do CSV relativo à pasta do notebook.

    Fica absoluto quando estão em discos diferentes (Windows) ou distantes
    demais (mais de 3 níveis acima), caso em que o relativo seria frágil.
    """
    csv = Path(opcoes.caminho_csv).resolve()
    try:
        relativo = PurePath(os.path.relpath(csv, Path(opcoes.saida).resolve().parent))
    except ValueError:
        return csv.as_posix()
    return relativo.as_posix() if relativo.parts.count("..") <= 3 else csv.as_posix()


def _fonte_apoio() -> str:
    """Código de apoio.py sem a docstring do módulo (começa nos imports)."""
    fonte = Path(apoio.__file__).read_text(encoding="utf-8")
    return fonte[fonte.index("\nimport ") + 1:].strip()


AJUDANTES_GRAFICOS = '''
def finalizar(ax, titulo="", xlabel="", ylabel=""):
    """Título à esquerda, rótulos dos eixos e sem as bordas de cima e da direita."""
    ax.set_title(titulo, fontsize=12, fontweight="bold", loc="left", pad=10)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)


def exibir():
    """Ajusta o espaçamento e mostra a figura."""
    plt.tight_layout()
    plt.show()


def formatar_eixo_datas(ax):
    """Datas do eixo x em formato numérico curto (dd/mm, mm/aaaa, aaaa)."""
    localizador = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(localizador)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(
        localizador,
        formats=["%Y", "%m/%Y", "%d/%m", "%H:%M", "%H:%M", "%S"],
        zero_formats=["", "%Y", "%m/%Y", "%d/%m", "%H:%M", "%H:%M"],
        offset_formats=["", "%Y", "%m/%Y", "%d/%m/%Y", "%d/%m/%Y", "%d/%m/%Y %H:%M"],
    ))
'''


# --------------------------------------------------------------------------- #
# Células
# --------------------------------------------------------------------------- #

def _celula_configuracao(opcoes: Opcoes, alvo: str | None) -> str:
    comentario_linhas = ""
    if opcoes.leitura_parametros.get("on_bad_lines") == "skip":
        comentario_linhas = ("\n# on_bad_lines='skip': linhas com campos a mais são ignoradas "
                             "(veja os avisos da leitura).")
    return _codigo('''
        %matplotlib inline
        from pathlib import Path

        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
        import seaborn as sns
        from IPython.display import display

        sns.set_theme(style="whitegrid", context="notebook")
        plt.rcParams["figure.dpi"] = 110
        pd.set_option("display.max_columns", 60)
        pd.set_option("display.width", 160)
        pd.set_option("display.max_colwidth", 80)

        # Caminho do CSV relativo à pasta deste notebook (se mover o notebook, ajuste aqui).
        CSV_PATH = Path(<<CSV>>)
        # Parâmetros de leitura detectados na geração do notebook.<<COMENTARIO>>
        LEITURA = <<LEITURA>>
        # Variável de interesse (None = nenhuma).
        ALVO = <<ALVO>>
    ''', CSV=repr(_caminho_relativo(opcoes)), COMENTARIO=comentario_linhas,
        LEITURA=_literal(opcoes.leitura_parametros), ALVO=repr(alvo))


def _celula_leitura() -> str:
    return _codigo('''
        df_bruto, avisos_colunas = padronizar_colunas(pd.read_csv(CSV_PATH, **LEITURA))
        for aviso in avisos_colunas:
            print("Aviso:", aviso)
        print(f"{len(df_bruto)} linhas × {df_bruto.shape[1]} colunas")
        df_bruto.head()
    ''')


def _rotulo_tipo(info: ColunaInfo) -> str:
    if info.nao_nulos == 0:
        return "vazia"
    if info.identificador:
        return "identificador"
    if info.binaria:
        return "numérica binária"
    return ROTULOS_TIPO[info.tipo]


def _celula_visao_geral(perfil: list[ColunaInfo]) -> str:
    tipos = {c.nome: _rotulo_tipo(c) for c in perfil}
    return _codigo('''
        # Tipo atribuído na geração: decide em quais análises cada coluna entra.
        TIPOS = <<TIPOS>>

        visao = pd.DataFrame({
            "tipo_analise": pd.Series(TIPOS),
            "tipo_pandas": df_bruto.dtypes.astype(str),
            "preenchidos": df_bruto.notna().sum(),
            "distintos": df_bruto.nunique(),
        }, index=df_bruto.columns)
        visao
    ''', TIPOS=_literal(tipos))


def _celula_duplicadas() -> str:
    return _codigo('''
        duplicadas = df_bruto.duplicated()
        print("Linhas idênticas a uma linha anterior:", int(duplicadas.sum()))
        if duplicadas.any():
            display(df_bruto[df_bruto.duplicated(keep=False)].head(10))
    ''')


def _celula_limpeza(plano: dict, identificadora: str | None) -> str:
    if plano["remover_duplicadas"]:
        motivo = f"Há coluna identificadora ({identificadora!r}): linhas idênticas são registros repetidos."
    else:
        motivo = "Sem coluna identificadora: linhas idênticas podem ser registros legítimos."
    return _codigo('''
        # Formato de cada coluna de data (códigos de pandas.to_datetime).
        FORMATOS_DATA = <<DATAS>>
        # <<MOTIVO>>
        REMOVER_DUPLICADAS = <<REMOVER>>

        PLANO_LIMPEZA = {
            "texto": <<TEXTO>>,
            "numericas": <<NUMERICAS>>,
            "datas": FORMATOS_DATA,
            "remover_duplicadas": REMOVER_DUPLICADAS,
        }
        df, registro_limpeza = limpar_dados(df_bruto, PLANO_LIMPEZA)
        for linha in registro_limpeza:
            print("-", linha)
        print(f"Linhas: {len(df_bruto)} lidas → {len(df)} na análise")
    ''', DATAS=_literal(plano["datas"]), MOTIVO=motivo, REMOVER=repr(plano["remover_duplicadas"]),
        TEXTO=repr(plano["texto"]), NUMERICAS=repr(plano["numericas"]))


def _celula_ausentes() -> str:
    return _codigo('''
        ausentes = df.isna().sum().to_frame("ausentes")
        ausentes["%"] = (100 * ausentes["ausentes"] / len(df)).round(1)
        ausentes = ausentes[ausentes["ausentes"] > 0].sort_values("ausentes", ascending=False)
        if ausentes.empty:
            print("Nenhum valor ausente.")
        else:
            display(ausentes)
    ''')


def _celula_grafico_ausentes() -> str:
    return _codigo('''
        pct_ausentes = df.isna().mean().mul(100)
        pct_ausentes = pct_ausentes[pct_ausentes > 0].sort_values().tail(30)

        fig, ax = plt.subplots(figsize=(8, 0.4 * len(pct_ausentes) + 1.2))
        ax.barh(pct_ausentes.index.astype(str), pct_ausentes.values, color="#C44E52")
        for y, valor in enumerate(pct_ausentes.values):
            ax.text(valor, y, f" {formatar_numero(valor, 1)}%", va="center", fontsize=9)
        ax.set_xlim(0, 110)
        finalizar(ax, "Valores ausentes por coluna", "% de linhas sem valor")
        exibir()
    ''')


def _celula_qualidade(numericas: list[str], categoricas: list[str], parecidas: list[str]) -> str:
    exemplo = "".join(
        f"\n# df[{nome!r}] = df[{nome!r}].str.strip().str.capitalize()" for nome in parecidas)
    if exemplo:
        exemplo = ("\n\n# Para unificar variantes de categorias, adapte e descomente (e rode as "
                   "células seguintes de novo):" + exemplo)
    return _codigo('''
        COLS_NUM = <<NUM>>
        COLS_CAT = <<CAT>>
        qualidade = checar_qualidade(df, COLS_NUM, COLS_CAT, bruto=df_bruto)
        if qualidade.empty:
            print("Nenhum problema encontrado pelas checagens automáticas.")
        else:
            display(qualidade)<<EXEMPLO>>
    ''', NUM=_literal(numericas), CAT=_literal(categoricas), EXEMPLO=exemplo)


def _celula_describe(sel: Selecao) -> str:
    return _codigo('''
        COLS_DESCRIBE = <<COLS>>
        NOMES = {"count": "n", "mean": "média", "std": "desvio_padrão", "min": "mínimo",
                 "25%": "q1", "50%": "mediana", "75%": "q3", "max": "máximo"}

        estatisticas = df[COLS_DESCRIBE].describe().T.rename(columns=NOMES)
        estatisticas["assimetria"] = df[COLS_DESCRIBE].skew()
        estatisticas["curtose"] = df[COLS_DESCRIBE].kurtosis()
        estatisticas["ausentes"] = df[COLS_DESCRIBE].isna().sum()
        estatisticas.round(2)
    ''', COLS=_literal(sel.numericas_describe))


GRADE_NUMERICAS = '''
n_colunas = min(3, len(COLS_NUM_GRAFICO))
n_linhas = int(np.ceil(len(COLS_NUM_GRAFICO) / n_colunas))
fig, axes = plt.subplots(n_linhas, n_colunas, figsize=(4.4 * n_colunas, 3.2 * n_linhas),
                         squeeze=False)
for ax in axes.ravel()[len(COLS_NUM_GRAFICO):]:
    ax.set_visible(False)
'''


def _celula_histogramas(sel: Selecao) -> str:
    return _codigo('''
        COLS_NUM_GRAFICO = <<COLS>>
        <<GRADE>>
        for ax, coluna in zip(axes.ravel(), COLS_NUM_GRAFICO):
            valores = df[coluna].dropna()
            # Curva de densidade só entre 50 e 50.000 valores (com poucos engana; com muitos é lenta).
            sns.histplot(valores, kde=50 <= len(valores) <= 50_000, ax=ax, color="#4C72B0")
            ax.axvline(valores.median(), color="#C44E52", linestyle="--", linewidth=1)
            finalizar(ax, coluna, "", "Frequência")
        exibir()
    ''', COLS=_literal(sel.numericas), GRADE=GRADE_NUMERICAS.strip())


def _celula_outliers() -> str:
    return _codigo('''
        <<GRADE>>
        for ax, coluna in zip(axes.ravel(), COLS_NUM_GRAFICO):
            sns.boxplot(x=df[coluna].dropna(), ax=ax, color="#55A868", fliersize=3)
            finalizar(ax, coluna)
        exibir()

        display(tabela_outliers(df, COLS_NUM_GRAFICO).round(2))
    ''', GRADE=GRADE_NUMERICAS.strip())


def _celula_frequencias(sel: Selecao) -> str:
    return _codigo('''
        COLS_FREQ = <<COLS>>
        for coluna in COLS_FREQ:
            contagem = df[coluna].value_counts(dropna=False)
            tabela = contagem.head(15).to_frame("registros")
            if len(contagem) > 15:
                tabela.loc["(outras)"] = contagem.iloc[15:].sum()
            tabela["%"] = (100 * tabela["registros"] / len(df)).round(1)
            print(f"{coluna}: {df[coluna].nunique()} valores distintos")
            display(tabela)
    ''', COLS=_literal(sel.categorias))


def _celula_barras(sel: Selecao) -> str:
    return _codigo('''
        COLS_CAT_GRAFICO = <<COLS>>
        for coluna in COLS_CAT_GRAFICO:
            contagem = df[coluna].value_counts().head(15).sort_values()
            total = df[coluna].notna().sum()
            fig, ax = plt.subplots(figsize=(8, 0.35 * len(contagem) + 1.2))
            ax.barh(contagem.index.astype(str), contagem.values, color="#4C72B0")
            for y, valor in enumerate(contagem.values):
                ax.text(valor, y, f" {formatar_numero(100 * valor / total, 1)}%", va="center", fontsize=9)
            finalizar(ax, f"{coluna}: categorias mais frequentes", "Registros")
            exibir()
    ''', COLS=_literal(sel.categorias_barra))


def _celula_texto(sel: Selecao) -> str:
    return _codigo('''
        COLS_TEXTO = <<COLS>>
        for coluna in COLS_TEXTO:
            textos = df[coluna].dropna().astype(str)
            print(f"{coluna}: {textos.nunique()} valores distintos, "
                  f"{textos.str.len().median():.0f} caracteres na mediana")
            for exemplo in textos.drop_duplicates().head(5):
                print("  -", exemplo[:120])
            print()
    ''', COLS=_literal(sel.texto))


def _celula_correlacao(sel: Selecao) -> str:
    return _codigo('''
        COLS_CORR = <<COLS>>
        # Pares com menos de 10 linhas preenchidas em comum ficam em branco.
        pearson = df[COLS_CORR].corr(method="pearson", min_periods=10)
        spearman = df[COLS_CORR].corr(method="spearman", min_periods=10)

        fig, ax = plt.subplots(figsize=(0.8 * len(COLS_CORR) + 3, 0.7 * len(COLS_CORR) + 2))
        sns.heatmap(pearson, annot=len(COLS_CORR) <= 12, fmt=".2f", cmap="vlag", vmin=-1, vmax=1,
                    square=True, linewidths=0.5, ax=ax)
        finalizar(ax, "Correlação de Pearson")
        exibir()

        pares = []
        for i, a in enumerate(COLS_CORR):
            for b in COLS_CORR[i + 1:]:
                r, rho = pearson.loc[a, b], spearman.loc[a, b]
                pares.append({"variável_a": a, "variável_b": b, "r": r, "rho": rho,
                              "n": len(df[[a, b]].dropna()),
                              "força": classificar_correlacao(rho if abs(rho) > abs(r) else r)})
        tabela_corr = pd.DataFrame(pares)
        ordem = tabela_corr[["r", "rho"]].abs().max(axis=1).sort_values(ascending=False).index
        tabela_corr.loc[ordem].head(15).round(3)
    ''', COLS=_literal(sel.numericas_correlacao))


def _celula_agregacoes(sel: Selecao) -> str:
    return _codigo('''
        PARES = <<PARES>>
        for categoria, numerica in PARES:
            tabela = (
                df.groupby(categoria)[numerica]
                .agg(n="count", média="mean", mediana="median", desvio_padrão="std",
                     mínimo="min", máximo="max")
                .sort_values("mediana", ascending=False)
            )
            eta2 = eta_quadrado(df, categoria, numerica)
            print(f"{numerica} por {categoria}: eta² = {formatar_numero(eta2) if eta2 is not None else '—'}")
            display(tabela.round(2))
    ''', PARES=_literal(sel.combos_num_cat))


def _celula_comparacao() -> str:
    return _codigo('''
        for categoria, numerica in PARES:
            base = df[[categoria, numerica]].dropna()
            ordem = base.groupby(categoria)[numerica].median().sort_values(ascending=False).index[:8]
            base = base[base[categoria].isin(ordem)]
            # Os pontos individuais usam no máximo 2.000 linhas (amostra fixa), por legibilidade.
            pontos = base if len(base) <= 2000 else base.sample(2000, random_state=0)
            nota = "" if len(pontos) == len(base) else f" (pontos: amostra de 2.000 de {len(base)})"

            fig, ax = plt.subplots(figsize=(9, 4.2))
            sns.boxplot(data=base, x=categoria, y=numerica, order=ordem, ax=ax,
                        color="#A1C9F4", fliersize=0)
            sns.stripplot(data=pontos, x=categoria, y=numerica, order=ordem, ax=ax,
                          color="#2F2F2F", alpha=0.35, size=2.5)
            finalizar(ax, f"{numerica} por {categoria}{nota}", categoria, numerica)
            ax.tick_params(axis="x", labelrotation=30)
            exibir()
    ''')


def _celula_cruzamento(sel: Selecao) -> str:
    a, b = sel.combos_cat_cat[0]
    return _codigo('''
        A, B = <<A>>, <<B>>
        print(f"V de Cramér entre {A} e {B}: {formatar_numero(v_de_cramer(df, A, B))}")
        display(pd.crosstab(df[A], df[B], margins=True, margins_name="(total)"))

        proporcao = pd.crosstab(df[A], df[B], normalize="index").mul(100)
        fig, ax = plt.subplots(figsize=(1.1 * proporcao.shape[1] + 4, 0.5 * proporcao.shape[0] + 1.8))
        sns.heatmap(proporcao, annot=True, fmt=".0f", cmap="Blues", linewidths=0.5, cbar=False, ax=ax)
        finalizar(ax, f"Composição de {B} em cada {A} (% da linha)", B, A)
        exibir()
    ''', A=repr(a), B=repr(b))


def _celula_serie_temporal(sel: Selecao) -> str:
    return _codigo('''
        # Periodicidade por coluna de data: D = dia, W = semana, MS = mês, QS = trimestre, YS = ano.
        REGRAS = <<REGRAS>>
        COLS_SERIE = <<SERIE>>
        FORMATO_PERIODO = {"D": "%d/%m/%Y", "W": "%d/%m/%Y", "MS": "%m/%Y", "QS": "%m/%Y", "YS": "%Y"}

        for coluna_data, regra in REGRAS.items():
            base = df.dropna(subset=[coluna_data]).set_index(coluna_data).sort_index()
            contagem = base.resample(regra).size()
            medias = base[COLS_SERIE].resample(regra).mean()

            paineis = len(COLS_SERIE) + 1
            fig, axes = plt.subplots(paineis, 1, figsize=(11, 2.4 * paineis + 0.6), sharex=True,
                                     squeeze=False)
            axes = axes.ravel()
            for ax, coluna in zip(axes, COLS_SERIE):
                # Períodos sem registros ficam como lacunas na linha.
                ax.plot(medias.index, medias[coluna], marker="o", markersize=3, linewidth=1.5)
                finalizar(ax, f"Média de {coluna} por período", "", coluna)
            largura = 0.8 * (contagem.index.to_series().diff().dt.days.median() if len(contagem) > 1 else 1)
            axes[-1].bar(contagem.index, contagem.values, width=largura, color="#A9A9A9")
            finalizar(axes[-1], f"Registros por período ({coluna_data})", "", "Registros")
            formatar_eixo_datas(axes[-1])
            exibir()

            tabela = medias.round(2)
            tabela.insert(0, "registros", contagem, allow_duplicates=True)
            tabela.index = tabela.index.strftime(FORMATO_PERIODO[regra])
            tabela.index.name = "período"
            if len(tabela) > 36:
                print(f"Últimos 36 de {len(tabela)} períodos:")
            display(tabela.tail(36))
    ''', REGRAS=_literal(sel.regras), SERIE=_literal(sel.serie_temporal))


def _celulas_alvo_numerico(sel: Selecao) -> list[str]:
    celulas = [_codigo('''
        valores = df[ALVO].dropna()
        display(valores.describe().to_frame().T.round(2))

        fig, ax = plt.subplots(figsize=(8, 3.6))
        sns.histplot(valores, kde=50 <= len(valores) <= 50_000, ax=ax, color="#DD8452")
        ax.axvline(valores.median(), color="#C44E52", linestyle="--", linewidth=1)
        finalizar(ax, f"Distribuição de {ALVO} (tracejado: mediana)", ALVO, "Frequência")
        exibir()
    ''')]
    if sel.alvo_numericas:
        celulas.append(_codigo('''
            COLS_CORR_ALVO = <<COLS>>
            base = df[[ALVO] + COLS_CORR_ALVO]
            correlacoes = pd.DataFrame({
                "r": base.corr(method="pearson", min_periods=10)[ALVO].drop(ALVO),
                "rho": base.corr(method="spearman", min_periods=10)[ALVO].drop(ALVO),
                "n": [len(df[[ALVO, coluna]].dropna()) for coluna in COLS_CORR_ALVO],
            })
            correlacoes["força"] = [classificar_correlacao(rho if abs(rho) > abs(r) else r)
                                    for r, rho in zip(correlacoes["r"], correlacoes["rho"])]
            correlacoes.sort_values("rho", key=abs, ascending=False).round(3)
        ''', COLS=_literal(sel.alvo_numericas)))
    if sel.alvo_categorias:
        celulas.append(_codigo('''
            CATS_ALVO = <<COLS>>
            for categoria in CATS_ALVO:
                tabela = (df.groupby(categoria)[ALVO]
                            .agg(n="count", média="mean", mediana="median")
                            .sort_values("média"))
                display(tabela.iloc[::-1].round(2))
                fig, ax = plt.subplots(figsize=(8, 0.4 * len(tabela) + 1.2))
                ax.barh(tabela.index.astype(str), tabela["média"], color="#DD8452")
                ax.axvline(df[ALVO].mean(), color="#C44E52", linestyle="--", linewidth=1)
                finalizar(ax, f"Média de {ALVO} por {categoria} (tracejado: média geral)", ALVO)
                exibir()
        ''', COLS=_literal(sel.alvo_categorias)))
    return celulas


def _celulas_alvo_classes(sel: Selecao) -> list[str]:
    celulas = [_codigo('''
        # Classe cuja taxa é comparada entre os grupos (troque se quiser outra).
        CLASSE_POSITIVA = <<CLASSE>>

        classes = df[ALVO].value_counts(dropna=False).to_frame("registros")
        classes["%"] = (100 * classes["registros"] / len(df)).round(1)
        classes.index = classes.index.map(lambda valor: "(ausente)" if pd.isna(valor) else str(valor))
        display(classes)

        fig, ax = plt.subplots(figsize=(7, 0.45 * len(classes) + 1.2))
        ax.barh(classes.index, classes["registros"], color="#55A868")
        finalizar(ax, f"Distribuição de {ALVO}", "Registros")
        exibir()
    ''', CLASSE=repr(sel.classe_positiva))]
    if sel.alvo_categorias:
        celulas.append(_codigo('''
            CATS_ALVO = <<COLS>>
            taxa_geral = 100 * (df[ALVO].dropna() == CLASSE_POSITIVA).mean()
            for categoria in CATS_ALVO:
                base = df.dropna(subset=[ALVO, categoria])
                taxa = (base[ALVO] == CLASSE_POSITIVA).groupby(base[categoria]).agg(["mean", "count"])
                taxa.columns = ["taxa_%", "n"]
                taxa["taxa_%"] = (100 * taxa["taxa_%"]).round(1)
                taxa = taxa.sort_values("taxa_%")
                display(taxa.iloc[::-1])

                fig, ax = plt.subplots(figsize=(8, 0.4 * len(taxa) + 1.2))
                ax.barh(taxa.index.astype(str), taxa["taxa_%"], color="#55A868")
                ax.axvline(taxa_geral, color="#C44E52", linestyle="--", linewidth=1)
                finalizar(ax, f"% de {ALVO} = {CLASSE_POSITIVA} por {categoria} (tracejado: geral)", "%")
                exibir()
        ''', COLS=_literal(sel.alvo_categorias)))
    if sel.alvo_numericas:
        celulas.append(_codigo('''
            COLS_NUM_ALVO = <<COLS>>
            medias = df.groupby(ALVO)[COLS_NUM_ALVO].mean().round(2)
            medias.insert(0, "n", df[ALVO].value_counts(), allow_duplicates=True)
            display(medias)

            fig, axes = plt.subplots(1, len(COLS_NUM_ALVO), figsize=(4.5 * len(COLS_NUM_ALVO), 4),
                                     squeeze=False)
            for ax, coluna in zip(axes.ravel(), COLS_NUM_ALVO):
                base = df[[ALVO, coluna]].dropna()
                classes_texto = base[ALVO].astype(str)
                sns.boxplot(x=classes_texto, y=base[coluna], order=sorted(classes_texto.unique()),
                            ax=ax, color="#4C72B0", fliersize=2)
                finalizar(ax, coluna, ALVO, coluna)
            exibir()
        ''', COLS=_literal(sel.alvo_numericas)))
    return celulas


# --------------------------------------------------------------------------- #
# Montagem
# --------------------------------------------------------------------------- #

def _dedentar(texto: str) -> str:
    """Tira a indentação de cada linha: o markdown gerado não usa recuo significativo."""
    return "\n".join(linha.strip() for linha in texto.strip().splitlines())


class _Montador:
    """Acumula as células e numera as seções na ordem em que aparecem."""

    def __init__(self):
        self.celulas: list[dict] = []
        self.numero = 0
        self.sub = 0

    def md(self, secao: str, texto: str) -> None:
        self.celulas.append({"tipo": "markdown", "fonte": _dedentar(texto), "secao": secao})

    def code(self, secao: str, fonte: str) -> None:
        self.celulas.append({"tipo": "code", "fonte": fonte.strip(), "secao": secao})

    def titulo(self, texto: str) -> str:
        self.numero += 1
        self.sub = 0
        return f"## {self.numero}. {texto}"

    def subtitulo(self, texto: str) -> str:
        self.sub += 1
        return f"### {self.numero}.{self.sub} {texto}"


def _descricao_leitura(parametros: dict) -> str:
    sep = parametros.get("sep", ",")
    partes = [f"separador {NOMES_SEPARADOR.get(sep, repr(sep))}", f"encoding {parametros.get('encoding')}"]
    if parametros.get("decimal") == ",":
        partes.append("decimal com vírgula e milhar com ponto")
    if parametros.get("compression"):
        partes.append(f"compressão {parametros['compression']}")
    return ", ".join(partes)


def gerar_celulas(df: pd.DataFrame, perfil: list[ColunaInfo], opcoes: Opcoes, resumo: str,
                  plano: dict, selecao: Selecao) -> list[dict]:
    """Lista de células do notebook: {"tipo", "fonte", "secao"}.

    `df` e `perfil` são os dados já limpos (os mesmos usados no resumo).
    """
    sel = selecao
    m = _Montador()
    alvo = sel.alvo or opcoes.alvo
    nome = Path(opcoes.caminho_csv).name
    identificadores = [c.nome for c in perfil if c.identificador]

    linha_alvo = f"\n- **Variável de interesse:** {md_codigo(alvo)}" if alvo else ""
    m.md("cabecalho", f"""
        # {opcoes.titulo}

        Notebook gerado pela skill **csv-eda-notebook** a partir de {md_codigo(nome)}.

        - **Leitura:** {_descricao_leitura(opcoes.leitura_parametros)}
        - **Linhas analisadas:** {len(df)} · **Colunas:** {df.shape[1]}{linha_alvo}

        As seções abaixo dependem do que existe no arquivo: só aparecem as análises que fazem
        sentido para os tipos de coluna detectados. Rode tudo em ordem (*Run All*). O CSV é lido de
        `CSV_PATH`, relativo à pasta deste notebook.
    """)

    m.md("configuracao", f"""
        {m.titulo("Configuração")}

        Bibliotecas, parâmetros de leitura e variável de interesse. Para analisar outro arquivo
        com a mesma estrutura, troque `CSV_PATH`.
    """)
    m.code("configuracao", _celula_configuracao(opcoes, alvo))
    m.md("apoio", """
        **Funções de apoio.** Cópia de `scripts/eda/apoio.py`: conversão de números e datas,
        limpeza, outliers e checagens de qualidade. São as mesmas funções que calcularam o resumo
        do fim do notebook. A célula seguinte traz três atalhos para os gráficos.
    """)
    m.code("apoio", _fonte_apoio())
    m.code("apoio", AJUDANTES_GRAFICOS)

    avisos = "".join(f"\n- {aviso}" for aviso in opcoes.avisos_leitura)
    bloco_avisos = f"\n**Avisos da leitura:**\n{avisos}" if avisos else ""
    m.md("leitura", f"""
        {m.titulo("Leitura dos dados")}

        `padronizar_colunas` tira espaços das bordas dos nomes, renomeia nomes vazios ou
        repetidos e descarta colunas `Unnamed` totalmente vazias.
        {bloco_avisos}
    """)
    m.code("leitura", _celula_leitura())

    m.md("visao_geral", f"""
        {m.titulo("Visão geral")}

        `tipo_analise` é o tipo atribuído pela skill, que decide em quais análises cada coluna
        entra; `identificador` fica fora dos gráficos.
    """)
    m.code("visao_geral", _celula_visao_geral(perfil))
    m.md("duplicadas", f"""
        {m.subtitulo("Linhas duplicadas")}

        Linhas idênticas a uma anterior, contadas nos dados como foram lidos.
    """)
    m.code("duplicadas", _celula_duplicadas())

    m.md("limpeza", f"""
        {m.titulo("Limpeza")}

        Ajustes mínimos, descritos em `PLANO_LIMPEZA`: espaços nas bordas dos textos, números
        gravados como texto (moeda, milhar), datas no formato detectado, ±inf como ausente e,
        se `REMOVER_DUPLICADAS` for `True`, linhas repetidas. A base original continua em
        `df_bruto`; o restante do notebook usa `df`.
    """)
    m.code("limpeza", _celula_limpeza(plano, identificadores[0] if identificadores else None))

    m.md("ausentes", f"""
        {m.titulo("Qualidade dos dados")}

        {m.subtitulo("Valores ausentes")}

        Contados depois da limpeza: textos vazios e valores que não converteram também contam.
    """)
    m.code("ausentes", _celula_ausentes())
    if df.isna().any().any():
        m.code("grafico_ausentes", _celula_grafico_ausentes())
    numericas = [c.nome for c in perfil if c.tipo == NUMERICA and not c.identificador]
    categoricas = [c.nome for c in perfil if c.tipo == CATEGORICA and not c.identificador]
    problemas = checar_qualidade(df, numericas, categoricas)
    parecidas = problemas.loc[problemas["problema"] == "categorias_parecidas", "coluna"].tolist()
    m.md("qualidade", f"""
        {m.subtitulo("Checagens automáticas")}

        Colunas constantes, com muitos ausentes, categorias que só diferem em caixa, acento ou
        espaços, poucos valores negativos (erro de digitação?), excesso de categorias,
        identificador repetido e valores infinitos. Nada é corrigido automaticamente aqui.
    """)
    m.code("qualidade", _celula_qualidade(numericas, categoricas, parecidas))

    if sel.numericas_describe:
        m.md("estatisticas_numericas", f"""
            {m.titulo("Variáveis numéricas")}

            {m.subtitulo("Estatísticas descritivas")}

            `assimetria` acima de 1 (ou abaixo de −1) indica cauda longa à direita (à esquerda);
            `curtose` alta indica valores extremos frequentes.
        """)
        m.code("estatisticas_numericas", _celula_describe(sel))
    if sel.numericas:
        m.md("distribuicoes", f"""
            {m.subtitulo("Distribuições")}

            Histogramas; a linha tracejada marca a mediana. Colunas binárias (0/1) e constantes
            ficam de fora.
        """)
        m.code("distribuicoes", _celula_histogramas(sel))
        m.md("outliers", f"""
            {m.subtitulo("Outliers")}

            Regra de Tukey: valores abaixo de Q1 − 1,5·IQR ou acima de Q3 + 1,5·IQR. Outlier não
            é sinônimo de erro: confira os casos antes de remover qualquer coisa.
        """)
        m.code("outliers", _celula_outliers())

    if sel.categorias:
        m.md("frequencias", f"""
            {m.titulo("Variáveis categóricas")}

            {m.subtitulo("Frequências")}

            As 15 categorias mais comuns de cada coluna; o restante é somado em "(outras)".
        """)
        m.code("frequencias", _celula_frequencias(sel))
        if sel.categorias_barra:
            m.md("barras_categoricas", m.subtitulo("Gráficos de frequência"))
            m.code("barras_categoricas", _celula_barras(sel))

    if sel.texto:
        m.md("texto_livre", f"""
            {m.titulo("Texto livre")}

            Colunas com muitos valores distintos (descrições, comentários): sem gráfico de
            frequência, só exemplos e o tamanho típico dos textos.
        """)
        m.code("texto_livre", _celula_texto(sel))

    if len(sel.numericas_correlacao) >= 2:
        binarias = [c for c in sel.numericas_correlacao if c in sel.binarias]
        nota = (f"\n\nColunas binárias ({', '.join(md_codigo(c) for c in binarias)}) entram como "
                "correlação ponto-bisserial (o `r` de Pearson com uma variável 0/1).") if binarias else ""
        m.md("correlacao", f"""
            {m.titulo("Correlação entre numéricas")}

            Pearson (`r`) mede relação linear; Spearman (`rho`) mede relação monotônica e é menos
            sensível a outliers. Força pelo maior dos dois, em módulo: abaixo de 0,1 desprezível,
            0,1 fraca, 0,3 moderada, 0,5 forte, 0,7 ou mais muito forte. Correlação não indica
            causa.{nota}
        """)
        m.code("correlacao", _celula_correlacao(sel))

    if sel.combos_num_cat:
        m.md("agregacoes", f"""
            {m.titulo("Numéricas por categoria")}

            Pares escolhidos pela maior diferença entre grupos, medida pelo eta²: a fração da
            variância da numérica explicada pela categoria (0 a 1; só grupos com {MIN_GRUPO} ou mais
            registros). Como referência, 0,01 é pequeno, 0,06 médio e 0,14 grande.
        """)
        m.code("agregacoes", _celula_agregacoes(sel))
        m.code("comparacao_grupos", _celula_comparacao())

    if sel.combos_cat_cat:
        a, b = sel.combos_cat_cat[0]
        m.md("cruzamento_categoricas", f"""
            {m.titulo("Relação entre categóricas")}

            Par de categóricas mais associado pelo V de Cramér (0 = independentes, 1 = associação
            total): contagens e composição de {md_codigo(b)} dentro de cada valor de {md_codigo(a)}.
        """)
        m.code("cruzamento_categoricas", _celula_cruzamento(sel))

    if sel.datas:
        periodos = ", ".join(f"{md_codigo(c)} por {NOME_PERIODO[r]}" for c, r in sel.regras.items())
        m.md("serie_temporal", f"""
            {m.titulo("Evolução temporal")}

            Registros e média das numéricas por período ({periodos}). A periodicidade fica em
            `REGRAS` e pode ser trocada. Períodos sem registros aparecem como lacunas.
        """)
        m.code("serie_temporal", _celula_serie_temporal(sel))

    if alvo:
        if sel.alvo_classes:
            explicacao = ("Distribuição das classes, taxa da classe `CLASSE_POSITIVA` por grupo e "
                          "numéricas comparadas entre as classes.")
            fontes = _celulas_alvo_classes(sel)
        else:
            explicacao = ("Distribuição, correlação com as demais numéricas e média por categoria "
                          "(categorias que mais diferenciam o alvo).")
            fontes = _celulas_alvo_numerico(sel)
        m.md("alvo", f"""
            {m.titulo("Variável de interesse: " + md_codigo(alvo))}

            {explicacao} Associação não é causa.
        """)
        for fonte in fontes:
            m.code("alvo", fonte)

    m.md("resumo", f"""
        {m.titulo("Resumo")}

        Calculado na geração do notebook, com as mesmas funções de limpeza. Se você mudar o
        notebook, este texto não se atualiza sozinho.
    """)
    m.md("resumo", resumo)
    return m.celulas

