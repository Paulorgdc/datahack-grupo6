# Arquitetura

```
archives/inep_trajetoria/*.xlsx      (Raw, local, fora do Git)
        │  openpyxl (streaming, cabeçalho linha 9)
        │  filtro em memória: CO_UF='51' + Graduação  (~26,5 mil linhas, ~28 MB)
        ▼
src/01_ingestao_trajetoria_supabase.py
        │  psycopg2: DDL + TRUNCATE + COPY (1 transação)
        ▼
Supabase (PostgreSQL) ── public.stg_trajetoria_mt          [Staging]
        │  sql/02_p1_trajetoria.sql · sql/03_p2_ranking_desistencia.sql
        ▼
outputs/p1_trajetoria_2015.csv · outputs/p2_ranking_desistencia.csv   [Analytical]
        ▼
dashboard/ (Caminho 3 — lê do Supabase ou dos CSVs)
```

## Módulos

| Arquivo | Responsabilidade |
|---|---|
| `src/db.py` | Engine SQLAlchemy/psycopg2 a partir de `SUPABASE_DB_URL` (`.env`); `testar_conexao()` com logs (sem expor a senha). `python src/db.py` testa a conexão. |
| `src/01_ingestao_trajetoria_supabase.py` | Leitura + filtro, carga idempotente, execução de P1/P2 no banco, exportação dos CSVs |
| `sql/01_stg_trajetoria.sql` | DDL explícito, índice, RLS e política de leitura |
| `sql/02_p1_trajetoria.sql` | P1: coorte 2015 presencial, TDA/TCA/TAP ponderadas e ano de maior perda |
| `sql/03_p2_ranking_desistencia.sql` | P2: ranking por CINE (rótulo e área geral), coortes 2015 vs 2020 no 5º ano, grupos < 10 omitidos |

### Censo e IBGE (P3, B1, B2)

| Arquivo | Responsabilidade |
|---|---|
| `src/02_censo_supabase.py` | Lê os CSVs de Cursos 2021-2024 em chunks filtrando MT + Graduação, baixa a população 18-24 do SIDRA 9514, carrega `stg_censo_cursos_mt` e `stg_ibge_populacao_mt` (TRUNCATE + COPY) e exporta os CSVs |
| `sql/04_stg_censo_mt.sql` | DDL das duas tabelas de staging (grão curso × município; EAD com uma linha por polo) |
| `sql/05_p3_evasao_censo.sql` | Evasão anual por ano × rede × modalidade (consolida por curso; células < 10 suprimidas) |
| `sql/06_b1_desertos.sql` | Vagas presenciais 2024 por 100 jovens de 18-24 e municípios sem oferta |
| `sql/07_b2_financiamento.sql` | Evasão na rede privada: alta vs baixa adesão a FIES/ProUni |

Saídas: `outputs/p3_evasao_censo.csv`, `outputs/b1_desertos_ensino_superior.csv`, `outputs/b2_financiamento_permanencia.csv`.

### Qualidade (P4, P5)

| Arquivo | Responsabilidade |
|---|---|
| `src/03_qualidade_supabase.py` | Lê CPC 2021–2023 e Enade Licenciaturas 2025 filtrando `Sigla da UF = MT`, carrega `stg_cpc_mt` e `stg_enade_licenciaturas_mt`, loga a taxa de match com a Trajetória e exporta os CSVs. Requer `stg_trajetoria_mt` já carregada |
| `sql/08_stg_qualidade_mt.sql` | DDL das duas tabelas (SC → NULL + `in_sem_conceito`) |
| `sql/09_p4_qualidade_retencao.sql` | CPC (Faixa e Contínuo) x TDA no 5º ano, com correlações |
| `sql/10_p5_funil_licenciaturas.sql` | Licenciaturas: TDA x proficiência no Enade 2025 e funil crítico por área |

Saídas: `outputs/p4_cpc_vs_desistencia.csv`, `outputs/p5_funil_licenciaturas.csv`.

## Configuração

```bash
pip install -r requirements.txt
cp .env.example .env        # preencher SUPABASE_DB_URL (senha com caracteres especiais: URL-encode)
python src/db.py            # testa a conexão
python src/01_ingestao_trajetoria_supabase.py
python src/02_censo_supabase.py
python src/03_qualidade_supabase.py
```

Opções: `--raw`, `--recriar`, `--so-consultas`. Os filtros de P1/P2 (CO_UF='51', Presencial, coortes 2015/2020, 5º ano, `HAVING SUM(qt_ingressante) >= 10`) são literais nos arquivos `sql/`, que rodam sem alteração no SQL Editor do Supabase.

Decisões e justificativas em `docs/estrategia.md`.
