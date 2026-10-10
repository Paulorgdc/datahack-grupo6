# DataHack UNIVAG 2026 — Desafio Rota do Diploma

Análise da trajetória de estudantes da educação superior em Mato Grosso (CO_UF = 51) a partir de dados oficiais (Censo da Educação Superior e Trajetória), usando Python + DuckDB.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `docs/` | Estratégia (`estrategia.md`) e arquitetura (`arquitetura.md`) |
| `src/` | Scripts parametrizados de carga e transformação |
| `sql/` | Consultas DuckDB (staging e analytical) |
| `outputs/` | Saídas consolidadas e determinísticas (Parquet/CSV) |
| `dashboard/` | Artefatos de visualização |
| `prompts/` | Índice e registros das sessões de IA (`prompts/README.md`) |

`data/` (dados brutos) **não é versionada**: baixe os arquivos oficiais localmente.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

## Princípios

- Pipeline em camadas Raw → Trusted/Staging → Analytical.
- Execução idempotente (sobrescrita atômica das saídas).
- Associação estatística, sem alegação de causalidade.
- Grupos com menos de 10 alunos são suprimidos.

Veja `docs/estrategia.md`.
