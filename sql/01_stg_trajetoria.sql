-- Staging da Trajetória (INEP) — somente MT (co_uf = '51') e Graduação.
-- Idempotente: o pipeline executa este DDL, TRUNCATE e COPY na mesma transação.
-- Códigos são TEXT (preserva zeros à esquerda).

CREATE TABLE IF NOT EXISTS public.stg_trajetoria_mt (
    co_ies                          TEXT NOT NULL,
    no_ies                          TEXT,
    tp_categoria_administrativa     TEXT,
    tp_organizacao_academica        TEXT,
    co_curso                        TEXT NOT NULL,
    no_curso                        TEXT,
    co_regiao                       TEXT,
    co_uf                           TEXT NOT NULL,
    co_municipio                    TEXT,
    tp_grau_academico               TEXT NOT NULL,
    tp_modalidade_ensino            TEXT NOT NULL,
    co_cine_rotulo                  TEXT,
    no_cine_rotulo                  TEXT,
    co_cine_area_geral              TEXT,
    no_cine_area_geral              TEXT,
    nu_ano_ingresso                 INTEGER NOT NULL,
    nu_ano_referencia               INTEGER NOT NULL,
    nu_prazo_integralizacao         INTEGER,
    nu_ano_integralizacao           INTEGER,
    nu_prazo_acompanhamento         INTEGER,
    nu_ano_maximo_acompanhamento    INTEGER,
    qt_ingressante                  INTEGER,
    qt_permanencia                  INTEGER,
    qt_concluinte                   INTEGER,
    qt_desistencia                  INTEGER,
    qt_falecido                     INTEGER,
    tap                             DOUBLE PRECISION,
    tca                             DOUBLE PRECISION,
    tda                             DOUBLE PRECISION,
    tcan                            DOUBLE PRECISION,
    tada                            DOUBLE PRECISION,
    PRIMARY KEY (co_ies, co_curso, nu_ano_ingresso, nu_ano_referencia),
    CONSTRAINT stg_trajetoria_mt_somente_mt CHECK (co_uf = '51')
);

CREATE INDEX IF NOT EXISTS ix_stg_trajetoria_mt_coorte
    ON public.stg_trajetoria_mt (nu_ano_ingresso, nu_ano_referencia);

-- Segurança: tabelas em `public` ficam expostas pela API do Supabase (chave anon).
-- RLS ligada + leitura pública (dados abertos do INEP); escrita só pelo papel postgres.
ALTER TABLE public.stg_trajetoria_mt ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS leitura_publica ON public.stg_trajetoria_mt;
CREATE POLICY leitura_publica ON public.stg_trajetoria_mt FOR SELECT TO anon, authenticated USING (true);
