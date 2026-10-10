# Sessão 2026-10-10 10:30 — Migração para Supabase

**Usuário:** Paulo (arquiteto técnico) · **Ferramenta:** Claude Code (Sonnet 5.5)

## Prompt utilizado

> Ajuste de decisão técnica do time: não usaremos banco analítico local (DuckDB/SQLite). Nosso banco central oficial será o SUPABASE (PostgreSQL na nuvem).
>
> Estratégia de conformidade com o limite gratuito de 500 MB: filtrar em memória antes da carga (somente MT, CO_UF='51', e Graduação). O volume cai de centenas de MB para ~10-15 MB; atende ao critério de banco em nuvem e facilita o dashboard do pitch (Caminho 3).
>
> 1. Adicionar `psycopg2-binary` e `python-dotenv` ao `requirements.txt` (manter sqlalchemy e pandas); criar `.env.example` com `SUPABASE_DB_URL=postgresql://postgres:[SUA_SENHA]@[HOST_DO_SUPABASE]:5432/postgres`; garantir `.env` no `.gitignore`.
> 2. Criar `src/db.py` (SQLAlchemy/psycopg2, URL do `.env`, função de teste de conexão com logs claros).
> 3. Criar `src/01_ingestao_trajetoria_supabase.py`: ler as 6 planilhas de `archives/inep_trajetoria/` (cabeçalho na linha 9); CO_CURSO, CO_IES, CO_UF, CO_MUNICIPIO e CINE como texto; filtrar CO_UF='51' e TP_GRAU_ACADEMICO em [1,2,3]; criar/recriar `stg_trajetoria_mt` com DDL explícito (`sql/01_stg_trajetoria.sql`); truncate-and-load idempotente; calcular P1 e P2 por SQL no Supabase e salvar `outputs/p1_trajetoria_2015.csv` e `outputs/p2_ranking_desistencia.csv`.
> 4. Atualizar `docs/estrategia.md` e `docs/arquitetura.md` com a escolha do Supabase e a pré-filtragem; criar este log e atualizar `prompts/README.md`.

## Aproveitado / decisões técnicas
- Leitura e filtro do pipeline anterior reaproveitados; DuckDB removido do código, do `requirements.txt` e da documentação. Script `01_trajetoria_p1_p2.py` e saídas `.parquet` removidos.
- Filtro em memória medido: 26.513 linhas (~28 MB em memória) para as 6 coortes.
- Carga: DDL + `TRUNCATE` + `COPY` (psycopg2 `copy_expert`) em uma transação; confere contagem banco × memória; chave primária `(co_ies, co_curso, nu_ano_ingresso, nu_ano_referencia)`.
- P1 e P2 viraram arquivos SQL PostgreSQL parametrizados (`sql/02_*`, `sql/03_*`).
- RLS habilitada com política de leitura pública (a chave anon do Supabase expõe tabelas do schema `public`).
- `.gitignore`: `.env` e `.env.*`, exceto `.env.example`.
- Verificação sem acesso ao Supabase: as consultas SQL foram executadas em um motor local temporário sobre os dados reais e conferidas com as saídas anteriores (diferença apenas de arredondamento). A carga real no Supabase e `db.py` dependem da `SUPABASE_DB_URL` do time e ainda não foram executados.
- Ajuste posterior (governança): consultas `sql/02` e `sql/03` reescritas com filtros literais (PostgreSQL nativo, validadas com o parser do PostgreSQL); coluna `perda_anual_pct` renomeada para `tada_pct`; o log intermediário das 11:30, que citava DuckDB, foi removido por incoerência cronológica.
