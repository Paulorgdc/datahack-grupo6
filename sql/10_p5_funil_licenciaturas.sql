-- P5: funil das Licenciaturas de MT — desistência (Trajetória) x proficiência no Enade 2025.
-- Cruza stg_enade_licenciaturas_mt com stg_trajetoria_mt via co_curso, apenas Licenciaturas
-- (tp_grau_academico = '2').
--  * TDA por curso: TDA no 5º ano de acompanhamento, coortes 2015-2020 agrupadas, ponderada por qt_ingressante.
--  * Proficiência: proporção de concluintes participantes igual ou acima do Padrão 1 (Enade 2025).
--  * Supressão: cursos com menos de 10 ingressantes OU menos de 10 concluintes participantes são omitidos.
--  * Funil crítico = TDA >= mediana E proficiência < mediana (medianas entre os cursos analisados).
--  * estimativa_proficientes_por_100_ingressantes = (100 - TDA) x proporção de proficientes: ordem de
--    grandeza do funil, supondo que a proficiência dos concluintes vale para quem permanece. É uma estimativa.
-- Resultado = ASSOCIAÇÃO, sem alegação de causalidade.
WITH traj AS (
    SELECT co_curso,
           sum(qt_ingressante) AS qt_ingressantes,
           sum(tda * qt_ingressante) / sum(qt_ingressante) AS tda_pct
    FROM public.stg_trajetoria_mt
    WHERE co_uf = '51'
      AND tp_grau_academico = '2'
      AND nu_ano_referencia - nu_ano_ingresso + 1 = 5
      AND qt_ingressante > 0 AND tda IS NOT NULL
    GROUP BY co_curso
    HAVING sum(qt_ingressante) >= 10
),
enade AS (
    SELECT DISTINCT ON (co_curso)
           co_curso, co_ies, sg_ies, co_area, no_area_avaliacao, no_modalidade_ensino,
           co_municipio, no_municipio, qt_concluintes_participantes,
           qt_proficiente_padrao1, prop_proficiente_padrao1, enade_faixa
    FROM public.stg_enade_licenciaturas_mt
    WHERE sg_uf = 'MT'
      AND prop_proficiente_padrao1 IS NOT NULL
      AND qt_concluintes_participantes >= 10
    ORDER BY co_curso, qt_concluintes_participantes DESC, co_municipio
),
juncao AS (
    SELECT e.co_area, e.no_area_avaliacao, e.co_curso, e.co_ies, e.sg_ies, e.no_modalidade_ensino,
           e.co_municipio, e.no_municipio,
           t.qt_ingressantes, t.tda_pct,
           e.qt_concluintes_participantes, e.qt_proficiente_padrao1,
           100.0 * e.prop_proficiente_padrao1 AS prop_proficiente_pct,
           e.enade_faixa
    FROM enade e
    JOIN traj t USING (co_curso)
),
medianas AS (
    SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY tda_pct) AS mediana_tda,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY prop_proficiente_pct) AS mediana_prof
    FROM juncao
),
classificado AS (
    SELECT j.*, m.mediana_tda, m.mediana_prof,
           (j.tda_pct >= m.mediana_tda AND j.prop_proficiente_pct < m.mediana_prof) AS funil_critico
    FROM juncao j CROSS JOIN medianas m
)
SELECT co_area, no_area_avaliacao, co_curso, co_ies, sg_ies, no_modalidade_ensino, co_municipio, no_municipio,
       qt_ingressantes,
       round(tda_pct::numeric, 4) AS tda_pct,
       qt_concluintes_participantes, qt_proficiente_padrao1,
       round(prop_proficiente_pct::numeric, 2) AS prop_proficiente_pct,
       enade_faixa,
       round(((100 - tda_pct) * prop_proficiente_pct / 100.0)::numeric, 2) AS estimativa_proficientes_por_100_ingressantes,
       round(mediana_tda::numeric, 4) AS mediana_tda_pct,
       round(mediana_prof::numeric, 2) AS mediana_prop_proficiente_pct,
       funil_critico,
       count(*) OVER (PARTITION BY co_area) AS n_cursos_area,
       count(*) FILTER (WHERE funil_critico) OVER (PARTITION BY co_area) AS n_cursos_criticos_area
FROM classificado
ORDER BY n_cursos_criticos_area DESC, no_area_avaliacao, funil_critico DESC, tda_pct DESC, co_curso;
