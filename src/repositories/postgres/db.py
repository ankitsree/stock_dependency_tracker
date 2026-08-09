"""Engine/session construction for the Postgres repositories."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


def normalize_database_url(url: str) -> str:
    """Render (and Heroku-style) connection strings use `postgres://`, and a
    bare `postgresql://` defaults to psycopg2 in SQLAlchemy. This project
    uses psycopg v3 (production-roadmap.md §6), which needs the dialect
    spelled out explicitly, or the same URL that works locally fails only in
    production.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix) and not url.startswith("postgresql+psycopg://"):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def make_engine(database_url: str) -> Engine:
    # pool_pre_ping: a hosted Postgres (Render) can drop idle connections;
    # this checks a connection is alive before handing it out instead of
    # surfacing a stale-connection error on the next request.
    return create_engine(normalize_database_url(database_url), pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)
