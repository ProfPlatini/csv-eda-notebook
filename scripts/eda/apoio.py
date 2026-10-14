"""Funções puras de limpeza e diagnóstico, usadas na geração e dentro do notebook.

O código deste módulo é copiado na célula "Funções de apoio" de cada notebook
gerado. Assim, o resumo calculado na geração e o notebook executado chegam aos
mesmos números, porque usam as mesmas funções. Por isso o módulo depende só de
pandas, numpy, re e unicodedata.
"""

import re
import unicodedata

import numpy as np
import pandas as pd

# Fração mínima de valores que precisam virar data para a coluna ser tratada como data.
LIMITE_CONVERSAO_DATA = 0.8
# Formatos testados, em ordem de preferência: em empate (todos os dias <= 12),
# dia/mês vence mês/dia, que é o padrão brasileiro.
FORMATOS_CANDIDATOS = [
    "ISO8601", "%d/%m/%Y", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%y",
    "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y", "%m/%d/%Y %H:%M", "%Y/%m/%d",
]
# Partes de nome que indicam identificador (comparadas por palavra inteira).
PALAVRAS_ID = {"id", "ids", "cod", "codigo", "cnpj", "cpf", "uuid", "hash", "key", "chave"}


# --------------------------------------------------------------------- textos

def plural(quantidade, singular, plural_=None):
    """'1 linha', '2 linhas'."""
    return f"{quantidade} {singular if quantidade == 1 else (plural_ or singular + 's')}"


def formatar_numero(valor, casas=2):
    """Número no padrão brasileiro: 1234.5 -> '1.234,50'."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "@").replace(".", ",").replace("@", ".")


def chave_normalizada(texto):
    """Chave para comparar textos: sem acento, sem diferença de caixa e de espaços."""
    decomposto = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


def parece_nome_de_id(nome):
    """True para nomes como `id_venda`, `codigoCliente`, `CNPJ`.

    A comparação é por palavra inteira: `data_pedido` não casa com "id".
    """
    separado = re.sub(r"([a-z])([A-Z])", r"\1_\2", str(nome))
    partes = re.split(r"[^a-z0-9]+", chave_normalizada(separado))
    return any(parte in PALAVRAS_ID for parte in partes)


def _mascara(serie_booleana):
    """Booleano puro (valores ausentes viram False)."""
    return serie_booleana.fillna(False).astype(bool)


# ------------------------------------------------------------------- números

def _texto_numerico(serie):
    """Remove moeda, %, espaços e parênteses contábeis. Devolve (texto, negativo)."""
    texto = serie.astype("string").str.strip().str.replace("−", "-", regex=False)
    texto = texto.str.replace(r"R\$|US\$|EUR|€|\$|%|\s", "", regex=True)
    negativo = _mascara(texto.str.fullmatch(r"\(.*\)"))
    texto = texto.str.replace(r"^\((.*)\)$", r"\1", regex=True)
    return texto, negativo


def detectar_decimal(serie, dica=None):
    """Devolve "," ou "." conforme o separador decimal usado na coluna.

    - valores com ponto e vírgula juntos: vale o último símbolo (1.234,56);
    - só vírgula: decimal vírgula, salvo quando todos parecem milhar (1,234);
    - só ponto: decimal ponto, salvo quando todos parecem milhar (1.234) e a
      `dica` do arquivo é vírgula (arquivo no padrão brasileiro).
    """
    texto = _texto_numerico(serie)[0]
    tem_ponto = _mascara(texto.str.contains(".", regex=False))
    tem_virgula = _mascara(texto.str.contains(",", regex=False))
    ambos = texto[tem_ponto & tem_virgula]
    if len(ambos):
        return "," if (ambos.str.rfind(",") > ambos.str.rfind(".")).mean() >= 0.5 else "."
    if tem_virgula.any():
        so_milhar = _mascara(texto[tem_virgula].str.fullmatch(r"[+-]?[1-9]\d{0,2}(,\d{3})+")).all()
        return "." if so_milhar else ","
    if tem_ponto.any() and dica == ",":
        so_milhar = _mascara(texto[tem_ponto].str.fullmatch(r"[+-]?[1-9]\d{0,2}(\.\d{3})+")).all()
        return "," if so_milhar else "."
    return "."


def normalizar_para_numerico(serie, decimal=None):
    """Converte texto em número (float); o que não for número vira NaN.

    Aceita moeda (R$, US$, EUR, €), %, separador de milhar, notação científica,
    sinal de menos tipográfico (−) e negativos entre parênteses: (1.234,00).
    Sem `decimal`, o separador é deduzido da própria coluna (`detectar_decimal`).
    """
    texto, negativo = _texto_numerico(serie)
    decimal = decimal or detectar_decimal(serie)
    if decimal == ",":
        # O ponto só pode aparecer como milhar, em grupos de 3 dígitos.
        valido = ~_mascara(texto.str.contains(".", regex=False)) | _mascara(
            texto.str.fullmatch(r"[+-]?[1-9]\d{0,2}(\.\d{3})+(,\d*)?"))
        texto = texto.where(valido).str.replace(".", "", regex=False)
        texto = texto.str.replace(",", ".", regex=False)
    else:
        valido = ~_mascara(texto.str.contains(",", regex=False)) | _mascara(
            texto.str.fullmatch(r"[+-]?[1-9]\d{0,2}(,\d{3})+(\.\d*)?"))
        # Vários pontos (1.234.567) só podem ser milhar.
        varios_pontos = _mascara(texto.str.count(r"\.") > 1)
        valido &= ~varios_pontos | _mascara(texto.str.fullmatch(r"[+-]?[1-9]\d{0,2}(\.\d{3})+"))
        texto = texto.where(valido).str.replace(",", "", regex=False)
        texto = texto.mask(varios_pontos, texto.str.replace(".", "", regex=False))
    numeros = pd.to_numeric(texto, errors="coerce").astype("float64")
    return numeros.where(~negativo, -numeros)


# --------------------------------------------------------------------- datas

def converter_datas(serie, formato):
    """Converte texto em data com um formato explícito; o que não casar vira NaT.

    Fora do ISO, a mesma data com ou sem hora também é aceita (01/02/2024 e
    01/02/2024 14:30 na mesma coluna, comum em planilhas do Excel).
    """
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie
    texto = serie.astype("string").str.strip()
    try:
        datas = pd.to_datetime(texto, format=formato, errors="coerce")
    except (ValueError, TypeError):  # fusos horários diferentes na mesma coluna
        return pd.to_datetime(texto, format=formato, errors="coerce", utc=True)
    if formato != "ISO8601":
        base = formato.split(" ")[0]
        for alternativo in (base, f"{base} %H:%M", f"{base} %H:%M:%S"):
            faltam = datas.isna() & texto.notna()
            if alternativo != formato and faltam.any():
                datas = datas.fillna(pd.to_datetime(texto[faltam], format=alternativo, errors="coerce"))
    return datas


def _datas_plausiveis(datas):
    """Evita falsos positivos: ao menos 90% das datas entre 1900 e daqui a 50 anos."""
    anos = datas.dropna().dt.year
    return bool(len(anos)) and anos.between(1900, pd.Timestamp.now().year + 50).mean() >= 0.9


def detectar_formato_data(serie):
    """Devolve o formato de data da coluna ("ISO8601", "%d/%m/%Y"...) ou None.

    Testa uma amostra de até 2.000 valores distintos contra FORMATOS_CANDIDATOS
    e fica com o formato que converte mais valores (em empate, o primeiro da
    lista). Colunas numéricas nunca são datas.
    """
    if not (pd.api.types.is_object_dtype(serie) or pd.api.types.is_string_dtype(serie)):
        return None
    valores = serie.dropna().astype(str).str.strip()
    valores = valores[valores != ""].drop_duplicates()
    if valores.empty:
        return None
    if len(valores) > 2000:
        valores = valores.sample(2000, random_state=0)
    parece_iso = valores.str.match(r"\d{4}-\d{2}-\d{2}").mean() >= 0.9
    melhor, melhor_taxa = None, 0.0
    for formato in FORMATOS_CANDIDATOS:
        if formato == "ISO8601" and not parece_iso:
            continue
        convertidas = converter_datas(valores, formato)
        taxa = convertidas.notna().mean()
        if taxa > melhor_taxa and _datas_plausiveis(convertidas):
            melhor, melhor_taxa = formato, taxa
    return melhor if melhor_taxa >= LIMITE_CONVERSAO_DATA else None


# ------------------------------------------------------------------- limpeza

def padronizar_colunas(df):
    """Nomes de coluna únicos e sem espaços nas bordas. Devolve (df, avisos).

    Também remove colunas `Unnamed: N` totalmente vazias, que surgem quando as
    linhas terminam com um separador sobrando.
    """
    avisos = []
    vazias = [i for i, nome in enumerate(df.columns)
              if str(nome).startswith("Unnamed: ") and df.iloc[:, i].isna().all()]
    for i in vazias:
        avisos.append(f"Coluna sem nome e 100% vazia removida: {df.columns[i]} "
                      "(provável separador sobrando no fim das linhas).")
    df = df.iloc[:, [i for i in range(df.shape[1]) if i not in vazias]]

    nomes, usados = [], set()
    for posicao, original in enumerate(df.columns, start=1):
        nome = str(original).strip() or f"coluna_{posicao}"
        base, sufixo = nome, 2
        while nome in usados:
            nome, sufixo = f"{base}_{sufixo}", sufixo + 1
        if nome != original:
            avisos.append(f"Coluna {str(original)!r} renomeada para {nome!r}.")
        usados.add(nome)
        nomes.append(nome)
    return df.set_axis(nomes, axis=1), avisos


def limpar_dados(df, plano):
    """Aplica o plano de limpeza sem alterar `df`. Devolve (df limpo, registro).

    `plano` traz as listas/dicionários "texto", "numericas" ({coluna: decimal}),
    "datas" ({coluna: formato}) e o booleano "remover_duplicadas". As
    duplicatas são medidas antes de qualquer conversão.
    """
    duplicadas = df.duplicated().to_numpy()
    df = df.copy()
    registro = []

    ajustadas, vazios = [], 0
    for coluna in plano.get("texto", []):
        original = df[coluna]
        if pd.api.types.infer_dtype(original, skipna=True) != "string":  # ex.: True/False com vazios
            continue
        texto = original.str.strip()
        texto = texto.mask(texto == "")
        if not texto.equals(original):
            ajustadas.append(coluna)
            vazios += int(texto.isna().sum() - original.isna().sum())
            df[coluna] = texto
    if ajustadas:
        registro.append(f"Espaços nas bordas removidos em {plural(len(ajustadas), 'coluna')} "
                        f"({', '.join(ajustadas)})"
                        + (f"; {plural(vazios, 'texto vazio', 'textos vazios')} → ausente."
                           if vazios else "."))

    for coluna, decimal in plano.get("numericas", {}).items():
        antes = int(df[coluna].notna().sum())
        df[coluna] = normalizar_para_numerico(df[coluna], decimal)
        perdidos = antes - int(df[coluna].notna().sum())
        registro.append(f"{coluna}: texto convertido em número"
                        + (f" (decimal '{decimal}')" if decimal else "")
                        + (f"; {plural(perdidos, 'valor não numérico', 'valores não numéricos')}"
                           " → ausente." if perdidos else "."))

    for coluna, formato in plano.get("datas", {}).items():
        antes = int(df[coluna].notna().sum())
        df[coluna] = converter_datas(df[coluna], formato)
        perdidos = antes - int(df[coluna].notna().sum())
        registro.append(f"{coluna}: convertida em data (formato {formato})"
                        + (f"; {plural(perdidos, 'valor não reconhecido', 'valores não reconhecidos')}"
                           " → ausente." if perdidos else "."))

    for coluna in df.columns:
        if pd.api.types.is_float_dtype(df[coluna]):
            infinitos = np.isinf(df[coluna].to_numpy(dtype="float64", na_value=np.nan))
            if infinitos.any():
                df[coluna] = df[coluna].mask(infinitos)
                registro.append(f"{coluna}: {plural(int(infinitos.sum()), 'valor infinito', 'valores infinitos')}"
                                " (±inf) → ausente.")

    n_duplicadas = int(duplicadas.sum())
    if n_duplicadas and plano.get("remover_duplicadas"):
        df = df[~duplicadas].reset_index(drop=True)
        registro.append(plural(n_duplicadas, "duplicata removida", "duplicatas removidas")
                        + " (linhas idênticas a uma anterior).")
    elif n_duplicadas:
        registro.append(plural(n_duplicadas, "linha idêntica mantida", "linhas idênticas mantidas")
                        + ": sem coluna identificadora não dá para saber se são registros "
                        "repetidos. Mude REMOVER_DUPLICADAS para True se forem erros.")

    return df, registro or ["Nenhum ajuste foi necessário."]


# --------------------------------------------------------------- diagnóstico

def tabela_outliers(df, colunas):
    """Outliers pela regra de Tukey (1,5 × IQR), uma linha por coluna."""
    linhas = {}
    for coluna in colunas:
        valores = df[coluna].dropna()
        q1, q3 = valores.quantile(0.25), valores.quantile(0.75)
        inferior, superior = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        n_outliers = int(((valores < inferior) | (valores > superior)).sum())
        linhas[coluna] = {
            "n_validos": len(valores), "q1": q1, "q3": q3,
            "limite_inferior": inferior, "limite_superior": superior,
            "n_outliers": n_outliers,
            "pct_outliers": 100 * n_outliers / len(valores) if len(valores) else 0.0,
            "minimo": valores.min(), "maximo": valores.max(),
        }
    tabela = pd.DataFrame.from_dict(linhas, orient="index")
    tabela.index.name = "coluna"
    return tabela.sort_values("pct_outliers", ascending=False) if len(tabela) else tabela


def checar_qualidade(df, numericas, categoricas, bruto=None):
    """Lista problemas de qualidade: DataFrame com coluna, problema e detalhe.

    `bruto` (opcional) é o DataFrame antes da limpeza, usado para contar os
    infinitos que a limpeza transformou em ausentes.
    """
    achados = []

    def anotar(coluna, problema, detalhe):
        achados.append({"coluna": coluna, "problema": problema, "detalhe": detalhe})

    for coluna in df.columns:
        pct = 100 * df[coluna].isna().mean() if len(df) else 0
        if pct >= 50:
            anotar(coluna, "muitos_ausentes", f"{formatar_numero(pct, 1)}% das linhas sem valor")
    for coluna in [*numericas, *categoricas]:
        distintos = df[coluna].dropna().unique()
        if len(distintos) == 1:
            anotar(coluna, "constante", f"um único valor: {distintos[0]}")
    for coluna in numericas:
        valores = pd.to_numeric(df[coluna], errors="coerce").dropna()
        negativos = int((valores < 0).sum())
        if negativos and negativos / len(valores) <= 0.05:
            anotar(coluna, "negativos_raros",
                   f"{plural(negativos, 'valor negativo', 'valores negativos')} em {len(valores)}, "
                   f"{formatar_numero(100 * negativos / len(valores), 1)}%; "
                   f"mínimo {formatar_numero(valores.min())}")
    for coluna in categoricas:
        distintos = df[coluna].dropna().unique()
        if len(distintos) > 50:
            anotar(coluna, "alta_cardinalidade", f"{len(distintos)} valores distintos")
        grupos = {}
        for valor in distintos:
            grupos.setdefault(chave_normalizada(valor), []).append(f'"{valor}"')
        parecidos = [" / ".join(variantes) for variantes in grupos.values() if len(variantes) > 1]
        if parecidos:
            anotar(coluna, "categorias_parecidas", "; ".join(parecidos[:5]))
    for coluna in df.columns:
        validos = df[coluna].dropna()
        if parece_nome_de_id(coluna) and len(validos):
            repetidos = len(validos) - validos.nunique()
            if repetidos and repetidos / len(validos) <= 0.05:
                anotar(coluna, "id_repetido", f"{plural(repetidos, 'valor repetido', 'valores repetidos')}")
    origem = df if bruto is None else bruto
    for coluna in origem.columns:
        if pd.api.types.is_float_dtype(origem[coluna]):
            n = int(np.isinf(origem[coluna].to_numpy(dtype="float64", na_value=np.nan)).sum())
            if n:
                anotar(coluna, "infinitos", f"{plural(n, 'valor infinito', 'valores infinitos')} (±inf)"
                       + (" tratados como ausentes na limpeza" if bruto is not None else ""))
    return pd.DataFrame(achados, columns=["coluna", "problema", "detalhe"])


def eta_quadrado(df, categoria, numerica, min_grupo=5):
    """Fração da variância de `numerica` explicada pelos grupos de `categoria` (0 a 1).

    Só entram grupos com ao menos `min_grupo` registros; devolve None se sobrarem
    menos de dois grupos ou se a numérica for constante.
    """
    base = df[[categoria, numerica]].dropna()
    tamanhos = base[categoria].value_counts()
    base = base[base[categoria].isin(tamanhos[tamanhos >= min_grupo].index)]
    if base[categoria].nunique() < 2:
        return None
    media = base[numerica].mean()
    total = float(((base[numerica] - media) ** 2).sum())
    if total == 0:
        return None
    medias_grupo = base.groupby(categoria)[numerica].transform("mean")
    return float(((medias_grupo - media) ** 2).sum()) / total


def v_de_cramer(df, a, b):
    """Associação entre duas categóricas: 0 = independentes, 1 = associação total."""
    tabela = pd.crosstab(df[a], df[b]).to_numpy(dtype=float)
    n = tabela.sum()
    if n == 0 or min(tabela.shape) < 2:
        return None
    esperado = np.outer(tabela.sum(axis=1), tabela.sum(axis=0)) / n
    qui2 = float(((tabela - esperado) ** 2 / esperado).sum())
    return float(np.sqrt(qui2 / (n * (min(tabela.shape) - 1))))


def classificar_correlacao(r):
    """Força de uma correlação pelo módulo: desprezível, fraca, moderada, forte, muito forte."""
    if pd.isna(r):
        return "indefinida"
    r = abs(r)
    if r < 0.1:
        return "desprezível"
    if r < 0.3:
        return "fraca"
    if r < 0.5:
        return "moderada"
    if r < 0.7:
        return "forte"
    return "muito forte"
