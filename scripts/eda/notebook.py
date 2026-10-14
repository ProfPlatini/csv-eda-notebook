"""Montagem, gravação e execução do arquivo `.ipynb`."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

VERSAO_NBFORMAT = 4
VERSAO_NBFORMAT_MINOR = 5
ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class Execucao:
    """Resultado da execução do notebook."""

    ok: bool
    mensagem: str
    celula_erro: int | None = None   # posição 1-based entre todas as células (como no Jupyter)
    secao_erro: str | None = None
    erro: str | None = None          # "Tipo: mensagem", sem códigos de cor
    sem_kernel: bool = False         # o kernel nem chegou a iniciar


def construir_notebook(celulas: list[dict], titulo: str) -> dict:
    """Converte a lista de células em um notebook nbformat 4 (com a seção em metadata.eda)."""
    celulas_nb = []
    for indice, celula in enumerate(celulas):
        fonte = celula["fonte"].strip() + "\n"
        celulas_nb.append({
            "cell_type": celula["tipo"],
            "id": f"celula-{indice:02d}",
            "metadata": {"eda": {"secao": celula.get("secao")}},
            "source": fonte.splitlines(keepends=True),
            **({"outputs": [], "execution_count": None} if celula["tipo"] == "code" else {}),
        })
    return {
        "cells": celulas_nb,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
            "title": titulo,
        },
        "nbformat": VERSAO_NBFORMAT,
        "nbformat_minor": VERSAO_NBFORMAT_MINOR,
    }


def salvar(notebook: dict, caminho: str | Path) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    return caminho


def dependencias_execucao() -> list[str]:
    """Módulos necessários para executar o notebook que não estão instalados."""
    return [m for m in ("nbclient", "nbformat", "ipykernel") if importlib.util.find_spec(m) is None]


def _gerenciador_de_kernel():
    """Kernel no mesmo Python que roda a skill.

    Um kernelspec "python3" instalado pelo usuário pode apontar para outro
    Python (sem pandas); por isso o comando do kernel é montado aqui.
    """
    from jupyter_client.kernelspec import KernelSpec, KernelSpecManager
    from jupyter_client.manager import KernelManager

    class EstePython(KernelSpecManager):
        def get_kernel_spec(self, kernel_name):
            # log_level=ERROR: o ipykernel 7 avisa no stderr sobre TCP sem criptografia (kernel local).
            argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}",
                    "--IPKernelApp.log_level=ERROR"]
            return KernelSpec(argv=argv,
                              display_name="Python 3", language="python")

    return KernelManager(kernel_name="python3", kernel_spec_manager=EstePython())


def _primeiro_erro(nb) -> tuple[int, str | None, str] | None:
    for posicao, celula in enumerate(nb.cells, start=1):
        for saida in celula.get("outputs", []):
            if saida.get("output_type") == "error":
                secao = celula.get("metadata", {}).get("eda", {}).get("secao")
                erro = ANSI.sub("", f"{saida.get('ename')}: {saida.get('evalue')}")
                return posicao, secao, erro
    return None


def executar(caminho: str | Path, timeout: int = 600) -> Execucao:
    """Executa o notebook e grava as saídas no próprio arquivo, mesmo se uma célula falhar.

    `timeout` é o limite, em segundos, de cada célula.
    """
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError, CellTimeoutError, DeadKernelError

    caminho = Path(caminho)
    nb = nbformat.read(caminho, as_version=4)
    cliente = NotebookClient(nb, km=_gerenciador_de_kernel(), timeout=timeout,
                             resources={"metadata": {"path": str(caminho.parent.resolve())}})
    # Com MPLBACKEND definido (ex.: Agg), o ipykernel não ativa os gráficos inline.
    ambiente = {k: v for k, v in os.environ.items() if k != "MPLBACKEND"}
    problema = None
    try:
        # cleanup_kc=True: com `km` próprio o nbclient não encerra o kernel sozinho.
        cliente.execute(env=ambiente, cleanup_kc=True)
    except CellExecutionError:
        pass
    except CellTimeoutError:
        problema = f"tempo limite de {timeout}s por célula excedido"
    except DeadKernelError as erro:
        problema = f"o kernel parou durante a execução ({erro})"
    except Exception as erro:  # noqa: BLE001 - kernel não iniciou (ipykernel ausente, porta...)
        return Execucao(False, f"não executado: o kernel Python não iniciou ({type(erro).__name__}: "
                               f"{ANSI.sub('', str(erro))[:300]})", sem_kernel=True)
    finally:
        nbformat.write(nb, caminho)

    achado = _primeiro_erro(nb)
    if achado:
        posicao, secao, erro = achado
        mensagem = f"falhou na célula {posicao} (seção {secao}): {erro}"
        if erro.startswith("ModuleNotFoundError"):
            mensagem += (" — instale as dependências no mesmo Python que roda o script: "
                         f"pip install -r {Path(__file__).resolve().parents[2] / 'requirements.txt'}")
        return Execucao(False, mensagem, posicao, secao, erro)
    if problema:
        return Execucao(False, f"falhou: {problema}")
    return Execucao(True, "ok")
