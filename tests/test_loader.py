"""Leitura, detecção e perfil (scripts/eda/loader.py; plano, 6.2 e 7.3)."""

from __future__ import annotations

import codecs
import re
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eda.apoio import normalizar_para_numerico, padronizar_colunas
from eda.loader import (
    CATEGORICA,
    DATA,
    NUMERICA,
    TEXTO,
    ErroLeitura,
    carregar_csv,
    classificar_coluna,
    detectar_encoding,
    detectar_separador,
    ler_amostra,
    perfilar,
)
from fixtures import GABARITO


def mesmo_encoding(obtido: str, esperado: str) -> bool:
    return codecs.lookup(obtido).name == codecs.lookup(esperado).name


def _por_nome(perfil):
    return {info.nome: info for info in perfil}


# ------------------------------------------------------------ separador

@pytest.mark.parametrize("linhas, esperado", [
    (["a,b,c", "1,2,3", "4,5,6"], ","),
    (["a;b;c", "1;2;3", "4;5;6"], ";"),
    (["a\tb\tc", "1\t2\t3", "4\t5\t6"], "\t"),
    (["a|b|c", "1|2|3", "4|5|6"], "|"),
    (["nome;valor"] + [f"item {i};{i},{i % 10}" for i in range(30)], ";"),
    (["descricao;valor;qtd"] + [f'"produto, tipo {i}";{i},5;{i}' for i in range(30)], ";"),  # F25
], ids=["virgula", "ponto_e_virgula", "tab", "pipe", "decimal_virgula", "aspas_com_virgula"])
def test_detectar_separador(linhas, esperado):
    assert detectar_separador(linhas) == esperado


@pytest.mark.parametrize("linhas, esperado", [
    (["id,comentario,valor"] + [f"{i},{'bom, muito' if i % 7 == 3 else 'ok'},{i}" for i in range(40)], ","),
    (["a;b;c"] + [f"{i};{i % 3};x;" for i in range(20)], ";"),   # ';' sobrando só nas linhas de dados
], ids=["virgulas_sem_aspas_15pct", "sep_sobrando_so_nos_dados"])
def test_detectar_separador_maioria_das_linhas(linhas, esperado):
    assert detectar_separador(linhas) == esperado


def test_detectar_separador_uma_coluna_com_virgula_decimal():
    linhas = ["valor"] + [f"{i},5" for i in range(1, 31)]                        # F08
    assert detectar_separador(linhas) != ","


# ------------------------------------------------------------ encoding

@pytest.mark.parametrize("amostra, esperado", [
    (b"a,b\n1,2\n", "utf-8"),
    ("Região;Preço\nSão Paulo;1,5\n".encode("utf-8"), "utf-8"),
    (codecs.BOM_UTF8 + "Região;Preço\n".encode("utf-8"), "utf-8-sig"),
    ("Café “especial” – € 1,50\nação\n".encode("cp1252"), "cp1252"),
    (b"abc\x81def\xe9\n", "latin-1"),                     # 0x81 não existe em cp1252
    (("x" * 50 + "é").encode("utf-8")[:-1], "utf-8"),    # "é" cortado no fim da amostra
], ids=["ascii", "utf8", "bom", "cp1252", "latin1", "utf8_cortado"])
def test_detectar_encoding(amostra, esperado):
    obtido = detectar_encoding(amostra)
    assert mesmo_encoding(obtido, esperado), f"{obtido!r} != {esperado!r}"


@pytest.mark.parametrize("nome", ["br_cp1252", "br_cp1252_gz", "br_cp1252_zip"])
def test_ler_amostra_texto_legivel(fabricar, nome):
    texto, separador, encoding = ler_amostra(fabricar(nome))
    assert separador == ";"
    assert mesmo_encoding(encoding, "cp1252"), encoding
    assert texto.startswith("Região;Preço;Valor total"), texto[:80]
    assert GABARITO["br_cp1252_observacao_especial"] in texto


def test_ler_amostra_nao_le_o_arquivo_inteiro(tmp_path, monkeypatch):
    """5 MB com 'é' cruzando o byte 65.536: só a amostra pode ser lida (D13)."""
    cabecalho = "texto,n\n" + "abcdefghij,1\n" * 5000
    linha_cortada = "a" * (65_535 - len(cabecalho)) + "é" + "b" * 10 + ",1\n"
    dados = (cabecalho + linha_cortada + "abcdefghij,1\n" * 380_000).encode("utf-8")
    assert dados.index("é".encode("utf-8")) == 65_535 and len(dados) > 5_000_000
    caminho = tmp_path / "grande_utf8.csv"
    caminho.write_bytes(dados)

    def proibido(*_args, **_kwargs):
        raise AssertionError("ler_amostra não pode ler o arquivo inteiro")

    monkeypatch.setattr(Path, "read_text", proibido)
    monkeypatch.setattr(Path, "read_bytes", proibido)
    texto, separador, encoding = ler_amostra(caminho, n_bytes=65_536)
    assert mesmo_encoding(encoding, "utf-8"), encoding
    assert separador == ","
    assert len(texto) <= 65_536


# ------------------------------------------------------------ carregar_csv

def test_carregar_csv_br_cp1252(fabricar):
    leitura = carregar_csv(fabricar("br_cp1252"))
    df = leitura.df
    assert leitura.separador == ";"
    assert mesmo_encoding(leitura.encoding, "cp1252"), leitura.encoding
    assert len(df) == 61
    assert df["Região"].iloc[0] == "São Paulo"
    assert df["Observação"].iloc[-1] == GABARITO["br_cp1252_observacao_especial"]
    assert pd.api.types.is_numeric_dtype(df["Preço"]), f"Preço lido como {df['Preço'].dtype}"
    np.testing.assert_allclose(df["Preço"].astype(float), GABARITO["br_cp1252"]["Preço"])


def test_carregar_csv_milhar_ptbr(fabricar):
    df = carregar_csv(fabricar("milhar_ptbr")).df
    np.testing.assert_allclose(df["estoque"].astype(float), GABARITO["milhar_ptbr"]["estoque"],
                               err_msg="'1.137' deveria virar 1137 (D09)")
    np.testing.assert_allclose(df["preco"].astype(float), GABARITO["milhar_ptbr"]["preco"])


@pytest.mark.parametrize("comprimido, original", [
    ("br_cp1252_gz", "br_cp1252"), ("br_cp1252_zip", "br_cp1252"),
    ("exemplo_gz", "exemplo"), ("exemplo_zip", "exemplo"),
])
def test_carregar_csv_comprimido_igual_ao_original(fabricar, comprimido, original):
    lido = carregar_csv(fabricar(comprimido))
    esperado = carregar_csv(fabricar(original))
    pd.testing.assert_frame_equal(lido.df, esperado.df)
    assert mesmo_encoding(lido.encoding, esperado.encoding)


def test_carregar_csv_malformado(fabricar):
    leitura = carregar_csv(fabricar("malformado"))
    assert len(leitura.df) == 32
    assert re.search(r"linha 3\b", " ".join(leitura.avisos)), leitura.avisos
    assert leitura.parametros.get("on_bad_lines") == "skip"


def test_carregar_csv_uma_coluna(fabricar):
    df = carregar_csv(fabricar("uma_coluna_virgula")).df
    assert list(df.columns) == ["valor"] and len(df) == 30, df.head()
    assert _por_nome(perfilar(df))["valor"].tipo == NUMERICA


@pytest.mark.parametrize("nome, separador", [("tsv", "\t"), ("pipe", "|")])
def test_carregar_csv_outros_separadores(fabricar, nome, separador):
    leitura = carregar_csv(fabricar(nome))
    assert leitura.separador == separador
    assert list(leitura.df.columns) == ["a", "grupo", "v"] and len(leitura.df) == 30


def test_carregar_csv_sep_sobrando(fabricar):
    leitura = carregar_csv(fabricar("sep_sobrando"))
    assert list(leitura.df.columns) == ["a", "b", "c"]
    assert leitura.avisos


def test_carregar_csv_coordenadas_negativas_ptbr(tmp_path):
    """Com thousands=".", -23.550520 e 0.125 não podem virar inteiros (-23550520, 125)."""
    caminho = tmp_path / "coordenadas.csv"
    caminho.write_text("cidade;valor;lat;peso\nC0;0,50;-23.550520;0.125\nC1;1.234,50;-22.906847;0.250\n",
                       encoding="utf-8")
    df = carregar_csv(caminho).df
    np.testing.assert_allclose(df["valor"], [0.5, 1234.5])
    np.testing.assert_allclose(normalizar_para_numerico(df["lat"]), [-23.55052, -22.906847])
    np.testing.assert_allclose(normalizar_para_numerico(df["peso"]), [0.125, 0.25])


def test_carregar_csv_zip_com_pasta(tmp_path):
    caminho = tmp_path / "dados.zip"
    with zipfile.ZipFile(caminho, "w") as arquivo_zip:
        arquivo_zip.writestr("dados/", "")
        arquivo_zip.writestr("dados/vendas.csv", "a,b\n1,2\n")
    with pytest.raises(ErroLeitura, match="pasta"):
        carregar_csv(caminho)


def test_carregar_csv_campo_a_mais_na_primeira_linha(tmp_path, capsys):
    """index_col=False descarta o campo excedente em silêncio; tem de virar aviso (sem vazar)."""
    caminho = tmp_path / "extra.csv"
    caminho.write_text("id,comentario,valor\n0,texto, com virgula,0\n"
                       + "".join(f"{i},ok,{i}\n" for i in range(1, 30)), encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("error", pd.errors.ParserWarning)
        leitura = carregar_csv(caminho)
    assert any("campo a mais" in aviso and "--sep" in aviso for aviso in leitura.avisos), leitura.avisos
    assert capsys.readouterr().err == ""


def test_carregar_csv_virgulas_sem_aspas(tmp_path):
    caminho = tmp_path / "comentarios.csv"
    caminho.write_text("id,comentario,valor\n" + "".join(
        f"{i},{'bom, muito bom' if i % 7 == 3 else 'ok'},{i}\n" for i in range(40)), encoding="utf-8")
    leitura = carregar_csv(caminho)
    assert list(leitura.df.columns) == ["id", "comentario", "valor"] and len(leitura.df) == 34
    assert re.search(r"6 linhas malformadas ignoradas", " ".join(leitura.avisos)), leitura.avisos


def test_carregar_csv_avisa_nomes_trocados_pelo_pandas(tmp_path):
    caminho = tmp_path / "nomes.csv"
    caminho.write_text("dup,dup,,x\n" + "".join(f"{i},{i},{i},{i}\n" for i in range(5)), encoding="utf-8")
    leitura = carregar_csv(caminho)
    assert list(leitura.df.columns) == ["dup", "dup.1", "Unnamed: 2", "x"]   # o notebook relê igual
    aviso = " ".join(leitura.avisos)
    assert "'dup' → 'dup.1'" in aviso and "(sem nome) → 'Unnamed: 2'" in aviso, leitura.avisos
    relido, _ = padronizar_colunas(pd.read_csv(caminho, **leitura.parametros))
    pd.testing.assert_frame_equal(relido, leitura.df)


def test_carregar_csv_sep_sobrando_sem_aviso_de_nome(fabricar):
    avisos = carregar_csv(fabricar("sep_sobrando")).avisos
    assert not any("trocados" in aviso for aviso in avisos), avisos


def test_carregar_csv_indice_exportado_sem_aviso_de_nome(tmp_path):
    caminho = tmp_path / "indice.csv"
    pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]}).to_csv(caminho)
    avisos = carregar_csv(caminho).avisos
    assert not any("trocados" in aviso for aviso in avisos), avisos


@pytest.mark.parametrize("nome, kwargs", [
    ("vazio", {}), ("so_cabecalho", {}), ("diretorio", {}), ("zip_dois_membros", {}),
    ("exemplo", {"encoding": "xyz"}),
    ("exemplo", {"encoding": "hex"}),       # codec de bytes: LookupError só na leitura
    ("br_cp1252", {"encoding": "utf-8"}),   # encoding informado que falha não é trocado em silêncio
    ("exemplo", {"separador": ";;"}),       # separador com mais de 1 caractere
])
def test_carregar_csv_erros(fabricar, nome, kwargs):
    with pytest.raises(ErroLeitura) as erro:
        carregar_csv(fabricar(nome), **kwargs)
    if nome == "zip_dois_membros":
        assert "primeiro.csv" in str(erro.value) and "segundo.csv" in str(erro.value)


@pytest.mark.parametrize("nome", [
    "exemplo", "br_cp1252", "br_cp1252_gz", "exemplo_zip", "milhar_ptbr", "malformado",
    "nomes_estranhos", "sep_sobrando", "aspas_ponto_virgula", "uma_coluna_virgula", "tsv",
    "com_indice",
])
def test_paridade_parametros_read_csv(fabricar, nome):
    """pd.read_csv(**parametros) + padronizar_colunas == Leitura.df (o notebook relê assim)."""
    caminho = fabricar(nome)
    leitura = carregar_csv(caminho)
    relido, _ = padronizar_colunas(pd.read_csv(caminho, **leitura.parametros))
    pd.testing.assert_frame_equal(relido, leitura.df)


# ------------------------------------------------------------ perfil

@pytest.mark.parametrize("coluna, valores, esperado", [
    ("id_venda", list(range(48)) + [0, 1], True),                 # 2 ids repetidos em 50
    ("id", list(range(20)), True),                                # único em 20 linhas
    ("protocolo", [f"PRT-{i:05d}-X" for i in range(60)], True),   # texto curto, único, sem espaço
    ("Observação", [f"o cliente {i} gostou muito" for i in range(60)], False),
    ("valor", [i * 1.37 for i in range(60)], False),
])
def test_identificador(coluna, valores, esperado):
    info = _por_nome(perfilar(pd.DataFrame({coluna: valores})))[coluna]
    assert info.identificador is esperado, f"{coluna}: tipo={info.tipo}, n_unicos={info.n_unicos}"


def test_texto_livre_unico_continua_texto():
    serie = [f"o cliente {i} gostou muito" for i in range(60)]
    assert _por_nome(perfilar(pd.DataFrame({"Observação": serie})))["Observação"].tipo == TEXTO


def test_indice_exportado_vira_identificador(fabricar):
    perfil = perfilar(carregar_csv(fabricar("com_indice")).df)
    indices = [info for info in perfil if info.nome.startswith("Unnamed")]
    assert len(indices) == 1 and indices[0].identificador, [(i.nome, i.tipo) for i in perfil]


def test_binaria(fabricar):
    perfil = _por_nome(perfilar(carregar_csv(fabricar("churn")).df))
    assert perfil["churn"].binaria and perfil["ativo"].binaria
    assert not perfil["idade"].binaria


def test_classificar_coluna_nome_nao_textual():
    assert classificar_coluna(pd.Series(["a", "b"] * 10, name=0)) == CATEGORICA


def test_perfil_br_cp1252(fabricar):
    perfil = _por_nome(perfilar(carregar_csv(fabricar("br_cp1252")).df))
    tipos = {nome: info.tipo for nome, info in perfil.items()}
    assert tipos == {"Região": CATEGORICA, "Preço": NUMERICA, "Valor total": NUMERICA,
                     "Data venda": DATA, "Observação": TEXTO}
    assert perfil["Data venda"].formato_data == "%d/%m/%Y"
    assert not perfil["Observação"].identificador
