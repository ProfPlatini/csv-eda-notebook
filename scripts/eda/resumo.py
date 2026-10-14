"""Resumo em markdown com achados calculados a partir dos dados reais.

O resumo é calculado na geração, sobre o mesmo `df` limpo e a mesma seleção de
colunas usados pelo notebook, para que os números do texto e os das tabelas
coincidam. As frases descrevem associações, nunca causas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from .apoio import (
    checar_qualidade,
    classificar_correlacao,
    eta_quadrado,
    formatar_numero,
    plural,
    tabela_outliers,
)
from .loader import CATEGORICA, DATA, NUMERICA, TEXTO, ColunaInfo

if TYPE_CHECKING:
    from .codigo import Selecao

MAX_ACHADOS = 12
MIN_GRUPO = 5           # registros mínimos para citar a mediana de um grupo
MIN_GRUPO_TAXA = 10     # registros mínimos para citar a taxa do alvo em um grupo
MIN_ETA2 = 0.01         # abaixo disso a diferença entre grupos é desprezível e não vira achado
NOME_PERIODO = {"D": "dia", "W": "semana", "MS": "mês", "QS": "trimestre", "YS": "ano"}
PERIODO_PANDAS = {"D": "D", "W": "W", "MS": "M", "QS": "Q", "YS": "Y"}
FORMATO_PERIODO = {"D": "%d/%m/%Y", "W": "%d/%m/%Y", "MS": "%m/%Y", "QS": "%m/%Y", "YS": "%Y"}
PROBLEMAS = {
    "constante": "valor constante",
    "muitos_ausentes": "muitos valores ausentes",
    "categorias_parecidas": "categorias que só diferem em caixa, acento ou espaços",
    "negativos_raros": "poucos valores negativos, possível erro de digitação",
    "alta_cardinalidade": "categorias demais para resumir",
    "id_repetido": "identificador com valores repetidos",
    "infinitos": "valores infinitos",
}


def md_codigo(texto) -> str:
    """Nome de coluna como código markdown, mesmo que contenha crases."""
    texto = str(texto)
    return f"`` {texto} ``" if "`" in texto else f"`{texto}`"


def _pct(valor: float) -> str:
    return formatar_numero(valor, 1) + "%"


def _variacao(antes: float, depois: float) -> str:
    if not antes:
        return ""
    return f" ({'+' if depois >= antes else ''}{_pct(100 * (depois - antes) / abs(antes))})"


def _forca(r: float, rho: float) -> str:
    """Força e sinal pelo maior módulo entre Pearson e Spearman (igual à tabela do notebook)."""
    maior = rho if abs(rho) > abs(r) else r
    return f"{classificar_correlacao(maior)}, {'positiva' if maior > 0 else 'negativa'}"


# --------------------------------------------------------------------- achados

def _pares_correlacao(df: pd.DataFrame, colunas: list[str]) -> list[tuple]:
    """(|rho|, a, b, r, rho, n) para cada par com ao menos 10 linhas em comum."""
    if len(colunas) < 2:
        return []
    pearson = df[colunas].corr(method="pearson", min_periods=10)
    spearman = df[colunas].corr(method="spearman", min_periods=10)
    pares = []
    for i, a in enumerate(colunas):
        for b in colunas[i + 1:]:
            r, rho = pearson.loc[a, b], spearman.loc[a, b]
            if pd.notna(r) and pd.notna(rho):
                pares.append((abs(rho), a, b, r, rho, len(df[[a, b]].dropna())))
    return sorted(pares, key=lambda p: -p[0])


def _alvo_numerico(sel: Selecao) -> str | None:
    """O alvo numérico já tem achados próprios; os blocos gerais o deixam de fora."""
    return sel.alvo if sel.alvo and not sel.alvo_classes else None


def _achados_correlacao(df: pd.DataFrame, sel: Selecao) -> list[str]:
    alvo = _alvo_numerico(sel)
    pares = [p for p in _pares_correlacao(df, sel.numericas_correlacao) if alvo not in (p[1], p[2])]
    if not pares:
        return []
    relevantes = [p for p in pares if p[0] >= 0.3][:3]
    if not relevantes:
        _, a, b, _, rho, _ = pares[0]
        return [f"Nenhum par de numéricas com |rho| de 0,3 ou mais; o maior é "
                f"{md_codigo(a)} × {md_codigo(b)}, rho = {formatar_numero(rho)}."]
    achados = []
    for _, a, b, r, rho, n in relevantes:
        texto = (f"{md_codigo(a)} × {md_codigo(b)}: rho = {formatar_numero(rho)}, "
                 f"r = {formatar_numero(r)} ({_forca(r, rho)}; n = {n})")
        if abs(rho - r) >= 0.2:
            texto += "; a diferença entre rho e r sugere relação monotônica não linear ou influência de outliers"
        achados.append(texto + ".")
    return achados


def _medianas_por_grupo(df: pd.DataFrame, categoria: str, numerica: str) -> pd.DataFrame:
    grupos = df.groupby(categoria)[numerica].agg(["median", "count"])
    return grupos[grupos["count"] >= MIN_GRUPO].sort_values("median")


def _achados_grupos(df: pd.DataFrame, sel: Selecao) -> list[str]:
    achados = []
    for categoria, numerica in sel.combos_num_cat:
        if numerica == _alvo_numerico(sel):
            continue
        grupos = _medianas_por_grupo(df, categoria, numerica)
        eta2 = eta_quadrado(df, categoria, numerica, MIN_GRUPO)
        if len(grupos) < 2 or eta2 is None or eta2 < MIN_ETA2:
            continue
        menor, maior = grupos.iloc[0], grupos.iloc[-1]
        razao = (f"; {formatar_numero(maior['median'] / menor['median'], 1)} vezes a menor"
                 if menor["median"] > 0 else "")
        achados.append(
            f"{md_codigo(numerica)} por {md_codigo(categoria)}: mediana mais alta em "
            f"{md_codigo(grupos.index[-1])} ({formatar_numero(maior['median'])}; n = {int(maior['count'])}) "
            f"e mais baixa em {md_codigo(grupos.index[0])} ({formatar_numero(menor['median'])}; "
            f"n = {int(menor['count'])}){razao}; eta² = {formatar_numero(eta2)}.")
    return achados


def _achado_tendencia(df: pd.DataFrame, sel: Selecao, principal: str | None) -> list[str]:
    """Primeiro x último período completo da primeira coluna de data."""
    if not sel.datas:
        return []
    coluna = sel.datas[0]
    regra = sel.regras[coluna]
    datas = df[coluna]
    if getattr(datas.dt, "tz", None) is not None:
        datas = datas.dt.tz_localize(None)
    base = pd.DataFrame({"periodo": datas.dt.to_period(PERIODO_PANDAS[regra])})
    if principal:
        base["valor"] = df[principal]
    base = base.dropna(subset=["periodo"])
    inicio, fim = datas.min().normalize(), datas.max().normalize()
    completos = sorted(p for p in base["periodo"].unique()
                       if p.start_time >= inicio and p.end_time.normalize() <= fim)
    if len(completos) < 2:
        return []
    primeiro, ultimo = completos[0], completos[-1]
    a, b = base[base["periodo"] == primeiro], base[base["periodo"] == ultimo]
    formato = FORMATO_PERIODO[regra]
    # resample("W") rotula a semana pelo domingo (fim); os demais períodos, pelo início.
    rotulo = (lambda p: p.end_time) if regra == "W" else (lambda p: p.start_time)
    texto = (f"Por {NOME_PERIODO[regra]} ({md_codigo(coluna)}), do primeiro ao último período completo "
             f"({rotulo(primeiro):{formato}} → {rotulo(ultimo):{formato}}): registros de "
             f"{len(a)} para {len(b)}{_variacao(len(a), len(b))}")
    if principal and a["valor"].notna().any() and b["valor"].notna().any():
        ma, mb = a["valor"].mean(), b["valor"].mean()
        texto += (f"; média de {md_codigo(principal)} de {formatar_numero(ma)} para "
                  f"{formatar_numero(mb)}{_variacao(ma, mb)}")
    return [texto + "."]


def _achados_alvo(df: pd.DataFrame, sel: Selecao) -> list[str]:
    alvo = sel.alvo
    if not alvo:
        return []
    achados = []
    if sel.alvo_classes:
        positiva = sel.classe_positiva
        base_alvo = df[alvo].dropna()
        geral = 100 * (base_alvo == positiva).mean()
        for categoria in sel.alvo_categorias:
            base = df.dropna(subset=[alvo, categoria])
            taxa = (base[alvo] == positiva).groupby(base[categoria]).agg(["mean", "count"])
            taxa = taxa[taxa["count"] >= MIN_GRUPO_TAXA].sort_values("mean")
            if len(taxa) < 2:
                continue
            achados.append(
                f"Taxa de {md_codigo(alvo)} = {md_codigo(positiva)} por {md_codigo(categoria)}: "
                f"maior em {md_codigo(taxa.index[-1])} ({_pct(100 * taxa['mean'].iloc[-1])}; "
                f"n = {int(taxa['count'].iloc[-1])}) e menor em {md_codigo(taxa.index[0])} "
                f"({_pct(100 * taxa['mean'].iloc[0])}; n = {int(taxa['count'].iloc[0])}); "
                f"taxa geral {_pct(geral)}.")
        if not achados:
            achados.append(f"Taxa geral de {md_codigo(alvo)} = {md_codigo(positiva)}: {_pct(geral)} "
                           f"({len(base_alvo)} registros).")
        return achados

    pares = [p for p in _pares_correlacao(df, [alvo] + sel.alvo_numericas) if alvo in (p[1], p[2])]
    if pares:
        _, a, b, r, rho, n = pares[0]
        outra = b if a == alvo else a
        achados.append(f"Maior correlação de {md_codigo(alvo)}: com {md_codigo(outra)}, "
                       f"rho = {formatar_numero(rho)}, r = {formatar_numero(r)} ({_forca(r, rho)}; n = {n}).")
    for categoria in sel.alvo_categorias[:1]:
        medias = df.groupby(categoria)[alvo].agg(["mean", "count"])
        medias = medias[medias["count"] >= MIN_GRUPO].sort_values("mean")
        if len(medias) >= 2:
            achados.append(
                f"Média de {md_codigo(alvo)} por {md_codigo(categoria)}: maior em "
                f"{md_codigo(medias.index[-1])} ({formatar_numero(medias['mean'].iloc[-1])}; "
                f"n = {int(medias['count'].iloc[-1])}) e menor em {md_codigo(medias.index[0])} "
                f"({formatar_numero(medias['mean'].iloc[0])}; n = {int(medias['count'].iloc[0])}).")
    return achados


def _achados_numericas(df: pd.DataFrame, sel: Selecao) -> list[str]:
    achados = []
    for coluna in sel.numericas[:3]:
        valores = df[coluna].dropna()
        texto = (f"{md_codigo(coluna)}: mediana {formatar_numero(valores.median())} "
                 f"(de {formatar_numero(valores.min())} a {formatar_numero(valores.max())})")
        assimetria = valores.skew()
        if pd.notna(assimetria) and abs(assimetria) > 1:
            lado = "à direita" if assimetria > 0 else "à esquerda"
            texto += f"; cauda longa {lado} (assimetria = {formatar_numero(assimetria)})"
        achados.append(texto + ".")
    if sel.numericas:
        outliers = tabela_outliers(df, sel.numericas)
        outliers = outliers[outliers["pct_outliers"] > 1].head(2)
        if len(outliers):
            partes = [f"{md_codigo(nome)} {_pct(linha['pct_outliers'])} "
                      f"({plural(int(linha['n_outliers']), 'valor', 'valores')})"
                      for nome, linha in outliers.iterrows()]
            achados.append("Mais outliers pela regra de 1,5 × IQR: " + ", ".join(partes) + ".")
    return achados


def _achados_categoricas(df: pd.DataFrame, sel: Selecao) -> list[str]:
    achados = []
    candidatas = [c for c in sel.categorias if c not in sel.binarias and c != sel.alvo]
    for coluna in candidatas:
        contagem = df[coluna].value_counts()
        if len(contagem) < 2:  # constantes já aparecem em "Pontos de atenção"
            continue
        if len(achados) == 2:
            break
        achados.append(f"{md_codigo(coluna)}: {plural(len(contagem), 'categoria')}; a mais frequente é "
                       f"{md_codigo(contagem.index[0])} ({_pct(100 * contagem.iloc[0] / contagem.sum())} "
                       "dos registros preenchidos).")
    return achados


# ---------------------------------------------------------------------- resumo

def _visao_geral(df: pd.DataFrame, perfil: list[ColunaInfo], sel: Selecao, nome_arquivo: str) -> list[str]:
    def contar(tipo):
        return sum(1 for c in perfil if c.tipo == tipo and not c.identificador and c.nao_nulos)

    binarias = len(sel.binarias)
    numericas = plural(contar(NUMERICA), "numérica", "numéricas") + (
        f" ({plural(binarias, 'binária', 'binárias')})" if binarias else "")
    linhas = [
        f"- **Arquivo:** {md_codigo(nome_arquivo)}",
        f"- **Dimensões (após a limpeza):** {plural(len(df), 'linha')} × {plural(df.shape[1], 'coluna')}",
        f"- **Tipos:** {numericas}, {plural(contar(CATEGORICA), 'categórica', 'categóricas')}, "
        f"{plural(contar(DATA), 'data', 'datas')}, {plural(contar(TEXTO), 'coluna de texto livre', 'colunas de texto livre')}.",
    ]
    identificadores = [md_codigo(c.nome) for c in perfil if c.identificador]
    if identificadores:
        linhas.append(f"- **Identificadores (fora das análises):** {', '.join(identificadores)}.")
    com_ausentes = sorted((c for c in perfil if c.nulos), key=lambda c: -c.nulos_pct)
    if com_ausentes:
        total = sum(c.nulos for c in perfil) / max(df.size, 1) * 100
        piores = ", ".join(f"{md_codigo(c.nome)} ({_pct(c.nulos_pct)})" for c in com_ausentes[:3])
        linhas.append(f"- **Valores ausentes:** {_pct(total)} das células; mais afetadas: {piores}.")
    else:
        linhas.append("- **Valores ausentes:** nenhum.")
    datas = [df[c].dropna() for c in sel.datas]
    datas = [d for d in datas if len(d)]
    if datas:
        inicio, fim = min(d.min() for d in datas), max(d.max() for d in datas)
        linhas.append(f"- **Período coberto:** {inicio:%d/%m/%Y} a {fim:%d/%m/%Y} "
                      f"({plural((fim - inicio).days, 'dia')}).")
    return linhas


def _pontos_de_atencao(df, perfil, sel, avisos) -> tuple[list[str], pd.DataFrame]:
    numericas = [c.nome for c in perfil if c.tipo == NUMERICA and not c.identificador]
    categoricas = [c.nome for c in perfil if c.tipo == CATEGORICA and not c.identificador]
    qualidade = checar_qualidade(df, numericas, categoricas)
    pontos = [f"{md_codigo(coluna)}: {PROBLEMAS[problema]} — {detalhe}."
              for coluna, problema, detalhe in qualidade.itertuples(index=False)]
    pontos += [str(aviso) for aviso in avisos]
    return pontos, qualidade


def _proximos_passos(df, sel, qualidade: pd.DataFrame, avisos) -> list[str]:
    passos = []
    for coluna in qualidade.loc[qualidade["problema"] == "categorias_parecidas", "coluna"][:2]:
        passos.append(f"Unificar as variantes de {md_codigo(coluna)} (há um exemplo comentado na "
                      "seção de qualidade) e rodar o notebook de novo.")
    for coluna in qualidade.loc[qualidade["problema"] == "muitos_ausentes", "coluna"][:2]:
        passos.append(f"Entender por que {md_codigo(coluna)} tem tantos ausentes (campo opcional? "
                      "falha de coleta?) antes de usá-la.")
    # Com poucas colunas, linhas iguais por coincidência são esperadas.
    if df.shape[1] >= 4 and int(df.duplicated().sum()):
        passos.append("Confirmar se as linhas idênticas são registros repetidos; se forem, use "
                      "`REMOVER_DUPLICADAS = True` na seção de limpeza.")
    if any("ambíguas" in str(aviso) for aviso in avisos):
        passos.append("Confirmar com a origem dos dados se as datas estão em dia/mês; se estiverem "
                      "em mês/dia, troque o formato em `FORMATOS_DATA`.")
    if sel.numericas:
        outliers = tabela_outliers(df, sel.numericas)
        for coluna in outliers.index[outliers["pct_outliers"] > 5][:1]:
            passos.append(f"Conferir os valores extremos de {md_codigo(coluna)}: erro de registro ou "
                          "casos reais? A tabela da seção de outliers traz os limites.")
    return passos[:5]


def resumo_markdown(df_limpo: pd.DataFrame, perfil: list[ColunaInfo], selecao: Selecao,
                    nome_arquivo: str, alvo: str | None = None, avisos=()) -> str:
    """Resumo em markdown: visão geral, principais achados, atenção e próximos passos."""
    df, sel = df_limpo, selecao
    alvo = alvo or sel.alvo
    principal = alvo if alvo in sel.serie_temporal else (sel.serie_temporal or [None])[0]
    with np.errstate(all="ignore"):
        achados = (_achados_alvo(df, sel) + _achados_correlacao(df, sel) + _achados_grupos(df, sel)
                   + _achado_tendencia(df, sel, principal) + _achados_numericas(df, sel)
                   + _achados_categoricas(df, sel))[:MAX_ACHADOS]
        pontos, qualidade = _pontos_de_atencao(df, perfil, sel, avisos)
        passos = _proximos_passos(df, sel, qualidade, avisos)

    linhas = ["### Visão geral", ""] + _visao_geral(df, perfil, sel, nome_arquivo)
    linhas += ["", "### Principais achados", ""]
    linhas += [f"- {a}" for a in achados] or ["- Nenhum padrão numérico a destacar com as colunas disponíveis."]
    linhas += ["", "### Pontos de atenção", ""]
    linhas += [f"- {p}" for p in pontos[:10]] or ["- Nenhum problema encontrado pelas checagens automáticas."]
    if passos:
        linhas += ["", "### Próximos passos sugeridos", ""]
        linhas += [f"{i}. {passo}" for i, passo in enumerate(passos, start=1)]
    return "\n".join(linhas) + "\n"
