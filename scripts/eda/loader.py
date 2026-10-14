"""Leitura e perfil de arquivos CSV.

Responsável por ler o arquivo de forma tolerante (compressão, encoding,
separador, decimal brasileiro, linhas malformadas) e por classificar cada
coluna como numérica, categórica, data ou texto livre. Essa classificação é a
base de todo o notebook: as análises só são criadas para os tipos que existem.
"""

from __future__ import annotations

import bz2
import codecs
import contextlib
import csv
import gzip
import io
import lzma
import re
import warnings
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .apoio import (
    converter_datas,
    detectar_formato_data,
    normalizar_para_numerico,
    padronizar_colunas,
    parece_nome_de_id,
    plural,
)

NUMERICA = "numerica"
CATEGORICA = "categorica"
DATA = "data"
TEXTO = "texto"

# Um texto com muitos valores distintos não serve para gráficos de frequência.
LIMITE_CATEGORICAS = 50
# Fração de valores que precisam ser interpretáveis como número.
LIMITE_CONVERSAO_NUMERICA = 0.90
# Tamanho da amostra usada para decidir o tipo de uma coluna de texto.
AMOSTRA_CLASSIFICACAO = 5_000
# Ordem de desempate na detecção do separador.
SEPARADORES = [";", "\t", "|", ","]
APELIDOS_SEPARADOR = {"\\t": "\t", "tab": "\t", "tabulacao": "\t", "tabulação": "\t"}
COMPRESSOES = {".gz": "gzip", ".bz2": "bz2", ".xz": "xz", ".zip": "zip"}


class ErroLeitura(ValueError):
    """O arquivo não pôde ser lido como CSV (mensagem em português)."""


@dataclass
class Leitura:
    """Resultado de `carregar_csv`: os dados e como foram lidos."""

    df: pd.DataFrame
    parametros: dict  # argumentos exatos de pd.read_csv, repetidos no notebook
    avisos: list[str] = field(default_factory=list)

    @property
    def separador(self) -> str:
        return self.parametros["sep"]

    @property
    def encoding(self) -> str:
        return self.parametros["encoding"]


@dataclass
class ColunaInfo:
    """Perfil resumido de uma coluna do CSV."""

    nome: str
    tipo: str
    total: int
    nulos: int
    n_unicos: int
    exemplos: list
    formato_data: str | None = None
    parece_codigo: bool = False      # texto curto, sem espaços e único (ex.: "PRT-00012")
    indice_exportado: bool = False   # "Unnamed: 0" com 0, 1, 2... (índice salvo pelo pandas)

    @property
    def nulos_pct(self) -> float:
        return (self.nulos / self.total * 100) if self.total else 0.0

    @property
    def nao_nulos(self) -> int:
        return self.total - self.nulos

    @property
    def binaria(self) -> bool:
        return self.tipo == NUMERICA and self.n_unicos == 2

    @property
    def identificador(self) -> bool:
        """True quando a coluna identifica registros (id, cpf, índice exportado...)."""
        if self.indice_exportado:
            return True
        if self.nao_nulos == 0:
            return False
        if (parece_nome_de_id(self.nome) and self.nao_nulos >= 10
                and self.n_unicos / self.nao_nulos >= 0.95):
            return True
        return self.tipo == TEXTO and self.n_unicos == self.nao_nulos and self.parece_codigo


# ------------------------------------------------------------------- leitura

def _ler_bytes(caminho: Path, n_bytes: int) -> bytes:
    """Lê até `n_bytes` (já descomprimidos) do início do arquivo."""
    compressao = COMPRESSOES.get(caminho.suffix.lower())
    if compressao == "zip":
        with zipfile.ZipFile(caminho) as arquivo_zip:
            membros = [m for m in arquivo_zip.infolist() if not m.is_dir()]
            if len(membros) != 1:
                nomes = ", ".join(m.filename for m in membros) or "nenhum"
                raise ErroLeitura(f"O ZIP precisa conter exatamente um arquivo; contém: {nomes}. "
                                  "Extraia o CSV desejado e rode de novo.")
            if len(arquivo_zip.infolist()) > 1:
                raise ErroLeitura(f"O ZIP guarda {membros[0].filename} dentro de uma pasta, e o pandas "
                                  "só lê ZIP com um único item. Extraia o CSV e rode de novo.")
            with arquivo_zip.open(membros[0]) as arquivo:
                return arquivo.read(n_bytes)
    abrir = {"gzip": gzip.open, "bz2": bz2.open, "xz": lzma.open}.get(compressao, open)
    with abrir(caminho, "rb") as arquivo:
        return arquivo.read(n_bytes)


def detectar_encoding(amostra: bytes) -> str:
    """utf-8 (com ou sem BOM), cp1252 (Excel no Windows) ou latin-1."""
    if amostra.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if amostra.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    try:
        # Decodificador incremental: um caractere cortado no fim da amostra não é erro.
        codecs.getincrementaldecoder("utf-8")().decode(amostra, final=False)
        return "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        amostra.decode("cp1252")
        return "cp1252"
    except UnicodeDecodeError:  # bytes 0x81, 0x8D, 0x8F, 0x90 e 0x9D não existem em cp1252
        return "latin-1"


def detectar_separador(linhas: list[str]) -> str:
    """Escolhe o separador que divide cabeçalho e linhas no mesmo número de campos.

    Um candidato é consistente quando o cabeçalho tem mais de um campo e ao
    menos 90% das linhas têm esse mesmo número de campos (aspas respeitadas).
    Sem nenhum consistente, vale o que divide a maioria das linhas nesse número
    ou em um a mais (separador sobrando no fim); as demais são malformadas e
    ignoradas na leitura. Sem nenhum, o arquivo tem uma coluna só e o separador
    devolvido é um caractere que não aparece no texto.
    """
    linhas = [linha for linha in linhas if linha.strip()][:201]
    candidatos = []  # (separador, campos do cabeçalho, moda das linhas, fração com a moda)
    for separador in SEPARADORES:
        try:
            campos = [len(registro) for registro in csv.reader(linhas, delimiter=separador)]
        except csv.Error:  # caractere nulo ou aspas inválidas
            continue
        if not campos or campos[0] <= 1:
            continue
        resto = campos[1:]
        moda, frequencia = Counter(resto).most_common(1)[0] if resto else (campos[0], 1)
        candidatos.append((separador, campos[0], moda, frequencia / max(len(resto), 1)))
    for aceitos in ([c for c in candidatos if c[2] == c[1] and c[3] >= 0.9],
                    [c for c in candidatos if c[2] in (c[1], c[1] + 1) and c[3] >= 0.5]):
        if aceitos:
            return max(aceitos, key=lambda c: c[1])[0]
    return next((s for s in SEPARADORES if not any(s in linha for linha in linhas)), ",")


def ler_amostra(caminho, n_bytes: int = 65_536) -> tuple[str, str, str]:
    """Lê o início do arquivo e devolve (texto, separador, encoding)."""
    caminho = Path(caminho)
    amostra = _ler_bytes(caminho, n_bytes)
    encoding = detectar_encoding(amostra)
    texto = codecs.getincrementaldecoder(encoding)().decode(amostra, final=False)
    linhas = texto.splitlines()
    if len(amostra) == n_bytes and len(linhas) > 1:
        linhas = linhas[:-1]  # a última linha provavelmente foi cortada
    return texto, detectar_separador(linhas), encoding


def _decimal_virgula(texto: str, separador: str) -> bool:
    """True se a amostra traz números com vírgula decimal fora de aspas (1,5 · 3.188,44)."""
    if separador == ",":
        return False
    linhas = texto.splitlines()[1:200]
    numero = re.compile(r"\s*[-+]?\d[\d.]*,\d+\s*")
    for registro in csv.reader(linhas, delimiter=separador):
        if any(numero.fullmatch(campo) for campo in registro):
            return True
    return False


def _colunas_pontuadas(texto: str, separador: str) -> list[int]:
    """Posições de colunas com números pontuados que não são milhar (05.03.2024, 1.2.3, IPs).

    Com thousands=".", o pandas leria esses valores como inteiros (5032024);
    por isso essas colunas são lidas como texto.
    """
    pontuado = re.compile(r"\s*[-+]?\d+(\.\d+)+\s*")
    milhar = re.compile(r"\s*[-+]?[1-9]\d{0,2}(\.\d{3})+(,\d+)?\s*")
    posicoes = set()
    for registro in csv.reader(texto.splitlines()[1:200], delimiter=separador):
        posicoes.update(i for i, campo in enumerate(registro)
                        if pontuado.fullmatch(campo) and not milhar.fullmatch(campo))
    return sorted(posicoes)


def _ler_csv(caminho: Path, parametros: dict) -> tuple[pd.DataFrame, list[int], bool]:
    """pd.read_csv que, diante de linhas malformadas, relê ignorando-as.

    Devolve (df, números das linhas ignoradas, se algum campo foi descartado).
    O descarte acontece quando a 1ª linha de dados tem um campo a mais que o
    cabeçalho: com index_col=False o pandas corta esse campo em silêncio (só
    emite um ParserWarning). Quando há linhas ignoradas, `parametros` ganha
    on_bad_lines="skip" para o notebook repetir a leitura.
    """
    # O pandas 2.1+ avisa com ParserWarning; o 2.0 escreve no stderr. Os dois são capturados.
    stderr = io.StringIO()
    with warnings.catch_warnings(record=True) as capturados, contextlib.redirect_stderr(stderr):
        warnings.simplefilter("always", pd.errors.ParserWarning)
        try:
            df = pd.read_csv(caminho, **parametros)
        except pd.errors.ParserError:
            df = pd.read_csv(caminho, **parametros, on_bad_lines="warn")
            parametros["on_bad_lines"] = "skip"
    for aviso in capturados:  # outros avisos seguem adiante
        if not issubclass(aviso.category, pd.errors.ParserWarning):
            warnings.warn_explicit(aviso.message, aviso.category, aviso.filename, aviso.lineno)
    mensagens = " ".join([str(aviso.message) for aviso in capturados] + [stderr.getvalue()])
    linhas = [int(n) for n in re.findall(r"Skipping line (\d+)", mensagens)]
    return df, linhas, "Length of header or names does not match" in mensagens


def _avisos_nomes_do_pandas(df: pd.DataFrame, texto: str, separador: str) -> list[str]:
    """Aviso para nomes repetidos ou vazios que o pandas trocou ('dup' → 'dup.1', '' → 'Unnamed: 2').

    As colunas `Unnamed` 100% vazias ficam de fora: padronizar_colunas remove e avisa.
    O índice salvo por df.to_csv() também: o perfil já o reconhece.
    """
    primeira = next((linha for linha in texto.splitlines() if linha.strip()), "")
    cabecalho = next(csv.reader([primeira], delimiter=separador), [])
    if len(cabecalho) != df.shape[1]:
        return []
    trocas = [f"{original!r} → {nome!r}" if original.strip() else f"(sem nome) → {nome!r}"
              for posicao, (original, nome) in enumerate(zip(cabecalho, df.columns))
              if original != nome
              and not (str(nome).startswith("Unnamed: ") and df.iloc[:, posicao].isna().all())
              and not (posicao == 0 and _indice_exportado(str(nome), df.iloc[:, 0].dropna()))]
    if not trocas:
        return []
    return [f"Nomes de coluna repetidos ou vazios no cabeçalho foram trocados: {'; '.join(trocas)}."]


def resolver_separador(separador: str) -> str:
    """Aceita apelidos (\\t, tab) e exige um único caractere."""
    resolvido = APELIDOS_SEPARADOR.get(separador.lower(), separador) if len(separador) > 1 else separador
    if len(resolvido) != 1:
        raise ErroLeitura(f"Separador inválido: {separador!r}. Use um único caractere "
                          "(',', ';', '|') ou tab.")
    return resolvido


def carregar_csv(caminho, separador: str | None = None, encoding: str | None = None,
                 decimal: str | None = None) -> Leitura:
    """Lê o CSV detectando o que não foi informado. Lança ErroLeitura em pt-BR."""
    caminho = Path(caminho).expanduser()
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    if caminho.is_dir():
        raise ErroLeitura(f"{caminho} é uma pasta, não um arquivo CSV.")
    if caminho.stat().st_size == 0:
        raise ErroLeitura(f"O arquivo {caminho.name} está vazio (0 bytes).")
    if separador is not None:
        separador = resolver_separador(separador)
    if encoding:
        try:
            "".encode(encoding)  # LookupError também para codecs que não são de texto (hex, zlib)
        except LookupError:
            raise ErroLeitura(f"Encoding desconhecido: {encoding!r}. "
                              "Exemplos válidos: utf-8, cp1252, latin-1.") from None
    try:
        texto, sep_detectado, enc_detectado = ler_amostra(caminho)
    except (OSError, EOFError, zipfile.BadZipFile, lzma.LZMAError) as erro:
        raise ErroLeitura(f"Não foi possível abrir {caminho.name}: {erro}") from None

    parametros = {"sep": separador or sep_detectado, "encoding": encoding or enc_detectado}
    decimal = decimal or ("," if _decimal_virgula(texto, parametros["sep"]) else ".")
    if decimal == ",":
        parametros.update(decimal=",", thousands=".")
        pontuadas = _colunas_pontuadas(texto, parametros["sep"])
        if pontuadas:
            parametros["dtype"] = {posicao: "str" for posicao in pontuadas}
    compressao = COMPRESSOES.get(caminho.suffix.lower())
    if compressao:
        parametros["compression"] = compressao
    # index_col=False impede o pandas de usar a 1ª coluna como índice quando as
    # linhas têm um campo a mais que o cabeçalho.
    parametros.update(index_col=False, low_memory=False)

    avisos = []
    tentativas = [encoding] if encoding else list(dict.fromkeys(
        [enc_detectado, "utf-8", "cp1252", "latin-1"]))
    for tentativa in tentativas:
        parametros["encoding"] = tentativa
        try:
            df, linhas_ruins, campo_descartado = _ler_csv(caminho, parametros)
            break
        except UnicodeDecodeError:
            if encoding:
                raise ErroLeitura(f"O arquivo não está em {encoding}. Rode sem --encoding "
                                  "para detectar automaticamente.") from None
        except pd.errors.EmptyDataError:
            raise ErroLeitura(f"O arquivo {caminho.name} não tem colunas "
                              "(vazio ou só linhas em branco).") from None
        except pd.errors.ParserError as erro:
            raise ErroLeitura(f"Não foi possível interpretar o CSV: {erro}") from None
    if tentativa != enc_detectado and not encoding:
        avisos.append(f"O início do arquivo parecia {enc_detectado}, mas há bytes inválidos "
                      f"adiante: lido como {tentativa}.")
    if "on_bad_lines" in parametros and not linhas_ruins:
        avisos.append("Linhas malformadas (campos a mais) foram ignoradas.")
    if linhas_ruins:
        lista = ", ".join(str(n) for n in linhas_ruins[:10])
        avisos.append(f"{plural(len(linhas_ruins), 'linha malformada ignorada', 'linhas malformadas ignoradas')} "
                      f"(campos a mais; {'linha' if len(linhas_ruins) == 1 else 'linhas'} {lista}"
                      f"{'...' if len(linhas_ruins) > 10 else ''}).")

    if campo_descartado:
        avisos.append("A 1ª linha de dados tem um campo a mais que o cabeçalho: o último campo "
                      "dela e das linhas na mesma situação foi descartado. Confira o separador (--sep).")
    avisos += _avisos_nomes_do_pandas(df, texto, parametros["sep"])

    df, avisos_colunas = padronizar_colunas(df)
    avisos += avisos_colunas
    if df.shape[1] == 0:
        raise ErroLeitura(f"O arquivo {caminho.name} não tem colunas com dados.")
    if df.empty:
        raise ErroLeitura(f"O arquivo {caminho.name} só tem o cabeçalho, sem linhas de dados.")
    return Leitura(df=df, parametros=parametros, avisos=avisos)


# --------------------------------------------------------------------- perfil

def _e_texto(serie: pd.Series) -> bool:
    return pd.api.types.is_object_dtype(serie) or pd.api.types.is_string_dtype(serie)


def _classificar(serie: pd.Series) -> tuple[str, str | None]:
    """Devolve (tipo, formato de data). A decisão usa uma amostra de até 5.000 valores."""
    nao_nulos = serie.dropna()
    if nao_nulos.empty or pd.api.types.is_bool_dtype(serie):
        return CATEGORICA, None
    if pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_complex_dtype(serie):
        return NUMERICA, None
    if pd.api.types.is_datetime64_any_dtype(serie):
        return DATA, None
    if not _e_texto(serie):
        return CATEGORICA, None

    amostra = nao_nulos
    if len(amostra) > AMOSTRA_CLASSIFICACAO:
        amostra = amostra.sample(AMOSTRA_CLASSIFICACAO, random_state=0)
    amostra = amostra.astype(str).str.strip()
    amostra = amostra[amostra != ""]
    if amostra.empty:
        return CATEGORICA, None

    formato = detectar_formato_data(amostra)
    if formato:
        return DATA, formato
    if normalizar_para_numerico(amostra).notna().mean() >= LIMITE_CONVERSAO_NUMERICA:
        return NUMERICA, None
    n_unicos = nao_nulos.nunique()
    if n_unicos <= LIMITE_CATEGORICAS or n_unicos / len(nao_nulos) <= 0.5:
        return CATEGORICA, None
    return TEXTO, None


def classificar_coluna(serie: pd.Series) -> str:
    """Retorna NUMERICA, CATEGORICA, DATA ou TEXTO para uma série."""
    return _classificar(serie)[0]


def _indice_exportado(nome: str, nao_nulos: pd.Series) -> bool:
    """`Unnamed: N` com inteiros únicos e consecutivos: índice salvo por df.to_csv()."""
    if not re.fullmatch(r"Unnamed: \d+", nome) or not pd.api.types.is_integer_dtype(nao_nulos):
        return False
    return nao_nulos.is_unique and bool((nao_nulos.sort_values().diff().dropna() == 1).all())


def perfilar(df: pd.DataFrame, tipos: dict[str, str] | None = None) -> list[ColunaInfo]:
    """Perfil de todas as colunas. `tipos` fixa o tipo de colunas já classificadas."""
    perfil = []
    for nome in df.columns:
        serie = df[nome]
        if tipos and nome in tipos:
            tipo, formato = tipos[nome], None
        else:
            tipo, formato = _classificar(serie)
        nao_nulos = serie.dropna()
        n_unicos = int(nao_nulos.nunique())
        codigo = False
        if tipo == TEXTO and n_unicos == len(nao_nulos) and _e_texto(serie):
            texto = nao_nulos.astype(str)
            codigo = (not texto.str.contains(r"\s").any()) and texto.str.len().median() <= 40
        perfil.append(ColunaInfo(
            nome=str(nome),
            tipo=tipo,
            total=int(len(serie)),
            nulos=int(len(serie) - len(nao_nulos)),
            n_unicos=n_unicos,
            exemplos=[str(v) for v in nao_nulos.unique()[:3]],
            formato_data=formato,
            parece_codigo=bool(codigo),
            indice_exportado=_indice_exportado(str(nome), nao_nulos),
        ))
    return perfil


def avisos_do_perfil(df: pd.DataFrame, perfil: list[ColunaInfo]) -> list[str]:
    """Avisos sobre suposições feitas na classificação (datas ambíguas, índice exportado)."""
    avisos = []
    for info in perfil:
        if info.indice_exportado:
            avisos.append(f"{info.nome} parece índice exportado (0, 1, 2...): tratada como "
                          "identificador, fora das análises.")
        if info.formato_data and info.formato_data.startswith("%d"):
            dias = converter_datas(df[info.nome], info.formato_data).dt.day
            if dias.notna().any() and dias.max() <= 12:
                avisos.append(f"Datas ambíguas em {info.nome}: todos os dias são <= 12, "
                              "interpretadas como dia/mês (padrão brasileiro).")
    return avisos
