-- Staging dos Indicadores de Qualidade do INEP — somente Mato Grosso (sg_uf = 'MT').
-- Idempotente: o pipeline executa este DDL, TRUNCATE e COPY na mesma transação.
-- Códigos são TEXT. '--', 'SC' (Sem Conceito) e vazios viram NULL (nunca zero);
-- in_sem_conceito marca explicitamente os cursos sem conceito.

-- CPC: ciclo 2021-2023 (um arquivo por ano; cada área é avaliada uma vez no ciclo).
CREATE TABLE IF NOT EXISTS public.stg_cpc_mt (
    nu_ano_cpc                      INTEGER NOT NULL,
    co_area                         TEXT,
    no_area_avaliacao               TEXT,
    no_grau_academico               TEXT,           -- só existe no arquivo de 2021
    co_ies                          TEXT NOT NULL,
    no_ies                          TEXT,
    sg_ies                          TEXT,
    no_organizacao_academica        TEXT,
    no_categoria_administrativa     TEXT,
    co_curso                        TEXT NOT NULL,
    no_modalidade_ensino            TEXT,
    co_municipio                    TEXT NOT NULL,
    no_municipio                    TEXT,
    sg_uf                           TEXT NOT NULL,
    qt_concluintes_inscritos        INTEGER,
    qt_concluintes_participantes    INTEGER,
    nota_padronizada_fg             DOUBLE PRECISION,
    nota_padronizada_ce             DOUBLE PRECISION,
    conceito_enade_continuo         DOUBLE PRECISION,
    nota_padronizada_idd            DOUBLE PRECISION,
    nota_padronizada_org_didatico   DOUBLE PRECISION,
    nota_padronizada_infraestrutura DOUBLE PRECISION,
    nota_padronizada_oportunidade   DOUBLE PRECISION,
    nota_padronizada_mestres        DOUBLE PRECISION,
    nota_padronizada_doutores       DOUBLE PRECISION,
    nota_padronizada_regime         DOUBLE PRECISION,
    cpc_continuo                    DOUBLE PRECISION,
    cpc_faixa                       SMALLINT,
    in_sem_conceito                 BOOLEAN NOT NULL,
    PRIMARY KEY (nu_ano_cpc, co_curso, co_municipio),
    CONSTRAINT stg_cpc_mt_somente_mt CHECK (sg_uf = 'MT'),
    CONSTRAINT stg_cpc_mt_faixa CHECK (cpc_faixa IS NULL OR cpc_faixa BETWEEN 1 AND 5)
);

-- Enade 2025 — edição especial das Licenciaturas.
CREATE TABLE IF NOT EXISTS public.stg_enade_licenciaturas_mt (
    nu_ano_enade                    INTEGER NOT NULL,
    co_area                         TEXT,
    no_area_avaliacao               TEXT,
    no_grau_academico               TEXT,
    co_ies                          TEXT NOT NULL,
    no_ies                          TEXT,
    sg_ies                          TEXT,
    no_organizacao_academica        TEXT,
    no_categoria_administrativa     TEXT,
    co_curso                        TEXT NOT NULL,
    no_modalidade_ensino            TEXT,
    co_municipio                    TEXT NOT NULL,
    no_municipio                    TEXT,
    sg_uf                           TEXT NOT NULL,
    qt_concluintes_inscritos        INTEGER,
    qt_concluintes_participantes    INTEGER,
    qt_proficiente_padrao1          INTEGER,        -- concluintes igual ou acima do Padrão 1 de Proficiência
    prop_proficiente_padrao1        DOUBLE PRECISION, -- fração (0 a 1)
    enade_faixa                     SMALLINT,
    in_sem_conceito                 BOOLEAN NOT NULL,
    in_cebas                        TEXT,
    PRIMARY KEY (nu_ano_enade, co_curso, co_municipio),
    CONSTRAINT stg_enade_lic_mt_somente_mt CHECK (sg_uf = 'MT'),
    CONSTRAINT stg_enade_lic_mt_faixa CHECK (enade_faixa IS NULL OR enade_faixa BETWEEN 1 AND 5)
);

CREATE INDEX IF NOT EXISTS ix_stg_cpc_mt_curso ON public.stg_cpc_mt (co_curso);
CREATE INDEX IF NOT EXISTS ix_stg_enade_lic_mt_curso ON public.stg_enade_licenciaturas_mt (co_curso);

-- Segurança: RLS ligada + leitura pública (dados abertos); escrita só pelo papel postgres.
ALTER TABLE public.stg_cpc_mt ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS leitura_publica ON public.stg_cpc_mt;
CREATE POLICY leitura_publica ON public.stg_cpc_mt FOR SELECT TO anon, authenticated USING (true);

ALTER TABLE public.stg_enade_licenciaturas_mt ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS leitura_publica ON public.stg_enade_licenciaturas_mt;
CREATE POLICY leitura_publica ON public.stg_enade_licenciaturas_mt FOR SELECT TO anon, authenticated USING (true);
