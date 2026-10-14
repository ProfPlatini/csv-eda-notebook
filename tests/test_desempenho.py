"""Desempenho com 200 mil linhas (plano, D17, M07 e 7.5). Limites folgados para o CI."""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.lento


@pytest.fixture(scope="module")
def grande(tmp_path_factory):
    from fixtures import Fabrica

    return Fabrica(tmp_path_factory.mktemp("grande"))("grande")


def _cronometrar(funcao, *args, **kwargs):
    inicio = time.perf_counter()
    retorno = funcao(*args, **kwargs)
    return retorno, time.perf_counter() - inicio


def test_perfilar_grande(grande):
    from eda.loader import carregar_csv, perfilar

    leitura = carregar_csv(grande)
    assert len(leitura.df) == 200_000
    _, segundos = _cronometrar(perfilar, leitura.df)
    assert segundos < 10, f"perfilar levou {segundos:.1f} s (meta local < 2 s)"


def test_gerar_sem_executar_grande(grande, tmp_path):
    from eda.cli import gerar

    resultado, segundos = _cronometrar(gerar, grande, saida=tmp_path / "g.ipynb",
                                       executar_notebook=False)
    assert resultado.codigo == 0
    assert segundos < 15, f"gerar levou {segundos:.1f} s (meta local < 5 s)"


@pytest.mark.e2e
def test_gerar_e_executar_grande(grande, tmp_path):
    from eda.cli import gerar

    resultado, segundos = _cronometrar(gerar, grande, saida=tmp_path / "g.ipynb")
    assert resultado.codigo == 0, resultado.mensagem
    assert segundos < 60, f"gerar + executar levou {segundos:.1f} s (meta local < 20 s)"
