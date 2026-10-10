-- B2: financiamento (FIES + ProUni) e evasão anual na rede privada de MT, Graduação, 2021-2024.
-- Proporção de financiados por curso = (QT_ING_FIES + QT_ING_PROUNII + QT_ING_PROUNIP) / NULLIF(QT_ING, 0).
-- Alta adesão = proporção >= 10%; baixa adesão = < 10% (a maioria dos cursos privados tem 0%, então
-- uma divisão pela mediana não separaria os grupos). Cursos sem ingressantes ficam fora (proporção nula),
-- assim como proporções > 100% (inconsistência de registro).
-- EAD: consolidado por (nu_ano_censo, co_curso) somando polos de MT. Grupos com < 10 alunos suprimidos.
-- Resultado descreve ASSOCIAÇÃO entre adesão e evasão, sem alegação de causalidade.
WITH cursos AS (
    SELECT nu_ano_censo, co_curso, tp_modalidade_ensino,
           sum(qt_ing) AS qt_ing,
           sum(qt_ing_fies + qt_ing_prounii + qt_ing_prounip) AS qt_ing_financ,
           sum(qt_mat) AS qt_mat,
           sum(qt_sit_desvinculado) AS qt_desvinculado,
           sum(qt_sit_transferido)  AS qt_transferido
    FROM public.stg_censo_cursos_mt
    WHERE co_uf = '51'
      AND tp_nivel_academico = '1'
      AND tp_rede = '2'
      AND nu_ano_censo BETWEEN 2021 AND 2024
    GROUP BY nu_ano_censo, co_curso, tp_modalidade_ensino
),
classificado AS (
    SELECT *,
           qt_ing_financ::numeric / NULLIF(qt_ing, 0) AS prop_financiados,
           CASE WHEN qt_ing_financ::numeric / NULLIF(qt_ing, 0) >= 0.10
                THEN 'Alta adesão (>=10%)' ELSE 'Baixa adesão (<10%)' END AS grupo_adesao
    FROM cursos
),
grupos AS (
    SELECT nu_ano_censo,
           tp_modalidade_ensino,
           CASE tp_modalidade_ensino WHEN '1' THEN 'Presencial' WHEN '2' THEN 'EAD' END AS modalidade,
           grupo_adesao,
           count(DISTINCT co_curso) AS n_cursos,
           sum(qt_ing)         AS qt_ing,
           sum(qt_ing_financ)  AS qt_ing_financ,
           sum(qt_mat)         AS qt_mat,
           sum(qt_desvinculado) AS qt_desvinculado,
           sum(qt_transferido)  AS qt_transferido,
           sum(qt_mat + qt_desvinculado + qt_transferido) AS base_alunos
    FROM classificado
    WHERE prop_financiados IS NOT NULL AND prop_financiados <= 1
    GROUP BY nu_ano_censo, tp_modalidade_ensino, grupo_adesao
    HAVING sum(qt_mat + qt_desvinculado + qt_transferido) >= 10
)
SELECT nu_ano_censo, tp_modalidade_ensino, modalidade, grupo_adesao,
       n_cursos, qt_ing, qt_ing_financ,
       round(100.0 * qt_ing_financ / NULLIF(qt_ing, 0), 2) AS prop_financiados_pct,
       qt_mat, qt_desvinculado, qt_transferido, base_alunos,
       round(100.0 * qt_desvinculado / NULLIF(base_alunos, 0), 4) AS evasao_anual_pct,
       round(
           100.0 * qt_desvinculado / NULLIF(base_alunos, 0)
           - max(100.0 * qt_desvinculado / NULLIF(base_alunos, 0))
               FILTER (WHERE grupo_adesao = 'Baixa adesão (<10%)')
               OVER (PARTITION BY nu_ano_censo, tp_modalidade_ensino), 4
       ) AS dif_evasao_pp_vs_baixa_adesao
FROM grupos
ORDER BY nu_ano_censo, tp_modalidade_ensino, grupo_adesao;
