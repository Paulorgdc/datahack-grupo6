-- Staging do Censo da Educação Superior (Cursos, 2021-2024) e população IBGE — somente Mato Grosso.
-- Idempotente: o pipeline executa este DDL, TRUNCATE e COPY na mesma transação.
-- Códigos são TEXT (preserva zeros à esquerda).

-- Grão: curso x município do local de oferta (cursos EAD têm uma linha por polo).
-- A consolidação por (nu_ano_censo, co_curso) é feita nas consultas 05 e 07.
CREATE TABLE IF NOT EXISTS public.stg_censo_cursos_mt (
    nu_ano_censo                INTEGER NOT NULL,
    co_uf                       TEXT NOT NULL,
    co_municipio                TEXT NOT NULL,
    no_municipio                TEXT,
    tp_organizacao_academica    TEXT,
    tp_categoria_administrativa TEXT,
    tp_rede                     TEXT,
    co_ies                      TEXT NOT NULL,
    co_curso                    TEXT NOT NULL,
    no_curso                    TEXT,
    co_cine_rotulo              TEXT,
    no_cine_rotulo              TEXT,
    co_cine_area_geral          TEXT,
    no_cine_area_geral          TEXT,
    tp_grau_academico           TEXT,
    tp_modalidade_ensino        TEXT NOT NULL,
    tp_nivel_academico          TEXT NOT NULL,
    qt_vg_total                 INTEGER,
    qt_ing                      INTEGER,
    qt_ing_fies                 INTEGER,
    qt_ing_prounii              INTEGER,
    qt_ing_prounip              INTEGER,
    qt_mat                      INTEGER,
    qt_conc                     INTEGER,
    qt_sit_trancada             INTEGER,
    qt_sit_desvinculado         INTEGER,
    qt_sit_transferido          INTEGER,
    qt_sit_falecido             INTEGER,
    PRIMARY KEY (nu_ano_censo, co_curso, co_municipio),
    CONSTRAINT stg_censo_cursos_mt_somente_mt CHECK (co_uf = '51'),
    CONSTRAINT stg_censo_cursos_mt_somente_graduacao CHECK (tp_nivel_academico = '1')
);

CREATE INDEX IF NOT EXISTS ix_stg_censo_cursos_mt_municipio
    ON public.stg_censo_cursos_mt (nu_ano_censo, co_municipio);

-- População residente de 18 a 24 anos por município de MT (Censo Demográfico 2022, SIDRA tabela 9514).
CREATE TABLE IF NOT EXISTS public.stg_ibge_populacao_mt (
    co_municipio    TEXT PRIMARY KEY,
    no_municipio    TEXT NOT NULL,
    nu_ano_censo    INTEGER NOT NULL,
    pop_18_19       INTEGER,
    pop_20_24       INTEGER,
    pop_18_24       INTEGER,
    CONSTRAINT stg_ibge_populacao_mt_somente_mt CHECK (co_municipio LIKE '51%')
);

-- Segurança: tabelas em `public` ficam expostas pela API do Supabase (chave anon).
-- RLS ligada + leitura pública (dados abertos); escrita só pelo papel postgres.
ALTER TABLE public.stg_censo_cursos_mt ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS leitura_publica ON public.stg_censo_cursos_mt;
CREATE POLICY leitura_publica ON public.stg_censo_cursos_mt FOR SELECT TO anon, authenticated USING (true);

ALTER TABLE public.stg_ibge_populacao_mt ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS leitura_publica ON public.stg_ibge_populacao_mt;
CREATE POLICY leitura_publica ON public.stg_ibge_populacao_mt FOR SELECT TO anon, authenticated USING (true);
