"""Conexão com o Supabase (PostgreSQL na nuvem) via SQLAlchemy + psycopg2.

A URL vem de SUPABASE_DB_URL (arquivo .env na raiz; veja .env.example).
Teste rápido:  python src/db.py
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

ROOT = Path(__file__).resolve().parents[1]
ENV_VAR = "SUPABASE_DB_URL"
log = logging.getLogger("datahack.db")


def _url() -> str:
    load_dotenv(ROOT / ".env")
    raw = os.environ.get(ENV_VAR, "").strip()
    if not raw or "[SUA_SENHA]" in raw or "[HOST_DO_SUPABASE]" in raw:
        raise RuntimeError(
            f"{ENV_VAR} ausente ou ainda com placeholders. Copie .env.example para .env e preencha "
            "(Supabase > Project Settings > Database > Connection string)."
        )
    # SQLAlchemy exige o driver explícito; Supabase/Heroku às vezes entregam 'postgres://'.
    for prefix in ("postgres://", "postgresql://"):
        if raw.startswith(prefix):
            raw = "postgresql+psycopg2://" + raw[len(prefix):]
            break
    return raw


def get_engine() -> Engine:
    url = make_url(_url())
    connect_args = {} if "sslmode" in url.query else {"sslmode": "require"}  # Supabase exige TLS
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


def testar_conexao(engine: Engine | None = None) -> bool:
    """Abre uma conexão e loga versão, banco e usuário. Nunca imprime a senha."""
    try:
        engine = engine or get_engine()
        alvo = engine.url.render_as_string(hide_password=True)
        log.info("Conectando em %s ...", alvo)
        with engine.connect() as conn:
            versao, banco, usuario = conn.execute(
                text("SELECT version(), current_database(), current_user")
            ).one()
        log.info("Conexão OK | banco=%s | usuário=%s | %s", banco, usuario, versao.split(",")[0])
        return True
    except Exception as exc:  # noqa: BLE001 — queremos qualquer falha de rede/auth/URL
        log.error("Falha na conexão: %s", str(exc).splitlines()[0])
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(0 if testar_conexao() else 1)
