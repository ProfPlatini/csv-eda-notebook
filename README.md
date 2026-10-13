# csv-eda-notebook

**por [ProfPlatini](https://github.com/ProfPlatini)**

Skill para agentes de IA que transforma um **arquivo CSV em um notebook Jupyter (`.ipynb`)**
com análise exploratória de dados — visão geral, estatísticas, gráficos adaptados ao conteúdo
real e um resumo em markdown.

Você envia o CSV, o agente gera o notebook com os gráficos já executados.

- **Stack:** pandas + matplotlib + seaborn (sem outras bibliotecas de análise).
- **Linguagem do código, da documentação e das saídas:** português.
- **Agentes compatíveis:** Claude Code, Claude.ai, Codex e opencode (todos leem o padrão
  Agent Skills / `SKILL.md`). Também funciona direto no terminal, sem agente.

---

## Índice

- [Teste rápido](#teste-rápido)
- [O que o notebook gerado contém](#o-que-o-notebook-gerado-contém)
- [Instalação](#instalação)
- [Uso pela linha de comando](#uso-pela-linha-de-comando)
- [Exemplo de uso](#exemplo-de-uso)
- [Usando com agentes de IA](#usando-com-agentes-de-ia)
  - [Claude Code](#claude-code) · [Claude.ai (web, desktop e app)](#claudeai-web-desktop-e-app)
  · [Codex](#codex) · [opencode](#opencode)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Decisões de projeto](#decisões-de-projeto)
- [Publicar no GitHub](#publicar-no-github)
- [Licença](#licença)

---

## Teste rápido

Rode isto antes de configurar qualquer agente — leva cerca de 2 minutos e valida o
código. O `pip install` baixa pandas, seaborn e nbconvert.

```bash
cd csv-eda-notebook    # ou a pasta onde você clonou

python3 -m venv .venv
source .venv/bin/activate                        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python scripts/gerar_eda.py exemplos/vendas_exemplo.csv \
    -o analise_vendas.ipynb --alvo avaliado --titulo "Análise exploratória — vendas 2024"
```

Saída esperada:

```
Notebook gerado em: /.../analise_vendas.ipynb
Notebook executado com sucesso: gráficos e tabelas já estão no arquivo.
```

Abra com `jupyter lab analise_vendas.ipynb` ou arraste o arquivo para o Colab. Se a
`source` falhar no seu shell, use o interpretador direto: `./.venv/bin/python scripts/gerar_eda.py ...`.

Outros testes válidos:

```bash
# base real: detecção automática de separador, encoding, moeda e datas
python scripts/gerar_eda.py ~/Downloads/meu_arquivo.csv -o analise_meu.ipynb

# base grande: gera rápido, sem rodar as células
python scripts/gerar_eda.py base_grande.csv --nao-executar --max-graficos 10

# quando a detecção automática errar
python scripts/gerar_eda.py dados.csv --sep ";" --encoding latin-1
```

## O que o notebook gerado contém

| Seção | Conteúdo |
|---|---|
| 0. Configuração | Parâmetros de leitura e funções de apoio para os gráficos |
| 1. Carregamento | `pd.read_csv` com separador e encoding detectados |
| 2. Visão geral | Dimensões, tipos por coluna, valores distintos, ausentes e duplicadas |
| 3. Limpeza mínima | Espaços em texto, números como texto (moeda/separador de milhar), datas, duplicatas exatas |
| 4. Estatísticas | `describe` + distorção/cauda para numéricas; frequências para categóricas; exemplos para texto livre |
| 5. Agregações | Métricas por categoria e tabela de contingência entre categóricas |
| 6. Visualizações | Ausentes, histogramas, boxplots, barras de frequência, correlação, boxplot por categoria, cruzamento, série temporal |
| 7. Variável de interesse | Seção extra gerada quando você informa `--alvo` |
| 8. Resumo | Principais achados, pontos de atenção e próximos passos em markdown |

Tudo é decidido a partir do arquivo: **não existem seções genéricas com placeholders**.
Um CSV sem coluna de data não gera série temporal; um CSV de uma coluna numérica gera
apenas o que faz sentido para uma coluna. Colunas que parecem identificador (`id_venda`,
`cnpj`) são reconhecidas e deixadas de fora dos gráficos por não terem significado analítico.

## Instalação

Requer **Python 3.10 ou superior**.

```bash
git clone https://github.com/ProfPlatini/csv-eda-notebook.git
cd csv-eda-notebook

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

O que cada dependência faz:

| Pacote | Para quê |
|---|---|
| `pandas` | Leitura, limpeza, agregação e correlação |
| `matplotlib` | Base dos gráficos |
| `seaborn` | Estilo e os gráficos prontos (histograma, boxplot, heatmap) |
| `numpy` | Dependência do pandas, usada na organização dos gráficos |
| `nbformat`, `nbconvert`, `ipykernel` | Opcional: gravam os resultados no `.ipynb` |

Se você instalar só os três primeiros, o script ainda gera o notebook — apenas sem os
gráficos embutidos (aviso na saída). Para gravar os resultados:

```bash
pip install nbformat nbconvert ipykernel
```

## Uso pela linha de comando

```bash
python scripts/gerar_eda.py <arquivo.csv> [opções]
```

| Opção | Padrão | Descrição |
|---|---|---|
| `-o, --saida` | `<nome-do-csv>_eda.ipynb` | Caminho do notebook gerado |
| `--alvo COLUNA` | — | Variável de interesse (gera a seção 7) |
| `--titulo "..."` | `Análise exploratória — <arquivo>` | Título do cabeçalho |
| `--sep` / `--separador` | autodetectado | Ex.: `--sep ";"` |
| `--encoding` | autodetectado | Ex.: `--encoding latin-1` |
| `--max-graficos N` | `6` | Máximo de variáveis numéricas nos gráficos |
| `--nao-executar` | executa | Salva o notebook sem rodar as células |

A detecção automática resolve os casos mais comuns: `,` `;` `\t` `|`, com ou sem
aspas; encoding UTF-8, UTF-8 com BOM e Latin-1; números com separador de milhar ou
decimal vírgula (`1.234,56`, `R$ 1.234,56`, `1,234.56`); datas em `AAAA-MM-DD`,
`DD/MM/AAAA` e afins.

Como biblioteca Python:

```python
import sys
sys.path.insert(0, "scripts")
from eda import gerar

caminho, mensagem = gerar("dados.csv", saida="analise.ipynb", alvo="churn")
```

## Exemplo de uso

Existe um arquivo de exemplo em [`exemplos/vendas_exemplo.csv`](exemplos/vendas_exemplo.csv)
(50 vendas, com data, região, categoria, canal, valores e uma coluna de avaliação).

```bash
python scripts/gerar_eda.py exemplos/vendas_exemplo.csv \
    -o analise_vendas.ipynb \
    --alvo avaliado \
    --titulo "Análise exploratória — vendas 2024"
```

```
Notebook gerado em: /caminho/analise_vendas.ipynb
Notebook executado com sucesso: gráficos e tabelas já estão no arquivo.
```

O arquivo `analise_vendas.ipynb` (43 células, 8 gráficos) sai com:

- **Visão geral:** 50 linhas x 11 colunas, `id_venda` reconhecida como identificador,
  2 linhas duplicadas (idênticas às vendas 1 e 3).
- **Descritivas:** `valor_total` de 89,90 a 2.469,81, com assimetria à direita por causa
  dos eletrônicos; `preco_unitario`, `quantidade` e `desconto_pct`.
- **Categóricas:** região, categoria, canal e vendedor com frequência e percentual.
- **Correlações:** heatmap entre as quatro numéricas + tabela dos pares ordenados por `r`.
- **Comparações:** `valor_total` e `preco_unitario` por região (boxplot + pontos).
- **Cruzamento:** composição de categoria por região em heatmap.
- **Série temporal:** média e volume de vendas por mês (detecção automática de `MS`).
- **Alvo `avaliado`:** distribuição das classes e boxplots das numéricas por classe.
- **Resumo em markdown** com achados, pontos de atenção e próximos passos.

Para conferir sem gerar nada novo, abra qualquer notebook com
[JupyterLab](https://jupyterlab.readthedocs.io/) ou
[Colab](https://colab.research.google.com/).

## Usando com agentes de IA

Todos os agentes abaixo seguem o padrão **Agent Skills** (uma pasta com `SKILL.md`),
então a mesma skill funciona nos quatro. O que muda é só **onde a pasta é instalada**.

| Agente | Caminho da skill | Como acionar |
|---|---|---|
| Claude Code | `~/.claude/skills/csv-eda-notebook` | Automático, ou `/csv-eda-notebook` |
| Claude.ai (app desktop) | pela UI de skills | Automático, digitando `@` na conversa |
| Codex | `~/.agents/skills/csv-eda-notebook` | Automático, ou `$csv-eda-notebook` |
| opencode | `~/.config/opencode/skills/csv-eda-notebook` | Automático |

Depois de instalar, garanta que o Python que o agente executa tem as dependências:

```bash
pip install -r requirements.txt    # rode dentro do venv que o agente usa
```

### Claude Code

```bash
git clone https://github.com/ProfPlatini/csv-eda-notebook.git \
    ~/.claude/skills/csv-eda-notebook
pip install -r ~/.claude/skills/csv-eda-notebook/requirements.txt
```

Reinicie o Claude Code. A skill aparece automaticamente em `/skills` (ou digite
`/csv-eda-notebook`). Exemplos de pedidos que a acionam:

- "Analisa esse CSV pra mim e me diz o que tem de interessante"
- "Faz uma EDA do arquivo de vendas que tá na pasta `dados/`"
- "Gera um notebook de exploração desse CSV, a coluna `churn` é o que importa"
- "Quero entender a distribuição e as correlações dessa base"

O Claude lê o `SKILL.md`, roda `scripts/gerar_eda.py`, entrega o caminho do notebook
e resume os achados. Depois é só pedir ajustes ("inclui as vendas online também",
"usa escala logarítmica no eixo de valor") — ele edita as células do notebook.

### Claude.ai (web, desktop e app)

Na web o Claude não executa código na sua máquina, então **suba o script para um
ambiente com Python** (Codespaces, Colab, seu servidor) e envie o arquivo do CSV junto
com o `SKILL.md`:

> "Use as instruções deste SKILL.md. O CSV está anexo. Gere o notebook e me diga os
> principais achados."

Para uso recorrente, no app desktop use **Configurações → Skills → Adicionar** e
aponte para a pasta do repositório clonado; aí a skill fica disponível em todas as
conversas, com execução local.

### Codex

```bash
git clone https://github.com/ProfPlatini/csv-eda-notebook.git \
    ~/.agents/skills/csv-eda-notebook
```

Reinicie o Codex e confira com `/skills` (ou mencione com `$csv-eda-notebook`). Para
usar só dentro de um projeto, basta clonar dentro do repositório em
`.agents/skills/csv-eda-notebook` — o Codex detecta a skill ao subir na pasta.

> `$csv-eda-notebook analisa ~/Downloads/vendas.csv, a coluna churn é o alvo`

O Codex também aceita um `AGENTS.md` no projeto. Se preferir não instalar a skill,
basta colocar no `AGENTS.md` do repositório uma linha como
*"para análise exploratória de CSV, rode `python scripts/gerar_eda.py <arquivo>`"*.

### opencode

```bash
git clone https://github.com/ProfPlatini/csv-eda-notebook.git \
    ~/.config/opencode/skills/csv-eda-notebook
```

A skill é descoberta automaticamente ao iniciar o opencode. Se você estiver usando a
configuração padrão com `AGENTS.md`, uma alternativa é chamar o script direto pelo
terminal — ele funciona sem nenhuma configuração de agente.

## Estrutura do repositório

```
csv-eda-notebook/
├── SKILL.md                  # instruções que o agente lê (quando acionar, como rodar)
├── README.md                 # este arquivo
├── LICENSE                   # MIT
├── requirements.txt
├── .gitignore
├── exemplos/
│   └── vendas_exemplo.csv    # base pequena para experimentar
└── scripts/
    ├── gerar_eda.py          # ponto de entrada da linha de comando
    └── eda/
        ├── __init__.py       # expõe gerar() e main()
        ├── cli.py            # argumentos e orquestração
        ├── loader.py         # leitura (separador/encoding) e classificação de colunas
        ├── codigo.py         # monta as células do notebook a partir do conteúdo do CSV
        ├── resumo.py         # texto de resumo em markdown com números reais
        └── notebook.py       # montagem do .ipynb, gravação e execução
```

O fluxo é linear e cada arquivo tem uma função só: `loader` entende o arquivo →
`codigo` decide o que analisar → `resumo` escreve as conclusões → `notebook` monta e
executa → `cli` coordena.

## Decisões de projeto

Escolhas que fiz por conta própria porque o pedido não especificava. Todas são fáceis
de ajustar:

| # | Escolha | Onde ajustar |
|---|---|---|
| 1 | Nome do repositório: **`csv-eda-notebook`**, licença **MIT**, autor **`ProfPlatini`** | `README.md`, `LICENSE`, `pyproject.toml` (se criar) |
| 2 | Agentes-alvo: **Claude Code, Claude.ai, Codex e opencode** — todos seguem o padrão Agent Skills; só o caminho de instalação muda | Seção "Usando com agentes de IA" do `README.md` |
| 3 | O notebook é **executado por padrão** para vir com gráficos embutidos; se `nbconvert` faltar, é salvo sem resultados com um aviso | `scripts/eda/notebook.py` (`executar`) e `--nao-executar` |
| 4 | Detecção de tipos com regras fixas: conversível para número com moeda aceito, datas dentro de faixa plausível (1971–ano corrente +2), `id`/`cnpj` por palavra inteira do nome | `scripts/eda/loader.py` (`classificar_coluna`) |
| 5 | A limpeza remove **duplicatas exatas** e reporta quantas linhas saíram; a base original fica preservada em `df_bruto` | `scripts/eda/codigo.py` (`_celula_limpeza`) |
| 6 | Limite de 6 variáveis numéricas e 4 categóricas nos gráficos, para o notebook não virar uma parede de figuras | `scripts/eda/codigo.py` (constantes no topo) |
| 7 | Números no padrão brasileiro no resumo (`1.234,56`), com os títulos dos gráficos sem acento para não quebrar em ambientes sem UTF-8 | `scripts/eda/resumo.py` |
| 8 | Sem testes automatizados nem `pyproject.toml`: o objetivo é a skill ser copiável e legível. Para publicar no PyPI seria o próximo passo | — |
| 9 | Os gráficos do notebook não usam acento em títulos (`"Frequencia"`, não `"Frequência"`), para evitar `UnicodeEncodeError` em ambientes Windows sem UTF-8 | `scripts/eda/codigo.py` |

Se você quiser algo diferente, comece por `SKILL.md` (comportamento do agente) e por
`codigo.py` (conteúdo do notebook).

## Publicar no GitHub

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

Antes de publicar, revise:

- [x] autor `ProfPlatini` no `README.md` e no `LICENSE`;
- [ ] se o repositório for se cham `ProfPlatini/csv-eda-notebook`, mantenha o nome do
      projeto (`name` do `SKILL.md`) igual ao nome da pasta da skill; se preferir outro,
      renomeie os dois juntos e atualize os comandos de clone acima;
- [ ] `git status` não deve mostrar `*.ipynb` gerados (já estão no `.gitignore`);
- [ ] confirmar que `requirements.txt` está com as versões mínimas, e não fixadas demais.

Depois de publicada, para instalar a skill em qualquer um dos agentes basta o comando
de clone da seção [Usando com agentes de IA](#usando-com-agentes-de-ia).

## Licença

MIT — veja [LICENSE](LICENSE).