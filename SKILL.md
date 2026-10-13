---
name: csv-eda-notebook
description: >-
  Gera um notebook Jupyter (.ipynb) com análise exploratória completa a partir de um
  arquivo CSV fornecido pelo usuário. Use esta skill sempre que alguém enviar uma base
  em CSV (ou .csv.zip, .tsv, arquivo separado por ponto e vírgula) e pedir para analisar,
  explorar, resumir, entender ou "dar uma olhada" nos dados — mesmo que a pessoa não diga
  as palavras "notebook", "EDA", "estatística" ou "gráfico". Exemplos de pedidos que
  devem acionar esta skill: "analisa esse CSV", "faz uma EDA do arquivo de vendas",
  "quero entender essas colunas", "gera um relatório dos dados em notebook",
  "tem uma base aqui, dá uma olhada nos dados", "qual a distribuição dessa coluna",
  "tem correlação entre essas variáveis?". Não use para CSV que precisa ser apenas
  convertido para outro formato (isso é outra tarefa), nem quando o pedido for sobre
  dados que não vieram em arquivo tabular.
---

# csv-eda-notebook

Transforma um CSV em um notebook Jupyter executado, com a análise adaptada ao conteúdo
real do arquivo.

## Quando usar

- O usuário anexa ou informa o caminho de um CSV e quer **entender os dados**: perfil,
  distribuições, categorias, correlações, evolução temporal, resumo.
- O pedido é vago ("dá uma olhada", "me ajuda a entender essa base") e o caminho é um CSV.

Não use quando: o pedido for apenas converter formato, limpar para um formato de
entrada específico (ex.: "converta para JSON"), ou quando os dados não são tabulares.

## Entrada esperada

- **Obrigatório:** caminho (ou caminho via anexo do usuário) de um arquivo CSV/TSV.
- **Opcional:** nome da coluna de interesse (variável alvo), título desejado para o
  notebook, separador ou encoding quando a autodetecção falhar.

Se o usuário não informar o caminho, peça o arquivo. Não tente adivinhar qual CSV ele
quer analisar.

## Como executar

Rode sempre o script versionado neste repositório — ele já contém a lógica de leitura,
classificação de colunas e geração do notebook:

```bash
python scripts/gerar_eda.py <caminho-do-csv> -o <saida.ipynb>
```

Opções úteis:

| Opção | Quando usar |
|---|---|
| `--alvo COLUNA` | O usuário falou de churn, preço, conversão, meta... Gere a seção da variável de interesse. |
| `--titulo "..."` | O usuário quer um título específico no cabeçalho. |
| `--sep ";"` / `--encoding latin-1` | Só quando a autodetecção falhar (o script avisa no resumo). |
| `--max-graficos N` | Bases muito largas; padrão é 6 variáveis numéricas nos gráficos. |
| `--nao-executar` | Bases grandes ou quando o usuário preferir rodar o notebook depois. |

O script detecta separador e encoding, classifica cada coluna (numérica, categórica,
data ou texto livre) e monta o notebook com código **escrito para as colunas que existem**.
Depois ele executa o notebook via `nbconvert` para que os gráficos já fiquem embutidos.

## Saída produzida

Um arquivo `.ipynb` (por padrão `<nome-do-csv>_eda.ipynb`, no mesmo diretório do CSV) com:

1. Configuração e funções de apoio (funções para converter texto em número e padronizar gráficos).
2. Leitura do CSV com os parâmetros detectados.
3. Visão geral: tipos, valores distintos por coluna, ausentes e duplicadas.
4. Limpeza mínima e transparente (espaços, números como texto, datas, duplicatas exatas),
   preservando a base original em `df_bruto`.
5. Estatísticas descritivas (numéricas) e frequências (categóricas).
6. Agregações por categoria e cruzamento entre categóricas.
7. Visualizações adaptadas: ausentes, histogramas, boxplots, barras de frequência,
   matriz de correlação, boxplot por categoria, cruzamento de categóricas e série temporal
   quando houver coluna de data.
8. Resumo em markdown com as principais observações, pontos de atenção e próximos passos.

## Como entregar o resultado

- Informe o caminho do `.ipynb` gerado e um resumo curto do que a análise encontrou
  (dimensões, tipos de coluna, variáveis mais relevantes).
- Se rodar o notebook foi possível, diga que os gráficos já estão no arquivo; caso
  contrário, avise que o notebook foi salvo sem resultados e precisa ser executado
  (`jupyter lab <arquivo>.ipynb`).
- Aponte as limitações reais: colunas ignoradas por serem identificadores, colunas de
  texto livre sem gráfico, conversões que falharam.

## Ajustes comuns no notebook gerado

O notebook é código comum — quando o usuário quiser algo além do padrão, edite as células
diretamente em vez de reescrever o script:

- trocar a paleta ou o tema: edite a célula de configuração (`sns.set_theme`, cores fixas);
- incluir mais variáveis nos gráficos: mude a lista `COLS_NUM_GRAFICO` / `COLS_CAT_GRAFICO`;
- usar outra periodicidade na série temporal: ajuste `REGRA` (`D`, `W`, `MS`, `QS`, `YS`);
- trocar o alvo: ajuste `ALVO` na célula correspondente.

## Requisitos

`pandas`, `matplotlib`, `seaborn` (obrigatórios) e `nbconvert` + `nbformat` + `ipykernel`
(opcionais, apenas para gravar os resultados no `.ipynb`). Instalação:

```bash
pip install -r requirements.txt
```