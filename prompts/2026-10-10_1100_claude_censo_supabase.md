# Sessão 2026-10-10 11:00 — Censo da Educação Superior + IBGE no Supabase (P3, B1, B2)

**Usuário:** Paulo (arquiteto técnico) · **Ferramenta:** Claude Code (Sonnet 5.5)

## Prompt utilizado

> Implementar `src/02_censo_supabase.py` para responder P3, B1 e B2 com os microdados do Censo da Educação Superior (2021 a 2024) e do IBGE.
>
> Restrição de storage (Supabase gratuito, 500 MB): filtrar Mato Grosso durante a leitura de cada CSV; nunca enviar outros estados.
>
> 1. Leitura/filtro em memória: CSVs de Cursos 2021-2024 em chunks (';', latin-1/cp1252); `CO_CURSO`, `CO_IES`, `CO_MUNICIPIO`, `CO_UF` como string; filtrar `CO_UF == '51'` e `TP_NIVEL_ACADEMICO == 1`.
> 2. EAD tem várias linhas por município de polo: P3 e B2 consolidam por `(NU_ANO_CENSO, CO_CURSO)`; B1 usa só presencial (`TP_MODALIDADE_ENSINO == 1`) por `CO_MUNICIPIO`.
> 3. DDL `sql/04_stg_censo_mt.sql` com `stg_censo_cursos_mt` e `stg_ibge_populacao_mt` (jovens 18-24 de MT, tabela 9514 do IBGE); carga TRUNCATE + COPY transacional com validação de contagem.
> 4. `sql/05_p3_evasao_censo.sql` (evasão = DESVINCULADO / (MAT + DESVINCULADO + TRANSFERIDO) por ano, rede e modalidade, células < 10 suprimidas → `outputs/p3_evasao_censo.csv`); `sql/06_b1_desertos.sql` (vagas presenciais 2024 por 100 jovens de 18-24 e municípios sem oferta → `outputs/b1_desertos_ensino_superior.csv`); `sql/07_b2_financiamento.sql` (rede privada, proporção FIES + ProUni, evasão de alta vs baixa adesão → `outputs/b2_financiamento_permanencia.csv`).
> 5. Registrar a sessão e atualizar `prompts/README.md`.

## Aproveitado / decisões técnicas
- Leitura em chunks de 100 mil linhas com `usecols`; filtro MT + Graduação por chunk. Lidas ~2,4 milhões de linhas nos 4 CSVs; ficaram 62.662 (~22 MB em memória).
- **EAD:** nos dados, as linhas de polos de um mesmo curso têm valores diferentes de matrícula/desvinculados (não são cópias). Por isso a consolidação por `(ano, curso)` **soma** as linhas dos polos de MT. Presencial tem uma linha por curso. A chave primária do staging é `(nu_ano_censo, co_curso, co_municipio)`.
- **IBGE:** `archives/ibge/` tem só metadados e a página HTML da tabela 9514, sem os valores. O script baixa os dados da API SIDRA (Censo 2022; idades 18, 19 e 20-24; 141 municípios) e guarda o JSON em `archives/ibge/ibge_9514_mt_18_24_2022.json` (cache; `--atualizar-ibge` rebaixa). Total de jovens 18-24 em MT: 397.671.
- **Rede:** pública = `TP_REDE` 1; privada separada por `TP_CATEGORIA_ADMINISTRATIVA` (4 = com fins lucrativos, 5 = sem fins lucrativos).
- **B2:** como ~85% dos cursos privados têm 0% de financiados, a mediana não separa grupos; adotou-se corte fixo de 10% (alta ≥ 10%). Excluídos cursos sem ingressantes e 1 curso com proporção > 100%. Resultado interpretado como associação, não causalidade.
- **B1:** parte de todos os municípios do IBGE; 101 dos 141 municípios têm 0 vagas presenciais em 2024 (11 deles registram curso, mas com 0 vagas). Outlier: São José dos Quatro Marcos (412 vagas por 100 jovens).
- Verificação: SQL validado com o parser do PostgreSQL e executado num motor local temporário sobre os dados reais; **a carga no Supabase e as extrações finais ainda dependem da `SUPABASE_DB_URL` e não foram executadas**. Os CSVs de `outputs/` desta sessão vêm desse motor local e serão regravados na primeira execução real.
