"""Montagem, gravação e execução do arquivo `.ipynb`."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

VERSAO_NBFORMAT = 4
VERSAO_NBFORMAT_MINOR = 5


def construir_notebook(celulas: list[dict], titulo: str) -> dict:
    """Converte a lista de células em um notebook no formato nbformat 4."""
    celulas_nb = []
    for indice, celula in enumerate(celulas):
        fonte = celula["fonte"].strip() + "\n"
        celulas_nb.append({
            "cell_type": celula["tipo"],
            "id": f"celula-{indice:02d}",
            "metadata": {},
            "source": fonte.splitlines(keepends=True),
            **({"outputs": [], "execution_count": None} if celula["tipo"] == "code" else {}),
        })

    return {
        "cells": celulas_nb,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
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


def nbconvert_disponivel() -> bool:
    return (importlib.util.find_spec("nbconvert") is not None
            and importlib.util.find_spec("nbformat") is not None)


def executar(caminho: str | Path, timeout: int = 900) -> tuple[bool, str]:
    """Executa o notebook e grava os resultados na própria pasta.

    Devolve (executou, mensagem). Quando o `nbconvert` não está instalado o
    notebook é salvo sem resultados — ainda assim continua válido e executável.
    """
    caminho = Path(caminho)
    if not nbconvert_disponivel():
        return False, (
            "nbconvert/nbformat não instalados: notebook salvo sem resultados. "
            "Rode `pip install nbconvert` e abra o notebook para ver os gráficos."
        )

    comando = [
        sys.executable, "-m", "jupyter", "nbconvert",
        "--to", "notebook",
        "--execute",
        "--inplace",
        f"--ExecutePreprocessor.timeout={timeout}",
        str(caminho),
    ]
    try:
        processo = subprocess.run(comando, capture_output=True, text=True, timeout=timeout + 60)
    except subprocess.TimeoutExpired:
        return False, f"Tempo de execução excedido ({timeout}s)."
    if processo.returncode != 0:
        erro = (processo.stderr or processo.stdout or "").strip().splitlines()
        return False, "Falha ao executar o notebook: " + (erro[-1] if erro else "erro desconhecido")
    return True, "Notebook executado com sucesso: gráficos e tabelas já estão no arquivo."
