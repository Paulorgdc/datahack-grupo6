-- B1: desertos de ensino superior presencial em MT.
-- Vagas presenciais de Graduação em 2024 (QT_VG_TOTAL) por município x população de 18 a 24 anos
-- (Censo Demográfico 2022, IBGE). Parte de TODOS os municípios do IBGE, então municípios sem
-- nenhuma oferta presencial aparecem com 0 vagas (deserto = TRUE).
-- Presencial tem uma linha por (curso, município); EAD não entra.
WITH vagas AS (
    SELECT co_municipio,
           sum(qt_vg_total)        AS vagas_presenciais_2024,
           count(DISTINCT co_curso) AS n_cursos_presenciais,
           count(DISTINCT co_ies)   AS n_ies
    FROM public.stg_censo_cursos_mt
    WHERE co_uf = '51'
      AND tp_nivel_academico = '1'
      AND tp_modalidade_ensino = '1'
      AND nu_ano_censo = 2024
    GROUP BY co_municipio
)
SELECT p.co_municipio,
       p.no_municipio,
       p.pop_18_24,
       coalesce(v.vagas_presenciais_2024, 0) AS vagas_presenciais_2024,
       coalesce(v.n_cursos_presenciais, 0)   AS n_cursos_presenciais,
       coalesce(v.n_ies, 0)                  AS n_ies,
       round(100.0 * coalesce(v.vagas_presenciais_2024, 0) / NULLIF(p.pop_18_24, 0), 2) AS vagas_por_100_jovens,
       (coalesce(v.vagas_presenciais_2024, 0) = 0) AS deserto
FROM public.stg_ibge_populacao_mt p
LEFT JOIN vagas v ON v.co_municipio = p.co_municipio
ORDER BY deserto DESC, vagas_por_100_jovens ASC NULLS FIRST, p.co_municipio;
