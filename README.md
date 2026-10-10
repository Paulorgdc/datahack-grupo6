# DataHack UNIVAG 2026 — Desafio Rota do Diploma

Análise da trajetória de estudantes da educação superior em Mato Grosso (CO_UF = 51) a partir de dados oficiais (Censo da Educação Superior e Trajetória), usando Python + Supabase (PostgreSQL na nuvem).

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `docs/` | Estratégia (`estrategia.md`) e arquitetura (`arquitetura.md`) |
| `src/` | Conexão (`db.py`) e pipelines de ingestão/carga |
| `sql/` | DDL e consultas PostgreSQL (staging e analytical) |
| `outputs/` | Saídas consolidadas e determinísticas (CSV) |
| `dashboard/` | Artefatos de visualização |
| `prompts/` | Índice e registros das sessões de IA (`prompts/README.md`) |

Dados brutos (`data/`, `archives/`) e `.env` **não são versionados**. Copie `.env.example` para `.env` e preencha `SUPABASE_DB_URL`.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

## Princípios

- Pipeline em camadas Raw → Trusted/Staging → Analytical.
- Pré-filtro em memória (MT + Graduação) para caber nos 500 MB do Supabase gratuito.
- Carga idempotente (TRUNCATE + COPY em transação) e saídas com substituição atômica.
- Associação estatística, sem alegação de causalidade.
- Grupos com menos de 10 alunos são suprimidos.

Veja `docs/estrategia.md`.
