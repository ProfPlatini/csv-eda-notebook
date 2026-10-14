"""Resumo em markdown devolvido por gerar() (plano, D12, D22, D25, M03, M04)."""

from __future__ import annotations

import re

import pandas as pd
import pytest

from eda.apoio import classificar_correlacao

ORDEM_FORCA = ["desprezível", "fraca", "moderada", "forte", "muito forte"]
NUMERO = r"(-?\d+(?:,\d+)?)"


def _resumo(gerar_sem_executar, nome, alvo=None) -> str:
    return gerar_sem_executar(nome, alvo)[0].resumo


def test_categorias_contadas_depois_da_limpeza(gerar_sem_executar):
    resumo = _resumo(gerar_sem_executar, "espaco_categoria")
    assert "2 categorias" in resumo, resumo     # "X" e " X" são a mesma categoria (D12)
    assert "3 categorias" not in resumo


def test_periodo_de_datas_br(gerar_sem_executar):
    assert "01/01/2024 a 30/03/2024" in _resumo(gerar_sem_executar, "datas_br")


def test_uma_numerica_sem_correlacao(gerar_sem_executar):
    resumo = _resumo(gerar_sem_executar, "uma_numerica")
    assert not re.search(r"(?im)^#+.*correla", resumo), resumo
    assert not re.search(rf"\b(?:r|rho)\s*=\s*{NUMERO}", resumo), resumo


def _achados(resumo: str) -> str:
    assert "### Principais achados" in resumo, resumo
    return resumo.split("### Principais achados", 1)[1].split("\n#", 1)[0]


def test_indice_exportado_fora_dos_achados(gerar_sem_executar):
    assert "Unnamed" not in _achados(_resumo(gerar_sem_executar, "com_indice"))   # D16


# (fixture, alvo, nº mínimo de linhas com correlação e força citadas)
@pytest.mark.parametrize("nome, alvo, minimo", [("exemplo", None, 2), ("exemplo", "valor_total", 2),
                                                ("churn", "churn", 1), ("larga", None, 0)])
def test_texto_do_resumo(gerar_sem_executar, nome, alvo, minimo):
    resumo = _resumo(gerar_sem_executar, nome, alvo)

    # D25: números em pt-BR e plural correto.
    ponto = re.findall(r"\b(?:r|rho|skew|assimetria)\s*=\s*-?\d+\.\d", resumo)
    assert not ponto, f"número com ponto decimal: {ponto}"
    assert not re.search(r"\b1 categorias\b", resumo)

    # D22/M03: a força citada bate com o maior |r| ou |rho| da mesma linha.
    conferidas = 0
    for linha in resumo.splitlines():
        valores = [abs(float(v.replace(",", "."))) for v in
                   re.findall(rf"\b(?:r|rho|ρ)\s*=\s*{NUMERO}", linha)]
        citadas = [f for f in ORDEM_FORCA if re.search(rf"(?<!muito )\b{f}\b", linha)]
        if valores and citadas:
            esperada = classificar_correlacao(max(valores))
            assert esperada in citadas, f"força errada ({esperada} esperada): {linha}"
            conferidas += 1
    assert conferidas >= minimo, f"esperava >= {minimo} correlações com força no resumo:\n{resumo}"

    # M04: no máximo 12 bullets em "Principais achados".
    bloco = _achados(resumo)
    bullets = [l for l in bloco.splitlines() if re.match(r"\s*[-*] ", l)]
    assert 1 <= len(bullets) <= 12, bloco


def test_semanas_citadas_com_os_rotulos_da_tabela(gerar_sem_executar, fabricar_sessao):
    """resample("W") rotula a semana pelo domingo: o resumo cita as datas que a tabela mostra."""
    resumo = _resumo(gerar_sem_executar, "colisoes")
    citadas = re.search(r"Por semana .*?\((\d\d/\d\d/\d{4}) → (\d\d/\d\d/\d{4})\)", resumo)
    assert citadas, resumo
    dados = pd.read_csv(fabricar_sessao("colisoes"), parse_dates=["data"]).set_index("data")
    rotulos = set(dados.resample("W").size().index.strftime("%d/%m/%Y"))
    assert set(citadas.groups()) <= rotulos, (citadas.groups(), sorted(rotulos))
