# Estratégia — Fase 1

## 1. Justificativa da stack

**Python + Supabase (PostgreSQL na nuvem)** como banco central oficial. Decisão do time (2026-10-10): **não** usar banco analítico local (DuckDB/SQLite). Motivos:

- atende ao critério de banco de dados em nuvem do desafio;
- uma única fonte de verdade consultável por qualquer integrante e pelo dashboard do pitch final (Caminho 3);
- SQL padrão PostgreSQL versionado em `sql/`.

Python (pandas + openpyxl) faz apenas a leitura e a pré-filtragem das planilhas; todo o cálculo analítico (P1, P2) roda em SQL no Supabase. As saídas agregadas ficam em `outputs/*.csv`.

### Conformidade com o limite gratuito de 500 MB

O Censo e a Trajetória brutos somam centenas de MB, acima do que o plano gratuito comporta. A estratégia é **pré-filtrar em memória antes da carga**:

1. leitura em streaming das planilhas (`openpyxl` read-only);
2. descarte imediato de tudo que não é **Mato Grosso (`CO_UF = '51'`)** e **Graduação** (`TP_GRAU_ACADEMICO` em 1, 2, 3);
3. carga só do que sobra no Supabase.

Resultado medido: a Trajetória (6 coortes, 2015–2020) cai para **26.513 linhas (~28 MB em memória)** e, no banco, ocupa bem menos que isso, com folga frente ao limite de 500 MB. Os dados brutos nunca vão ao banco nem ao Git.

## 2. Camadas de dados

| Camada | Onde | Conteúdo / regras |
|---|---|---|
| **Raw** | `archives/inep_trajetoria/` (local, fora do Git) | Planilhas oficiais, somente leitura |
| **Trusted/Staging** | Supabase: `public.stg_trajetoria_mt` | MT + Graduação; códigos (`co_*`, CINE, `tp_*`) como `TEXT`; suprimidos/inválidos viram `NULL`; chave primária `(co_ies, co_curso, nu_ano_ingresso, nu_ano_referencia)` |
| **Analytical** | Consultas SQL no Supabase → `outputs/` | P1 e P2 agregados, ponderados por `qt_ingressante` |

## 3. Idempotência

- Pipeline `src/01_ingestao_trajetoria_supabase.py`: DDL (`CREATE TABLE IF NOT EXISTS`) + **`TRUNCATE` + `COPY` na mesma transação**. Falha em qualquer ponto faz rollback; reexecuções nunca duplicam linhas.
- A chave primária impede duplicatas mesmo se o `TRUNCATE` for removido por engano.
- Após o `COPY`, a contagem no banco é conferida com a de memória; divergência aborta a transação.
- `--recriar` faz `DROP` + `CREATE` quando o schema mudar.
- CSVs de saída são gravados em arquivo temporário e promovidos por `os.replace` (substituição atômica).

## 4. Segurança

- Credencial somente em `.env` (ignorado pelo Git); o repositório traz apenas `.env.example`.
- RLS habilitada na tabela, com política de leitura pública (dados abertos do INEP). Escrita apenas pela conexão direta (`postgres`).

## 5. Armadilhas metodológicas e mitigação

| Armadilha | Mitigação |
|---|---|
| Cursos EAD aparecem em múltiplos polos/locais | Agregação obrigatória por `CO_CURSO`; a carga aborta se houver chave duplicada |
| Planilha de Trajetória com cabeçalho deslocado | Cabeçalhos na **linha 9**; o script valida as colunas esperadas |
| Perda de zeros à esquerda em códigos | Tudo lido como texto; `TEXT` no DDL; `zfill` em UF e CINE |
| Censo em formato legado | Encoding **latin-1** e delimitador **`;`** (ao ingerir o Censo) |
| Risco de reidentificação | **Supressão de grupos com < 10 alunos** (`HAVING sum(qt_ingressante) >= 10`) |
| Taxas instáveis em grupos pequenos | Exibir `qt_ingressantes` e `n_cursos` junto de cada taxa |
| Interpretação indevida dos resultados | **Associação estatística**, sem alegação de causalidade |
