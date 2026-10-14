"""Notebook gerado sem execução (codigo.py; plano, 6.3, 7.3, D03, D05, D14, D18)."""

from __future__ import annotations

import re

import matplotlib
import nbformat
import numpy as np
import pandas as pd
import pytest

from utilitarios import (
    SECOES_CONHECIDAS,
    SECOES_SEMPRE,
    compilar,
    secao,
    secoes,
    variantes_de_caminho,
)

# (fixture, alvo): F02–F26, comprimidos, nomes problemáticos e alvos de todos os tipos.
CASOS = [
    ("exemplo", None), ("exemplo", "valor_total"), ("exemplo", "avaliado"),
    ("br_cp1252", None), ("br_cp1252_zip", None), ("exemplo_gz", None),
    ("iso_datas", None), ("datas_br", None), ("datas_br_ambiguas", None), ("datas_us", None),
    ("so_categoricas", None), ("dup_com_id", None), ("uma_coluna_virgula", None),
    ("milhar_ptbr", None), ("tsv", None), ("pipe", None), ("malformado", None),
    ("nomes_estranhos", None), ("nomes_estranhos", 'diz "oi"'),
    ("aspas_nomes", None), ("aspas_nomes", 'grupo "A"'),
    ("nomes_sinistros", None), ("nomes_sinistros", 'cat "A"'), ("nomes_sinistros", "num\\x"),
    ("com_indice", None), ("sep_sobrando", None), ("ausentes", None), ("larga", None),
    ("churn", "churn"), ("churn", "plano"), ("churn", "renda"), ("churn", "ativo"),
    ("qualidade", None), ("degenerados", None), ("uma_numerica", None),
    ("uma_numerica", "valor"), ("so_datas", None), ("aspas_ponto_virgula", None),
    ("espaco_categoria", None), ("serie_lacuna", None), ("colisoes", "churn"),
]


def _id(caso):
    nome, alvo = caso
    return nome if alvo is None else f"{nome}-alvo={alvo}"


@pytest.mark.parametrize("caso", CASOS, ids=[_id(c) for c in CASOS])
def test_notebook_gerado_e_valido(gerar_sem_executar, tmp_path_factory, caso):
    resultado, nb, texto = gerar_sem_executar(*caso)
    assert resultado.codigo == 0, resultado.mensagem
    nbformat.validate(nb)

    desconhecidas = {s for s in secoes(nb)} - SECOES_CONHECIDAS
    assert not desconhecidas, f"células sem metadata.eda.secao válida: {desconhecidas}"

    for i, celula in enumerate(nb.cells):
        if celula.cell_type == "code":
            try:
                compilar(celula.source, f"<célula {i}>")
            except SyntaxError as erro:
                pytest.fail(f"célula {i} ({secao(celula)}) não compila: {erro}\n{celula.source}")

    for variante in variantes_de_caminho(tmp_path_factory.getbasetemp()):
        assert variante not in texto, f"caminho absoluto gravado no notebook: {variante} (D18)"

    # M08: seções numeradas na ordem, sem saltos (## 1., ## 2., ...).
    numeros = [int(n) for c in nb.cells if c.cell_type == "markdown"
               for n in re.findall(r"(?m)^## (\d+)\.", c.source)]
    assert numeros and numeros == list(range(1, len(numeros) + 1)), f"numeração: {numeros}"


# Seções presentes/ausentes logo na geração (tabela 7.4); o E2E confere as saídas.
SECOES_ESPERADAS = [
    ("exemplo", None,
     {"leitura", "limpeza", "qualidade", "estatisticas_numericas", "outliers", "frequencias",
      "agregacoes", "correlacao", "comparacao_grupos", "cruzamento_categoricas",
      "serie_temporal", "resumo"},
     {"texto_livre", "alvo"}),
    ("exemplo", "valor_total", {"alvo"}, set()),
    ("exemplo", "avaliado", {"alvo"}, set()),
    ("br_cp1252", None, {"serie_temporal", "correlacao", "texto_livre"}, set()),
    ("iso_datas", None, {"serie_temporal"}, set()),
    ("so_datas", None, {"serie_temporal"}, {"correlacao"}),
    ("datas_us", None, {"serie_temporal"}, set()),
    ("so_categoricas", None, {"frequencias", "barras_categoricas", "cruzamento_categoricas"},
     {"estatisticas_numericas", "distribuicoes", "correlacao", "serie_temporal"}),
    ("uma_coluna_virgula", None, {"estatisticas_numericas", "distribuicoes", "outliers"},
     {"correlacao", "frequencias", "serie_temporal"}),
    ("uma_numerica", None, {"estatisticas_numericas", "distribuicoes", "outliers"},
     {"correlacao", "frequencias", "serie_temporal"}),
    ("churn", "churn", {"alvo"}, set()),
    ("churn", "plano", {"alvo"}, set()),
    ("churn", "renda", {"alvo"}, set()),
]


@pytest.mark.parametrize("nome, alvo, presentes, ausentes", SECOES_ESPERADAS,
                         ids=[_id(c[:2]) for c in SECOES_ESPERADAS])
def test_secoes_presentes_e_ausentes(gerar_sem_executar, nome, alvo, presentes, ausentes):
    _, nb, _ = gerar_sem_executar(nome, alvo)
    encontradas = set(secoes(nb))
    assert not (presentes | SECOES_SEMPRE) - encontradas, \
        f"faltam seções: {sorted((presentes | SECOES_SEMPRE) - encontradas)}"
    assert not ausentes & encontradas, f"seções que não deveriam existir: {sorted(ausentes & encontradas)}"


class _IPythonFalso:
    def run_line_magic(self, *_args, **_kwargs):
        return None

    run_cell_magic = run_line_magic


def test_serie_temporal_com_lacuna(gerar_sem_executar, monkeypatch):
    """D05: com um mês sem dados, as linhas ficam dentro do eixo e a contagem é por linha."""
    import matplotlib.pyplot as plt

    resultado, nb, _ = gerar_sem_executar("serie_lacuna")
    alvo = [i for i, c in enumerate(nb.cells) if secao(c) == "serie_temporal"]
    assert alvo, "seção serie_temporal ausente"
    monkeypatch.chdir(resultado.caminho.parent)

    figuras: dict[int, object] = {}

    def guardar_figuras(*_args, **_kwargs):
        for numero in plt.get_fignums():
            figura = plt.figure(numero)
            figuras.setdefault(id(figura), figura)

    namespace = {"__name__": "__main__", "get_ipython": _IPythonFalso}
    with matplotlib.rc_context():
        for i, celula in enumerate(nb.cells[: alvo[-1] + 1]):
            if celula.cell_type != "code":
                continue
            plt.close("all")
            monkeypatch.setattr(plt, "show", guardar_figuras if i in alvo else lambda *a, **k: None)
            exec(compilar(celula.source, f"<célula {i}>"), namespace)  # noqa: S102
            if i in alvo:
                guardar_figuras()

    linhas = [(ax, linha) for figura in figuras.values() for ax in figura.axes
              for linha in ax.get_lines() if linha.get_transform() == ax.transData]
    pontos = [(ax, linha.get_xydata()) for ax, linha in linhas]
    pontos = [(ax, xy[np.isfinite(xy).all(axis=1)]) for ax, xy in pontos]
    pontos = [(ax, xy) for ax, xy in pontos if len(xy)]
    plt.close("all")
    assert pontos, "o gráfico da série temporal não tem nenhuma linha com dados"
    for ax, xy in pontos:
        x0, x1 = sorted(ax.get_xlim())
        assert x0 <= xy[:, 0].min() and xy[:, 0].max() <= x1, \
            f"linha fora do eixo x: [{xy[:, 0].min()}, {xy[:, 0].max()}] vs xlim [{x0}, {x1}]"

    assert "contagem" in namespace, "variável `contagem` (D05) não definida na seção"
    assert int(namespace["contagem"].sum()) == int(namespace["df"]["data"].notna().sum())


def test_placeholders_substituidos_numa_passada_so():
    """Uma coluna chamada "<<B>>" não pode ser substituída de novo (viraria SyntaxError)."""
    from eda.codigo import _codigo

    assert _codigo("A = <<A>>\nB = <<B>>", A=repr("<<B>>"), B="1") == "A = '<<B>>'\nB = 1"


@pytest.mark.parametrize("valores, esperada", [
    (["não"] * 20 + ["sim"] * 30, "sim"),
    ([0] * 30 + [1] * 20, 1),
    (["ok"] * 30 + ["cancelado"] * 5, "cancelado"),           # binária sem 1/sim: a menos frequente
    (["a"] * 30 + ["b"] * 15 + ["1"], "b"),                   # 3 classes: "1" não tem prioridade
    (["Sudeste"] * 20 + ["Sul"] * 12 + ["sudeste"], "Sul"),   # grafia rara não vira a classe
    (["a"] * 5 + ["b"] * 3 + ["c"] * 2, "a"),                 # todas pequenas: a mais frequente
], ids=["sim", "um", "menor_binaria", "um_raro", "grafia_rara", "todas_pequenas"])
def test_classe_positiva(valores, esperada):
    from eda.codigo import _classe_positiva

    assert _classe_positiva(pd.Series(valores)) == esperada
