"""Funções puras de scripts/eda/apoio.py (plano, 6.1 e 7.3)."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest

from eda.apoio import (
    chave_normalizada,
    checar_qualidade,
    classificar_correlacao,
    converter_datas,
    detectar_formato_data,
    limpar_dados,
    normalizar_para_numerico,
    padronizar_colunas,
    tabela_outliers,
)
from fixtures import DATAS_AMBIGUAS, DATAS_BR

PROBLEMAS_ESTAVEIS = {"constante", "muitos_ausentes", "categorias_parecidas", "negativos_raros",
                      "alta_cardinalidade", "id_repetido", "infinitos"}


@pytest.mark.parametrize("valores, decimal, esperado", [
    (["1.234,56"], None, [1234.56]),
    (["1,234.56"], None, [1234.56]),
    (["R$ 1.234,56"], None, [1234.56]),
    (["R$ 1.234", "2,50"], None, [1234, 2.5]),
    (["1.234.567"], None, [1234567]),
    (["12%"], None, [12]),
    (["-3,2"], None, [-3.2]),
    (["(1.234,00)"], None, [-1234]),
    (["−5"], None, [-5]),
    (["1e5"], None, [100000]),
    (["EUR 10,50"], None, [10.5]),
    (["abc"], None, [np.nan]),
    (["0,125", "0,250"], None, [0.125, 0.25]),    # 0,125 não é milhar (grupo começa em 0)
    (["-23.550520"], None, [-23.55052]),
    (["1.234", "12.500"], ",", [1234, 12500]),
    (["1.234", "12.500"], ".", [1.234, 12.5]),
])
def test_normalizar_para_numerico(valores, decimal, esperado):
    resultado = normalizar_para_numerico(pd.Series(valores), decimal=decimal)
    assert pd.api.types.is_float_dtype(resultado), f"dtype {resultado.dtype}, esperado float"
    obtido = resultado.to_numpy(dtype="float64", na_value=np.nan)
    np.testing.assert_allclose(obtido, esperado, equal_nan=True,
                               err_msg=f"{valores} com decimal={decimal!r}")


def _datas(indice: pd.DatetimeIndex, formato: str) -> pd.Series:
    return pd.Series(list(indice.strftime(formato)))


@pytest.mark.parametrize("serie, formato_real", [
    (_datas(pd.date_range("2024-01-01", periods=60, freq="5D"), "%Y-%m-%d"), "%Y-%m-%d"),
    (_datas(pd.date_range("2024-01-01", periods=120, freq="h"), "%Y-%m-%d %H:%M:%S"),
     "%Y-%m-%d %H:%M:%S"),
    (_datas(DATAS_BR, "%d/%m/%Y"), "%d/%m/%Y"),
    (_datas(DATAS_BR, "%m/%d/%Y"), "%m/%d/%Y"),
    (_datas(DATAS_AMBIGUAS, "%d/%m/%Y"), "%d/%m/%Y"),   # todos os dias <= 12: vale dd/mm
], ids=["iso", "iso_hora", "br", "us", "br_ambiguo"])
def test_detectar_e_converter_datas(serie, formato_real):
    formato = detectar_formato_data(serie)
    assert formato is not None, f"nenhum formato detectado para {serie.head(3).tolist()}"
    convertida = converter_datas(serie, formato)
    gabarito = pd.to_datetime(serie, format=formato_real)
    assert pd.api.types.is_datetime64_any_dtype(convertida)
    texto = "%Y-%m-%d %H:%M:%S"
    assert convertida.dt.strftime(texto).tolist() == gabarito.dt.strftime(texto).tolist(), \
        f"formato detectado {formato!r} diverge de {formato_real!r}"


@pytest.mark.parametrize("serie", [
    pd.Series([f"{h:02d}:{m:02d}" for h in range(8, 18) for m in (0, 30)]),
    pd.Series(["jan/2024", "fev/2024", "mar/2024", "abr/2024", "mai/2024", "jun/2024"] * 3),
    pd.Series([str(100001 + i) for i in range(30)]),
    pd.Series([20240101 + i for i in range(30)]),
], ids=["hora", "mes_abreviado", "numero_como_texto", "dtype_numerico"])
def test_detectar_formato_data_rejeita_nao_datas(serie):
    assert detectar_formato_data(serie) is None


def test_converter_datas_valor_invalido_vira_nat():
    convertida = converter_datas(pd.Series(["01/02/2024", "xx", None]), "%d/%m/%Y")
    assert convertida.iloc[0] == pd.Timestamp(2024, 2, 1)
    assert convertida.iloc[1:].isna().all()


@pytest.mark.parametrize("formato", ["%d/%m/%Y", "%d/%m/%Y %H:%M"])
def test_converter_datas_com_e_sem_hora(formato):
    """Excel omite a hora à meia-noite: as duas formas convivem na mesma coluna."""
    serie = pd.Series(["01/02/2024", "03/02/2024 14:30", "05/02/2024 10:00:05", "xx", None])
    convertida = converter_datas(serie, formato)
    assert convertida.iloc[:3].tolist() == [pd.Timestamp(2024, 2, 1), pd.Timestamp(2024, 2, 3, 14, 30),
                                            pd.Timestamp(2024, 2, 5, 10, 0, 5)]
    assert convertida.iloc[3:].isna().all()


def test_detectar_formato_data_com_e_sem_hora():
    serie = pd.Series([f"{d:02d}/03/2024" for d in range(13, 24)] + [f"{d:02d}/03/2024 14:30" for d in range(24, 29)])
    formato = detectar_formato_data(serie)
    assert formato == "%d/%m/%Y" and converter_datas(serie, formato).notna().all()


@pytest.mark.parametrize("a, b", [
    (" São  Paulo ", "sao paulo"),
    ("SUDESTE", "Sudeste"),
    ("Ceará", "ceara"),
])
def test_chave_normalizada_equivalentes(a, b):
    assert chave_normalizada(a) == chave_normalizada(b)


def test_chave_normalizada_distingue_valores_diferentes():
    assert chave_normalizada("Sul") != chave_normalizada("Sudeste")


def test_padronizar_colunas_nomes_unicos(fabricar):
    df = pd.read_csv(fabricar("nomes_estranhos"))
    novo, avisos = padronizar_colunas(df)
    nomes = list(novo.columns)
    assert len(nomes) == len(set(nomes)) == 6, f"nomes repetidos ou perdidos: {nomes}"
    assert all(n == n.strip() and n for n in nomes), nomes
    assert "valor" in nomes
    assert len(novo) == 40
    assert avisos, "renomear 'valor ' deveria gerar aviso"


def test_padronizar_colunas_nome_vazio():
    df = pd.DataFrame([[1, 2, 3]], columns=["a", "  ", "a "])
    novo, avisos = padronizar_colunas(df)
    nomes = list(novo.columns)
    assert len(set(nomes)) == 3 and all(nomes), nomes
    assert nomes[0] == "a"
    assert avisos


def test_padronizar_colunas_remove_unnamed_vazia(fabricar):
    df = pd.read_csv(fabricar("sep_sobrando"), sep=";")
    novo, avisos = padronizar_colunas(df)
    assert list(novo.columns) == ["a", "b", "c"]
    assert any("Unnamed" in a or "vazia" in a.lower() for a in avisos), avisos


def _bruto() -> pd.DataFrame:
    # Linhas 0 e 1 só ficam iguais depois do strip; 3 e 4 são duplicatas exatas.
    return pd.DataFrame({
        "t": [" a ", "a", "", "b", "b"],
        "n": ["1,5", "1,5", "2,5", "x", "x"],
        "d": ["01/02/2024", "01/02/2024", "03/02/2024", "", ""],
        "f": [1.0, 1.0, np.inf, -np.inf, -np.inf],
    })


@pytest.mark.parametrize("remover, linhas", [(True, 4), (False, 5)])
def test_limpar_dados(remover, linhas):
    bruto = _bruto()
    copia = bruto.copy()
    plano = {"texto": ["t"], "numericas": {"n": ","}, "datas": {"d": "%d/%m/%Y"},
             "remover_duplicadas": remover}
    limpo, log = limpar_dados(bruto, plano)

    assert bruto.equals(copia), "limpar_dados modificou o DataFrame de entrada"
    assert len(limpo) == linhas, "duplicatas devem ser medidas nos dados brutos"
    assert limpo["t"].isna().tolist()[:3] == [False, False, True]
    assert limpo["t"].iloc[:2].tolist() == ["a", "a"]
    np.testing.assert_allclose(limpo["n"].to_numpy(dtype="float64", na_value=np.nan)[:4],
                               [1.5, 1.5, 2.5, np.nan], equal_nan=True)
    assert pd.api.types.is_datetime64_any_dtype(limpo["d"])
    assert limpo["d"].iloc[2] == pd.Timestamp(2024, 2, 3)
    assert not np.isinf(limpo["f"].to_numpy(dtype="float64", na_value=np.nan)).any()
    # A mesma linha do registro cita a duplicata e a contagem (1).
    assert any(re.search(r"duplicat|idêntic", linha, re.I) and re.search(r"\b1\b", linha)
               for linha in log), log
    assert any(re.search(r"inf", linha) and re.search(r"\b3\b", linha) for linha in log), log


def test_limpar_dados_booleana_com_vazios():
    """O pandas lê True/False com vazios como object de bools: não é texto para o strip."""
    bruto = pd.DataFrame({"ativo": [True, np.nan, False, True]}, dtype=object)
    limpo, _ = limpar_dados(bruto, {"texto": ["ativo"], "remover_duplicadas": False})
    assert limpo["ativo"].tolist()[::2] == [True, False]


def test_tabela_outliers():
    tabela = tabela_outliers(pd.DataFrame({"x": list(range(1, 11)) + [100]}), ["x"])
    colunas = {"n_validos", "q1", "q3", "limite_inferior", "limite_superior", "n_outliers",
               "pct_outliers", "minimo", "maximo"}
    assert colunas <= set(tabela.columns), f"faltam colunas: {colunas - set(tabela.columns)}"
    assert tabela.loc["x", "n_outliers"] == 1
    assert tabela.loc["x", "maximo"] == 100


def test_checar_qualidade_f20(fabricar):
    df = pd.read_csv(fabricar("qualidade"))
    tabela = checar_qualidade(df, numericas=["preco"], categoricas=["regiao", "constante"])
    assert {"coluna", "problema", "detalhe"} <= set(tabela.columns)
    assert set(tabela["problema"]) <= PROBLEMAS_ESTAVEIS, set(tabela["problema"])
    achados = {(c, p): str(d) for c, p, d in tabela[["coluna", "problema", "detalhe"]].itertuples(index=False)}
    assert ("regiao", "categorias_parecidas") in achados, tabela.to_string()
    assert "SUDESTE" in achados[("regiao", "categorias_parecidas")]
    assert ("preco", "negativos_raros") in achados, tabela.to_string()
    assert ("constante", "constante") in achados, tabela.to_string()


def test_checar_qualidade_ausentes_e_cardinalidade():
    n = 100
    df = pd.DataFrame({"pouco": [np.nan] * 60 + list(range(40)),
                       "codigo": [f"c{i}" for i in range(n)]})
    tabela = checar_qualidade(df, numericas=["pouco"], categoricas=["codigo"])
    pares = set(zip(tabela["coluna"], tabela["problema"]))
    assert ("pouco", "muitos_ausentes") in pares, tabela.to_string()
    assert ("codigo", "alta_cardinalidade") in pares, tabela.to_string()


def test_checar_qualidade_infinitos_e_id_repetido():
    bruto = pd.DataFrame({"id_cliente": list(range(39)) + [0],
                          "v": [np.inf, -np.inf] + [float(i) for i in range(38)]})
    limpo = bruto.assign(v=bruto["v"].replace([np.inf, -np.inf], np.nan))
    tabela = checar_qualidade(limpo, numericas=["v"], categoricas=[], bruto=bruto)
    pares = set(zip(tabela["coluna"], tabela["problema"]))
    assert ("v", "infinitos") in pares, tabela.to_string()
    assert ("id_cliente", "id_repetido") in pares, tabela.to_string()


@pytest.mark.parametrize("r, forca", [
    (0.0, "desprezível"), (0.099, "desprezível"), (0.1, "fraca"), (0.299, "fraca"),
    (0.3, "moderada"), (0.499, "moderada"), (0.5, "forte"), (0.699, "forte"),
    (0.7, "muito forte"), (1.0, "muito forte"),
    (-0.099, "desprezível"), (-0.31, "moderada"), (-0.7, "muito forte"),
])
def test_classificar_correlacao(r, forca):
    assert classificar_correlacao(r) == forca
