"""Configuração comum: caminho dos scripts, backend do matplotlib, markers e fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PASTA_TESTES = Path(__file__).resolve().parent
RAIZ = PASTA_TESTES.parent
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(PASTA_TESTES))
os.environ.setdefault("MPLBACKEND", "Agg")

from fixtures import Fabrica  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: executa notebooks em um kernel Jupyter (nbclient)")
    config.addinivalue_line("markers", "lento: desempenho com o CSV de 200 mil linhas")


@pytest.fixture
def fabricar(tmp_path):
    """Gera fixtures CSV (ver tests/fixtures.py) em um diretório exclusivo do teste."""
    return Fabrica(tmp_path / "csv")


@pytest.fixture(scope="session")
def fabricar_sessao(tmp_path_factory):
    """Igual a `fabricar`, mas compartilhado: só para testes que não escrevem ao lado do CSV."""
    return Fabrica(tmp_path_factory.mktemp("csv"))


@pytest.fixture(scope="session")
def gerar_sem_executar(fabricar_sessao, tmp_path_factory):
    """gerar(..., executar_notebook=False) com cache: (Resultado, notebook, texto JSON).

    Cada combinação (fixture, alvo) é gerada uma única vez por sessão.
    """
    from eda.cli import gerar
    from utilitarios import ler_notebook

    pasta = tmp_path_factory.mktemp("nb_sem_execucao")
    cache: dict = {}

    def obter(nome: str, alvo: str | None = None):
        chave = (nome, alvo)
        if chave not in cache:
            try:
                saida = pasta / f"{nome}_{len(cache)}.ipynb"
                resultado = gerar(fabricar_sessao(nome), saida=saida, alvo=alvo,
                                  executar_notebook=False)
                texto = resultado.caminho.read_text(encoding="utf-8")
                cache[chave] = (resultado, ler_notebook(resultado.caminho), texto)
            except Exception as erro:  # noqa: BLE001 - repassado a cada teste que pedir
                cache[chave] = erro
        valor = cache[chave]
        if isinstance(valor, Exception):
            raise valor
        return valor

    return obter
