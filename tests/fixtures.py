"""Fixtures CSV determinísticas (plano, seção 7.2).

Nada aqui é versionado como arquivo: cada CSV é gerado sob demanda em um
diretório temporário pela classe `Fabrica`. Os nomes aceitos estão em
`NOMES`; `GABARITO` traz os valores esperados de algumas fixtures.
"""

from __future__ import annotations

import gzip
import io
import zipfile
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = RAIZ / "exemplos" / "vendas_exemplo.csv"

_CONSTRUTORES: dict[str, tuple[str, Callable[[], bytes]]] = {}


def _fixture(nome: str, arquivo: str):
    def registrar(funcao: Callable[[], bytes]) -> Callable[[], bytes]:
        _CONSTRUTORES[nome] = (arquivo, funcao)
        return funcao
    return registrar


def _csv(df: pd.DataFrame, **kwargs) -> bytes:
    """CSV em UTF-8 com quebra de linha LF em qualquer sistema operacional."""
    kwargs.setdefault("index", False)
    return df.to_csv(lineterminator="\n", **kwargs).encode("utf-8")


def _linhas(linhas: list[str], encoding: str = "utf-8", fim: str = "\n") -> bytes:
    return (fim.join(linhas) + fim).encode(encoding)


def _br(valor: float) -> str:
    """1234.5 -> '1.234,50'."""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _gzip(conteudo: bytes) -> bytes:
    return gzip.compress(conteudo, mtime=0)


def _zip(membros: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as arquivo_zip:
        for nome, conteudo in membros.items():
            info = zipfile.ZipInfo(nome, date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            arquivo_zip.writestr(info, conteudo)
    return buffer.getvalue()


# ---------------------------------------------------------------- gabaritos

DATAS_ISO = pd.date_range("2024-01-01", periods=60, freq="5D")          # F03
DATAS_BR = pd.date_range("2024-01-01", periods=90, freq="D")            # F04 / F05
DATAS_AMBIGUAS = pd.DatetimeIndex(                                      # F04b
    [pd.Timestamp(2024, mes, dia) for mes in range(1, 7) for dia in range(1, 11)])
DATAS_SEMANAIS = pd.date_range("2020-01-01", periods=50, freq="W")      # F24


def _dados_br() -> tuple[list[str], dict[str, list]]:
    rng = np.random.default_rng(0)
    regioes = ["São Paulo", "Paraná", "Ceará", "Goiás", "Pará"]
    linhas = ["Região;Preço;Valor total;Data venda;Observação"]
    gabarito: dict[str, list] = {"Preço": [], "Valor total": [], "Data venda": []}
    for i in range(60):
        preco = round(float(rng.uniform(10, 5000)), 2)
        total = round(preco * int(rng.integers(1, 5)), 2)
        dia, mes = i % 28 + 1, i % 12 + 1
        linhas.append(f"{regioes[i % 5]};{_br(preco)};R$ {_br(total)};"
                      f"{dia:02d}/{mes:02d}/2023;ação nº {i}")
        gabarito["Preço"].append(preco)
        gabarito["Valor total"].append(total)
        gabarito["Data venda"].append(f"2023-{mes:02d}-{dia:02d}")
    linhas.append("São Paulo;1,50;R$ 1,50;15/06/2023;Café “especial” – € 1,50")
    gabarito["Preço"].append(1.5)
    gabarito["Valor total"].append(1.5)
    gabarito["Data venda"].append("2023-06-15")
    return linhas, gabarito


GABARITO = {
    "br_cp1252": _dados_br()[1],
    "br_cp1252_observacao_especial": "Café “especial” – € 1,50",
    "milhar_ptbr": {"estoque": [1000 + 137 * i for i in range(40)],
                    "preco": [i + 0.5 for i in range(40)]},
    "uma_coluna_virgula": [i + 0.5 for i in range(1, 31)],
}


# ---------------------------------------------------------------- F01–F26

@_fixture("exemplo", "vendas_exemplo.csv")                       # F01
def _exemplo() -> bytes:
    return EXEMPLO.read_bytes()


@_fixture("br_cp1252", "br_cp1252.csv")                          # F02
def _br_cp1252() -> bytes:
    return _linhas(_dados_br()[0], encoding="cp1252", fim="\r\n")


@_fixture("iso_datas", "iso_datas.csv")                          # F03
def _iso_datas() -> bytes:
    return _csv(pd.DataFrame({"dt": DATAS_ISO.strftime("%Y-%m-%d"),
                              "tipo": ["a", "b"] * 30,
                              "valor": range(60)}))


@_fixture("datas_br", "datas_br.csv")                            # F04
def _datas_br() -> bytes:
    rng = np.random.default_rng(0)
    return _csv(pd.DataFrame({"data": DATAS_BR.strftime("%d/%m/%Y"),
                              "vendas": rng.integers(0, 100, 90),
                              "loja": ["A", "B", "C"] * 30}))


@_fixture("datas_br_ambiguas", "datas_br_ambiguas.csv")          # F04b
def _datas_br_ambiguas() -> bytes:
    rng = np.random.default_rng(0)
    return _csv(pd.DataFrame({"data": DATAS_AMBIGUAS.strftime("%d/%m/%Y"),
                              "vendas": rng.integers(0, 100, len(DATAS_AMBIGUAS))}))


@_fixture("datas_us", "datas_us.csv")                            # F05
def _datas_us() -> bytes:
    rng = np.random.default_rng(1)
    return _csv(pd.DataFrame({"date": DATAS_BR.strftime("%m/%d/%Y"),
                              "sales": rng.integers(0, 100, 90)}))


@_fixture("so_categoricas", "so_categoricas.csv")                # F06
def _so_categoricas() -> bytes:
    return _csv(pd.DataFrame({"cor": ["azul", "verde", "vermelho"] * 20,
                              "tamanho": ["P", "M", "G", "GG"] * 15}))


@_fixture("dup_com_id", "dup_com_id.csv")                        # F07
def _dup_com_id() -> bytes:
    # 40 linhas únicas + 2 repetidas (mesmo id). O plano fala em 30 + 2, mas
    # aí id teria 30/32 = 0,94 valores únicos, abaixo do limite de 0,95 da
    # regra de identificador (D20), e nada seria removido.
    linhas = ["id,grupo,valor"] + [f"{i},g{i % 3},{i * 1.5}" for i in range(1, 41)]
    linhas += [linhas[5], linhas[10]]
    return _linhas(linhas)


@_fixture("uma_coluna_virgula", "uma_coluna_virgula.csv")        # F08
def _uma_coluna_virgula() -> bytes:
    return _linhas(["valor"] + [f"{i},5" for i in range(1, 31)])


@_fixture("milhar_ptbr", "milhar_ptbr.csv")                      # F09
def _milhar_ptbr() -> bytes:
    linhas = ["produto;estoque;preco"]
    linhas += [f"P{i % 6};{1000 + 137 * i:,}".replace(",", ".") + f";{i},50" for i in range(40)]
    return _linhas(linhas)


@_fixture("br_cp1252_gz", "br_cp1252.csv.gz")                    # F10
def _br_cp1252_gz() -> bytes:
    return _gzip(_br_cp1252())


@_fixture("br_cp1252_zip", "br_cp1252.csv.zip")                  # F10
def _br_cp1252_zip() -> bytes:
    return _zip({"br_cp1252.csv": _br_cp1252()})


@_fixture("exemplo_gz", "vendas_exemplo.csv.gz")                 # F10
def _exemplo_gz() -> bytes:
    return _gzip(_exemplo())


@_fixture("exemplo_zip", "vendas_exemplo.csv.zip")               # F10
def _exemplo_zip() -> bytes:
    return _zip({"vendas_exemplo.csv": _exemplo()})


@_fixture("zip_dois_membros", "dois_membros.csv.zip")            # F10
def _zip_dois_membros() -> bytes:
    return _zip({"primeiro.csv": b"a,b\n1,2\n", "segundo.csv": b"a,b\n3,4\n"})


def _tres_colunas(separador: str) -> bytes:
    linhas = [separador.join(["a", "grupo", "v"])]
    linhas += [separador.join([str(i), "xyz"[i % 3], f"{i / 29:.4f}"]) for i in range(30)]
    return _linhas(linhas)


@_fixture("tsv", "dados.tsv")                                    # F11
def _tsv() -> bytes:
    return _tres_colunas("\t")


@_fixture("pipe", "pipe.csv")                                    # F11
def _pipe() -> bytes:
    return _tres_colunas("|")


@_fixture("malformado", "malformado.csv")                        # F12
def _malformado() -> bytes:
    return _linhas(["a,b,c", "1,2,3", "4,5,6,7", "7,8,9"] + [f"{i},{i},{i}" for i in range(30)])


@_fixture("vazio", "vazio.csv")                                  # F13
def _vazio() -> bytes:
    return b""


@_fixture("so_cabecalho", "so_cabecalho.csv")                    # F13
def _so_cabecalho() -> bytes:
    return b"a,b,c\n"


@_fixture("nomes_estranhos", "nomes_estranhos.csv")              # F14
def _nomes_estranhos() -> bytes:
    cabecalho = '"nome com espaço","preço (R$)","diz ""oi""","valor","valor ","Unnamed: 0"'
    linhas = [f'"a{i % 3}",{i}.5,"x{i % 4}",{i},{i * 2},{i}' for i in range(40)]
    return _linhas([cabecalho] + linhas)


@_fixture("aspas_nomes", "aspas_nomes.csv")                      # F14b
def _aspas_nomes() -> bytes:
    return _linhas(['grupo "A",tipo\\b,valor'] + [f"g{i % 3},t{i % 2},{i}" for i in range(30)])


@_fixture("nomes_sinistros", "nomes_sinistros.csv")              # 7.3: " ' \ { } ` | e acentos
def _nomes_sinistros() -> bytes:
    rng = np.random.default_rng(0)
    n = 40
    return _csv(pd.DataFrame({
        'cat "A"': ["a", "b", "c", "d"] * 10,
        "cat 'B'": ["x", "y"] * 20,
        "pipe | w": ["p", "q", "r", "s", "t"] * 8,
        "num\\x": rng.normal(10, 2, n).round(2),
        "num {y}": rng.normal(50, 5, n).round(2),
        "crase `z`": rng.integers(0, 100, n),
        "ação": rng.normal(0, 1, n).round(3),
        "data {d}": pd.date_range("2024-01-01", periods=n, freq="7D").strftime("%Y-%m-%d"),
    }))


@_fixture("com_indice", "com_indice.csv")                        # F15
def _com_indice() -> bytes:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"x": rng.normal(size=40).round(3), "g": ["a", "b"] * 20})
    return _csv(df, index=True)


@_fixture("sep_sobrando", "sep_sobrando.csv")                    # F16
def _sep_sobrando() -> bytes:
    return _linhas(["a;b;c;"] + [f"{i};{i % 3};x{i % 2};" for i in range(40)])


@_fixture("ausentes", "ausentes.csv")                            # F17
def _ausentes() -> bytes:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"v1": rng.normal(size=100), "v2": rng.normal(size=100),
                       "g": rng.choice(list("abc"), 100)})
    df.loc[rng.random(100) < 0.7, "v1"] = np.nan
    df.loc[rng.random(100) < 0.95, "v2"] = np.nan
    df["vazia"] = np.nan
    return _csv(df)


@_fixture("larga", "larga.csv")                                  # F18
def _larga() -> bytes:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({f"col_{i:02d}": rng.normal(i, 1 + i, 200).round(3) for i in range(35)})
    for j in range(8):
        df[f"cat_{j}"] = rng.choice(list("ABCDE"), 200)
    return _csv(df)


@_fixture("churn", "churn.csv")                                  # F19
def _churn() -> bytes:
    rng = np.random.default_rng(0)
    n = 300
    x1 = rng.normal(0, 1, n)
    plano = rng.choice(["a", "b", "c"], n)
    churn = (x1 + (plano == "a") * 1.0 + rng.normal(0, 1, n) > 0.8).astype(int)
    return _csv(pd.DataFrame({
        "cliente_id": range(n), "idade": rng.integers(18, 80, n),
        "renda": np.exp(rng.normal(8, 1, n)).round(2), "x1": x1.round(3),
        "plano": plano, "churn": churn, "ativo": rng.integers(0, 2, n),
        "status": rng.choice(["ok", "atraso", "cancelado"], n),
    }))


@_fixture("qualidade", "qualidade.csv")                          # F20
def _qualidade() -> bytes:
    rng = np.random.default_rng(0)
    return _csv(pd.DataFrame({
        "regiao": ["Sudeste", "sudeste", "Sudeste ", "SUDESTE", "Sul", "sul", "Nordeste"] * 10,
        "preco": list(rng.uniform(1, 100, 69).round(2)) + [-5.0],
        "constante": ["X"] * 70,
    }))


@_fixture("grande", "grande.csv")                                # F21
def _grande() -> bytes:
    rng = np.random.default_rng(0)
    n = 200_000
    datas = pd.Timestamp("2022-01-01") + pd.to_timedelta(rng.integers(0, 900, n), unit="D")
    df = pd.DataFrame({
        "id": np.arange(n),
        "data": pd.Series(datas).dt.strftime("%d/%m/%Y"),
        "loja": rng.choice([f"Loja {i}" for i in range(30)], n),
        "categoria": rng.choice(["A", "B", "C", "D"], n),
        "valor": np.exp(rng.normal(4, 1, n)).round(2),
        "qtd": rng.integers(1, 20, n),
        "obs": [f"pedido {i} cliente {i % 9973}" for i in range(n)],
    })
    return _csv(df, sep=";", decimal=",")


@_fixture("degenerados", "degenerados.csv")                      # F22
def _degenerados() -> bytes:
    rng = np.random.default_rng(0)
    n = 60
    com_inf = rng.normal(10, 2, n).round(2)
    com_inf[3], com_inf[7] = np.inf, -np.inf
    quase_vazia = np.full(n, np.nan)
    quase_vazia[:2] = [1.0, 2.0]
    return _csv(pd.DataFrame({"constante_num": 5.0, "com_inf": com_inf,
                              "quase_vazia": quase_vazia,
                              "v": rng.normal(0, 1, n).round(3),
                              "g": ["a", "b", "c"] * 20}))


@_fixture("uma_numerica", "uma_numerica.csv")                    # F23
def _uma_numerica() -> bytes:
    rng = np.random.default_rng(0)
    return _csv(pd.DataFrame({"valor": rng.normal(100, 15, 200).round(2)}))


@_fixture("so_datas", "so_datas.csv")                            # F24
def _so_datas() -> bytes:
    return _csv(pd.DataFrame({"dt": DATAS_SEMANAIS.strftime("%Y-%m-%d"), "tipo": ["a", "b"] * 25}))


@_fixture("aspas_ponto_virgula", "aspas_ponto_virgula.csv")      # F25
def _aspas_ponto_virgula() -> bytes:
    return _linhas(["descricao;valor;qtd"] + [f'"produto, tipo {i}";{i},5;{i}' for i in range(30)])


@_fixture("espaco_categoria", "espaco_categoria.csv")            # F26
def _espaco_categoria() -> bytes:
    return _linhas(["cat,v"] + [f"{['X', ' X', 'Y'][i % 3]},{i}" for i in range(30)])


@_fixture("serie_lacuna", "serie_lacuna.csv")                    # D05: 2024 diário sem junho
def _serie_lacuna() -> bytes:
    rng = np.random.default_rng(0)
    datas = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    datas = datas[datas.month != 6]
    n = len(datas)
    return _csv(pd.DataFrame({"data": datas.strftime("%Y-%m-%d"),
                              "quantidade": rng.integers(1, 15, n),
                              "valor_total": rng.normal(670, 100, n).round(2),
                              "canal": rng.choice(["online", "loja"], n)}))


@_fixture("colisoes", "colisoes.csv")    # nomes e valores que coincidem com os do código gerado
def _colisoes() -> bytes:
    rng = np.random.default_rng(1)
    n = 120
    return _csv(pd.DataFrame({
        "data": pd.date_range("2024-01-01", periods=n, freq="D").strftime("%Y-%m-%d"),
        "registros": rng.integers(1, 50, n),
        "n": rng.normal(10, 2, n).round(2),
        "situacao": rng.choice(["Total", "Parcial", "Nenhum"], n),
        "churn": rng.choice(np.array(["Sim", "Não", None], dtype=object), n, p=[0.3, 0.6, 0.1]),
    }))


NOMES = sorted(_CONSTRUTORES) + ["diretorio"]


class Fabrica:
    """Escreve as fixtures em `diretorio` sob demanda (uma vez por nome)."""

    def __init__(self, diretorio: Path):
        self.diretorio = Path(diretorio)

    def __call__(self, nome: str) -> Path:
        self.diretorio.mkdir(parents=True, exist_ok=True)
        if nome == "diretorio":                                  # F13
            caminho = self.diretorio / "uma_pasta.csv"
            caminho.mkdir(exist_ok=True)
            return caminho
        arquivo, construtor = _CONSTRUTORES[nome]
        caminho = self.diretorio / arquivo
        if not caminho.exists():
            caminho.write_bytes(construtor())
        return caminho

