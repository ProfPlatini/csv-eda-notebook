<div align="center">

# 📊 csv-eda-notebook

### Transforme qualquer CSV em um notebook Jupyter de análise exploratória — pronto, com gráficos e resumo.

**Você envia o CSV. O agente entrega o notebook com os gráficos já executados.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![pandas](https://img.shields.io/badge/pandas-%3E%3D2.0-orange.svg)](https://pandas.pydata.org/)
[![seaborn](https://img.shields.io/badge/seaborn-%3E%3D0.13-teal.svg)](https://seaborn.pydata.org/)
[![Agentes: Claude Code · Claude.ai · Codex · opencode](https://img.shields.io/badge/agentes-Claude%20Code%20%C2%B7%20Claude.ai%20%C2%B7%20Codex%20%C2%B7%20opencode-8A2BE2.svg)](#-usando-com-agentes-de-ia)
[![Feito com](https://img.shields.io/badge/feito%20com-opencode%20%F0%9F%90%BB%20space%20bunny-free-ff69b4.svg)](https://opencode.ai)

**[⭐ Star no GitHub](https://github.com/ProfPlatini/csv-eda-notebook)** · **[🐛 Reportar issue](https://github.com/ProfPlatini/csv-eda-notebook/issues)** · **[📖 Ver exemplos](exemplos/)**

</div>

---

## 🤔 O problema

> *"Tenho um CSV aqui, me ajuda a entender esses dados."*

Normalmente isso vira uma conversa longa: pedir para descrever colunas, pedir histograms, pedir
correlações, pedir um resumo… **um pedido por vez, e cada resposta no chat se perde.**

## 🚀 A solução

Um **agente de IA** executa esta skill e entrega **um arquivo `.ipynb`**: um notebook Jupyter
completo, com código legível em português, gráficos já renderizados e um resumo com os principais
achados dos seus dados.

| Antes 😐 | Depois 🚀 |
|---|---|
| "quais colunas tem esse CSV?" | Um notebook com tudo, de uma vez |
| "agora faz um histograma da coluna X" | Gráficos já executados dentro do arquivo |
| "e tem correlação entre elas?" | Resumo em markdown no final do notebook |
| Respostas espalhadas no chat | **Um arquivo que você abre, compartilha e reproduz** |

---

## ✨ O que você recebe

| | |
|---|---|
| 🧠 **Análise real** | Nada de seções genéricas com placeholders — tudo é decidido a partir do conteúdo do seu arquivo |
| 📈 **Gráficos prontos** | Já embutidos no `.ipynb`, sem precisar executar nada |
| 🇧🇷 **Tudo em português** | Código, comentários, títulos dos gráficos e o resumo |
| 🧠 **Resumo com achados** | Principais observações, pontos de atenção e próximos passos |
| 🤖 **Zero configuração de agente** | Funciona com Claude Code, Claude.ai, Codex e opencode — ou direto no terminal |
| 🧪 **Base de exemplo** | Um CSV pronto em [`exemplos/`](exemplos/) para você testar em 2 minutos |

### 📋 As 9 seções do notebook gerado

| Seção | O que tem | Ícone |
|---|---|---|
| 0. Configuração | Parâmetros de leitura e funções de apoio para os gráficos | ⚙️ |
| 1. Carregamento | `pd.read_csv` com separador e encoding **detectados automaticamente** | 📥 |
| 2. Visão geral | Dimensões, tipos por coluna, valores distintos, ausentes e duplicadas | 🔎 |
| 3. Limpeza mínima | Espaços em texto, números como texto (moeda/separador de milhar), datas, duplicatas | 🧹 |
| 4. Estatísticas | `describe` + distorção/cauda para numéricas; frequências para categóricas | 📊 |
| 5. Agregações | Métricas por categoria e tabela de contingência entre categóricas | 🧮 |
| 6. Visualizações | Ausentes, histogramas, boxplots, barras, correlação, boxplot por categoria, série temporal | 🎨 |
| 7. Variável de interesse | Seção extra gerada quando você informa `--alvo` (ex.: churn, preço) | 🎯 |
| 8. Resumo | Principais achados, pontos de atenção e próximos passos em markdown | 📝 |

> 💡 **Nada é inventado.** Um CSV sem coluna de data **não** gera série temporal. Um CSV de uma
> única coluna numérica gera **apenas** o que faz sentido. Colunas que parecem identificador
> (`id_venda`, `cnpj`) são reconhecidas e deixadas de fora dos gráficos — porque número de nota
> fiscal não tem significado analítico.

---

## ⚡ Teste rápido (2 minutos)

Rode isto **antes** de configurar qualquer agente — valida o código e já te entrega um notebook.

```bash
git clone https://github.com/ProfPlatini/csv-eda-notebook.git
cd csv-eda-notebook

python3 -m venv .venv
source .venv/bin/activate          # 🪟 Windows: .venv\Scripts\activate
pip install -r requirements.txt

python scripts/gerar_eda.py exemplos/vendas_exemplo.csv \
    -o analise_vendas.ipynb --alvo avaliado --titulo "Análise exploratória — vendas 2024"
```

✅ **Saída esperada:**

```
Notebook gerado em: /.../analise_vendas.ipynb
Notebook executado com sucesso: gráficos e tabelas já estão no arquivo.
```

🎉 Pronto. Abra com:

```bash
jupyter lab analise_vendas.ipynb
```

…ou arraste o arquivo direto para o [Google Colab](https://colab.research.google.com/).

> 💡 Se o `source` falhar no seu shell, use o interpretador direto:
> `./.venv/bin/python scripts/gerar_eda.py ...`

### 🧪 Outros testes válidos

```bash
# 📂 base real: detecção automática de separador, encoding, moeda e datas
python scripts/gerar_eda.py ~/Downloads/meu_arquivo.csv -o analise_meu.ipynb

# ⚡ base grande: gera rápido, sem rodar as células
python scripts/gerar_eda.py base_grande.csv --nao-executar --max-graficos 10

# 🛠️ quando a detecção automática errar
python scripts/gerar_eda.py dados.csv --sep ";" --encoding latin-1
```

---

## 📖 O que acontece com o arquivo de exemplo

Usando [`exemplos/vendas_exemplo.csv`](exemplos/vendas_exemplo.csv) (50 vendas, com data,
região, categoria, canal, valores e uma coluna de avaliação), o notebook sai com **43 células
e 8 gráficos**:

| Bloco | Resultado |
|---|---|
| 🔎 **Visão geral** | 50 linhas × 11 colunas, `id_venda` reconhecida como identificador, 2 linhas duplicadas |
| 📊 **Descritivas** | `valor_total` de 89,90 a 2.469,81, com assimetria à direita por causa dos eletrônicos |
| 🏷️ **Categóricas** | região, categoria, canal e vendedor com frequência e percentual |
| 🔗 **Correlações** | heatmap entre as 4 numéricas + tabela dos pares ordenados por `r` |
| ⚖️ **Comparações** | `valor_total` e `preco_unitario` por região (boxplot + pontos) |
| 🔀 **Cruzamento** | composição de categoria por região em heatmap |
| 📅 **Série temporal** | média e volume de vendas por mês (detecção automática de `MS`) |
| 🎯 **Alvo `avaliado`** | distribuição das classes e boxplots das numéricas por classe |
| 📝 **Resumo** | achados, pontos de atenção e próximos passos em markdown |

---

## 🤖 Usando com agentes de IA

Todos os agentes abaixo seguem o padrão **Agent Skills** (uma pasta com `SKILL.md`).
A mesma skill funciona nos quatro — o que muda é **só onde a pasta é instalada**.

| Agente | 📍 Caminho da skill | 🎯 Como acionar |
|---|---|---|
| **Claude Code** | `~/.claude/skills/csv-eda-notebook` | Automático, ou `/csv-eda-notebook` |
| **Claude.ai** (app desktop) | pela UI de skills | Automático, digitando `@` na conversa |
| **Codex** | `~/.agents/skills/csv-eda-notebook` | Automático, ou `$csv-eda-notebook` |
| **opencode** | `~/.config/opencode/skills/csv-eda-notebook` | Automático |

> ⚠️ Depois de instalar, garanta que o **Python que o agente executa** tem as dependências:
> ```bash
> pip install -r requirements.txt    # rode dentro do venv que o agente usa
> ```

<details>
<summary><b>🤖 Claude Code</b> — clique para expandir</summary>

```bash
git clone https://github.com/ProfPlatini/csv-eda-notebook.git \
    ~/.claude/skills/csv-eda-notebook
pip install -r ~/.claude/skills/csv-eda-notebook/requirements.txt
```

Reinicie o Claude Code. A skill aparece automaticamente em `/skills` (ou digite
`/csv-eda-notebook`).

**Frases que acionam a skill** — copie e cole:

- 🗣️ *"Analisa esse CSV pra mim e me diz o que tem de interessante"*
- 🗣️ *"Faz uma EDA do arquivo de vendas que tá na pasta `dados/`"*
- 🗣️ *"Gera um notebook de exploração desse CSV, a coluna `churn` é o que importa"*
- 🗣️ *"Quero entender a distribuição e as correlações dessa base"*

O Claude lê o `SKILL.md`, roda `scripts/gerar_eda.py`, entrega o caminho do notebook e resume
os achados. Depois é só pedir ajustes — *"inclui as vendas online também"*, *"usa escala
logarítmica no eixo de valor"* — e ele edita as células do notebook.

</details>

<details>
<summary><b>🌐 Claude.ai (web, desktop e app)</b> — clique para expandir</summary>

Na web o Claude não executa código na sua máquina, então **suba o script para um ambiente com
Python** (Codespaces, Colab, seu servidor) e envie o CSV junto com o `SKILL.md`:

> *"Use as instruções deste SKILL.md. O CSV está anexo. Gere o notebook e me diga os principais achados."*

Para uso recorrente, no **app desktop** use *Configurações → Skills → Adicionar* e aponte para
a pasta do repositório clonado. Aí a skill fica disponível em todas as conversas, com execução local.

</details>

<details>
<summary><b>📘 Codex</b> — clique para expandir</summary>

```bash
git clone https://github.com/ProfPlatini/csv-eda-notebook.git \
    ~/.agents/skills/csv-eda-notebook
```

Reinicie o Codex e confira com `/skills` (ou mencione com `$csv-eda-notebook`).

Para usar **só dentro de um projeto**, basta clonar dentro do repositório em
`.agents/skills/csv-eda-notebook` — o Codex detecta a skill ao subir na pasta.

> `$csv-eda-notebook analisa ~/Downloads/vendas.csv, a coluna churn é o alvo`

💡 O Codex também aceita um `AGENTS.md` no projeto. Se preferir **não** instalar a skill, basta
colocar no `AGENTS.md` do repositório uma linha como:
*"para análise exploratória de CSV, rode `python scripts/gerar_eda.py <arquivo>`"*.

</details>

<details>
<summary><b>🐰 opencode</b> — clique para expandir</summary>

```bash
git clone https://github.com/ProfPlatini/csv-eda-notebook.git \
    ~/.config/opencode/skills/csv-eda-notebook
```

A skill é descoberta **automaticamente** ao iniciar o opencode.

💡 Se você estiver na configuração padrão com `AGENTS.md`, uma alternativa é chamar o script
direto pelo terminal — ele funciona sem nenhuma configuração de agente.

</details>

---

## 💻 Uso pela linha de comando

```bash
python scripts/gerar_eda.py <arquivo.csv> [opções]
```

| ⚙️ Opção | 📌 Padrão | 📖 Descrição |
|---|---|---|
| `-o, --saida` | `<nome-do-csv>_eda.ipynb` | Caminho do notebook gerado |
| `--alvo COLUNA` | — | Variável de interesse (gera a seção 🎯 7) |
| `--titulo "..."` | `Análise exploratória — <arquivo>` | Título do cabeçalho |
| `--sep` / `--separador` | 🔍 autodetectado | Ex.: `--sep ";"` |
| `--encoding` | 🔍 autodetectado | Ex.: `--encoding latin-1` |
| `--max-graficos N` | `6` | Máximo de variáveis numéricas nos gráficos |
| `--nao-executar` | executa | Salva o notebook sem rodar as células |

### 🧠 O que a detecção automática resolve

| Situação | Exemplos tratados |
|---|---|
| Separadores | `,` · `;` · `\t` · `|` — com ou sem aspas |
| Encodings | UTF-8 · UTF-8 com BOM · Latin-1 |
| Números | `1.234,56` · `R$ 1.234,56` · `1,234.56` |
| Datas | `AAAA-MM-DD` · `DD/MM/AAAA` e afins |
| Identificadores | `id_venda` · `cnpj` · `cpf` — fora dos gráficos |

### 🧩 Como biblioteca Python

```python
import sys
sys.path.insert(0, "scripts")
from eda import gerar

caminho, mensagem = gerar("dados.csv", saida="analise.ipynb", alvo="churn")
```

---

## 🛠️ Instalação e dependências

> 📌 Requer **Python 3.10 ou superior**.

```bash
git clone https://github.com/ProfPlatini/csv-eda-notebook.git
cd csv-eda-notebook

python -m venv .venv
source .venv/bin/activate          # 🪟 Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

| 📦 Pacote | 🎯 Para quê |
|---|---|
| `pandas` | Leitura, limpeza, agregação e correlação |
| `matplotlib` | Base dos gráficos |
| `seaborn` | Estilo e os gráficos prontos (histograma, boxplot, heatmap) |
| `numpy` | Dependência do pandas, usada na organização dos gráficos |
| `nbformat` `nbconvert` `ipykernel` | *Opcional:* gravam os resultados (gráficos) no `.ipynb` |

> ⚠️ Se você instalar **só os três primeiros**, o script ainda gera o notebook — apenas sem os
> gráficos embutidos (com um aviso na saída). Para gravar os resultados:
> ```bash
> pip install nbformat nbconvert ipykernel
> ```

---

## 🗂️ Estrutura do repositório

```
csv-eda-notebook/
├── 📄 SKILL.md                  # instruções que o agente lê (quando acionar, como rodar)
├── 📖 README.md                 # este arquivo
├── ⚖️ LICENSE                   # MIT
├── 📦 requirements.txt
├── 🚫 .gitignore
├── 📂 exemplos/
│   └── 🗒️ vendas_exemplo.csv    # base pequena para experimentar
└── 📂 scripts/
    ├── 🐍 gerar_eda.py          # ponto de entrada da linha de comando
    └── 📂 eda/
        ├── __init__.py          # expõe gerar() e main()
        ├── cli.py               # argumentos e orquestração
        ├── loader.py            # leitura (separador/encoding) e classificação de colunas
        ├── codigo.py            # monta as células do notebook a partir do conteúdo do CSV
        ├── resumo.py            # texto de resumo em markdown com números reais
        └── notebook.py          # montagem do .ipynb, gravação e execução
```

### 🔄 Como os módulos conversam

```
   📄 CSV
     │
     ▼
 ┌───────────┐   entende o arquivo
 │  loader   │ ───────────────┐
 └───────────┘                │
     │                        ▼
     ▼                 ┌───────────┐
 ┌───────────┐         │  codigo   │ decide o que analisar
 │   cli     │ ──────▶ └───────────┘
 └───────────┘                │
     │                        ▼
     ▼                 ┌───────────┐
 ┌───────────┐         │  resumo   │ escreve as conclusões
 │ notebook  │ ◀────── └───────────┘
 └───────────┘
     │
     ▼
 📓 analise_eda.ipynb  (gráficos já executados)
```

O fluxo é **linear** e cada arquivo tem uma função só: `loader` → `codigo` → `resumo` →
`notebook`, coordenados pelo `cli`.

---

## 🧠 Decisões de projeto

Escolhas que fiz por conta própria porque o pedido não especificava. Todas são fáceis de ajustar:

| # | Escolha | 📍 Onde ajustar |
|---|---|---|
| 1 | Nome do repositório **`csv-eda-notebook`**, licença **MIT**, autor **`ProfPlatini`** | `README.md`, `LICENSE` |
| 2 | Agentes-alvo: **Claude Code, Claude.ai, Codex e opencode** — só o caminho muda | Seção "Usando com agentes de IA" |
| 3 | O notebook é **executado por padrão** para vir com gráficos embutidos; se `nbconvert` faltar, é salvo sem resultados com aviso | `scripts/eda/notebook.py` · flag `--nao-executar` |
| 4 | Detecção de tipos com regras fixas: conversível para número com moeda aceito, datas em faixa plausível (1971–ano+2), `id`/`cnpj` por palavra inteira | `scripts/eda/loader.py` (`classificar_coluna`) |
| 5 | A limpeza remove **duplicatas exatas** e reporta quantas saíram; a base original fica em `df_bruto` | `scripts/eda/codigo.py` (`_celula_limpeza`) |
| 6 | Limite de 6 numéricas e 4 categóricas nos gráficos, para não virar uma parede de figuras | `scripts/eda/codigo.py` (constantes no topo) |
| 7 | Números no padrão brasileiro (`1.234,56`), com títulos dos gráficos **sem acento** para não quebrar em ambientes sem UTF-8 | `scripts/eda/resumo.py` |
| 8 | Sem testes automatizados nem `pyproject.toml`: o objetivo é a skill ser **copiável e legível** | — |

> 💡 Para mudar o comportamento do agente → comece pelo `SKILL.md`.
> Para mudar o conteúdo do notebook → comece pelo `codigo.py`.

### 🎨 Personalizando o notebook gerado

O notebook é **código comum** — quando você quiser algo além do padrão, edite as células
diretamente em vez de reescrever o script:

| O que mudar | 📍 Onde |
|---|---|
| Paleta / tema dos gráficos | célula de configuração (`sns.set_theme`, cores fixas) |
| Mais variáveis nos gráficos | listas `COLS_NUM_GRAFICO` / `COLS_CAT_GRAFICO` |
| Periodicidade da série temporal | variável `REGRA` (`D`, `W`, `MS`, `QS`, `YS`) |
| Trocar a variável de interesse | `ALVO` na célula correspondente |

---

## ❓ Perguntas frequentes

<details>
<summary><b>O notebook já vem com os gráficos ou preciso executar?</b></summary>

**Já vem.** Por padrão o script executa o notebook via `nbconvert` e grava os resultados dentro
do `.ipynb`. Se faltar o `nbconvert`, o arquivo é salvo **sem** resultados e um aviso aparece
na saída — basta rodar `jupyter lab <arquivo>.ipynb`.
</details>

<details>
<summary><b>Funciona com meu CSV "bagunçado" (separador ;, acento, moeda, milhar)?</b></summary>

Sim — a detecção automática cobre `,` `;` `\t` `|`, UTF-8 / UTF-8 com BOM / Latin-1,
`R$ 1.234,56`, `1.234,56`, `1,234.56` e datas em vários formatos. Se ainda assim errar, force
com `--sep` e `--encoding`.
</details>

<details>
<summary><b>Funciona sem agente de IA?</b></summary>

**Sim.** O `scripts/gerar_eda.py` é um CLI comum e roda em qualquer lugar com Python 3.10+.
A skill de agente é só uma forma automatizada de te poupar de decorar os comandos.
</details>

<details>
<summary><b>Posso mudar o conteúdo do notebook?</b></summary>

**Sim.** Ele é gerado a partir do seu arquivo, mas o resultado é código Python comum. Edite as
células direto no Jupyter, ou ajuste as constantes em `scripts/eda/codigo.py`.
</details>

<details>
<summary><b>Funciona com `.tsv`, `.csv.zip` ou arquivo com ponto e vírgula?</b></summary>

Sim, desde que seja tabular. Arquivos que precisam apenas de **conversão de formato** (ex.:
"converta para JSON") não são o caso de uso desta skill.
</details>

---

## 🚀 Publicar no GitHub

<details>
<summary><b>Clique para expandir os comandos</b></summary>

```bash
# 1. dentro da pasta do projeto
git init -b main
git add .
git commit -m "feat: skill de análise exploratória de CSV com geração de notebook"

# 2. crie o repositório vazio no GitHub (sem README/LICENSE, para não conflitar)
gh repo create ProfPlatini/csv-eda-notebook --public --description \
  "Skill para agentes de IA: transforma CSV em notebook Jupyter de análise exploratória"

# 3. publique
git remote add origin https://github.com/ProfPlatini/csv-eda-notebook.git
git push -u origin main

# 4. tag de versão
git tag -a v1.0.0 -m "Primeira versão"
git push origin v1.0.0
```

**Checklist antes de publicar:**

- [x] autor `ProfPlatini` no `README.md` e no `LICENSE`
- [ ] nome do projeto (`name` do `SKILL.md`) igual ao nome da pasta da skill
- [ ] `git status` não mostra `*.ipynb` gerados (já estão no `.gitignore`)
- [ ] `requirements.txt` com versões mínimas, não fixadas demais

</details>

---

## 📄 Licença

<div align="center">

**MIT** — veja [LICENSE](LICENSE)

Feito por [ProfPlatini](https://github.com/ProfPlatini)

</div>