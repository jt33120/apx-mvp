"""Engine and session factory, from DATABASE_URL (no credentials in source — AD-47)."""

from __future__ import annotations

import os
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _normalise(url: str) -> str:
    """Bind a managed host's URL to the installed driver. Railway, Heroku and Supabase
    hand out ``postgres://`` or ``postgresql://`` (no driver); we run psycopg 3, which
    SQLAlchemy addresses as ``postgresql+psycopg://`` — so the app connects unchanged
    against whatever DATABASE_URL the platform injects. Other URLs (sqlite, an explicit
    driver) pass through untouched."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _with_sslmode(url: str) -> str:
    """Encrypt the app↔store connection in transit (AD-31). For a PostgreSQL URL, apply
    ``APX_DB_SSLMODE`` (default ``require``) unless the URL already carries an ``sslmode`` —
    so a hosted connection uses TLS out of the box, with no permissive default. A same-machine
    loopback (the single-machine install, a CI service container) may set
    ``APX_DB_SSLMODE=disable`` with a documented rationale — traffic that never leaves the
    host. Non-PostgreSQL URLs (sqlite in tests) pass through untouched."""
    if not url.startswith("postgresql"):
        return url
    query = urlsplit(url).query
    if "sslmode" in parse_qs(query):
        return url  # an explicit sslmode (anywhere it's already set) is never overridden
    sslmode = os.environ.get("APX_DB_SSLMODE", "require").strip() or "require"
    sep = "&" if query else "?"
    return f"{url}{sep}sslmode={sslmode}"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. APX reads it from the environment (AD-47). "
            "e.g. postgresql+psycopg://apx:...@localhost:5432/apx"
        )
    return _with_sslmode(_normalise(url))


def make_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=create_engine(database_url(), future=True))
