-- P2: ranking de desistência por CINE (rótulo e área geral), Mato Grosso, Graduação, Presencial.
-- Coorte 2015 vs coorte 2020, ambas avaliadas no 5º ano do curso (ref. 2019 e 2024).
-- PostgreSQL nativo sobre public.stg_trajetoria_mt (executável direto no SQL Editor do Supabase).
-- Regra eliminatória do edital: grupos com SUM(qt_ingressante) < 10 são suprimidos (HAVING).
WITH base AS (
    SELECT *, nu_ano_referencia - nu_ano_ingresso + 1 AS ano_do_curso
    FROM public.stg_trajetoria_mt
    WHERE co_uf = '51'
      AND tp_grau_academico IN ('1', '2', '3')
      AND tp_modalidade_ensino = '1'
      AND nu_ano_ingresso IN (2015, 2020)
      AND qt_ingressante > 0
      AND tda IS NOT NULL AND tca IS NOT NULL AND tap IS NOT NULL
),
filtrada AS (
    SELECT * FROM base WHERE ano_do_curso = 5
),
u AS (
    SELECT 'CINE_ROTULO' AS nivel, nu_ano_ingresso AS coorte,
           co_cine_rotulo, no_cine_rotulo, co_cine_area_geral, no_cine_area_geral,
           count(DISTINCT co_curso) AS n_cursos,
           sum(qt_ingressante) AS qt_ingressantes,
           (sum(tda * qt_ingressante) / sum(qt_ingressante))::numeric AS tda_pct,
           (sum(tca * qt_ingressante) / sum(qt_ingressante))::numeric AS tca_pct,
           (sum(tap * qt_ingressante) / sum(qt_ingressante))::numeric AS tap_pct
    FROM filtrada
    GROUP BY nu_ano_ingresso, co_cine_rotulo, no_cine_rotulo, co_cine_area_geral, no_cine_area_geral
    HAVING sum(qt_ingressante) >= 10
    UNION ALL
    SELECT 'CINE_AREA_GERAL', nu_ano_ingresso,
           NULL::text, NULL::text, co_cine_area_geral, no_cine_area_geral,
           count(DISTINCT co_curso),
           sum(qt_ingressante),
           (sum(tda * qt_ingressante) / sum(qt_ingressante))::numeric,
           (sum(tca * qt_ingressante) / sum(qt_ingressante))::numeric,
           (sum(tap * qt_ingressante) / sum(qt_ingressante))::numeric
    FROM filtrada
    GROUP BY nu_ano_ingresso, co_cine_area_geral, no_cine_area_geral
    HAVING sum(qt_ingressante) >= 10
)
SELECT nivel, coorte, 5 AS ano_do_curso,
       co_cine_rotulo, no_cine_rotulo, co_cine_area_geral, no_cine_area_geral,
       n_cursos, qt_ingressantes,
       round(tda_pct, 4) AS tda_pct,
       round(tca_pct, 4) AS tca_pct,
       round(tap_pct, 4) AS tap_pct,
       rank() OVER (PARTITION BY nivel, coorte ORDER BY tda_pct DESC) AS ranking_desistencia,
       count(*) OVER (PARTITION BY nivel, coorte) AS n_grupos_ranqueados,
       round(tda_pct - lag(tda_pct) OVER (
           PARTITION BY nivel, coalesce(co_cine_rotulo, co_cine_area_geral) ORDER BY coorte), 4
       ) AS delta_tda_pp_vs_coorte_anterior
FROM u
ORDER BY nivel, coorte, ranking_desistencia, coalesce(co_cine_rotulo, co_cine_area_geral);
