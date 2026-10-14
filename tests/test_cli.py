"""Linha de comando: códigos de saída, mensagens e stdout (plano, 6.4 e 7.3)."""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest

from utilitarios import anexar_celula, ler_notebook, rodar_main, secao, secoes


@pytest.mark.parametrize("nome, extras", [
    ("inexistente", []),
    ("vazio", []),
    ("so_cabecalho", []),
    ("diretorio", []),
    ("zip_dois_membros", []),
    ("exemplo", ["--encoding", "xyz"]),
    ("iso_datas", ["--alvo", "dt"]),          # alvo do tipo data (D03)
    ("br_cp1252", ["--alvo", "Observação"]),  # texto livre
    ("churn", ["--alvo", "cliente_id"]),      # identificador
    ("qualidade", ["--alvo", "constante"]),   # um único valor
])
def test_erros_de_entrada_saem_com_1(fabricar, tmp_path, capsys, nome, extras):
    csv = tmp_path / "nao_existe.csv" if nome == "inexistente" else fabricar(nome)
    codigo = rodar_main([csv, "-o", tmp_path / "saida.ipynb", "--nao-executar", *extras])
    saida = capsys.readouterr()
    assert codigo == 1, saida.err
    assert saida.err.startswith("Erro: "), saida.err
    assert "Traceback" not in saida.err


def test_alvo_inexistente_sai_com_1_e_sugere(fabricar, tmp_path, capsys):
    codigo = rodar_main([fabricar("churn"), "-o", tmp_path / "s.ipynb", "--nao-executar",
                         "--alvo", "Churnn"])
    erro = capsys.readouterr().err
    assert codigo == 1
    assert erro.startswith("Erro: ") and "Traceback" not in erro
    assert "Churnn" in erro and "churn" in erro, erro


def test_alvo_ignora_caixa(fabricar, tmp_path):
    saida = tmp_path / "s.ipynb"
    assert rodar_main([fabricar("churn"), "-o", saida, "--nao-executar", "--alvo", "CHURN"]) == 0
    nb = ler_notebook(saida)
    assert "alvo" in secoes(nb)
    fontes = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
    assert re.search(r"""ALVO\s*=\s*['"]churn['"]""", fontes), "ALVO deveria ser 'churn'"


@pytest.mark.parametrize("nome, opcoes", [
    ("tsv", ["--sep", "\\t"]),
    ("tsv", ["--sep", "\t"]),
    ("tsv", ["--sep", "tab"]),
    ("tsv", ["--sep", "TAB"]),
    ("pipe", ["--sep", "|"]),
    ("milhar_ptbr", ["--decimal", ","]),
    ("br_cp1252", ["--encoding", "cp1252"]),
], ids=["sep_barra_t", "sep_tab_real", "sep_tab", "sep_TAB", "sep_pipe", "decimal", "encoding"])
def test_opcoes_aceitas(fabricar, tmp_path, capsys, nome, opcoes):
    codigo = rodar_main([fabricar(nome), "-o", tmp_path / "s.ipynb", "--nao-executar", *opcoes])
    assert codigo == 0, capsys.readouterr().err


@pytest.mark.parametrize("nome, padrao", [
    ("malformado", r"linha 3\b"),                     # D10
    ("datas_br_ambiguas", r"(?i)amb[ií]gu"),           # D01: dd/mm assumido
    ("com_indice", r"(?i)[íi]ndice"),                  # D16: índice exportado
    ("sep_sobrando", r"Unnamed"),                      # D16: coluna vazia removida
    ("nomes_estranhos", r"valor"),                     # D11: 'valor ' renomeada
    ("dup_com_id", r"\b2 duplicatas removidas"),       # D02
    ("so_categoricas", r"\b48 linhas idênticas mantidas"),
])
def test_avisos_relevantes(gerar_sem_executar, nome, padrao):
    avisos = gerar_sem_executar(nome)[0].avisos
    assert any(re.search(padrao, aviso) for aviso in avisos), avisos


@pytest.mark.parametrize("valor", ["0", "-1"])
def test_max_graficos_invalido_e_erro_de_uso(fabricar, tmp_path, valor):
    argv = [fabricar("exemplo"), "-o", tmp_path / "s.ipynb", "--nao-executar", "--max-graficos", valor]
    assert rodar_main(argv) == 2


@pytest.mark.parametrize("nome, esperado", [
    ("exemplo", "vendas_exemplo_eda.ipynb"),
    ("exemplo_gz", "vendas_exemplo_eda.ipynb"),
    ("exemplo_zip", "vendas_exemplo_eda.ipynb"),
    ("tsv", "dados_eda.ipynb"),
])
def test_nome_padrao_da_saida(fabricar, nome, esperado):
    csv = fabricar(nome)
    assert rodar_main([csv, "--nao-executar"]) == 0
    assert (csv.parent / esperado).is_file(), sorted(p.name for p in csv.parent.iterdir())


def test_stdout_segue_o_contrato(fabricar, tmp_path, capsys):
    saida = tmp_path / "s.ipynb"
    assert rodar_main([fabricar("malformado"), "-o", saida, "--nao-executar"]) == 0
    linhas = capsys.readouterr().out.splitlines()

    caminho = re.fullmatch(r"Notebook gerado em: (.+)", linhas[0])
    assert caminho, linhas[:2]
    assert Path(caminho.group(1)).is_absolute() and Path(caminho.group(1)).samefile(saida)
    assert linhas[1].startswith("Execução: não executado"), linhas[1]
    assert "Avisos:" in linhas and "---" in linhas, linhas[:10]
    avisos = linhas[linhas.index("Avisos:") + 1: linhas.index("---")]
    assert avisos and all(a.startswith("- ") for a in avisos), avisos
    assert any(re.search(r"linha 3\b", a) for a in avisos), avisos
    assert "### Principais achados" in linhas[linhas.index("---"):]


def test_geracao_sem_runtime_warning(fabricar, tmp_path, capsys):
    """D26: ±inf e colunas constantes não podem vazar avisos do numpy."""
    with warnings.catch_warnings(record=True) as capturados:
        warnings.simplefilter("always")
        codigo = rodar_main([fabricar("degenerados"), "-o", tmp_path / "s.ipynb", "--nao-executar"])
    assert codigo == 0
    runtime = [str(w.message) for w in capturados if issubclass(w.category, RuntimeWarning)]
    assert not runtime, runtime
    assert capsys.readouterr().err == ""


def test_sem_kernel_sai_com_4(fabricar, tmp_path, monkeypatch, capsys):
    import eda.cli
    import eda.notebook

    for modulo in (eda.notebook, eda.cli):
        if hasattr(modulo, "dependencias_execucao"):
            monkeypatch.setattr(modulo, "dependencias_execucao", lambda: ["ipykernel"])
    codigo = rodar_main([fabricar("uma_numerica"), "-o", tmp_path / "s.ipynb"])
    saida = capsys.readouterr()
    assert codigo == 4, saida.out + saida.err
    assert "ipykernel" in saida.out + saida.err


@pytest.mark.e2e
def test_falha_de_execucao_sai_com_3(fabricar, tmp_path, monkeypatch, capsys):
    """D04: código 3, notebook gravado com as saídas anteriores e erro legível."""
    anexar_celula(monkeypatch, {"tipo": "code", "fonte": "raise ValueError('boom')", "secao": "teste"})
    saida = tmp_path / "s.ipynb"
    codigo = rodar_main([fabricar("uma_numerica"), "-o", saida])
    out = capsys.readouterr().out

    assert codigo == 3, out
    linha = next((l for l in out.splitlines() if l.startswith("Execução:")), "")
    assert re.search(r"falhou na célula \d+ \(seção teste\)", linha), linha
    assert "boom" in linha and "\x1b" not in out
    nb = ler_notebook(saida)
    anteriores = [c for c in nb.cells if c.cell_type == "code" and secao(c) != "teste"]
    assert any(c.outputs for c in anteriores), "saídas das células anteriores não foram gravadas"


def _erro_de_entrada(codigo, capsys) -> str:
    erro = capsys.readouterr().err
    assert codigo == 1, erro
    assert erro.startswith("Erro: ") and "Traceback" not in erro, erro
    return erro


@pytest.mark.parametrize("caso", ["proprio_csv", "sem_ipynb", "csv_chamado_ipynb"])
def test_saida_invalida_nao_toca_no_csv(fabricar, tmp_path, capsys, caso):
    csv = fabricar("exemplo")
    if caso == "csv_chamado_ipynb":
        csv = tmp_path / "dados.ipynb"
        csv.write_bytes(fabricar("exemplo").read_bytes())
    original = csv.read_bytes()
    destino = tmp_path / "analise.txt" if caso == "sem_ipynb" else csv
    _erro_de_entrada(rodar_main([csv, "-o", destino, "--nao-executar"]), capsys)
    assert csv.read_bytes() == original
    assert not (tmp_path / "analise.txt").exists()


def test_pasta_de_saida_que_e_arquivo(fabricar, capsys):
    csv = fabricar("exemplo")
    erro = _erro_de_entrada(rodar_main([csv, "-o", csv / "s.ipynb", "--nao-executar"]), capsys)
    assert "é um arquivo" in erro, erro


def test_alvo_vazio(tmp_path, capsys):
    csv = tmp_path / "vazio.csv"
    csv.write_text("a,b\n" + "".join(f"{i},\n" for i in range(10)), encoding="utf-8")
    erro = _erro_de_entrada(rodar_main([csv, "-o", tmp_path / "s.ipynb", "--nao-executar",
                                        "--alvo", "b"]), capsys)
    assert "está vazia" in erro, erro


def test_alvo_ambiguo(tmp_path, capsys):
    csv = tmp_path / "ambiguo.csv"
    csv.write_text("Preço,preco,grupo\n" + "".join(f"{i},{2 * i},{'ab'[i % 2]}\n" for i in range(20)),
                   encoding="utf-8")
    erro = _erro_de_entrada(rodar_main([csv, "-o", tmp_path / "s.ipynb", "--nao-executar",
                                        "--alvo", "PRECO"]), capsys)
    assert "ambíguo" in erro and "'Preço'" in erro and "'preco'" in erro, erro
