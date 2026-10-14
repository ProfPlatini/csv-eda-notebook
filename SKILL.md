---
name: csv-eda-notebook
description: >-
  Gera um notebook Jupyter (.ipynb) já executado, em português, com a análise exploratória
  de um arquivo tabular do usuário: tipos de coluna, ausentes, duplicatas, qualidade,
  distribuições, outliers, frequências, correlações, comparação entre grupos, série
  temporal e um resumo com achados numéricos. Use sempre que alguém enviar ou apontar um
  CSV (.csv, .tsv, .txt, .csv.gz, .csv.zip; separado por vírgula, ponto e vírgula, tab ou
  barra vertical) e pedir para analisar, explorar, resumir, entender, "dar uma olhada" ou
  fazer uma EDA, mesmo sem dizer "notebook" ou "gráfico". Exemplos: "analisa esse CSV",
  "faz uma EDA do arquivo de vendas", "quero entender essas colunas", "tem correlação entre
  essas variáveis?", "o que se relaciona com o churn nessa base?". Não use para apenas
  converter formato (CSV para JSON ou Excel), para dados que não estão em arquivo tabular
  nem para treinar modelos.
license: MIT
compatibility: Requer Python 3.10+ com pandas, numpy, matplotlib e seaborn; nbclient, nbformat e ipykernel para executar o notebook. Roda localmente, sem rede.
---

# csv-eda-notebook

Transforma um CSV em um notebook Jupyter executado, com código legível em português e
análises escolhidas a partir do conteúdo real do arquivo.

## 1. Onde está o script

Os caminhos abaixo são relativos à pasta que contém este `SKILL.md` (chamada aqui de
`<DIR_SKILL>`). No Claude Code ela também está disponível em `${CLAUDE_SKILL_DIR}`.
Rode o script a partir de qualquer pasta, com caminhos absolutos:

```bash
python3 <DIR_SKILL>/scripts/gerar_eda.py /caminho/absoluto/dados.csv -o /caminho/absoluto/dados_eda.ipynb
```

Sem `-o`, o notebook é salvo ao lado do CSV como `<nome>_eda.ipynb`. No Windows, use
`python` em vez de `python3`.

## 2. Antes de rodar

- Sem o caminho do arquivo, peça ao usuário. Não adivinhe qual CSV analisar.
- Se o pedido cita uma variável de resultado ("o que influencia o churn", "preço",
  "conversão"), passe `--alvo <coluna>`. O nome pode vir com outra caixa ou sem acento.
- Não abra o CSV inteiro no contexto para "entender" antes: o script faz isso e devolve
  um resumo. Se precisar, leia só as primeiras linhas.

## 3. Dependências

Se a saída for `Erro: Dependência ausente: <pacote>` (código 1) ou o código de saída for 4,
avise o usuário e proponha:

```bash
python3 -m pip install -r <DIR_SKILL>/requirements.txt
```

de preferência dentro de um ambiente virtual. Não instale nada sem o usuário concordar.

## 4. Códigos de saída

| Código | Significado | O que fazer |
|---|---|---|
| 0 | Notebook gerado (e executado, salvo com `--nao-executar`) | Entregar o resultado (seção 5). |
| 1 | Erro de entrada: arquivo inexistente, vazio, só cabeçalho, ZIP com vários arquivos ou com pasta dentro, encoding inválido, `--alvo` inexistente, ambíguo ou inadequado, `-o` igual ao CSV ou sem `.ipynb`, dependência ausente | Ler a mensagem `Erro: ...` no stderr e corrigir o argumento. Para `--alvo`, a mensagem sugere colunas parecidas. |
| 2 | Uso incorreto da linha de comando (argparse) | Conferir as opções (seção 6). |
| 3 | Notebook gerado, mas uma célula falhou | A linha `Execução:` cita a célula, a seção e o erro. O arquivo tem as saídas até o erro; relate o problema ao usuário. |
| 4 | Notebook gerado sem execução: falta nbclient, nbformat ou ipykernel, ou o kernel não iniciou | Seção 3. O notebook pode ser rodado depois no Jupyter. |

## 5. Ler a saída e responder

O stdout tem sempre este formato:

```
Notebook gerado em: <caminho absoluto>
Execução: <ok | falhou na célula N (seção X): Tipo: mensagem | não executado: motivo>
Avisos:                (só quando há avisos)
- ...
---
<resumo em markdown: Visão geral, Principais achados, Pontos de atenção, Próximos passos>
```

Na resposta ao usuário:

1. Informe o caminho do notebook e se ele já tem gráficos (`Execução: ok`) ou se precisa
   ser executado.
2. Traga de 3 a 6 achados de "Principais achados", com os números como estão no resumo.
3. Cite as limitações que aparecem em `Avisos` e em "Pontos de atenção" (linhas
   ignoradas, datas ambíguas, duplicatas, categorias com grafias diferentes, ausentes).
4. Não afirme nada que não esteja na saída. Correlação e diferença entre grupos são
   associações, não causas.

## 6. Opções

| Opção | Quando usar |
|---|---|
| `--alvo COLUNA` | O usuário quer saber o que se relaciona com uma variável (numérica, binária ou categórica com até 20 classes). |
| `--titulo "..."` | Título específico no cabeçalho do notebook. |
| `--sep` | Só se a detecção errar: `,` `;` `\|` ou `tab`. |
| `--encoding` | Só se a detecção errar: `utf-8`, `cp1252`, `latin-1`. |
| `--decimal {.,,}` | Números como `1.234` lidos errado: `--decimal ,` força o padrão brasileiro. |
| `--max-graficos N` | Máximo de numéricas nos histogramas e boxplots (padrão 6). |
| `--nao-executar` | Base muito grande ou o usuário prefere rodar depois. |

A detecção cobre separador, encoding (utf-8, utf-8 com BOM, cp1252, latin-1), arquivos
`.gz`, `.zip`, `.bz2` e `.xz`, números com moeda e milhar (`R$ 1.234,56`, `1,234.56`),
datas ISO, `dd/mm/aaaa` e `mm/dd/aaaa`, colunas identificadoras e linhas malformadas.

## 7. Estrutura do notebook

Configuração e funções de apoio, leitura, visão geral e duplicatas, limpeza, qualidade
dos dados (ausentes e checagens), numéricas (descritivas, distribuições, outliers),
categóricas (frequências), texto livre, correlação (Pearson e Spearman), numéricas por
categoria, relação entre categóricas, evolução temporal, variável de interesse e resumo.
Só aparecem as seções que fazem sentido para as colunas do arquivo; a numeração se ajusta.

## 8. Ajustes no notebook gerado

O notebook é código comum. Para mudanças que as opções cobrem (alvo, separador, decimal,
encoding, título), gere de novo. Para o resto, edite as constantes no topo das células:

- `CSV_PATH` e `LEITURA` (configuração): outro arquivo com a mesma estrutura;
- `ALVO` (configuração) e `CLASSE_POSITIVA` (variável de interesse);
- `FORMATOS_DATA`, `REMOVER_DUPLICADAS` e `PLANO_LIMPEZA` (limpeza);
- `COLS_DESCRIBE`, `COLS_NUM_GRAFICO`, `COLS_FREQ`, `COLS_CAT_GRAFICO`, `COLS_CORR`,
  `PARES`, `A, B` (colunas de cada análise);
- `REGRAS` (série temporal): `D`, `W`, `MS`, `QS` ou `YS` por coluna de data.

Depois de editar, o usuário roda tudo de novo no Jupyter, VS Code ou Colab (*Run All*).
O resumo final é calculado na geração e não se atualiza sozinho.

## 9. Limites

- Datas em que todos os dias são até 12 são lidas como dia/mês (há aviso).
- Linhas idênticas só são removidas quando há coluna identificadora (ex.: `id_venda`).
- Números como `1.234` sem nenhuma vírgula no arquivo são lidos como 1,234; use
  `--decimal ,` se forem milhares.
- Não treina modelos nem faz testes de hipótese.
