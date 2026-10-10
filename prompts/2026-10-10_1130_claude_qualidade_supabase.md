# Sessão 2026-10-10 11:30 — Indicadores de Qualidade no Supabase (P4 e P5)

**Usuário:** Paulo (arquiteto técnico) · **Ferramenta:** Claude Code (Sonnet 5.5)

## Prompt utilizado

> Implementar `src/03_qualidade_supabase.py` para responder P4 e P5, cruzando os Indicadores de Qualidade do INEP com a Trajetória já gravada no Supabase.
>
> 1. Ler CPC (2021, 2022, 2023) e Enade Licenciaturas 2025 de `archives/inep_indicadores_qualidade/`, com `Código do Curso` e `Código do Município` como texto; filtrar estritamente `Sigla da UF == 'MT'`; '--' e 'SC' (Sem Conceito) viram NULL, nunca zero.
> 2. `sql/08_stg_qualidade_mt.sql` com `stg_cpc_mt` (ciclo 2021–2023) e `stg_enade_licenciaturas_mt` (edição especial 2025); carga idempotente TRUNCATE + COPY.
> 3. `sql/09_p4_qualidade_retencao.sql`: cruza CPC com a Trajetória de MT via `CO_CURSO`, registra no log a taxa de match, analisa se maior CPC (Faixa e Contínuo) se associa a menor TDA, suprime grupos < 10 alunos → `outputs/p4_cpc_vs_desistencia.csv`. `sql/10_p5_funil_licenciaturas.sql`: cruza Enade Licenciaturas 2025 com a Trajetória (`TP_GRAU_ACADEMICO == 2`), TDA acumulada x concluintes no padrão de proficiência, mapeia por Área de Avaliação os cursos com funil crítico → `outputs/p5_funil_licenciaturas.csv`.
> 4. Registrar a sessão e atualizar `prompts/README.md`.

## Aproveitado / decisões técnicas
- Leitura em streaming (`openpyxl` read-only), com filtro `Sigla da UF = MT` na leitura (CPC: 155 + 165 + 238 cursos de MT; Enade: 97). Cabeçalhos normalizados por regex (sem acento, sem asteriscos/rodapés), porque os arquivos diferem entre si (2021 tem coluna de grau; 2022 usa vírgula decimal).
- **SC → NULL:** `cpc_faixa`/`enade_faixa` viram NULL e `in_sem_conceito = true`. O CPC 2022 grava 0 como Conceito Enade dos cursos sem conceito; esses valores contínuos também são zerados para NULL.
- **Chave de cruzamento:** `co_curso`. Staging com PK `(ano, co_curso, co_municipio)`.
- **TDA por curso:** TDA no 5º ano de acompanhamento, coortes 2015–2020 agrupadas e ponderadas por `qt_ingressante` (mesmo critério de P2). Cursos com < 10 ingressantes são omitidos.
- **P4:** CPC mais recente do ciclo por curso; agrupa por Faixa e por quartil do CPC Contínuo; inclui correlação de Pearson e Spearman (postos médios) por curso.
- **P5:** proficiência = proporção de concluintes igual ou acima do Padrão 1; supressão exige ≥ 10 ingressantes e ≥ 10 concluintes participantes; funil crítico = TDA ≥ mediana e proficiência < mediana; inclui estimativa de proficientes por 100 ingressantes (rotulada como estimativa).
- **Match (log do script):** 528 de 558 cursos do CPC casaram com a Trajetória (94,6%); 30 ficaram de fora. Cursos com conceito: 497 de 517. Enade Licenciaturas: 75 de 97.
- Verificação: SQL validado com o parser do PostgreSQL e executado num motor local temporário sobre os dados reais. **Carga no Supabase e extrações finais ainda dependem da `SUPABASE_DB_URL` e não foram executadas**; os CSVs atuais em `outputs/` vêm desse motor local e serão regravados na primeira execução real.
