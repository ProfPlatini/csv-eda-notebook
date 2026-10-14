"""Ponta a ponta: gerar + executar com nbclient (plano, 7.4).

Cada caso é executado uma única vez (cache de módulo). Uma célula de métricas
é anexada ao fim do notebook e imprime JSON com o estado de `df`.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest

from fixtures import DATAS_AMBIGUAS, DATAS_BR, DATAS_ISO, DATAS_SEMANAIS, GABARITO
from utilitarios import (
    CELULA_METRICAS,
    SECAO_TESTE,
    SECOES_COM_IMAGEM,
    SECOES_COM_TABELA,
    anexar_celula,
    erros,
    ler_notebook,
    metricas,
    secao,
    stderr,
    tipos_de_saida,
)

pytestmark = pytest.mark.e2e

CASOS = {
    "exemplo": ("exemplo", None),
    "exemplo-alvo-valor_total": ("exemplo", "valor_total"),
    "exemplo-alvo-avaliado": ("exemplo", "avaliado"),
    "exemplo_zip": ("exemplo_zip", None),
    "br_cp1252": ("br_cp1252", None),
    "br_cp1252_gz": ("br_cp1252_gz", None),
    "iso_datas": ("iso_datas", None),
    "so_datas": ("so_datas", None),
    "datas_us": ("datas_us", None),
    "datas_br_ambiguas": ("datas_br_ambiguas", None),
    "so_categoricas": ("so_categoricas", None),
    "dup_com_id": ("dup_com_id", None),
    "uma_coluna_virgula": ("uma_coluna_virgula", None),
    "uma_numerica": ("uma_numerica", None),
    "uma_numerica-alvo-valor": ("uma_numerica", "valor"),
    "malformado": ("malformado", None),
    "nomes_estranhos": ("nomes_estranhos", None),
    "aspas_nomes": ("aspas_nomes", None),
    "nomes_sinistros-alvo-barra": ("nomes_sinistros", "num\\x"),   # chave vira nome de arquivo
    "com_indice": ("com_indice", None),
    "sep_sobrando": ("sep_sobrando", None),
    "ausentes": ("ausentes", None),
    "larga": ("larga", None),
    "degenerados": ("degenerados", None),
    "qualidade": ("qualidade", None),
    "aspas_ponto_virgula": ("aspas_ponto_virgula", None),
    "churn-alvo-churn": ("churn", "churn"),
    "churn-alvo-plano": ("churn", "plano"),
    "churn-alvo-renda": ("churn", "renda"),
    # Alvo com ausentes, colunas "registros" e "n", categoria "Total" e série semanal.
    "colisoes-alvo-churn": ("colisoes", "churn"),
}


@pytest.fixture(scope="module")
def executado(fabricar_sessao, tmp_path_factory):
    """Devolve (Resultado, notebook executado) de um caso, executando-o só na 1ª vez."""
    from eda.cli import gerar

    pasta = tmp_path_factory.mktemp("nb_executados")
    cache: dict = {}

    def obter(caso: str):
        if caso not in cache:
            nome, alvo = CASOS[caso]
            try:
                with pytest.MonkeyPatch.context() as mp:
                    anexar_celula(mp, {"tipo": "code", "fonte": CELULA_METRICAS, "secao": SECAO_TESTE})
                    resultado = gerar(fabricar_sessao(nome), saida=pasta / f"{caso}.ipynb",
                                      alvo=alvo, executar_notebook=True)
                cache[caso] = (resultado, ler_notebook(resultado.caminho))
            except Exception as erro:  # noqa: BLE001 - repassado a cada teste do caso
                cache[caso] = erro
        valor = cache[caso]
        if isinstance(valor, Exception):
            raise valor
        return valor

    return obter


@pytest.mark.parametrize("caso", CASOS)
def test_executa_sem_erro(executado, caso):
    resultado, nb = executado(caso)
    assert not erros(nb), "\n".join(erros(nb))
    assert resultado.codigo == 0 and resultado.execucao is not None and resultado.execucao.ok, \
        resultado.mensagem


@pytest.mark.parametrize("caso", CASOS)
def test_saidas_por_secao(executado, caso):
    """Seções de gráfico têm PNG; seções de tabela têm HTML (tabela 6.3, D06)."""
    _, nb = executado(caso)
    tipos = tipos_de_saida(nb)
    presentes = {secao(c) for c in nb.cells} - {SECAO_TESTE}
    sem_imagem = sorted(s for s in presentes & SECOES_COM_IMAGEM if "image/png" not in tipos[s])
    sem_tabela = sorted(s for s in presentes & SECOES_COM_TABELA if "text/html" not in tipos[s])
    detalhes = {s: (sorted(tipos[s]), stderr(nb, s)) for s in sem_imagem + sem_tabela}
    assert not sem_imagem, f"seções sem image/png: {sem_imagem}; saídas/stderr: {detalhes}"
    assert not sem_tabela, f"seções sem text/html: {sem_tabela}; saídas/stderr: {detalhes}"

    for celula in nb.cells:
        for saida in celula.get("outputs", []):
            dados = saida.get("data", {})
            if saida.get("output_type") == "execute_result" and set(dados) == {"text/plain"}:
                assert not dados["text/plain"].startswith(("'", '"')), \
                    f"tabela exibida como string crua na seção {secao(celula)} (D06)"


@pytest.mark.parametrize("caso, nome_secao, tipo", [
    ("qualidade", "qualidade", "text/html"),          # M02: problemas viram tabela
    ("ausentes", "ausentes", "text/html"),
    ("ausentes", "grafico_ausentes", "image/png"),
    ("dup_com_id", "duplicadas", "text/html"),
])
def test_secoes_condicionais_com_saida(executado, caso, nome_secao, tipo):
    _, nb = executado(caso)
    assert tipo in tipos_de_saida(nb)[nome_secao], f"{nome_secao} sem {tipo}"


@pytest.mark.parametrize("caso", CASOS)
def test_sem_avisos_no_stderr(executado, caso):
    """Avisos de bibliotecas (ou o backend Agg sem gráficos inline) não podem vazar no notebook."""
    _, nb = executado(caso)
    vazamentos = {secao(c): stderr(nb, secao(c)) for c in nb.cells
                  for s in c.get("outputs", []) if s.get("name") == "stderr"}
    assert not vazamentos, vazamentos


def test_constante_fora_da_correlacao(executado):
    """D28: coluna constante não entra na correlação."""
    _, nb = executado("degenerados")
    html = [s["data"]["text/html"] for c in nb.cells if secao(c) == "correlacao"
            for s in c.get("outputs", []) if "text/html" in s.get("data", {})]
    assert html, "seção de correlação sem tabela"
    assert not any("constante_num" in h for h in html)


def test_correlacoes_do_resumo_batem_com_o_df_do_notebook(executado):
    """D12: o resumo é calculado sobre o mesmo df limpo que o notebook usa."""
    resultado, nb = executado("exemplo")
    numeros = metricas(nb)["numeros"]
    numero = r"(-?\d+,\d+)"
    conferidos = 0
    for a, b, resto in re.findall(r"`([^`]+)`\s*[×x]\s*`([^`]+)`:?(.*)", resultado.resumo):
        if a not in numeros or b not in numeros:
            continue
        par = pd.DataFrame({"a": numeros[a], "b": numeros[b]}, dtype=float)
        for nome, metodo in (("r", "pearson"), ("rho", "spearman")):
            citado = re.search(rf"\b{nome}\s*=\s*{numero}", resto)
            if citado:
                # DataFrame.corr: o Spearman da Series exige scipy, o do DataFrame não.
                esperado = par.corr(method=metodo).iloc[0, 1]
                assert abs(float(citado.group(1).replace(",", ".")) - esperado) <= 0.006, \
                    f"{a} × {b}: {nome} citado {citado.group(1)}, no df do notebook {esperado:.3f}"
                conferidos += 1
    assert conferidos >= 2, f"nenhum par de correlação reconhecido no resumo:\n{resultado.resumo}"


def test_kernel_usa_o_mesmo_pandas(executado):
    assert metricas(executado("exemplo")[1])["pandas"] == pd.__version__


def test_exemplo_datas_todas_validas(executado):
    m = metricas(executado("exemplo")[1])
    assert m["notna"]["data_pedido"] == m["len_df"], "datas ISO perdidas na limpeza (D01)"


@pytest.mark.parametrize("caso, len_df, len_bruto", [
    ("so_categoricas", 60, 60),     # sem identificador: linhas idênticas mantidas (D02)
    ("dup_com_id", 40, 42),         # com identificador: 2 duplicatas removidas
    ("malformado", 32, 32),         # linha 3 ignorada na leitura (D10)
    ("iso_datas", 60, 60),
    ("so_datas", 50, 50),
    ("br_cp1252", 61, 61),
])
def test_contagem_de_linhas(executado, caso, len_df, len_bruto):
    m = metricas(executado(caso)[1])
    assert (m["len_df"], m["len_df_bruto"]) == (len_df, len_bruto)


def _iso(indice) -> list[str]:
    return list(pd.DatetimeIndex(indice).strftime("%Y-%m-%d %H:%M:%S"))


@pytest.mark.parametrize("caso, coluna, gabarito", [
    ("iso_datas", "dt", _iso(DATAS_ISO)),
    ("so_datas", "dt", _iso(DATAS_SEMANAIS)),
    ("datas_us", "date", _iso(DATAS_BR)),
    ("datas_br_ambiguas", "data", _iso(DATAS_AMBIGUAS)),   # dd/mm assumido (D01)
    ("br_cp1252", "Data venda", _iso(pd.to_datetime(GABARITO["br_cp1252"]["Data venda"]))),
])
def test_datas_iguais_ao_gabarito(executado, caso, coluna, gabarito):
    m = metricas(executado(caso)[1])
    assert coluna in m["datas"], f"{coluna} não virou datetime; dtypes: {m['dtypes']}"
    assert m["datas"][coluna] == gabarito


def test_numeros_br_convertidos(executado):
    m = metricas(executado("br_cp1252")[1])
    for coluna in ("Preço", "Valor total"):
        assert coluna in m["numeros"], f"{coluna} não é numérica: {m['dtypes'][coluna]}"
        np.testing.assert_allclose(m["numeros"][coluna], GABARITO["br_cp1252"][coluna])


def test_uma_coluna_com_virgula_decimal(executado):
    m = metricas(executado("uma_coluna_virgula")[1])
    assert m["colunas"] == ["valor"]
    np.testing.assert_allclose(m["numeros"]["valor"], GABARITO["uma_coluna_virgula"])


def test_sep_sobrando_sem_coluna_vazia(executado):
    assert metricas(executado("sep_sobrando")[1])["colunas"] == ["a", "b", "c"]


@pytest.mark.parametrize("comprimido, original", [("exemplo_zip", "exemplo"),
                                                  ("br_cp1252_gz", "br_cp1252")])
def test_comprimido_gera_o_mesmo_df(executado, comprimido, original):
    a, b = metricas(executado(comprimido)[1]), metricas(executado(original)[1])
    for chave in ("colunas", "dtypes", "len_df", "hash"):
        assert a[chave] == b[chave], f"{chave} difere entre {comprimido} e {original}"
