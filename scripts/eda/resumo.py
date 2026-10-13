"""Geração do resumo textual em markdown a partir dos dados reais.

O texto é calculado aqui (fora do notebook) porque depende de números que só
ficam disponíveis no momento da geração. O agente pode reescrever esse bloco
depois de ler o notebook, mas o padrão já vem com os achados reais.
"""

from __future__ import annotations

import pandas as pd

from .loader import CATEGORICA, DATA, NUMERICA, TEXTO, ColunaInfo, normalizar_para_numerico


def _numero(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _porcentagem(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",") + "%"


def _plural(quantidade: int, singular: str, plural: str | None = None) -> str:
    if quantidade == 1:
        return f"{quantidade} {singular}"
    return f"{quantidade} {plural or singular + 's'}"


def _serie_numerica(df: pd.DataFrame, nome: str) -> pd.Series:
    serie = df[nome]
    if pd.api.types.is_numeric_dtype(serie):
        return serie
    return normalizar_para_numerico(serie)


def _contar_outliers(serie: pd.Series) -> int:
    valores = serie.dropna()
    if len(valores) < 4:
        return 0
    q1, q3 = valores.quantile(0.25), valores.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0 or pd.isna(iqr):
        return 0
    return int(((valores < q1 - 1.5 * iqr) | (valores > q3 + 1.5 * iqr)).sum())


def resumo_markdown(df: pd.DataFrame, perfil: list[ColunaInfo],
                    nome_arquivo: str, alvo: str | None = None) -> str:
    """Monta o resumo em markdown com números extraídos do próprio dataset."""
    tipos = (NUMERICA, CATEGORICA, DATA, TEXTO)
    por_tipo = {t: [c.nome for c in perfil if c.tipo == t] for t in tipos}
    linhas = [f"Resumo gerado automaticamente a partir de `{nome_arquivo}`", ""]

    # ---------------------------------------------------------------- visão geral
    linhas += [
        "### Visão geral",
        "",
        f"- **Arquivo analisado:** `{nome_arquivo}`",
        f"- **Dimensões:** {df.shape[0]:,} linhas x {_plural(df.shape[1], 'coluna')}"
        .replace(",", "."),
        f"- **Tipos identificados:** {_plural(len(por_tipo[NUMERICA]), 'numérica', 'numéricas')}, "
        f"{_plural(len(por_tipo[CATEGORICA]), 'categórica', 'categóricas')}, "
        f"{_plural(len(por_tipo[DATA]), 'data')}, "
        f"{_plural(len(por_tipo[TEXTO]), 'coluna de texto livre', 'colunas de texto livre')}.",
    ]

    duplicadas = int(df.duplicated().sum())
    linhas.append(
        f"- **Linhas duplicadas:** {duplicadas} "
        f"({_porcentagem(duplicadas / df.shape[0] * 100) if df.shape[0] else '0%'} do total)."
    )

    com_nulos = [c for c in perfil if c.nulos > 0]
    total_nulos = sum(c.nulos for c in com_nulos)
    if com_nulos:
        top_nulos = sorted(com_nulos, key=lambda c: c.nulos_pct, reverse=True)[:3]
        linhas.append(
            f"- **Valores ausentes:** "
            f"{_porcentagem(total_nulos / max(df.shape[0] * df.shape[1], 1))} "
            f"do total das células. Piores colunas: "
            + ", ".join(f"`{c.nome}` ({_porcentagem(c.nulos_pct)})" for c in top_nulos)
            + "."
        )
    else:
        linhas.append("- **Valores ausentes:** nenhuma célula vazia.")

    if por_tipo[DATA]:
        inicio, fim = None, None
        for coluna in por_tipo[DATA][:3]:
            serie = pd.to_datetime(df[coluna], errors="coerce")
            validos = serie.dropna()
            if not validos.empty:
                inicio = validos.min() if inicio is None else min(inicio, validos.min())
                fim = validos.max() if fim is None else max(fim, validos.max())
        if inicio is not None:
            dias = (fim - inicio).days
            linhas.append(
                f"- **Período coberto:** {inicio:%d/%m/%Y} a {fim:%d/%m/%Y} "
                f"(~{dias} dias, aproximadamente {dias / 30:.0f} meses)."
            )

    # ------------------------------------------------------------------- destaques
    linhas += ["", "### Principais achados", ""]

    numericas = [c for c in perfil
                 if c.tipo == NUMERICA and not c.identificador and c.nao_nulos > 0]
    if numericas:
        linhas.append("**Variáveis numéricas**")
        foco = sorted(numericas, key=lambda c: c.n_unicos, reverse=True)[:3]
        for coluna in foco:
            serie = _serie_numerica(df, coluna.nome).dropna()
            if serie.empty:
                continue
            assimetria = serie.skew()
            assim_txt = ""
            if pd.notna(assimetria) and abs(assimetria) > 1:
                lado = "à direita" if assimetria > 0 else "à esquerda"
                assim_txt = f", distribuição assimétrica {lado} (skew = {assimetria:.2f})"
            outliers = _contar_outliers(serie)
            out_txt = (f", {outliers} valor(es) fora de 1,5x IQR"
                       if outliers and outliers / len(serie) > 0.01 else "")
            linhas.append(
                f"- `{coluna.nome}`: mínimo {_numero(serie.min())}, "
                f"mediana {_numero(serie.median())}, média {_numero(serie.mean())}, "
                f"máximo {_numero(serie.max())}{assim_txt}{out_txt}."
            )
    else:
        linhas.append("- O arquivo não possui variáveis numéricas exploáveis "
                      "(ou todas separem valores de identificação).")

    categoricas = [c for c in perfil
                   if c.tipo == CATEGORICA and not c.identificador and c.nao_nulos > 0]
    if categoricas:
        linhas += ["", "**Variáveis categóricas**"]
        for coluna in sorted(categoricas, key=lambda c: c.nao_nulos, reverse=True)[:3]:
            serie = df[coluna.nome].dropna()
            if serie.nunique() > 20:
                linhas.append(
                    f"- `{coluna.nome}`: {serie.nunique()} valores distintos — "
                    "não resumida em suas categorias aqui."
                )
                continue
            contagem = serie.value_counts()
            dominancia = contagem.iloc[0] / serie.shape[0] * 100
            linhas.append(
                f"- `{coluna.nome}`: {serie.nunique()} categorias; "
                f"mais frequente é `{contagem.index[0]}` com "
                f"{_porcentagem(dominancia)} dos registros."
            )

    # ---------------------------------------------------------------- correlações
    numericas_graf = [c.nome for c in numericas][:15]
    if len(numericas_graf) >= 2:
        convertidas = {nome: _serie_numerica(df, nome) for nome in numericas_graf}
        matriz = pd.DataFrame(convertidas).corr(numeric_only=True)
        pares = []
        for i, a in enumerate(numericas_graf):
            for b in numericas_graf[i + 1:]:
                valor = matriz.loc[a, b]
                if pd.notna(valor):
                    pares.append((abs(valor), a, b, valor))
        pares.sort(reverse=True)
        fortes = [p for p in pares if p[0] >= 0.3]
        linhas += ["", "**Relações lineares (correlação de Pearson)**"]
        if fortes:
            for _, a, b, valor in fortes[:4]:
                tipo = "positiva" if valor > 0 else "negativa"
                linhas.append(f"- `{a}` x `{b}`: r = {valor:.2f} (forte, {tipo}).")
            fracas = [p for p in pares if p[0] < 0.1]
            if fracas:
                linhas.append(
                    f"- {len(fracas)} par(es) de variáveis com correlação praticamente nula, "
                    "o que sugere independentes ou relações não lineares."
                )
        else:
            linhas.append("- Nenhum par de variáveis numéricas apresentou correlação "
                          "de módulo acima de 0,3.")

    # -------------------------------------------------------------- pontos de atenção
    atencao = []
    for coluna in perfil:
        if coluna.nao_nulos and coluna.n_unicos == 1:
            valor = coluna.exemplos[0] if coluna.exemplos else "?"
            atencao.append(f"`{coluna.nome}` tem valor constante ({valor}).")
        elif coluna.identificador:
            atencao.append(f"`{coluna.nome}` parece ser um identificador único — útil para "
                           "juntar tabelas, mas sem significado analítico.")
        elif coluna.nulos_pct >= 50:
            atencao.append(
                f"`{coluna.nome}` tem {_porcentagem(coluna.nulos_pct)} de valores ausentes.")

    linhas += ["", "### Pontos de atenção", ""]
    if atencao:
        linhas += [f"- {item}" for item in atencao[:8]]
    else:
        linhas.append("- Nenhuma inconsistência estrutural evidente na leitura do arquivo.")

    if alvo:
        linhas += ["", f"A coluna `{alvo}` foi definida como variável de interesse e possui "
                    "uma seção dedicada neste notebook."]

    proximos = []
    if com_nulos:
        proximos.append(
            "Validar com quem conheça o processo de negócio o significado das colunas com "
            "muitos valores ausentes antes de preencher ou descartar registros.")
    if len(numericas_graf) >= 2:
        proximos.append(
            "Cruzar as variáveis com maior correlação em um modelo preditivo ou comparativo.")
    if duplicadas:
        proximos.append(
            "Investigar os registros duplicados antes de usar a base para treinar modelos.")
    if not proximos:
        proximos.append(
            "A base está estruturalmente saudável: o próximo passo é cruzar as variáveis com o "
            "contexto de negócio para decidir o que fazer com elas.")
    linhas += ["", "### Próximos passos sugeridos", ""]
    linhas += [f"{i}. {passo}" for i, passo in enumerate(proximos, start=1)]
    linhas.append("")
    return "\n".join(linhas)
