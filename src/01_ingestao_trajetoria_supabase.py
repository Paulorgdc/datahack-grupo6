"""Trajetória (INEP) -> Supabase (PostgreSQL) -> P1 e P2.

1. Lê as planilhas .xlsx (cabeçalho na linha 9), filtra em memória MT (CO_UF='51') + Graduação
   e mantém códigos como texto.
2. Carrega em public.stg_trajetoria_mt (DDL em sql/01_stg_trajetoria.sql) com TRUNCATE + COPY na
   mesma transação: reexecuções nunca duplicam linhas e uma falha faz rollback.
3. Executa sql/02_p1_trajetoria.sql e sql/03_p2_ranking_desistencia.sql no próprio Supabase e grava
   outputs/p1_trajetoria_2015.csv e outputs/p2_ranking_desistencia.csv (substituição atômica).

Filtros de P1/P2 (MT, Presencial, coortes, 5º ano, HAVING >= 10) são literais nos arquivos sql/.

Uso:  python src/01_ingestao_trajetoria_supabase.py [--raw archives/inep_trajetoria] [--recriar]
"""
from __future__ import annotations

import argparse
import io
import logging
import os
import sys
from pathlib import Path

import openpyxl
import pandas as pd
from sqlalchemy import text

from db import ROOT, get_engine, testar_conexao

log = logging.getLogger("datahack.trajetoria")

TABELA = "public.stg_trajetoria_mt"
SQL_DIR = ROOT / "sql"
HEADER_ROW = 9  # linhas 1-8 são metadados
GRAUS_GRADUACAO = {"1", "2", "3"}  # bacharelado, licenciatura, tecnológico
UF_MT = "51"  # Mato Grosso
MIN_GRUPO = 10  # regra do hackathon (aplicada em sql/03 via HAVING)

COLUNAS = [  # ordem do DDL (nomes em minúsculas no Postgres)
    "CO_IES", "NO_IES", "TP_CATEGORIA_ADMINISTRATIVA", "TP_ORGANIZACAO_ACADEMICA", "CO_CURSO", "NO_CURSO",
    "CO_REGIAO", "CO_UF", "CO_MUNICIPIO", "TP_GRAU_ACADEMICO", "TP_MODALIDADE_ENSINO",
    "CO_CINE_ROTULO", "NO_CINE_ROTULO", "CO_CINE_AREA_GERAL", "NO_CINE_AREA_GERAL",
    "NU_ANO_INGRESSO", "NU_ANO_REFERENCIA", "NU_PRAZO_INTEGRALIZACAO", "NU_ANO_INTEGRALIZACAO",
    "NU_PRAZO_ACOMPANHAMENTO", "NU_ANO_MAXIMO_ACOMPANHAMENTO",
    "QT_INGRESSANTE", "QT_PERMANENCIA", "QT_CONCLUINTE", "QT_DESISTENCIA", "QT_FALECIDO",
    "TAP", "TCA", "TDA", "TCAN", "TADA",
]
COLS_INT = [c for c in COLUNAS if c.startswith(("NU_", "QT_"))]
COLS_DBL = ["TAP", "TCA", "TDA", "TCAN", "TADA"]
PAD = {"CO_UF": 2, "CO_CINE_AREA_GERAL": 2, "CO_CINE_ROTULO": 7}


# ----------------------------------------------------------------- Leitura + filtro
def _cod(v) -> str:
    """Normaliza código vindo da célula (1, 1.0, ' 1 ', '51') para texto sem sufixo decimal."""
    t = str(v).strip()
    return t[:-2] if t.endswith(".0") else t


def listar_xlsx(raiz: Path) -> list[Path]:
    return sorted(p for p in raiz.rglob("*.xlsx") if not p.name.startswith("~$") and "trajetoria" in p.name.lower())


def ler_xlsx_mt_graduacao(path: Path, uf: str) -> pd.DataFrame:
    """Streaming do xlsx (cabeçalho na linha 9); descarta na leitura tudo que não é UF/Graduação."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        linhas = wb.worksheets[0].iter_rows(min_row=HEADER_ROW, values_only=True)
        header = [str(h).strip() for h in next(linhas)]
        faltam = [c for c in COLUNAS if c not in header]
        if faltam:
            raise ValueError(f"{path.name}: cabeçalho da linha {HEADER_ROW} sem colunas {faltam}")
        i_uf, i_grau = header.index("CO_UF"), header.index("TP_GRAU_ACADEMICO")
        dados = [
            tuple(None if v is None else str(v).strip() for v in r)
            for r in linhas
            if r[i_uf] is not None and _cod(r[i_uf]).zfill(2) == uf and r[i_grau] is not None and _cod(r[i_grau]) in GRAUS_GRADUACAO
        ]
    finally:
        wb.close()
    return pd.DataFrame(dados, columns=header, dtype="object")[COLUNAS]


def carregar_raw(raw: Path, uf: str) -> pd.DataFrame:
    arquivos = listar_xlsx(raw)
    if not arquivos:
        raise SystemExit(f"Nenhum .xlsx de Trajetória em {raw}")
    if len(arquivos) != 6:
        log.warning("Esperados 6 arquivos (coortes 2015-2020); encontrados %d", len(arquivos))
    partes = []
    for p in arquivos:
        df = ler_xlsx_mt_graduacao(p, uf)
        log.info("raw %s -> %s linhas (UF=%s, Graduação)", p.name, f"{len(df):,}", uf)
        partes.append(df)
    df = pd.concat(partes, ignore_index=True)
    for c, n in PAD.items():
        df[c] = df[c].str.zfill(n)
    for c in COLS_INT:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")  # suprimidos/inválidos -> NULL
    for c in COLS_DBL:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # Garantia: nada fora de MT/Graduação sobreviveu ao filtro de leitura.
    if set(df["CO_UF"]) != {uf} or not set(df["TP_GRAU_ACADEMICO"]) <= GRAUS_GRADUACAO:
        raise ValueError(f"Filtro falhou: UFs={set(df['CO_UF'])}, graus={set(df['TP_GRAU_ACADEMICO'])}")
    chave = ["CO_IES", "CO_CURSO", "NU_ANO_INGRESSO", "NU_ANO_REFERENCIA"]
    dup = int(df.duplicated(chave).sum())
    if dup:  # EAD/multi-polo: seria preciso agregar por CO_CURSO antes de carregar
        raise ValueError(f"{dup} linhas duplicadas na chave {chave}; agregar por CO_CURSO antes da carga")
    log.info("Em memória: %s linhas | ~%.1f MB | coortes %s", f"{len(df):,}",
             df.memory_usage(deep=True).sum() / 1e6, sorted(df["NU_ANO_INGRESSO"].dropna().unique().tolist()))
    return df


# ------------------------------------------------------------------- Carga Supabase
def carregar_supabase(engine, df: pd.DataFrame, recriar: bool) -> None:
    """DDL + TRUNCATE + COPY em uma única transação (tudo ou nada)."""
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)
    colunas = ", ".join(c.lower() for c in COLUNAS)
    with engine.begin() as conn:
        cur = conn.connection.cursor()
        if recriar:
            log.info("--recriar: DROP TABLE %s", TABELA)
            cur.execute(f"DROP TABLE IF EXISTS {TABELA}")
        cur.execute((SQL_DIR / "01_stg_trajetoria.sql").read_text(encoding="utf-8"))
        cur.execute(f"SELECT count(*) FROM {TABELA}")
        antes = cur.fetchone()[0]
        cur.execute(f"TRUNCATE TABLE {TABELA}")
        cur.copy_expert(f"COPY {TABELA} ({colunas}) FROM STDIN WITH (FORMAT csv, NULL '')", buf)
        cur.execute(f"SELECT count(*) FROM {TABELA}")
        depois = cur.fetchone()[0]
        if depois != len(df):
            raise RuntimeError(f"Contagem divergente após COPY: banco={depois} vs memória={len(df)} (rollback)")
        cur.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{TABELA}'))")
        tamanho = cur.fetchone()[0]
    log.info("Carga OK: %s antes -> %s depois (truncate-and-load) | tamanho da tabela: %s", f"{antes:,}", f"{depois:,}", tamanho)


# ------------------------------------------------------------------ P1 / P2 em SQL
def executar_sql(engine, arquivo: str) -> pd.DataFrame:
    """Executa o .sql como está (PostgreSQL nativo, filtros literais, sem parâmetros)."""
    sql = (SQL_DIR / arquivo).read_text(encoding="utf-8")
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def validar_somente_mt(engine) -> None:
    with engine.connect() as conn:
        ufs = [r[0] for r in conn.execute(text(f"SELECT DISTINCT co_uf FROM {TABELA}"))]
        graus = {r[0] for r in conn.execute(text(f"SELECT DISTINCT tp_grau_academico FROM {TABELA}"))}
    if ufs != [UF_MT] or not graus <= GRAUS_GRADUACAO:
        raise RuntimeError(f"Tabela fora do escopo: co_uf={ufs}, graus={graus}")
    log.info("Validação: %s contém somente co_uf=%s e graus %s", TABELA, UF_MT, sorted(graus))


def gravar_csv(df: pd.DataFrame, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".tmp")
    try:
        df.to_csv(tmp, index=False, encoding="utf-8", lineterminator="\n")
        os.replace(tmp, destino)
    finally:
        tmp.unlink(missing_ok=True)
    log.info("Gravado %s (%d linhas)", destino.relative_to(ROOT), len(df))


# ------------------------------------------------------------------------- Main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default=os.environ.get("TRAJETORIA_RAW", str(ROOT / "archives" / "inep_trajetoria")))
    ap.add_argument("--out", default=str(ROOT / "outputs"))
    ap.add_argument("--recriar", action="store_true", help="DROP + CREATE da tabela (mudança de schema)")
    ap.add_argument("--so-consultas", action="store_true", help="pula leitura/carga e recalcula P1/P2 do que já está no banco")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    engine = get_engine()
    if not testar_conexao(engine):
        return 1

    if not a.so_consultas:
        log.info("[1/3] Leitura e filtro em memória")
        df = carregar_raw(Path(a.raw), UF_MT)
        log.info("[2/3] Carga no Supabase")
        carregar_supabase(engine, df, a.recriar)
    log.info("[3/3] P1 e P2 no Supabase")
    out = Path(a.out)
    validar_somente_mt(engine)

    p1 = executar_sql(engine, "02_p1_trajetoria.sql")
    if p1.empty:
        log.error("P1 sem linhas — a tabela está vazia ou os filtros não casam.")
        return 1
    gravar_csv(p1, out / "p1_trajetoria_2015.csv")
    pior = p1[p1["maior_perda_anual"]].iloc[0]
    log.info("P1: maior perda anual no %dº ano do curso (ref. %d): %.2f%% dos ingressantes",
             pior.ano_do_curso, pior.ano_referencia, pior.tada_pct)

    p2 = executar_sql(engine, "03_p2_ranking_desistencia.sql")
    gravar_csv(p2, out / "p2_ranking_desistencia.csv")
    for (nivel, coorte), g in p2.groupby(["nivel", "coorte"]):
        log.info("P2 %s %s: %d grupos (>=%d alunos)", nivel, coorte, len(g), MIN_GRUPO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
