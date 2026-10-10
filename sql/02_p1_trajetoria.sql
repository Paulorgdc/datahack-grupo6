-- P1: coorte 2015, Presencial, Mato Grosso, Graduação, acompanhada de 2015 a 2024.
-- PostgreSQL nativo sobre public.stg_trajetoria_mt (executável direto no SQL Editor do Supabase).
-- TDA, TCA, TAP e TADA = média das taxas por curso ponderada por qt_ingressante.
-- Grupos com menos de 10 ingressantes são omitidos.
WITH base AS (
    SELECT *, nu_ano_referencia - nu_ano_ingresso + 1 AS ano_do_curso
    FROM public.stg_trajetoria_mt
    WHERE co_uf = '51'
      AND tp_grau_academico IN ('1', '2', '3')
      AND tp_modalidade_ensino = '1'
      AND nu_ano_ingresso = 2015
      AND qt_ingressante > 0
      AND tda IS NOT NULL AND tca IS NOT NULL AND tap IS NOT NULL AND tada IS NOT NULL
),
ano AS (
    SELECT nu_ano_ingresso AS coorte,
           nu_ano_referencia AS ano_referencia,
           ano_do_curso,
           count(DISTINCT co_curso) AS n_cursos,
           sum(qt_ingressante) AS qt_ingressantes,
           sum(qt_desistencia) AS qt_desistencia_ano,
           sum(qt_concluinte) AS qt_conclusao_ano,
           (sum(tda  * qt_ingressante) / sum(qt_ingressante))::numeric AS tda_pct,
           (sum(tca  * qt_ingressante) / sum(qt_ingressante))::numeric AS tca_pct,
           (sum(tap  * qt_ingressante) / sum(qt_ingressante))::numeric AS tap_pct,
           (sum(tada * qt_ingressante) / sum(qt_ingressante))::numeric AS tada_pct
    FROM base
    GROUP BY nu_ano_ingresso, nu_ano_referencia, ano_do_curso
    HAVING sum(qt_ingressante) >= 10
)
SELECT coorte, ano_referencia, ano_do_curso, n_cursos, qt_ingressantes,
       round(tda_pct, 4)  AS tda_pct,
       round(tca_pct, 4)  AS tca_pct,
       round(tap_pct, 4)  AS tap_pct,
       round(tda_pct + tca_pct + tap_pct, 4) AS soma_tda_tca_tap_pct,
       qt_desistencia_ano, qt_conclusao_ano,
       round(tada_pct, 4) AS tada_pct,
       (tada_pct = max(tada_pct) OVER ()) AS maior_perda_anual
FROM ano
ORDER BY ano_referencia;
