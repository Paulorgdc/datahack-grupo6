-- P4: cursos de MT com maior CPC têm menor Taxa de Desistência Acumulada (TDA)?
-- Cruza stg_cpc_mt (ciclo 2021-2023) com stg_trajetoria_mt via co_curso.
--  * CPC por curso: avaliação mais recente do ciclo; só cursos com conceito (SC fica fora).
--  * TDA por curso: TDA no 5º ano de acompanhamento, coortes 2015-2020 agrupadas, ponderada por
--    qt_ingressante (Graduação, MT).
--  * Supressão: cursos e grupos com menos de 10 ingressantes são omitidos.
-- Resultado = ASSOCIAÇÃO estatística entre qualidade e desistência, sem alegação de causalidade.
WITH traj AS (
    SELECT co_curso,
           count(DISTINCT nu_ano_ingresso) AS n_coortes,
           sum(qt_ingressante) AS qt_ingressantes,
           sum(tda * qt_ingressante) / sum(qt_ingressante) AS tda_pct
    FROM public.stg_trajetoria_mt
    WHERE co_uf = '51'
      AND tp_grau_academico IN ('1', '2', '3')
      AND nu_ano_referencia - nu_ano_ingresso + 1 = 5
      AND qt_ingressante > 0 AND tda IS NOT NULL
    GROUP BY co_curso
    HAVING sum(qt_ingressante) >= 10
),
cpc AS (
    SELECT DISTINCT ON (co_curso)
           co_curso, nu_ano_cpc, cpc_faixa, cpc_continuo
    FROM public.stg_cpc_mt
    WHERE sg_uf = 'MT' AND cpc_faixa IS NOT NULL AND cpc_continuo IS NOT NULL
    ORDER BY co_curso, nu_ano_cpc DESC, qt_concluintes_participantes DESC NULLS LAST, co_municipio
),
base AS (
    SELECT c.co_curso, c.cpc_faixa, c.cpc_continuo, t.qt_ingressantes, t.tda_pct,
           ntile(4) OVER (ORDER BY c.cpc_continuo) AS quartil_cpc
    FROM cpc c
    JOIN traj t USING (co_curso)
),
postos AS (  -- postos médios para Spearman (empates recebem a média dos postos)
    SELECT *,
           rank() OVER (ORDER BY cpc_continuo)
             + (count(*) OVER (PARTITION BY cpc_continuo) - 1) / 2.0 AS posto_cpc,
           rank() OVER (ORDER BY tda_pct)
             + (count(*) OVER (PARTITION BY tda_pct) - 1) / 2.0 AS posto_tda
    FROM base
),
correlacao AS (
    SELECT count(*) AS n_cursos_correlacao,
           round(corr(cpc_continuo, tda_pct)::numeric, 4) AS corr_pearson_cpc_tda,
           round(corr(posto_cpc, posto_tda)::numeric, 4) AS corr_spearman_cpc_tda
    FROM postos
),
grupos AS (
    SELECT 'CPC_FAIXA' AS agrupamento, cpc_faixa::text AS grupo, cpc_faixa AS ordem,
           count(*) AS n_cursos, sum(qt_ingressantes) AS qt_ingressantes,
           avg(cpc_continuo) AS cpc_continuo_medio,
           sum(tda_pct * qt_ingressantes) / sum(qt_ingressantes) AS tda_pct
    FROM base
    GROUP BY cpc_faixa
    HAVING sum(qt_ingressantes) >= 10
    UNION ALL
    SELECT 'CPC_CONTINUO_QUARTIL', 'Q' || quartil_cpc, quartil_cpc,
           count(*), sum(qt_ingressantes), avg(cpc_continuo),
           sum(tda_pct * qt_ingressantes) / sum(qt_ingressantes)
    FROM base
    GROUP BY quartil_cpc
    HAVING sum(qt_ingressantes) >= 10
)
SELECT g.agrupamento, g.grupo, g.n_cursos, g.qt_ingressantes,
       round(g.cpc_continuo_medio::numeric, 4) AS cpc_continuo_medio,
       round(g.tda_pct::numeric, 4) AS tda_pct,
       k.n_cursos_correlacao, k.corr_pearson_cpc_tda, k.corr_spearman_cpc_tda
FROM grupos g
CROSS JOIN correlacao k
ORDER BY g.agrupamento DESC, g.ordem;
