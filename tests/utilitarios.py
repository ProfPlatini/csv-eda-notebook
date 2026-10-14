"""Funções auxiliares compartilhadas pelos testes (notebook, CLI e células extras)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import nbformat
from IPython.core.inputtransformer2 import TransformerManager

# IDs de seção da tabela 6.3 do plano.
SECOES_SEMPRE = {"cabecalho", "configuracao", "apoio", "leitura", "visao_geral", "ausentes",
                 "duplicadas", "limpeza", "qualidade", "resumo"}
SECOES_CONHECIDAS = SECOES_SEMPRE | {
    "grafico_ausentes", "estatisticas_numericas", "distribuicoes", "outliers", "frequencias",
    "texto_livre", "agregacoes", "barras_categoricas", "correlacao", "comparacao_grupos",
    "cruzamento_categoricas", "serie_temporal", "alvo"}
# Saídas obrigatórias depois da execução (tabela 6.3; seções condicionais ficam de fora).
SECOES_COM_IMAGEM = {"grafico_ausentes", "distribuicoes", "outliers", "barras_categoricas",
                     "correlacao", "comparacao_grupos", "cruzamento_categoricas",
                     "serie_temporal", "alvo"}
SECOES_COM_TABELA = {"leitura", "visao_geral", "estatisticas_numericas", "outliers",
                     "frequencias", "agregacoes", "correlacao", "cruzamento_categoricas",
                     "serie_temporal", "alvo"}

SECAO_TESTE = "metricas_teste"
PREFIXO_METRICAS = "METRICAS_EDA="
# Célula anexada pelos testes E2E (o plano, 6.3, garante estas variáveis no kernel).
CELULA_METRICAS = r'''
import json as _json
import pandas as _pd

def _texto_data(valor):
    return None if _pd.isna(valor) else _pd.Timestamp(valor).strftime("%Y-%m-%d %H:%M:%S")

_metricas = {
    "pandas": _pd.__version__,
    "len_df": int(len(df)),
    "len_df_bruto": int(len(df_bruto)),
    "colunas": [str(c) for c in df.columns],
    "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
    "notna": {str(c): int(df[c].notna().sum()) for c in df.columns},
    "datas": {str(c): [_texto_data(v) for v in df[c]] for c in df.columns
              if _pd.api.types.is_datetime64_any_dtype(df[c])},
    "numeros": {str(c): [None if _pd.isna(v) else float(v) for v in df[c]] for c in df.columns
                if _pd.api.types.is_numeric_dtype(df[c]) and len(df) <= 500},
    "hash": str(int(_pd.util.hash_pandas_object(df, index=False).sum())),
    "alvo": ALVO,
    "remover_duplicadas": bool(REMOVER_DUPLICADAS),
}
print("METRICAS_EDA=" + _json.dumps(_metricas, default=str))
'''


def ler_notebook(caminho) -> nbformat.NotebookNode:
    return nbformat.read(str(caminho), as_version=4)


def secao(celula) -> str | None:
    return celula.get("metadata", {}).get("eda", {}).get("secao")


def secoes(nb) -> list[str | None]:
    return [secao(c) for c in nb.cells]


def erros(nb) -> list[str]:
    """Descrição curta de cada saída de erro: 'célula N (secao): Tipo: mensagem'."""
    achados = []
    for i, celula in enumerate(nb.cells):
        for saida in celula.get("outputs", []):
            if saida.get("output_type") == "error":
                achados.append(f"célula {i} ({secao(celula)}): {saida.get('ename')}: "
                               f"{str(saida.get('evalue'))[:200]}")
    return achados


def stderr(nb, nome_secao: str) -> str:
    textos = [s.get("text", "") for c in nb.cells if secao(c) == nome_secao
              for s in c.get("outputs", [])
              if s.get("output_type") == "stream" and s.get("name") == "stderr"]
    return "".join(textos)[:500]


def tipos_de_saida(nb) -> dict[str, set[str]]:
    """{secao: {"image/png", "text/html", "stream", ...}} juntando todas as células da seção."""
    tipos: dict[str, set[str]] = defaultdict(set)
    for celula in nb.cells:
        for saida in celula.get("outputs", []):
            tipo = saida.get("output_type")
            if tipo in ("display_data", "execute_result"):
                tipos[secao(celula)].update(saida.get("data", {}).keys())
            else:
                tipos[secao(celula)].add(tipo)
    return tipos


def metricas(nb) -> dict:
    for celula in nb.cells:
        if secao(celula) != SECAO_TESTE:
            continue
        for saida in celula.get("outputs", []):
            for linha in saida.get("text", "").splitlines():
                if linha.startswith(PREFIXO_METRICAS):
                    return json.loads(linha[len(PREFIXO_METRICAS):])
    raise AssertionError(f"célula de métricas sem saída; erros no notebook: {erros(nb)}")


def compilar(fonte: str, nome: str = "<celula>"):
    """compile() de uma célula, aceitando mágicas do IPython (%matplotlib inline)."""
    return compile(TransformerManager().transform_cell(fonte), nome, "exec")


def anexar_celula(monkeypatch, celula: dict) -> None:
    """Faz `gerar` incluir `celula` no fim do notebook (plano, 6.3 e 7.3)."""
    import eda.cli
    import eda.codigo

    original = eda.codigo.gerar_celulas

    def com_celula_extra(*args, **kwargs):
        return list(original(*args, **kwargs)) + [dict(celula)]

    monkeypatch.setattr(eda.codigo, "gerar_celulas", com_celula_extra)
    if hasattr(eda.cli, "gerar_celulas"):
        monkeypatch.setattr(eda.cli, "gerar_celulas", com_celula_extra)


def rodar_main(argv) -> int:
    """Chama eda.cli.main e devolve o código de saída (inclusive o SystemExit do argparse)."""
    from eda.cli import main

    try:
        return main([str(a) for a in argv])
    except SystemExit as saida:
        return saida.code if isinstance(saida.code, int) else 1


def variantes_de_caminho(caminho: Path) -> list[str]:
    """Formas como um caminho pode aparecer no JSON de um notebook."""
    texto = str(caminho)
    return sorted({texto, json.dumps(texto)[1:-1], Path(texto).as_posix()})
