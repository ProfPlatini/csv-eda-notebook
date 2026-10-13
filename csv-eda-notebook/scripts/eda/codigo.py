"""Geração das células de código do notebook de análise exploratória.

O notebook é montado *a partir do conteúdo real do CSV*: as células citam os
nomes das colunas que existem, mostram apenas os gráficos que fazem sentido
para os tipos detectados e nunca inventam variáveis.
"""

from __future__ import annotations

import inspect
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .loader import (
    CATEGORICA,
    DATA,
    NUMERICA,
    TEXTO,
    ColunaInfo,
    normalizar_para_numerico,
)

# --------------------------------------------------------------------------- #
# Configuração da geração
# --------------------------------------------------------------------------- #

MAX_NUMERICAS_GRAFICO = 6
MAX_CATEGORICAS_GRAFICO = 4
MAX_CATEGORICAS_AGRUPAR = 3
MAX_DATAS = 2
MAX_COMBINACOES = 3
MAX_COLUNAS_DESCRIBE = 25
LIMITE_CATEGORIAS_GRAFICO = 20
LIMITE_CATEGORIAS_AGRUPAR = 8
TOP_N_CATEGORIAS = 15


@dataclass
class Opcoes:
    """Parâmetros que controlam o notebook gerado."""

    caminho_csv: Path
    saida: Path
    titulo: str = "Análise exploratória de dados"
    separador: str = ","
    encoding: str = "utf-8"
    alvo: str | None = None
    max_numericas_grafico: int = MAX_NUMERICAS_GRAFICO
    max_categoricas_grafico: int = MAX_CATEGORICAS_GRAFICO


@dataclass
class Selecao:
    """Colunas escolhidas para cada tipo de análise."""

    numericas: list[str] = field(default_factory=list)
    numericas_describe: list[str] = field(default_factory=list)
    numericas_correlacao: list[str] = field(default_factory=list)
    categorias: list[str] = field(default_factory=list)
    categorias_barra: list[str] = field(default_factory=list)
    categorias_agrupar: list[str] = field(default_factory=list)
    texto: list[str] = field(default_factory=list)
    datas: list[str] = field(default_factory=list)
    combos_num_cat: list[tuple[str, str]] = field(default_factory=list)
    combos_cat_cat: list[tuple[str, str]] = field(default_factory=list)
    serie_temporal: list[str] = field(default_factory=list)
    para_numerico: list[str] = field(default_factory=list)


def _utilizaveis(perfil: list[ColunaInfo], tipo: str) -> list[ColunaInfo]:
    return [
        c for c in perfil
        if c.tipo == tipo and c.nao_nulos > 0 and not c.identificador and c.n_unicos > 0
    ]


def selecionar_colunas(df: pd.DataFrame, perfil: list[ColunaInfo],
                       opcoes: Opcoes) -> Selecao:
    """Decide quais colunas entram em cada bloco de análise."""
    sel = Selecao()

    numericas = _utilizaveis(perfil, NUMERICA)
    # Variáveis contínuas primeiro: são as que mais rendem em histograma.
    ordenadas = sorted(numericas, key=lambda c: (c.n_unicos <= 20, -c.nao_nulos))
    sel.numericas = [c.nome for c in ordenadas[: opcoes.max_numericas_grafico]]
    sel.numericas_describe = [c.nome for c in numericas[:MAX_COLUNAS_DESCRIBE]]
    sel.numericas_correlacao = sel.numericas[:15]
    sel.para_numerico = [
        c.nome for c in numericas
        if not pd.api.types.is_numeric_dtype(df[c.nome])
    ]

    categorias = _utilizaveis(perfil, CATEGORICA)
    sel.categorias = [c.nome for c in categorias]
    com_poucas = [c for c in categorias if 2 <= c.n_unicos <= LIMITE_CATEGORIAS_GRAFICO]
    sel.categorias_barra = [
        c.nome for c in sorted(com_poucas, key=lambda c: (c.n_unicos > 8, -c.nao_nulos))
    ][: opcoes.max_categoricas_grafico]
    candidatos_agrupar = [
        c for c in categorias if 2 <= c.n_unicos <= LIMITE_CATEGORIAS_AGRUPAR
    ]
    candidatos_agrupar.sort(
        key=lambda c: (c.n_unicos > LIMITE_CATEGORIAS_AGRUPAR, -c.nao_nulos))
    sel.categorias_agrupar = [c.nome for c in candidatos_agrupar][:MAX_CATEGORICAS_AGRUPAR]

    sel.texto = [c.nome for c in _utilizaveis(perfil, TEXTO)][:4]

    # Só entram colunas de data que realmente convertem para datas válidas.
    datas = []
    for coluna in _utilizaveis(perfil, DATA):
        convertida = pd.to_datetime(df[coluna.nome], errors="coerce", format="mixed",
                                    dayfirst=True)
        validos = int(convertida.notna().sum())
        if validos >= max(10, 0.5 * coluna.nao_nulos) and convertida.nunique() >= 5:
            datas.append(coluna.nome)
        if len(datas) >= MAX_DATAS:
            break
    sel.datas = datas

    for categoria in sel.categorias_agrupar:
        for numerica in sel.numericas:
            if len(sel.combos_num_cat) >= MAX_COMBINACOES:
                break
            sel.combos_num_cat.append((categoria, numerica))
    sel.combos_num_cat = sel.combos_num_cat[:MAX_COMBINACOES]

    for i, a in enumerate(sel.categorias_agrupar):
        for b in sel.categorias_agrupar[i + 1:]:
            sel.combos_cat_cat.append((a, b))
    sel.combos_cat_cat = sel.combos_cat_cat[:1]

    sel.serie_temporal = sel.numericas[:3]
    return sel


def _regra_resample(df: pd.DataFrame, colunas_data: list[str]) -> str:
    """Escolhe a periodicidade da série temporal olhando o período coberto."""
    series = [pd.to_datetime(df[c], errors="coerce").dropna() for c in colunas_data]
    validas = [s for s in series if not s.empty]
    if not validas:
        return "MS"
    dias = (max(s.max() for s in validas) - min(s.min() for s in validas)).days
    if dias <= 45:
        return "D"
    if dias <= 200:
        return "W"
    if dias <= 1200:
        return "MS"
    if dias <= 4000:
        return "QS"
    return "YS"


# --------------------------------------------------------------------------- #
# Blocos de código reutilizados por várias células
# --------------------------------------------------------------------------- #

BLOCO_HELPERS = '''
{source_normalizar}

# Atalho com o nome curto usado no restante do notebook.
para_numerico = normalizar_para_numerico


def finalizar(ax, titulo="", xlabel="", ylabel=""):
    """Padroniza título, rótulos e bordas de um eixo."""
    if titulo:
        ax.set_title(titulo, fontsize=12, fontweight="bold", pad=10, loc="left")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    return ax


def exibir():
    """Encaixa os elementos e mostra a figura."""
    plt.tight_layout()
    plt.show()


def formatar_valor(valor):
    """Número no padrão brasileiro (milhar com ponto, decimal com vírgula)."""
    return format(valor, ",.2f").replace(",", "@").replace(".", ",").replace("@", ".")
'''.lstrip()


def _helpers() -> str:
    fonte = textwrap.dedent(inspect.getsource(normalizar_para_numerico)).rstrip()
    return BLOCO_HELPERS.replace("{source_normalizar}", fonte)


def _celula_setup(opcoes: Opcoes) -> str:
    return textwrap.dedent(f'''
        import warnings
        warnings.filterwarnings("ignore")

        from pathlib import Path

        import numpy as np
        import pandas as pd
        import matplotlib.pyplot as plt
        import seaborn as sns

        sns.set_theme(style="whitegrid", context="notebook")
        plt.rcParams["figure.dpi"] = 110
        plt.rcParams["axes.titlesize"] = 12

        pd.set_option("display.max_columns", 100)
        pd.set_option("display.width", 160)
        pd.set_option("display.max_colwidth", 80)

        CSV_PATH = Path({str(opcoes.caminho_csv)!r})
        SEPARADOR = {opcoes.separador!r}
        ENCODING = {opcoes.encoding!r}

        ALVO = {opcoes.alvo!r}
    ''').strip()


def _celula_leitura() -> str:
    return textwrap.dedent('''
        df_bruto = pd.read_csv(CSV_PATH, sep=SEPARADOR, encoding=ENCODING, low_memory=False)
        df_bruto.columns = [str(coluna).strip() for coluna in df_bruto.columns]
        df_bruto = df_bruto.loc[:, [c for c in df_bruto.columns if c]]

        df = df_bruto.copy()
        print("Dimensoes:", df.shape)
        df.head(8)
    ''').strip()


def _celula_tipos() -> str:
    return textwrap.dedent('''
        tipos = df.dtypes.astype(str).to_frame("tipo").T
        print("Tipos por coluna:")
        tipos
    ''').strip()


def _celula_valores_unicos() -> str:
    return textwrap.dedent('''
        unicos = (
            df.nunique(dropna=True)
            .to_frame("valores_unicos")
            .assign(tipo=lambda t: df.dtypes.astype(str))
        )
        print("Quantidade de valores distintos por coluna:")
        unicos.sort_values("valores_unicos")
    ''').strip()


BLOCO_AUSENTES = textwrap.dedent('''
    ausentes = pd.DataFrame(
        {
            "nulos": df_bruto.isna().sum(),
            "percentual": df_bruto.isna().mean().mul(100).round(2),
        }
    ).sort_values("percentual", ascending=False)
    print("Colunas com mais valores ausentes:")
    ausentes[ausentes["nulos"] > 0]
''').strip()


BLOCO_DUPLICADAS = textwrap.dedent('''
    duplicadas = int(df_bruto.duplicated().sum())
    print("Linhas duplicadas (exatas):", duplicadas)

    if duplicadas:
        exemplo = (
            df_bruto[df_bruto.duplicated(keep=False)]
            .sort_values(by=list(df_bruto.columns))
            .head(10)
        )
        exemplo
    else:
        print("Nenhuma linha totalmente duplicada.")
''').strip()


def _celula_limpeza(sel: Selecao) -> str:
    """Normaliza textos, datas, números e remove duplicadas."""
    linhas = ["df_bruto = df.copy()", ""]
    passos = [
        ("Espacos nas bordas e strings vazias viram valores ausentes",
         ['for coluna in df.select_dtypes(include=["object", "string"]).columns:',
          '    df[coluna] = df[coluna].astype("string").str.strip().replace("", pd.NA)']),
    ]
    if sel.para_numerico:
        lista = ", ".join(repr(c) for c in sel.para_numerico)
        passos.append((
            "Numeros que chegaram como texto (moeda, separador de milhar)",
            [f"CONVERTIDAS = [{lista}]",
             "for coluna in CONVERTIDAS:",
             "    antes = df[coluna].notna().sum()",
             "    df[coluna] = para_numerico(df[coluna])",
             "    depois = df[coluna].notna().sum()",
             '    print("  " + coluna + ": " + str(antes) + " -> " + str(depois) +'
             ' " valores numericos (nao convertidos viraram ausentes)")'],
        ))
    if sel.datas:
        lista = ", ".join(repr(c) for c in sel.datas)
        passos.append((
            "Datas convertidas (dayfirst=True por padrao brasileiro)",
            [f"for coluna in [{lista}]:",
             '    df[coluna] = pd.to_datetime(df[coluna], errors="coerce", dayfirst=True)'],
        ))
    passos.append((
        "Remocao de linhas totalmente duplicadas",
        ["duplicadas_removidas = int(df.duplicated().sum())",
         "df = df.drop_duplicates().reset_index(drop=True)"],
    ))

    for numero, (descricao, corpo) in enumerate(passos, start=1):
        linhas.append(f"# {numero}. {descricao}")
        linhas.extend(corpo)
        linhas.append("")

    linhas += [
        'print("Linhas antes:", len(df_bruto), "| depois:", len(df),'
        ' "| duplicadas removidas:", duplicadas_removidas)',
        "",
        "df.dtypes.to_frame('tipo').T",
    ]
    return "\n".join(linhas)


def _celula_describe_numericas(sel: Selecao) -> str:
    lista = ", ".join(repr(c) for c in sel.numericas_describe)
    return textwrap.dedent(f'''
        COLS_NUM = [{lista}]

        if COLS_NUM:
            estatisticas = df[COLS_NUM].describe().T
            estatisticas["distorcao"] = df[COLS_NUM].skew()
            estatisticas["cauda"] = df[COLS_NUM].kurtosis()
            estatisticas["faltantes"] = df[COLS_NUM].isna().sum()
            print("Estatisticas descritivas:")
            estatisticas.round(3)
        else:
            print("Nenhuma variavel numerica para descrever.")
    ''').strip()


def _celula_frequencias(sel: Selecao) -> str:
    lista = ", ".join(repr(c) for c in sel.categorias)
    return textwrap.dedent(f'''
        COLS_CAT = [{lista}]

        for coluna in COLS_CAT:
            print("\\n== " + coluna + " ==", "| valores distintos:", df[coluna].nunique())
            print(df[coluna].value_counts(dropna=False).head({TOP_N_CATEGORIAS}).to_string())
    ''').strip()


def _celula_exemplos_texto(sel: Selecao) -> str:
    lista = ", ".join(repr(c) for c in sel.texto)
    return textwrap.dedent(f'''
        COLS_TEXTO = [{lista}]

        print("Texto livre: alguns exemplos de cada coluna (sem grafico de frequencia,")
        print("porque o numero de valores distintos e alto demais)")
        for coluna in COLS_TEXTO:
            exemplos = df[coluna].dropna().astype(str).unique()[:5]
            print("\\n== " + coluna + " ==")
            for exemplo in exemplos:
                print(" -", exemplo[:140])
    ''').strip()


def _celula_agregacoes(sel: Selecao) -> str:
    pares = ", ".join(f"({cat!r}, {num!r})" for cat, num in sel.combos_num_cat)
    linhas = [f"PARES = [{pares}]", ""]
    linhas += [
        "for categoria, numerica in PARES:",
        '    print("\\n== " + numerica + " por " + categoria + " ==")',
        "    tabela = (",
        "        df.groupby(categoria, dropna=False)[numerica]",
        '        .agg(["count", "mean", "median", "std", "min", "max"])',
        "        .round(2)",
        '        .sort_values("mean", ascending=False)',
        "    )",
        "    print(tabela.head(15).to_string())",
    ]
    if sel.combos_cat_cat:
        a, b = sel.combos_cat_cat[0]
        linhas += [
            "",
            f'print("\\n== contagem cruzada {a} x {b} ==")',
            f"pd.crosstab(df[{a!r}], df[{b!r}]).to_string()",
        ]
    return "\n".join(linhas)


def _celula_grafico_ausentes() -> str:
    return textwrap.dedent('''
        ausentes_pct = df_bruto.isna().mean().mul(100).sort_values(ascending=False)
        ausentes_pct = ausentes_pct[ausentes_pct > 0]

        if len(ausentes_pct):
            fig, ax = plt.subplots(figsize=(9, max(2.5, 0.45 * len(ausentes_pct))))
            sns.barplot(x=ausentes_pct.values, y=ausentes_pct.index, ax=ax, color="#C44E52")
            for i, valor in enumerate(ausentes_pct.values):
                ax.text(valor, i, "  " + format(valor, ".1f") + "%", va="center", fontsize=9)
            finalizar(ax, "Percentual de valores ausentes por coluna",
                      "% de celulas ausentes", "Coluna")
            exibir()
        else:
            print("Nenhum valor ausente no arquivo.")
    ''').strip()


def _celula_histogramas(sel: Selecao) -> str:
    lista = ", ".join(repr(c) for c in sel.numericas)
    return textwrap.dedent(f'''
        COLS_NUM_GRAFICO = [{lista}]

        if COLS_NUM_GRAFICO:
            n = len(COLS_NUM_GRAFICO)
            colunas = min(3, n)
            linhas = int(np.ceil(n / colunas))
            fig, axes = plt.subplots(linhas, colunas, figsize=(4.4 * colunas, 3.2 * linhas),
                                     squeeze=False)
            for ax, coluna in zip(axes.ravel(), COLS_NUM_GRAFICO):
                serie = df[coluna].dropna()
                if serie.empty:
                    ax.text(0.5, 0.5, "sem valores validos", ha="center", va="center")
                    finalizar(ax, coluna, coluna, "")
                    continue
                sns.histplot(serie, kde=len(serie) >= 50, ax=ax, color="#4C72B0")
                finalizar(ax, coluna, coluna, "Frequencia")
            for ax in axes.ravel()[n:]:
                ax.set_visible(False)
            plt.tight_layout()
            plt.show()
        else:
            print("Sem variaveis numericas para histogramas.")
    ''').strip()


def _celula_boxplots_numericas(sel: Selecao) -> str:
    lista = ", ".join(repr(c) for c in sel.numericas)
    return textwrap.dedent(f'''
        COLS_NUM_GRAFICO = [{lista}]

        if COLS_NUM_GRAFICO:
            n = len(COLS_NUM_GRAFICO)
            colunas = min(3, n)
            linhas = int(np.ceil(n / colunas))
            fig, axes = plt.subplots(linhas, colunas, figsize=(4.4 * colunas, 3.2 * linhas),
                                     squeeze=False)
            for ax, coluna in zip(axes.ravel(), COLS_NUM_GRAFICO):
                base = df.dropna(subset=[coluna])
                if base.empty:
                    ax.text(0.5, 0.5, "sem valores validos", ha="center", va="center")
                    finalizar(ax, coluna, coluna, "")
                    continue
                sns.boxplot(data=base, x=coluna, ax=ax, color="#55A868", fliersize=3)
                finalizar(ax, coluna, coluna, "Valor")
            for ax in axes.ravel()[n:]:
                ax.set_visible(False)
            plt.tight_layout()
            plt.show()
        else:
            print("Sem variaveis numericas para boxplots.")
    ''').strip()


def _celula_barras_categoricas(sel: Selecao) -> str:
    lista = ", ".join(repr(c) for c in sel.categorias_barra)
    return textwrap.dedent(f'''
        COLS_CAT_GRAFICO = [{lista}]

        if COLS_CAT_GRAFICO:
            fig, axes = plt.subplots(len(COLS_CAT_GRAFICO), 1,
                                     figsize=(9, 3.3 * len(COLS_CAT_GRAFICO)), squeeze=False)
            for ax, coluna in zip(axes.ravel(), COLS_CAT_GRAFICO):
                ordem = df[coluna].value_counts().head({TOP_N_CATEGORIAS}).index
                sns.countplot(data=df, y=coluna, order=ordem, ax=ax, color="#4C72B0")
                total = int(df[coluna].notna().sum())
                for posicao, categoria in enumerate(ordem):
                    quantidade = int((df[coluna] == categoria).sum())
                    pct = 100 * quantidade / total if total else 0
                    ax.text(quantidade, posicao, "  " + format(pct, ".1f") + "%",
                            va="center", fontsize=9)
                finalizar(ax, coluna + " - categorias mais frequentes", "Registros", coluna)
            exibir()
        else:
            print("Sem variaveis categoricas adequadas para grafico de frequencia.")
    ''').strip()


def _celula_correlacao(sel: Selecao) -> str:
    lista = ", ".join(repr(c) for c in sel.numericas_correlacao)
    return textwrap.dedent(f'''
        COLS_CORR = [{lista}]

        if len(COLS_CORR) >= 2:
            matriz = df[COLS_CORR].corr(numeric_only=True)
            fig, ax = plt.subplots(figsize=(1.15 * len(COLS_CORR) + 3,
                                            0.95 * len(COLS_CORR) + 2.5))
            sns.heatmap(matriz, annot=True, fmt=".2f", cmap="vlag", center=0,
                        square=True, linewidths=0.5, ax=ax)
            finalizar(ax, "Correlacao de Pearson entre variaveis numericas")
            plt.tight_layout()
            plt.show()

            pares = []
            for i, a in enumerate(COLS_CORR):
                for b in COLS_CORR[i + 1:]:
                    pares.append((abs(matriz.loc[a, b]), a, b, matriz.loc[a, b]))
            tabela = (pd.DataFrame(pares, columns=["abs", "variavel_a", "variavel_b", "r"])
                        .sort_values("abs", ascending=False)
                        .drop(columns="abs"))
            print("Pares de variaveis ordenados por correlacao:")
            tabela.round(3).head(15)
        else:
            print("E necessario ao menos 2 variaveis numericas para calcular correlacoes.")
    ''').strip()


def _celula_boxplot_agrupado(sel: Selecao) -> str:
    pares = ", ".join(f"({cat!r}, {num!r})" for cat, num in sel.combos_num_cat)
    return textwrap.dedent(f'''
        PARES = [{pares}]

        for categoria, numerica in PARES:
            base = df.dropna(subset=[categoria, numerica])
            if base.empty:
                continue
            top = base[categoria].value_counts().head(8).index
            fig, ax = plt.subplots(figsize=(9, 4.2))
            sns.boxplot(data=base, x=categoria, y=numerica, order=top, ax=ax,
                        color="#4C72B0", fliersize=3)
            sns.stripplot(data=base, x=categoria, y=numerica, order=top, ax=ax,
                          color="#2F2F2F", alpha=0.35, size=2.5)
            finalizar(ax, numerica + " por " + categoria, categoria, numerica)
            plt.xticks(rotation=30, ha="right")
            exibir()
    ''').strip()


def _celula_cruzamento_categorias(sel: Selecao) -> str:
    if not sel.combos_cat_cat:
        return ""
    a, b = sel.combos_cat_cat[0]
    return textwrap.dedent(f'''
        tabela = pd.crosstab(df[{a!r}], df[{b!r}], normalize="index").round(3)
        print("Proporcao de " + {b!r} + " dentro de cada valor de " + {a!r} + ":")
        fig, ax = plt.subplots(figsize=(8 + 1.2 * tabela.shape[1],
                                        2 + 0.6 * tabela.shape[0]))
        sns.heatmap(tabela, annot=True, cmap="Blues", linewidths=0.5, ax=ax, cbar=False)
        finalizar(ax, "Composicao relativa entre as duas variaveis")
        plt.tight_layout()
        plt.show()
    ''').strip()


def _celula_serie_temporal(df: pd.DataFrame, sel: Selecao) -> str:
    regra = _regra_resample(df, sel.datas)
    datas = ", ".join(repr(c) for c in sel.datas)
    series = ", ".join(repr(c) for c in sel.serie_temporal)
    cabecalho = textwrap.dedent(f'''
        COLS_DATA = [{datas}]
        COLS_SERIE = [{series}]
        REGRA = {regra!r}
    ''').strip()

    if sel.serie_temporal:
        corpo = textwrap.dedent('''
            for coluna_data in COLS_DATA:
                base = df.dropna(subset=[coluna_data]).set_index(coluna_data)
                medias = base[COLS_SERIE].resample(REGRA).mean()
                registros = base[COLS_SERIE].resample(REGRA).count().sum(axis=1)
                tem_dados = registros > 0

                fig, (ax_valor, ax_volume) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
                medias[tem_dados].plot(ax=ax_valor, marker="o", markersize=4, linewidth=2)
                finalizar(ax_valor, "Media por periodo de " + ", ".join(COLS_SERIE))
                registros[tem_dados].plot(ax=ax_volume, kind="bar", color="#A9A9A9", width=0.8)
                finalizar(ax_volume, "Registros por periodo", "", "Registros")
                exibir()

                tabela_periodo = medias[tem_dados].round(2)
                tabela_periodo.insert(0, "registros", registros[tem_dados])
                tabela_periodo.head(15)
        ''').strip()
    else:
        corpo = textwrap.dedent('''
            for coluna_data in COLS_DATA:
                serie = (
                    df.dropna(subset=[coluna_data])
                      .set_index(coluna_data)
                      .resample(REGRA)
                      .size()
                )
                fig, ax = plt.subplots(figsize=(11, 4))
                serie.plot(ax=ax, kind="bar", color="#4C72B0", width=0.8)
                finalizar(ax, "Registros por periodo", "Periodo", "Registros")
                plt.xticks(rotation=45, ha="right")
                exibir()
        ''').strip()
    return cabecalho + "\n\n" + corpo


def _celula_alvo(df: pd.DataFrame, sel: Selecao, opcoes: Opcoes) -> str:
    alvo = opcoes.alvo
    if alvo in sel.numericas:
        tipo_alvo = NUMERICA
    elif alvo in sel.categorias:
        tipo_alvo = CATEGORICA
    elif alvo in df.columns:
        tipo_alvo = NUMERICA if df[alvo].dropna().nunique() > 12 else CATEGORICA
    else:
        tipo_alvo = None

    linhas = [f"ALVO = {alvo!r}", "", "if ALVO and ALVO in df.columns:"]
    if tipo_alvo == NUMERICA:
        linhas += [
            "    print('Distribuicao da variavel de interesse:')",
            "    df[ALVO].describe()",
            "    fig, ax = plt.subplots(figsize=(8, 3.6))",
            "    sns.histplot(df[ALVO].dropna(), kde=True, ax=ax, color='#DD8452')",
            "    finalizar(ax, ALVO + ' - distribuicao', ALVO, 'Frequencia')",
            "    exibir()",
            "",
        ]
        correlacionaveis = [c for c in sel.numericas_correlacao if c != alvo]
        if correlacionaveis:
            lista = ", ".join(repr(c) for c in correlacionaveis)
            linhas += [
                "    correlacoes = (df[[ALVO] + " + lista + "]",
                "                  .corr(numeric_only=True)[ALVO]",
                "                  .drop(ALVO)",
                "                  .sort_values(key=abs, ascending=False))",
                "    print('Correlacao de cada variavel com ' + ALVO + ':')",
                "    correlacoes.round(3).to_frame('correlacao_com_alvo')",
            ]
    elif tipo_alvo == CATEGORICA:
        linhas += [
            "    print('Distribuicao das classes:')",
            "    print(df[ALVO].value_counts(dropna=False).to_string())",
            "    fig, ax = plt.subplots(figsize=(8, 3.6))",
            "    sns.countplot(data=df, x=ALVO, ax=ax, color='#55A868')",
            "    finalizar(ax, ALVO + ' - distribuicao das classes', ALVO, 'Registros')",
            "    plt.xticks(rotation=30, ha='right')",
            "    exibir()",
        ]
        for numerica in sel.numericas[:2]:
            linhas += [
                "",
                "    fig, ax = plt.subplots(figsize=(9, 4))",
                f"    top = df[{alvo!r}].value_counts().head(8).index",
                f"    sns.boxplot(data=df, x={alvo!r}, y={numerica!r}, order=top, ax=ax,"
                " color='#4C72B0')",
                f"    finalizar(ax, {numerica!r} + ' por ' + ALVO, ALVO, {numerica!r})",
                "    plt.xticks(rotation=30, ha='right')",
                "    exibir()",
            ]
    else:
        linhas += [
            "    print('Variavel de interesse nao encontrada no arquivo: ' + str(ALVO))",
        ]
    linhas += ["else:", '    print("Nenhuma variavel de interesse definida.")']
    return "\n".join(linhas)


# --------------------------------------------------------------------------- #
# Montagem do notebook
# --------------------------------------------------------------------------- #


def _dedentar(texto: str) -> str:
    """Remove a indentação de um texto multilinha mantendo a primeira linha.

    Os blocos markdown são escritos alinhados dentro das funções geradoras; sem
    isso o notebook sairia com parágrafos indentados e quebrando a renderização.
    """
    linhas = texto.strip("\n").split("\n")
    if len(linhas) <= 1:
        return texto.strip()
    cauda = [linha for linha in linhas[1:] if linha.strip()]
    margem = min((len(linha) - len(linha.lstrip()) for linha in cauda), default=0)
    return "\n".join(
        [linhas[0].strip()] + [linha[margem:] if linha.strip() else "" for linha in linhas[1:]]
    ).strip()


def _md(texto: str) -> dict:
    return {"tipo": "markdown", "fonte": _dedentar(texto)}


def _code(texto: str) -> dict:
    return {"tipo": "code", "fonte": texto.strip()}


def gerar_celulas(df: pd.DataFrame, perfil: list[ColunaInfo], opcoes: Opcoes,
                  resumo: str) -> list[dict]:
    """Devolve a lista completa de células do notebook."""
    sel = selecionar_colunas(df, perfil, opcoes)
    celulas: list[dict] = []

    celulas.append(_md(f"""
        # {opcoes.titulo}

        Notebook gerado automaticamente pela skill **csv-eda-notebook**.

        - **Arquivo:** `{opcoes.caminho_csv.name}`
        - **Dimensões:** {df.shape[0]} linhas x {df.shape[1]} colunas
        - **Leitura:** separador `{opcoes.separador!r}` e encoding `{opcoes.encoding!r}`

        O arquivo é lido na primeira célula de código e todas as análises abaixo se adaptam ao
        que realmente foi encontrado: distribuições para numéricas, frequências para categóricas,
        correlações entre numéricas e séries temporais quando existe coluna de data.
    """))
    celulas.append(_code(_celula_setup(opcoes)))
    celulas.append(_md("""
        ## 0. Configuração e funções de apoio

        Ajuste `CSV_PATH`, `SEPARADOR` e `ENCODING` se quiser apontar este notebook para outro
        arquivo — o resto do código continua funcionando.
    """))
    celulas.append(_code(_helpers()))
    celulas.append(_md("""
        ## 1. Carregamento dos dados

        Os valores abaixo foram detectados automaticamente na geração deste notebook.
    """))
    celulas.append(_code(_celula_leitura()))
    celulas.append(_md("""
        ## 2. Visão geral do dataset

        Dimensões, tipos das colunas e volume de valores distintos.
    """))
    celulas.append(_code(_celula_tipos()))
    celulas.append(_code(_celula_valores_unicos()))
    celulas.append(_md("""
        ### 2.1. Valores ausentes

        Percentual de células vazias por coluna, calculado sobre os dados originais (antes de
        qualquer limpeza).
    """))
    celulas.append(_code(BLOCO_AUSENTES))
    celulas.append(_md("""
        ### 2.2. Linhas duplicadas

        Duplicatas exatas contam como um problema de qualidade de dados: elas inflam médias e
        confundiram modelos treinados depois.
    """))
    celulas.append(_code(BLOCO_DUPLICADAS))
    celulas.append(_md("""
        ## 3. Limpeza mínima

        Ajustes seguros e reversíveis: espaços em texto, números gravados como texto (moeda,
        separador de milhar), conversão de datas e remoção de duplicatas exatas. Nenhuma coluna
        é inventada ou descartada aqui — a base original continua em `df_bruto`.
    """))
    celulas.append(_code(_celula_limpeza(sel)))
    celulas.append(_md("""
        ## 4. Estatísticas descritivas

        ### 4.1. Variáveis numéricas
    """))
    celulas.append(_code(_celula_describe_numericas(sel)))
    if sel.categorias:
        celulas.append(_md("### 4.2. Variáveis categóricas (frequências)"))
        celulas.append(_code(_celula_frequencias(sel)))
    if sel.texto:
        celulas.append(_md("### 4.3. Texto livre"))
        celulas.append(_code(_celula_exemplos_texto(sel)))
    if sel.combos_num_cat or sel.combos_cat_cat:
        celulas.append(_md("""
            ## 5. Agregações

            Resumo numérico por categoria — a leitura mais útil de dados com pouco volume de
            categorias distintas.
        """))
        celulas.append(_code(_celula_agregacoes(sel)))

    celulas.append(_md("""
        ## 6. Visualizações

        Cada gráfico foi escolhido pelo tipo da variável: distribuição e boxplot para numéricas,
        frequência para categóricas, correlação entre numéricas e comparação de grupos.
    """))
    celulas.append(_md("### 6.1. Valores ausentes"))
    celulas.append(_code(_celula_grafico_ausentes()))
    if sel.numericas:
        celulas.append(_md("### 6.2. Distribuição das variáveis numéricas"))
        celulas.append(_code(_celula_histogramas(sel)))
        celulas.append(_md("### 6.3. Outliers (boxplot)"))
        celulas.append(_code(_celula_boxplots_numericas(sel)))
    if sel.categorias_barra:
        celulas.append(_md("### 6.4. Frequência das variáveis categóricas"))
        celulas.append(_code(_celula_barras_categoricas(sel)))
    if len(sel.numericas_correlacao) >= 2:
        celulas.append(_md("### 6.5. Correlação entre variáveis numéricas"))
        celulas.append(_code(_celula_correlacao(sel)))
    if sel.combos_num_cat:
        celulas.append(_md("### 6.6. Comparação de uma numérica entre categorias"))
        celulas.append(_code(_celula_boxplot_agrupado(sel)))
    cruzamento = _celula_cruzamento_categorias(sel)
    if cruzamento:
        celulas.append(_md("### 6.7. Relação entre duas variáveis categóricas"))
        celulas.append(_code(cruzamento))
    if sel.datas:
        celulas.append(_md(f"""
            ### 6.8. Evolução temporal

            Série agregada automaticamente na periodicidade `{_regra_resample(df, sel.datas)}`
            (mês, semana ou dia, conforme o período coberto pelos dados).
        """))
        celulas.append(_code(_celula_serie_temporal(df, sel)))

    if opcoes.alvo:
        celulas.append(_md(f"""
            ## 7. Variável de interesse: `{opcoes.alvo}`

            Distribuição da variável alvo e sua relação com as demais.
        """))
        celulas.append(_code(_celula_alvo(df, sel, opcoes)))

    celulas.append(_md("## 8. Resumo das principais observações"))
    celulas.append(_md(resumo))
    celulas.append(_md("""
        ## 9. Próximos passos

        - Reescreva a seção 8 com as conclusões do seu domínio: a leitura dos números acima é
          automática, a interpretação é sua.
        - Aprofunde as variáveis com maior lacuna de qualidade (valores ausentes, outliers).
        - Se houver objetivo predictivo, use a seção da variável de interesse como ponto de
          partida para um modelo.
    """))
    return celulas
