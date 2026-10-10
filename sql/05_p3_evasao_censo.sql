-- P3: evasão anual no Censo (2021-2024), Mato Grosso, Graduação.
-- Evasão anual = QT_SIT_DESVINCULADO / (QT_MAT + QT_SIT_DESVINCULADO + QT_SIT_TRANSFERIDO).
-- EAD: o curso tem uma linha por polo; consolida-se por (nu_ano_censo, co_curso) antes de agrupar,
-- somando as linhas de polos de MT (os valores variam por polo, então não há dupla contagem).
-- Células com soma de alunos (denominador) < 10 são suprimidas.
WITH cursos AS (
    SELECT nu_ano_censo, co_curso, tp_rede, tp_categoria_administrativa, tp_modalidade_ensino,
           sum(qt_mat)             AS qt_mat,
           sum(qt_sit_desvinculado) AS qt_desvinculado,
           sum(qt_sit_transferido)  AS qt_transferido
    FROM public.stg_censo_cursos_mt
    WHERE co_uf = '51'
      AND tp_nivel_academico = '1'
      AND nu_ano_censo BETWEEN 2021 AND 2024
    GROUP BY nu_ano_censo, co_curso, tp_rede, tp_categoria_administrativa, tp_modalidade_ensino
),
rotulado AS (
    SELECT *,
           CASE
               WHEN tp_rede = '1' THEN 'Pública'
               WHEN tp_categoria_administrativa = '4' THEN 'Privada com fins lucrativos'
               WHEN tp_categoria_administrativa = '5' THEN 'Privada sem fins lucrativos'
               ELSE 'Privada (outra categoria)'
           END AS grupo_rede,
           CASE tp_modalidade_ensino WHEN '1' THEN 'Presencial' WHEN '2' THEN 'EAD' END AS modalidade
    FROM cursos
)
SELECT nu_ano_censo,
       tp_rede,
       grupo_rede,
       tp_modalidade_ensino,
       modalidade,
       count(DISTINCT co_curso) AS n_cursos,
       sum(qt_mat)         AS qt_mat,
       sum(qt_desvinculado) AS qt_desvinculado,
       sum(qt_transferido)  AS qt_transferido,
       sum(qt_mat + qt_desvinculado + qt_transferido) AS base_alunos,
       round(100.0 * sum(qt_desvinculado) / NULLIF(sum(qt_mat + qt_desvinculado + qt_transferido), 0), 4) AS evasao_anual_pct
FROM rotulado
GROUP BY nu_ano_censo, tp_rede, grupo_rede, tp_modalidade_ensino, modalidade
HAVING sum(qt_mat + qt_desvinculado + qt_transferido) >= 10
ORDER BY nu_ano_censo, tp_rede, grupo_rede, tp_modalidade_ensino;
