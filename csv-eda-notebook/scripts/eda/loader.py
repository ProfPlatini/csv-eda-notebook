"""Carregamento e perfilagem de arquivos CSV.

Responsável por ler o arquivo de forma tolerante (separador e encoding) e por
classificar cada coluna como numérica, categórica, data ou texto livre. Essa
classificação é a base de todo o notebook gerado: as análises só são criadas
para os tipos que realmente existem no arquivo.
"""

from __future__ import annotations

import csv
import re
import warnings
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

NUMERICA = "numerica"
CATEGORICA = "categorica"
DATA = "data"
TEXTO = "texto"

# Um texto com muitos valores distintos não serve para gráficos de frequência.
LIMITE_CATEGORICAS = 50
# Porcentagem de valores válidos que precisam ser interpretáveis como data.
LIMITE_CONVERSAO_DATA = 0.80
# Porcentagem de valores válidos que precisam ser interpretáveis como número.
LIMITE_CONVERSAO_NUMERICA = 0.90
# Letras que podem aparecer sem transformar o texto em não-número: só moeda
# (R$, US$, EUR...). "24h" traz a letra H e precisa continuar categórico.
LETRAS_MONETARIAS = {"R", "U", "S", "D"}

PADRAO_NOME_DATA = (
    "data", "date", "dia", "mes", "ano", "hora", "hour", "time",
    "dt", "period", "periodo", "timestamp", "birth", "nascimento",
)
PALAVRAS_ID = {"id", "ids", "cod", "codigo", "cnpj", "cpf", "uuid", "hash", "key", "chave"}


@dataclass
class ColunaInfo:
    """Perfil resumido de uma coluna do CSV."""

    nome: str
    tipo: str
    total: int
    nulos: int
    n_unicos: int
    exemplos: list

    @property
    def nulos_pct(self) -> float:
        return (self.nulos / self.total * 100) if self.total else 0.0

    @property
    def nao_nulos(self) -> int:
        return self.total - self.nulos

    @property
    def identificador(self) -> bool:
        """True quando a coluna parece ser um identificador único (id, cpf...)."""
        parece_id = _parece_nome_de_id(self.nome)
        unico = self.n_unicos >= max(self.nao_nulos, 1) and self.nao_nulos > 20
        return (parece_id and unico) or (unico and self.tipo == TEXTO)


def _parece_nome_de_id(nome: str) -> bool:
    """True para nomes como `id_venda`, `codigo_cliente`, `cnpj`.

    A comparação é feita por palavra inteira: sem isso, `data_pedido` casaria
    com "id" dentro de "pedido" e a coluna seria tratada como identificador.
    """
    partes = [p for p in re.split(r"[^a-z0-9]+", nome.lower()) if p]
    return any(parte in PALAVRAS_ID for parte in partes)


def ler_amostra(caminho: Path, n_bytes: int = 65_536) -> tuple[str, str, str | None]:
    """Lê uma amostra do arquivo e devolve (texto, separador, encoding)."""
    conteudo = None
    encoding = None
    for tentativa in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            conteudo = caminho.read_text(encoding=tentativa)[:n_bytes]
            encoding = tentativa
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if conteudo is None:  # arquivo binário ou com encoding exótico
        conteudo = caminho.read_bytes()[:n_bytes].decode("utf-8", errors="replace")
        encoding = "utf-8"

    separador = None
    linhas = [linha for linha in conteudo.splitlines() if linha.strip()]
    if len(linhas) > 1:
        try:
            separador = csv.Sniffer().sniff("\n".join(linhas[:20]), delimiters=",;\t|").delimiter
        except csv.Error:
            # Fallback: o separador que mais aparece na primeira linha.
            cabecalho = linhas[0]
            separador = max(",;\t|", key=cabecalho.count)
            if cabecalho.count(separador) == 0:
                separador = ","
    return conteudo, separador or ",", encoding


def carregar_csv(caminho: str | Path, separador: str | None = None,
                 encoding: str | None = None) -> tuple[pd.DataFrame, str, str]:
    """Lê o CSV inferindo separador e encoding quando não informados."""
    caminho = Path(caminho).expanduser()
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    _, sep_detectado, enc_detectado = ler_amostra(caminho)
    sep_final = separador or sep_detectado
    enc_final = encoding or enc_detectado

    df = None
    for enc in [enc_final, "utf-8-sig", "utf-8", "latin-1"]:
        try:
            df = pd.read_csv(caminho, sep=sep_final, encoding=enc, low_memory=False)
            enc_final = enc
            break
        except (UnicodeDecodeError, UnicodeError, pd.errors.ParserError):
            continue
    if df is None:
        # Último recurso: leitura tolerante, mantendo o que der.
        df = pd.read_csv(caminho, sep=sep_final, encoding="utf-8", errors="replace",
                         low_memory=False)

    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c]]
    return df, sep_final, enc_final


def normalizar_para_numerico(serie: pd.Series) -> pd.Series:
    """Converte texto em número aceitando moeda e separadores milhar.

    Trata "1.234,56", "1,234.56", "R$ 1.234", "+12%" etc. É usada tanto na
    detecção de tipos quanto dentro do notebook gerado.
    """
    txt = serie.astype("string").str.strip()
    txt = txt.str.replace(r"\s+", "", regex=True)
    txt = txt.str.replace(r"[^0-9,.\-+eE]", "", regex=True)

    tem_ponto = txt.str.contains(".", regex=False)
    tem_virgula = txt.str.contains(",", regex=False)

    so_virgula = tem_virgula & ~tem_ponto
    txt = txt.mask(so_virgula, txt.str.replace(",", ".", regex=False))

    ambos = tem_ponto & tem_virgula
    # O separador decimal é o último a aparecer na string.
    ponto_milhar = ambos & (txt.str.rfind(".") < txt.str.rfind(","))
    txt = txt.mask(ponto_milhar, txt.str.replace(".", "", regex=False)
                                  .str.replace(",", ".", regex=False))
    virgula_milhar = ambos & (txt.str.rfind(".") > txt.str.rfind(","))
    txt = txt.mask(virgula_milhar, txt.str.replace(",", "", regex=False))

    return pd.to_numeric(txt, errors="coerce")


def _para_data(serie: pd.Series) -> pd.Series:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return pd.to_datetime(serie, errors="coerce", format="mixed", dayfirst=True)
        except (ValueError, TypeError):
            return pd.to_datetime(serie, errors="coerce", dayfirst=True)


def _datas_plausiveis(convertida: pd.Series) -> bool:
    """Filtro contra falsos positivos de data.

    Números como texto ("100001") são interpretados pelo pandas como nanossegundos
    desde 1970. Uma data de verdade tem ano a partir de 1971 e no máximo o ano
    corrente mais um.
    """
    validos = convertida.dropna()
    if validos.empty:
        return False
    try:
        ano_min = int(validos.dt.year.min())
        ano_max = int(validos.dt.year.max())
    except (AttributeError, TypeError, ValueError):
        return False
    return ano_min >= 1971 and ano_max <= pd.Timestamp.now().year + 2


def _letras_presentes(serie: pd.Series) -> set[str]:
    """Todas as letras que aparecem nos valores textuais da coluna."""
    letras = serie.astype("string").str.replace(r"[^A-Za-z]", "", regex=True)
    return set("".join(letras.dropna().tolist()).upper())


def _taxa_de_conversao(original: pd.Series, convertido: pd.Series) -> float:
    validos = original.notna().sum()
    return 0.0 if validos == 0 else (convertido.notna().sum() / validos)


def classificar_coluna(serie: pd.Series) -> str:
    """Retorna NUMERICA, CATEGORICA, DATA ou TEXTO para uma série."""
    nao_nulos = serie.dropna()
    if nao_nulos.empty:
        return CATEGORICA

    if pd.api.types.is_bool_dtype(serie):
        return CATEGORICA

    if pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_complex_dtype(serie):
        return NUMERICA

    if pd.api.types.is_datetime64_any_dtype(serie):
        return DATA

    if not (pd.api.types.is_object_dtype(serie) or pd.api.types.is_string_dtype(serie)):
        return NUMERICA

    nulos = len(nao_nulos)
    n_unicos = nao_nulos.nunique()

    as_datas = _para_data(serie)
    taxa_data = _taxa_de_conversao(serie, as_datas)
    nome_sugere_data = any(p in serie.name.lower() for p in PADRAO_NOME_DATA)
    if _datas_plausiveis(as_datas) and (
        taxa_data >= LIMITE_CONVERSAO_DATA
        or (nome_sugere_data and taxa_data >= 0.5)
    ):
        return DATA

    como_numero = normalizar_para_numerico(serie)
    letras = _letras_presentes(serie)
    if (_taxa_de_conversao(serie, como_numero) >= LIMITE_CONVERSAO_NUMERICA
            and letras <= LETRAS_MONETARIAS):
        return NUMERICA

    if n_unicos <= LIMITE_CATEGORICAS or n_unicos / nulos <= 0.5:
        return CATEGORICA
    return TEXTO


def perfilar(df: pd.DataFrame) -> list[ColunaInfo]:
    """Devolve o perfil de todas as colunas do DataFrame."""
    perfil = []
    for nome in df.columns:
        serie = df[nome]
        nao_nulos = serie.dropna()
        perfil.append(ColunaInfo(
            nome=str(nome),
            tipo=classificar_coluna(serie),
            total=int(len(serie)),
            nulos=int(serie.isna().sum()),
            n_unicos=int(nao_nulos.nunique()),
            exemplos=[str(v) for v in nao_nulos.unique()[:3]],
        ))
    return perfil
