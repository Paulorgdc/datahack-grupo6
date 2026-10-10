# Arquitetura

```
data/ (Raw, fora do Git)
   │  src/ — carga parametrizada
   ▼
Trusted/Staging (DuckDB)  ← sql/
   │
   ▼
Analytical (CO_UF = 51)   → outputs/*.parquet|csv → dashboard/
```

Detalhes de decisões em `docs/estrategia.md`. Este documento será expandido conforme os módulos de `src/` e `sql/` forem definidos.
