"""Turso database engine and session helpers (SQLModel / SQLAlchemy)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import turso_serverless
from dotenv import load_dotenv
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

DB_URL = os.environ.get("DB_URL", "")
DB_TOKEN = os.environ.get("DB_TOKEN", "")


def _turso_connection():
    """Open a Turso DB-API connection compatible with SQLAlchemy's sqlite dialect."""
    if not DB_URL or not DB_TOKEN:
        raise RuntimeError("DB_URL and DB_TOKEN must be set to connect to Turso")

    conn = turso_serverless.connect(DB_URL, auth_token=DB_TOKEN)
    # SQLAlchemy's sqlite dialect expects sqlite3.create_function on connect.
    if not hasattr(conn, "create_function"):
        conn.create_function = lambda *args, **kwargs: None  # type: ignore[method-assign]
    return conn


engine = create_engine(
    "sqlite://",
    creator=_turso_connection,
    poolclass=NullPool,
)

_schema_ready = False


def init_db() -> None:
    """Create all SQLModel tables on Turso if they do not exist."""
    global _schema_ready
    if _schema_ready:
        return

    # Import models so they register on SQLModel.metadata before create_all.
    from api import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _schema_ready = True


@contextmanager
def get_session() -> Iterator[Session]:
    """Yield a SQLModel session bound to Turso."""
    with Session(engine) as session:
        yield session
