"""Indicadores de Qualidade do INEP (CPC 2021-2023, Enade Licenciaturas 2025) -> Supabase -> P4 e P5.

1. Lê as planilhas .xlsx em streaming (cabeçalho na linha 1) e descarta na leitura tudo que não é
   'Sigla da UF' = 'MT'. Códigos (curso, IES, município) são texto; '--', 'SC' (Sem Conceito) e
   vazios viram NULL, nunca zero.
2. Carrega public.stg_cpc_mt e public.stg_enade_licenciaturas_mt (sql/08_stg_qualidade_mt.sql) com
   TRUNCATE + COPY na mesma transação, conferindo a contagem de linhas.
3. Registra a taxa de match com a Trajetória (public.stg_trajetoria_mt, carregada por
   src/01_ingestao_trajetoria_supabase.py) e executa sql/09 e sql/10 no Supabase, gravando
   outputs/p4_cpc_vs_desistencia.csv e outputs/p5_funil_licenciaturas.csv.

Uso:  python src/03_qualidade_supabase.py [--raw archives/inep_indicadores_qualidade] [--recriar]
"""
from __future__ import annotations

import argparse
import io
import logging
import os
import re
import sys
import unicodedata
from pathlib import Path

import openpyxl
import pandas as pd
from sqlalchemy import text

from db import ROOT, get_engine, testar_conexao

log = logging.getLogger("datahack.qualidade")

SQL_DIR = ROOT / "sql"
UF = "MT"
T_CPC = "public.stg_cpc_mt"
T_ENADE = "public.stg_enade_licenciaturas_mt"
T_TRAJ = "public.stg_trajetoria_mt"
NULOS = {"", "--", "-", "SC", "S/C", "NA", "N/A", "ND", "*", "NAN", "NONE"}  # Sem Conceito / sem dado

# Cabeçalho normalizado (sem acento, minúsculo, sem pontuação) -> coluna do staging.
COMUNS = [
    (r"^ano$", "nu_ano"), (r"^codigo da area$", "co_area"), (r"^area de avaliacao$", "no_area_avaliacao"),
    (r"^grau academico$", "no_grau_academico"), (r"^codigo da ies$", "co_ies"), (r"^nome da ies$", "no_ies"),
    (r"^sigla da ies$", "sg_ies"), (r"^organizacao academica$", "no_organizacao_academica"),
    (r"^categoria administrativa$", "no_categoria_administrativa"), (r"^codigo do curso$", "co_curso"),
    (r"^modalidade de ensino$", "no_modalidade_ensino"), (r"^codigo do municipio$", "co_municipio"),
    (r"^municipio do curso$", "no_municipio"), (r"^sigla da uf$", "sg_uf"),
    (r"^no de concluintes inscritos$", "qt_concluintes_inscritos"),
    (r"^no de concluintes participantes$", "qt_concluintes_participantes"),
]
MAP_CPC = COMUNS + [
    (r"^nota padronizada fg$", "nota_padronizada_fg"), (r"^nota padronizada ce$", "nota_padronizada_ce"),
    (r"^conceito enade continuo$", "conceito_enade_continuo"), (r"^nota padronizada idd$", "nota_padronizada_idd"),
    (r"^nota padronizada organizacao", "nota_padronizada_org_didatico"),
    (r"^nota padronizada infraestrutura", "nota_padronizada_infraestrutura"),
    (r"^nota padronizada oportunidade", "nota_padronizada_oportunidade"),
    (r"^nota padronizada mestres$", "nota_padronizada_mestres"),
    (r"^nota padronizada doutores$", "nota_padronizada_doutores"),
    (r"^nota padronizada regime", "nota_padronizada_regime"),
    (r"^cpc continuo$", "cpc_continuo"), (r"^cpc faixa$", "cpc_faixa"),
]
MAP_ENADE = COMUNS + [
    (r"^total de concluinte igual", "qt_proficiente_padrao1"),
    (r"^percentual de concluintes igual", "prop_proficiente_padrao1"),
    (r"^conceito enade faixa$", "enade_faixa"), (r"^cebas$", "in_cebas"),
]

# Ordem exata das colunas no DDL (sql/08)
ORD_CPC = [
    "nu_ano_cpc", "co_area", "no_area_avaliacao", "no_grau_academico", "co_ies", "no_ies", "sg_ies",
    "no_organizacao_academica", "no_categoria_administrativa", "co_curso", "no_modalidade_ensino", "co_municipio",
    "no_municipio", "sg_uf", "qt_concluintes_inscritos", "qt_concluintes_participantes", "nota_padronizada_fg",
    "nota_padronizada_ce", "conceito_enade_continuo", "nota_padronizada_idd", "nota_padronizada_org_didatico",
    "nota_padronizada_infraestrutura", "nota_padronizada_oportunidade", "nota_padronizada_mestres",
    "nota_padronizada_doutores", "nota_padronizada_regime", "cpc_continuo", "cpc_faixa", "in_sem_conceito",
]
ORD_ENADE = [
    "nu_ano_enade", "co_area", "no_area_avaliacao", "no_grau_academico", "co_ies", "no_ies", "sg_ies",
    "no_organizacao_academica", "no_categoria_administrativa", "co_curso", "no_modalidade_ensino", "co_municipio",
    "no_municipio", "sg_uf", "qt_concluintes_inscritos", "qt_concluintes_participantes", "qt_proficiente_padrao1",
    "prop_proficiente_padrao1", "enade_faixa", "in_sem_conceito", "in_cebas",
]
TXT = ["co_area", "no_area_avaliacao", "no_grau_academico", "co_ies", "no_ies", "sg_ies", "no_organizacao_academica",
       "no_categoria_administrativa", "co_curso", "no_modalidade_ensino", "co_municipio", "no_municipio", "sg_uf", "in_cebas"]
INTS = ["nu_ano_cpc", "nu_ano_enade", "qt_concluintes_inscritos", "qt_concluintes_participantes", "qt_proficiente_padrao1",
        "cpc_faixa", "enade_faixa"]


# ---------------------------------------------------------------------- Leitura
def _norm(h: object) -> str:
    t = unicodedata.normalize("NFKD", str(h)).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)  # tira asteriscos, notas de rodapé e pontuação
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r" \d$", "", t)  # nota de rodapé no fim ('Sigla da IES ¹' -> 'sigla da ies 1')


def _limpa(v: object) -> str | None:
    """Célula -> texto; marcadores de sem conceito/sem dado -> None."""
    if v is None:
        return None
    t = str(v).strip()
    if t.endswith(".0") and t[:-2].lstrip("-").isdigit():
        t = t[:-2]
    return None if t.upper() in NULOS else t


def ler_xlsx_mt(path: Path, mapa: list[tuple[str, str]]) -> pd.DataFrame:
    """Streaming do xlsx (cabeçalho na linha 1); só linhas com Sigla da UF = MT entram na memória."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        linhas = wb.worksheets[0].iter_rows(values_only=True)
        header = [_norm(h) for h in next(linhas)]
        idx: dict[str, int] = {}
        for rx, col in mapa:
            achado = [i for i, h in enumerate(header) if re.search(rx, h)]
            if achado:
                idx[col] = achado[0]
        for obrig in ("nu_ano", "co_curso", "co_ies", "co_municipio", "sg_uf"):
            if obrig not in idx:
                raise ValueError(f"{path.name}: coluna '{obrig}' não encontrada em {header[:15]}")
        i_uf = idx["sg_uf"]
        dados = [
            {c: _limpa(r[i]) for c, i in idx.items()}
            for r in linhas
            if r[i_uf] is not None and str(r[i_uf]).strip().upper() == UF
        ]
    finally:
        wb.close()
    return pd.DataFrame(dados, dtype="object")


def _numeros(df: pd.DataFrame, cols: list[str]) -> None:
    for c in cols:
        if c in df:  # decimal com vírgula (CPC 2022) e valores textuais viram número ou NULL
            df[c] = pd.to_numeric(df[c].astype("string").str.replace(",", ".", regex=False), errors="coerce")


def _finalizar(df: pd.DataFrame, ordem: list[str], faixa: str, continuos: list[str]) -> pd.DataFrame:
    df["co_municipio"] = df["co_municipio"].str.zfill(7)
    # in_sem_conceito: faixa sem número (SC/--). Valores contínuos desses cursos são NULL, não zero
    # (alguns arquivos gravam 0 no lugar do conceito).
    df["in_sem_conceito"] = df[faixa].isna() | (pd.to_numeric(df[faixa], errors="coerce").isna())
    _numeros(df, [c for c in df.columns if c.startswith(("nota_", "conceito_", "cpc_c", "prop_"))])
    sem = df["in_sem_conceito"]
    for c in continuos:
        if c in df:
            df.loc[sem, c] = pd.NA
    _numeros(df, INTS)
    for c in INTS:
        if c in df:
            df[c] = df[c].round().astype("Int64")
    for c in ordem:
        if c not in df:
            df[c] = pd.NA
    return df[ordem]


def carregar_cpc(raiz: Path) -> pd.DataFrame:
    partes = []
    for p in sorted(raiz.glob("*.xlsx")):
        m = re.fullmatch(r"cpc_(2021|2022|2023)\.xlsx", p.name, flags=re.I)
        if not m:
            continue
        df = ler_xlsx_mt(p, MAP_CPC)
        log.info("cpc %s: %d cursos de MT", p.name, len(df))
        partes.append(df)
    if len(partes) != 3:
        raise SystemExit(f"Esperados CPC_2021, cpc_2022 e CPC_2023 em {raiz}; achados {len(partes)}")
    df = pd.concat(partes, ignore_index=True).rename(columns={"nu_ano": "nu_ano_cpc"})
    df = _finalizar(df, ORD_CPC, "cpc_faixa", ["cpc_continuo", "conceito_enade_continuo"])
    _validar(df, ["nu_ano_cpc", "co_curso", "co_municipio"], "CPC")
    log.info("CPC: %d linhas MT | sem conceito: %d | anos %s", len(df), int(df["in_sem_conceito"].sum()),
             sorted(df["nu_ano_cpc"].dropna().unique().tolist()))
    return df


def carregar_enade(raiz: Path) -> pd.DataFrame:
    p = raiz / "conceito_enade_licenciaturas.xlsx"
    if not p.exists():
        raise SystemExit(f"{p} não encontrado")
    df = ler_xlsx_mt(p, MAP_ENADE).rename(columns={"nu_ano": "nu_ano_enade"})
    df = _finalizar(df, ORD_ENADE, "enade_faixa", ["prop_proficiente_padrao1"])
    # Edição especial 2025: o 'Percentual' é proporção (0 a 1); se vier em % (>1), converte.
    if (df["prop_proficiente_padrao1"].dropna() > 1).any():
        df["prop_proficiente_padrao1"] = df["prop_proficiente_padrao1"] / 100
    _validar(df, ["nu_ano_enade", "co_curso", "co_municipio"], "Enade")
    log.info("Enade licenciaturas: %d linhas MT | sem conceito: %d | anos %s", len(df),
             int(df["in_sem_conceito"].sum()), sorted(df["nu_ano_enade"].dropna().unique().tolist()))
    return df


def _validar(df: pd.DataFrame, chave: list[str], nome: str) -> None:
    if set(df["sg_uf"]) != {UF}:
        raise ValueError(f"{nome}: restaram UFs fora de MT: {set(df['sg_uf'])}")
    dup = int(df.duplicated(chave).sum())
    if dup:
        raise ValueError(f"{nome}: {dup} linhas duplicadas em {chave}")


# ------------------------------------------------------------------------ Carga
def _copy(cur, tabela: str, df: pd.DataFrame) -> None:
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)
    cur.execute(f"SELECT count(*) FROM {tabela}")
    antes = cur.fetchone()[0]
    cur.execute(f"TRUNCATE TABLE {tabela}")
    cur.copy_expert(f"COPY {tabela} ({', '.join(df.columns)}) FROM STDIN WITH (FORMAT csv, NULL '')", buf)
    cur.execute(f"SELECT count(*) FROM {tabela}")
    depois = cur.fetchone()[0]
    if depois != len(df):
        raise RuntimeError(f"{tabela}: banco={depois} vs memória={len(df)} (rollback)")
    log.info("%s: %s -> %s linhas (truncate-and-load)", tabela, antes, depois)


def carregar_supabase(engine, cpc: pd.DataFrame, enade: pd.DataFrame, recriar: bool) -> None:
    with engine.begin() as conn:  # uma transação: tudo ou nada
        cur = conn.connection.cursor()
        if recriar:
            log.info("--recriar: DROP das tabelas de qualidade")
            cur.execute(f"DROP TABLE IF EXISTS {T_CPC}, {T_ENADE}")
        cur.execute((SQL_DIR / "08_stg_qualidade_mt.sql").read_text(encoding="utf-8"))
        _copy(cur, T_CPC, cpc)
        _copy(cur, T_ENADE, enade)


# ------------------------------------------------------------------- Match / saída
SQL_MATCH = f"""
WITH traj AS (SELECT DISTINCT co_curso FROM {T_TRAJ} WHERE co_uf = '51'),
trajlic AS (SELECT DISTINCT co_curso FROM {T_TRAJ} WHERE co_uf = '51' AND tp_grau_academico = '2'),
cpc AS (SELECT DISTINCT co_curso FROM {T_CPC} WHERE sg_uf = 'MT'),
cpc_c AS (SELECT DISTINCT co_curso FROM {T_CPC} WHERE sg_uf = 'MT' AND cpc_faixa IS NOT NULL),
en AS (SELECT DISTINCT co_curso FROM {T_ENADE} WHERE sg_uf = 'MT')
SELECT
  (SELECT count(*) FROM cpc)                                              AS cpc_cursos,
  (SELECT count(*) FROM cpc WHERE co_curso IN (SELECT co_curso FROM traj)) AS cpc_com_trajetoria,
  (SELECT count(*) FROM cpc_c)                                            AS cpc_cursos_com_conceito,
  (SELECT count(*) FROM cpc_c WHERE co_curso IN (SELECT co_curso FROM traj)) AS cpc_conceito_com_trajetoria,
  (SELECT count(*) FROM en)                                               AS enade_cursos,
  (SELECT count(*) FROM en WHERE co_curso IN (SELECT co_curso FROM trajlic)) AS enade_com_trajetoria_lic
"""


def logar_match(engine) -> None:
    with engine.connect() as conn:
        if not conn.execute(text(f"SELECT to_regclass('{T_TRAJ}') IS NOT NULL")).scalar():
            raise SystemExit(f"{T_TRAJ} não existe: rode antes src/01_ingestao_trajetoria_supabase.py")
        if conn.execute(text(f"SELECT count(*) FROM {T_TRAJ}")).scalar() == 0:
            raise SystemExit(f"{T_TRAJ} está vazia: rode antes src/01_ingestao_trajetoria_supabase.py")
        r = conn.execute(text(SQL_MATCH)).one()
    pct = lambda a, b: f"{100 * a / b:.1f}%" if b else "n/a"
    log.info("MATCH P4 (CPC x Trajetória, via co_curso): %d/%d cursos casaram (%s); %d ficaram de fora",
             r.cpc_com_trajetoria, r.cpc_cursos, pct(r.cpc_com_trajetoria, r.cpc_cursos), r.cpc_cursos - r.cpc_com_trajetoria)
    log.info("MATCH P4 (só cursos com conceito CPC): %d/%d casaram (%s); %d de fora",
             r.cpc_conceito_com_trajetoria, r.cpc_cursos_com_conceito,
             pct(r.cpc_conceito_com_trajetoria, r.cpc_cursos_com_conceito),
             r.cpc_cursos_com_conceito - r.cpc_conceito_com_trajetoria)
    log.info("MATCH P5 (Enade Licenciaturas x Trajetória grau 2): %d/%d cursos casaram (%s); %d de fora",
             r.enade_com_trajetoria_lic, r.enade_cursos, pct(r.enade_com_trajetoria_lic, r.enade_cursos),
             r.enade_cursos - r.enade_com_trajetoria_lic)


def validar_somente_mt(engine) -> None:
    with engine.connect() as conn:
        ufs = {r[0] for t in (T_CPC, T_ENADE) for r in conn.execute(text(f"SELECT DISTINCT sg_uf FROM {t}"))}
    if ufs != {UF}:
        raise RuntimeError(f"Staging fora do escopo: sg_uf={ufs}")
    log.info("Validação: %s e %s contêm somente sg_uf=%s", T_CPC, T_ENADE, UF)


def executar_sql(engine, arquivo: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text((SQL_DIR / arquivo).read_text(encoding="utf-8")), conn)


def gravar_csv(df: pd.DataFrame, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".tmp")
    try:
        df.to_csv(tmp, index=False, encoding="utf-8", lineterminator="\n")
        os.replace(tmp, destino)
    finally:
        tmp.unlink(missing_ok=True)
    log.info("Gravado %s (%d linhas)", destino.relative_to(ROOT), len(df))


def extrair(engine, out: Path) -> None:
    p4 = executar_sql(engine, "09_p4_qualidade_retencao.sql")
    p5 = executar_sql(engine, "10_p5_funil_licenciaturas.sql")
    gravar_csv(p4, out / "p4_cpc_vs_desistencia.csv")
    gravar_csv(p5, out / "p5_funil_licenciaturas.csv")
    if p4.empty or p5.empty:
        raise RuntimeError("P4 ou P5 sem linhas — verifique a carga e o match com a Trajetória.")
    k = p4.iloc[0]
    log.info("P4: %d cursos na correlação | Pearson=%s | Spearman=%s", k.n_cursos_correlacao,
             k.corr_pearson_cpc_tda, k.corr_spearman_cpc_tda)
    log.info("P5: %d licenciaturas analisadas | %d em funil crítico", len(p5), int(p5["funil_critico"].sum()))


# ------------------------------------------------------------------------- Main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default=os.environ.get("QUALIDADE_RAW", str(ROOT / "archives" / "inep_indicadores_qualidade")))
    ap.add_argument("--out", default=str(ROOT / "outputs"))
    ap.add_argument("--recriar", action="store_true", help="DROP + CREATE das tabelas (mudança de schema)")
    ap.add_argument("--so-consultas", action="store_true", help="pula leitura/carga e recalcula P4/P5 do que está no banco")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    engine = get_engine()
    if not testar_conexao(engine):
        return 1
    if not a.so_consultas:
        log.info("[1/4] Leitura e filtro em memória (UF = MT)")
        cpc, enade = carregar_cpc(Path(a.raw)), carregar_enade(Path(a.raw))
        log.info("[2/4] Carga no Supabase")
        carregar_supabase(engine, cpc, enade, a.recriar)
    validar_somente_mt(engine)
    log.info("[3/4] Taxa de match com a Trajetória")
    logar_match(engine)
    log.info("[4/4] P4 e P5 no Supabase")
    extrair(engine, Path(a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
