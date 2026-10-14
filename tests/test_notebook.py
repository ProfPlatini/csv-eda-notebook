"""Montagem, gravação e execução do .ipynb (scripts/eda/notebook.py; plano, 6.3 e D04)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import nbformat
import pytest

from eda.notebook import construir_notebook, dependencias_execucao, executar, salvar
from utilitarios import ler_notebook, secoes

CELULAS = [
    {"tipo": "markdown", "fonte": "# Título", "secao": "cabecalho"},
    {"tipo": "code", "fonte": "print('antes')", "secao": "configuracao"},
    {"tipo": "code", "fonte": "raise ValueError('boom')", "secao": "quebra"},
    {"tipo": "code", "fonte": "print('depois')", "secao": "resumo"},
]


def test_construir_e_salvar_notebook_valido(tmp_path):
    caminho = salvar(construir_notebook(CELULAS, "Título"), tmp_path / "sub" / "nb.ipynb")
    nb = ler_notebook(caminho)
    nbformat.validate(nb)
    assert [c.cell_type for c in nb.cells] == ["markdown", "code", "code", "code"]
    assert secoes(nb) == [c["secao"] for c in CELULAS]


def test_dependencias_execucao_presentes():
    assert dependencias_execucao() == []


@pytest.mark.e2e
def test_executar_grava_saidas_parciais_quando_falha(tmp_path):
    caminho = salvar(construir_notebook(CELULAS, "Título"), tmp_path / "nb.ipynb")
    execucao = executar(caminho, timeout=120)

    assert execucao.ok is False
    assert execucao.secao_erro == "quebra"
    assert isinstance(execucao.celula_erro, int)
    assert "boom" in f"{execucao.erro} {execucao.mensagem}"
    assert "\x1b" not in execucao.mensagem and "\x1b" not in (execucao.erro or "")
    nb = ler_notebook(caminho)
    saida_antes = "".join(s.get("text", "") for s in nb.cells[1].outputs)
    assert "antes" in saida_antes, "a célula anterior ao erro deveria ter a saída gravada"
    assert any(s.output_type == "error" for s in nb.cells[2].outputs)


def _kernels_filhos() -> set[int]:
    """PIDs de processos ipykernel filhos deste processo (psutil ou /proc)."""
    try:
        import psutil
    except ImportError:
        psutil = None
    if psutil is not None:
        return {p.pid for p in psutil.Process().children(recursive=True)
                if "ipykernel" in " ".join(p.cmdline())}
    if not Path("/proc").is_dir():
        pytest.skip("sem psutil nem /proc para listar processos filhos")
    pids = set()
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            ppid = int(stat.read_text().rsplit(")", 1)[1].split()[1])
            linha = (stat.parent / "cmdline").read_bytes().replace(b"\0", b" ")
        except (OSError, ValueError, IndexError):
            continue
        if ppid == os.getpid() and b"ipykernel" in linha:
            pids.add(int(stat.parent.name))
    return pids


@pytest.mark.e2e
def test_executar_encerra_o_kernel(tmp_path):
    """Cada execução precisa encerrar o próprio kernel (gerar() pode ser chamado em laço)."""
    antes = _kernels_filhos()
    caminho = salvar(construir_notebook(CELULAS[:2], "Título"), tmp_path / "ok.ipynb")
    assert executar(caminho, timeout=120).ok
    limite = time.monotonic() + 10
    while (novos := _kernels_filhos() - antes) and time.monotonic() < limite:
        time.sleep(0.2)
    assert not novos, f"{len(novos)} processo(s) de kernel continuam vivos depois de executar()"
