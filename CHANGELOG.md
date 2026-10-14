# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões seguem [SemVer](https://semver.org/lang/pt-BR/).

## [1.0.0] — 2026-10-14

Primeira versão publicada. Em relação ao protótipo inicial:

### Corrigido
- Datas: um único detector de formato (ISO, dd/mm/aaaa, mm/dd/aaaa e variações) usado na geração, na limpeza e no resumo. Datas ISO não são mais destruídas e datas ambíguas viram dia/mês com aviso.
- Duplicatas: só são removidas quando existe coluna identificadora, e sempre contadas nos dados brutos. Bases sem chave não perdem linhas legítimas.
- `--alvo` numérico (inclusive 0/1) não quebra mais o notebook; o tipo do alvo vem do perfil da coluna. Alvo inexistente gera erro com sugestões.
- Falha na execução: o notebook é gravado com as saídas parciais, a mensagem cita célula, seção e erro (sem códigos de cor), e o código de saída é 3.
- Datas com e sem hora na mesma coluna (`05/03/2024` e `05/03/2024 14:30`) são todas convertidas.
- Alvo categórico com células vazias não quebra mais no pandas 3 (os ausentes aparecem como `(ausente)`); a classe comparada ignora grafias raras.
- Colunas chamadas `registros` ou `n`, categorias com o valor `Total` e nomes como `<<CAT>>` não quebram mais as células.
- Colunas `True`/`False` com células vazias não derrubam mais a limpeza.
- O kernel é encerrado ao fim de cada execução.
- Série temporal: linhas e barras no mesmo eixo de datas, lacunas visíveis e contagem igual ao número de linhas por período.
- Tabelas que não apareciam (describe, correlação, agregações, série temporal) agora são exibidas.
- Leitura: separador por consistência de campos (arquivo de uma coluna com vírgula decimal), `.gz`/`.zip`/`.bz2`/`.xz`, cp1252, milhar brasileiro (`1.137` = 1137) sem confundir coordenadas (`-23.550520`) nem `0.125`, linhas malformadas ignoradas com aviso (inclusive quando são até metade do arquivo), nomes de coluna repetidos ou vazios, colunas `Unnamed` vazias e índice exportado.
- Resumo calculado sobre os mesmos dados limpos e a mesma seleção do notebook; força das correlações com escala correta; números em pt-BR.
- Nomes de coluna com aspas, barras ou crases não quebram mais as células; o CSV é referenciado por caminho relativo.
- Mensagens de erro de entrada em português, sem traceback, com códigos de saída documentados (0, 1, 2, 3, 4).

### Adicionado
- Seção de qualidade (constantes, ausentes, categorias quase iguais, negativos raros, alta cardinalidade, id repetido, infinitos).
- Tabela de outliers (regra de Tukey), correlação de Spearman ao lado de Pearson, pares numérica × categoria escolhidos por eta² e par de categóricas por V de Cramér.
- Seção de variável de interesse para alvo numérico, binário ou categórico.
- Opção `--decimal`; `--sep` aceita `tab`.
- Avisos quando o pandas descarta um campo a mais ou troca nomes de coluna repetidos ou vazios.
- `-o` igual ao próprio CSV, ou sem `.ipynb`, é recusado em vez de sobrescrever os dados.
- Notebook de exemplo executado em `exemplos/` e testes automatizados com CI.

### Alterado
- Execução com `nbclient` (no mesmo Python que roda o script) em vez de `nbconvert`.

[1.0.0]: https://github.com/ProfPlatini/csv-eda-notebook/releases/tag/v1.0.0
