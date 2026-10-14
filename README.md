<div align="center">

# 📊 csv-eda-notebook

### Transforme um CSV em um notebook Jupyter de análise exploratória, já executado, com gráficos e resumo.

**Você envia o CSV. O agente entrega o notebook com os gráficos prontos e os principais achados.**

[![Testes](https://github.com/ProfPlatini/csv-eda-notebook/actions/workflows/testes.yml/badge.svg)](https://github.com/ProfPlatini/csv-eda-notebook/actions/workflows/testes.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![pandas](https://img.shields.io/badge/pandas-%3E%3D2.0-orange.svg)](https://pandas.pydata.org/)
[![Agentes: Claude Code · Codex · opencode · Claude.ai](https://img.shields.io/badge/agentes-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20opencode%20%C2%B7%20Claude.ai-8A2BE2.svg)](#-usando-com-agentes-de-ia)

**[📓 Ver o notebook de exemplo](exemplos/vendas_exemplo_eda.ipynb)** · **[🐛 Reportar issue](https://github.com/ProfPlatini/csv-eda-notebook/issues)** · **[📝 Changelog](CHANGELOG.md)**

</div>

---

## 🤔 O problema

> *"Tenho um CSV aqui, me ajuda a entender esses dados."*

Normalmente isso vira uma conversa longa: pedir para descrever colunas, pedir histogramas, pedir
correlações, pedir um resumo… **um pedido por vez, e cada resposta no chat se perde.**

## 🚀 A solução

Um **agente de IA** (ou você, pelo terminal) roda esta skill e recebe **um arquivo `.ipynb`**:
um notebook Jupyter com código legível em português, gráficos já renderizados e um resumo com
os achados dos seus dados, com números.

| Antes 😐 | Depois 🚀 |
|---|---|
| "quais colunas tem esse CSV?" | Um notebook com tudo, de uma vez |
| "agora faz um histograma da coluna X" | Gráficos já executados dentro do arquivo |
| "e tem correlação entre elas?" | Pearson e Spearman, com a força de cada par |
| Respostas espalhadas no chat | **Um arquivo que você abre, compartilha e reproduz** |

---

## ✨ O que você recebe

| | |
|---|---|
| 🧠 **Análise adaptada** | As seções dependem das colunas que existem: sem coluna de data, sem série temporal; sem categóricas, sem gráficos de frequência |
| 📈 **Gráficos prontos** | O notebook é executado na geração; gráficos e tabelas já vêm no `.ipynb` |
| 🧹 **Limpeza transparente** | Espaços, números gravados como texto, datas, infinitos e duplicatas, tudo descrito em `PLANO_LIMPEZA`; os dados originais ficam em `df_bruto` |
| 🔎 **Qualidade dos dados** | Ausentes, colunas constantes, categorias com grafias diferentes (`Sudeste` / `sudeste`), negativos raros, ids repetidos |
| 📝 **Resumo com números** | Correlações com força correta, diferenças entre grupos, tendência no tempo, outliers, pontos de atenção |
| 🇧🇷 **Tudo em português** | Código, comentários, títulos dos gráficos, números no formato `1.234,56` |

### 📋 Seções do notebook

Configuração e funções de apoio → leitura → visão geral e duplicatas → limpeza → qualidade dos
dados → variáveis numéricas (descritivas, distribuições, outliers) → categóricas (frequências) →
texto livre → correlação → numéricas por categoria → relação entre categóricas → evolução
temporal → variável de interesse (`--alvo`) → resumo.

Só aparecem as seções que fazem sentido para o arquivo, e a numeração se ajusta.

> 💡 **Nada é inventado.** Colunas que identificam registros (`id_venda`, `cpf`, um índice
> salvo por engano) são reconhecidas e ficam fora dos gráficos. Correlações e diferenças entre
> grupos são descritas como associações, nunca como causa.

---

## ⚡ Teste rápido (2 minutos)

```bash
git clone https://github.com/ProfPlatini/csv-eda-notebook.git
cd csv-eda-notebook

python3 -m venv .venv
source .venv/bin/activate          # 🪟 Windows: .venv\Scripts\activate
pip install -r requirements.txt

python scripts/gerar_eda.py exemplos/vendas_exemplo.csv -o analise_vendas_eda.ipynb --alvo valor_total
```

✅ **Saída (início):**

```
Notebook gerado em: /.../csv-eda-notebook/analise_vendas_eda.ipynb
Execução: ok
Avisos:
- 1 duplicata removida (linhas idênticas a uma anterior).
---
### Visão geral

- **Arquivo:** `vendas_exemplo.csv`
...
```

🎉 Abra com `jupyter lab analise_vendas_eda.ipynb`, no VS Code, ou envie o arquivo para o
[Google Colab](https://colab.research.google.com/). Se mover o notebook de pasta, ajuste
`CSV_PATH` na primeira célula de código.

---

## 📖 O exemplo, passo a passo

[`exemplos/vendas_exemplo.csv`](exemplos/vendas_exemplo.csv) tem 51 linhas de vendas de 2024 (data,
região, categoria, canal, vendedor, quantidade, preço, desconto, valor total e avaliação), com
alguns problemas de propósito (a venda 22, por exemplo, aparece duas vezes). O notebook gerado
com o comando abaixo está versionado em
[`exemplos/vendas_exemplo_eda.ipynb`](exemplos/vendas_exemplo_eda.ipynb) (o GitHub mostra os
gráficos):

```bash
python scripts/gerar_eda.py exemplos/vendas_exemplo.csv --alvo valor_total --titulo "Análise exploratória — vendas 2024"
```

Os números abaixo foram copiados dessa execução:

| Bloco | Resultado |
|---|---|
| 🔎 **Leitura e visão geral** | 51 linhas × 11 colunas; `id_venda` reconhecida como identificador |
| 🧹 **Limpeza** | `data_pedido` convertida no formato ISO; espaço removido de `" Vestuário"`; a venda 22, gravada duas vezes, vira uma (51 → 50 linhas) |
| ⚠️ **Qualidade** | `desconto_pct` com 3 ausentes (6,0%); `regiao` com as grafias `"Sudeste"` / `"sudeste"` |
| 📊 **Numéricas** | `valor_total`: mediana 323,65, de 89,90 a 3.149,10, assimetria 1,93; 12,0% de outliers em `preco_unitario` e em `valor_total` |
| 🔗 **Correlação** | `preco_unitario` × `valor_total`: r = 0,83 e rho = 0,44; `quantidade` × `preco_unitario`: rho = −0,81 |
| ⚖️ **Numéricas por categoria** | `valor_total` por `categoria` (eta² = 0,65): média de 1.453,55 em Eletrônicos contra 182,35 em Livros |
| 🔀 **Categóricas** | `regiao` × `vendedor`, V de Cramér = 0,61 |
| 📅 **Série temporal** | Mensal, de 05/01/2024 a 29/12/2024 |
| 🎯 **Alvo `valor_total`** | Distribuição, correlação com as outras numéricas e média por `categoria` e `vendedor` |
| 📝 **Resumo** | Achados, pontos de atenção e próximos passos ligados aos dados (ex.: unificar as grafias de `regiao`) |

---

## 🤖 Usando com agentes de IA

A skill segue o padrão **Agent Skills** (uma pasta com `SKILL.md`). O que muda entre os
agentes é onde a pasta fica e como ela é acionada.

| Agente | 📍 Onde instalar | 🎯 Como acionar |
|---|---|---|
| **Claude Code** | `~/.claude/skills/csv-eda-notebook` (pessoal) ou `.claude/skills/csv-eda-notebook` (no projeto) | Automático pelo pedido, ou `/csv-eda-notebook` |
| **Codex** | `~/.agents/skills/csv-eda-notebook` (usuário) ou `.agents/skills/csv-eda-notebook` (no repositório) | Automático, `$csv-eda-notebook` ou `/skills`; reinicie se não aparecer |
| **opencode** | `~/.config/opencode/skills/csv-eda-notebook`; também lê `~/.claude/skills` e `~/.agents/skills` | Automático, pela ferramenta `skill` |
| **Claude.ai** | Upload de um ZIP da pasta (veja abaixo) | Automático pelo pedido |

> ⚠️ O Python que o agente usa precisa ter as dependências:
> `pip install -r <pasta-da-skill>/requirements.txt` (de preferência num ambiente virtual).
> Sem `nbclient`/`ipykernel` o notebook é gerado sem execução e o script sai com código 4.

<details>
<summary><b>🤖 Claude Code</b></summary>

```bash
git clone https://github.com/ProfPlatini/csv-eda-notebook.git ~/.claude/skills/csv-eda-notebook
pip install -r ~/.claude/skills/csv-eda-notebook/requirements.txt
```

Frases que acionam a skill:

- 🗣️ *"Analisa esse CSV pra mim e me diz o que tem de interessante"*
- 🗣️ *"Faz uma EDA do arquivo de vendas que tá na pasta `dados/`"*
- 🗣️ *"Gera um notebook de exploração desse CSV; a coluna `churn` é o que importa"*

O Claude lê o `SKILL.md`, roda `scripts/gerar_eda.py`, entrega o caminho do notebook e resume
os achados. Depois é só pedir ajustes, e ele edita as células do notebook.

</details>

<details>
<summary><b>📘 Codex</b></summary>

```bash
git clone https://github.com/ProfPlatini/csv-eda-notebook.git ~/.agents/skills/csv-eda-notebook
pip install -r ~/.agents/skills/csv-eda-notebook/requirements.txt
```

Confira com `/skills` ou mencione com `$csv-eda-notebook`. Para usar só em um projeto, clone em
`.agents/skills/csv-eda-notebook` dentro do repositório.

> `$csv-eda-notebook analisa ~/Downloads/vendas.csv, a coluna churn é o alvo`

</details>

<details>
<summary><b>🐰 opencode</b></summary>

```bash
git clone https://github.com/ProfPlatini/csv-eda-notebook.git ~/.config/opencode/skills/csv-eda-notebook
pip install -r ~/.config/opencode/skills/csv-eda-notebook/requirements.txt
```

O opencode também procura skills em `~/.claude/skills` e `~/.agents/skills`: um único clone
pode servir a dois agentes.

</details>

<details>
<summary><b>🌐 Claude.ai</b> (não testado)</summary>

1. Gere o ZIP da skill a partir do clone (fica de fora o que não é da skill, como testes e CI):

   ```bash
   git archive --format=zip --prefix=csv-eda-notebook/ -o csv-eda-notebook.zip HEAD
   ```

2. Em *Customize → Skills*, clique em **+** → *Upload a skill* e envie o ZIP (em alguns planos o
   caminho é *Settings → Capabilities*). A opção *Code execution and file creation* precisa
   estar ativa.

A skill roda no contêiner do Claude, não na sua máquina. Não verificamos se `nbclient` e
`ipykernel` estão disponíveis lá; sem eles, o notebook sai sem execução (código 4) e você o
roda depois no Jupyter ou no Colab.

</details>

---

## 💻 Linha de comando

```bash
python scripts/gerar_eda.py <arquivo> [opções]
```

| ⚙️ Opção | 📌 Padrão | 📖 Descrição |
|---|---|---|
| `-o, --saida` | `<nome-do-csv>_eda.ipynb` ao lado do CSV | Notebook gerado (`dados.csv.zip` → `dados_eda.ipynb`) |
| `--alvo COLUNA` | — | Variável de interesse: numérica, binária ou categórica com até 20 classes |
| `--titulo "..."` | `Análise exploratória — <arquivo>` | Título do cabeçalho |
| `--sep` / `--separador` | 🔍 detectado | `,` `;` `\|` ou `tab` |
| `--encoding` | 🔍 detectado | `utf-8`, `cp1252`, `latin-1`... |
| `--decimal {.,,}` | 🔍 detectado | Força o separador decimal (`,` = padrão brasileiro, com milhar `.`) |
| `--max-graficos N` | `6` | Máximo de numéricas nos histogramas e boxplots |
| `--nao-executar` | executa | Salva o notebook sem rodar as células |

### 🚦 Códigos de saída

| Código | Significado |
|---|---|
| `0` | Notebook gerado (e executado, salvo com `--nao-executar`) |
| `1` | Erro de entrada, com mensagem `Erro: ...` em português no stderr: arquivo inexistente, vazio ou só com cabeçalho, ZIP com mais de um arquivo ou com pasta dentro, encoding inválido, `--alvo` inexistente (com sugestões), ambíguo ou inadequado, `-o` igual ao CSV ou sem `.ipynb`, dependência ausente |
| `2` | Uso incorreto das opções (ex.: `--max-graficos 0`) |
| `3` | Notebook gerado, mas uma célula falhou; a linha `Execução:` cita a célula, a seção e o erro, e o arquivo guarda as saídas até ali |
| `4` | Notebook gerado sem execução: falta `nbclient`, `nbformat` ou `ipykernel`, ou o kernel não iniciou |

### 🧠 O que a detecção automática resolve

| Situação | Exemplos tratados |
|---|---|
| Separador | `,` · `;` · tab · `\|`, com aspas; arquivo de uma coluna só |
| Encoding | UTF-8 · UTF-8 com BOM · cp1252 (Excel no Windows: `“ ” – €`) · Latin-1 |
| Compressão | `.csv.gz` · `.csv.zip` (um arquivo dentro) · `.bz2` · `.xz` |
| Números | `1.234,56` · `R$ 1.234,56` · `1,234.56` · `1.137` em arquivo brasileiro · `12%` · `(1.234,00)` |
| Datas | `AAAA-MM-DD` (com ou sem hora) · `DD/MM/AAAA` · `MM/DD/AAAA` · `DD-MM-AAAA` · `DD.MM.AAAA` |
| Problemas de leitura | Linhas com campos a mais (ignoradas, com aviso e número da linha) · nomes de coluna repetidos ou vazios · separador sobrando no fim das linhas · índice exportado (`Unnamed: 0`) |
| Identificadores | `id_venda` · `cnpj` · `codigoCliente` · códigos únicos como `PRT-00012` |

### 🧩 Como biblioteca Python

```python
import sys
sys.path.insert(0, "scripts")
from eda import gerar

resultado = gerar("dados.csv", saida="analise.ipynb", alvo="churn")
print(resultado.codigo, resultado.mensagem)   # 0 ok
print(resultado.resumo)                        # o mesmo resumo em markdown do terminal
```

---

## 🛠️ Instalação e dependências

> 📌 Requer **Python 3.10 ou superior**. Testado com pandas 2.0, 2.2 e 3.0.

| 📦 Pacote | 🎯 Para quê |
|---|---|
| `pandas`, `numpy` | Leitura, limpeza, agregações e correlações |
| `matplotlib`, `seaborn` | Gráficos |
| `nbformat`, `nbclient`, `ipykernel` | Executar o notebook e gravar gráficos e tabelas no `.ipynb` |

Sem os três últimos o notebook ainda é gerado, mas sem resultados (código de saída 4); rode-o
depois no Jupyter. O notebook é executado num kernel do **mesmo Python** que roda o script, então
basta instalar tudo num único ambiente.

---

## 🗂️ Estrutura do repositório

```
csv-eda-notebook/
├── SKILL.md                    # instruções que o agente lê
├── README.md · CHANGELOG.md · LICENSE
├── requirements.txt            # dependências da skill
├── requirements-dev.txt        # + pytest, para os testes
├── .gitattributes              # o que fica fora do ZIP da skill (git archive)
├── .github/workflows/testes.yml  # CI (Linux e Windows)
├── exemplos/
│   ├── vendas_exemplo.csv      # base pequena para experimentar
│   └── vendas_exemplo_eda.ipynb  # notebook gerado com --alvo valor_total
├── scripts/
│   ├── gerar_eda.py            # ponto de entrada da linha de comando
│   └── eda/
│       ├── cli.py              # argumentos, validação e orquestração
│       ├── loader.py           # leitura do arquivo e perfil das colunas
│       ├── apoio.py            # limpeza e diagnósticos (copiado para dentro do notebook)
│       ├── codigo.py           # escolhe as análises e escreve as células
│       ├── resumo.py           # resumo em markdown com os números reais
│       └── notebook.py         # monta, grava e executa o .ipynb
└── tests/                      # pytest (unitários e ponta a ponta)
```

### 🔄 Como os módulos conversam

```
 📄 CSV ──▶ loader ──▶ apoio.limpar_dados ──▶ codigo.selecionar_colunas ──┬──▶ resumo
           (leitura,    (mesmo plano que o      (o que analisar)          │
            perfil)      notebook executa)                                ▼
                                                              codigo.gerar_celulas
                                                                          │
                                                                          ▼
                                                     notebook (grava e executa) ──▶ 📓 .ipynb
```

`cli` coordena tudo. O resumo e o notebook partem do **mesmo** `df` limpo e da **mesma** seleção
de colunas, e as funções de `apoio.py` são copiadas para o notebook: os números do resumo batem
com as tabelas.

---

## ⚠️ Limitações conhecidas

| Situação | Comportamento |
|---|---|
| Linhas idênticas | Removidas só quando há coluna identificadora (`id`, `codigo`...); sem ela, ficam e o notebook avisa. Mude `REMOVER_DUPLICADAS` na seção de limpeza se precisar. |
| Datas ambíguas | Se todos os dias forem até 12, a coluna é lida como dia/mês (padrão brasileiro), com aviso. Troque o formato em `FORMATOS_DATA` se for mês/dia. |
| Milhar sem vírgula | Em arquivo sem nenhum número com vírgula decimal, `1.234` é lido como 1,234. Use `--decimal ,` se forem milhares. |
| Gráficos | Até 6 numéricas nos histogramas (`--max-graficos`), 4 categóricas nos gráficos de barras, 15 numéricas na correlação, 3 pares numérica × categoria, 2 colunas de data. Os pontos individuais dos boxplots usam amostra de 2.000 linhas em bases grandes; as estatísticas usam a base inteira. |
| Estatística | Descritiva e exploratória: sem p-valores, testes de hipótese ou modelos. |
| Kernel | O notebook é executado com o Python que roda o script (não com um kernel `python3` instalado à parte). |

### 🎨 Personalizando o notebook gerado

O notebook é código comum. Cada análise começa com constantes que você pode editar:

| O que mudar | 📍 Onde |
|---|---|
| Arquivo e leitura | `CSV_PATH`, `LEITURA` (configuração) |
| Variável de interesse | `ALVO` (configuração) e `CLASSE_POSITIVA` (seção do alvo) |
| Limpeza | `FORMATOS_DATA`, `REMOVER_DUPLICADAS`, `PLANO_LIMPEZA` |
| Colunas de cada análise | `COLS_DESCRIBE`, `COLS_NUM_GRAFICO`, `COLS_FREQ`, `COLS_CAT_GRAFICO`, `COLS_CORR`, `PARES` |
| Periodicidade da série temporal | `REGRAS` (`D`, `W`, `MS`, `QS`, `YS` por coluna de data) |

---

## ❓ Perguntas frequentes

<details>
<summary><b>O notebook já vem com os gráficos ou preciso executar?</b></summary>

**Já vem.** O script executa o notebook com `nbclient` e grava os resultados no `.ipynb`. Se
faltar `nbclient`, `nbformat` ou `ipykernel`, o arquivo sai sem resultados, o script avisa e
termina com código 4; aí é só abrir no Jupyter e rodar tudo.
</details>

<details>
<summary><b>Funciona com meu CSV "bagunçado" (ponto e vírgula, acento, moeda, milhar)?</b></summary>

Na maioria dos casos, sim: veja a tabela da detecção automática. Quando algo for lido errado,
force com `--sep`, `--encoding` ou `--decimal`. Os avisos da saída dizem o que foi ajustado
(linhas ignoradas, datas ambíguas, colunas renomeadas).
</details>

<details>
<summary><b>Funciona sem agente de IA?</b></summary>

**Sim.** `scripts/gerar_eda.py` é um script de linha de comando comum e roda em qualquer lugar
com Python 3.10+.
</details>

<details>
<summary><b>O que acontece se uma célula falhar?</b></summary>

O notebook é salvo mesmo assim, com as saídas até a célula que falhou. A linha `Execução:` diz
qual célula, de qual seção, e o erro; o código de saída é 3.
</details>

---

## 🧪 Desenvolvimento

```bash
pip install -r requirements-dev.txt
python -m pytest -m "not lento"      # unitários e ponta a ponta (executa notebooks)
python -m pytest -m lento            # desempenho com 200 mil linhas
```

O CI roda a suíte no Linux (pandas 2.0, 2.2 e 3.x) e no Windows.

---

## 📄 Licença

<div align="center">

**MIT**: veja [LICENSE](LICENSE)

Feito por [ProfPlatini](https://github.com/ProfPlatini)

</div>
