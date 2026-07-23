"""Engine and session factory, from DATABASE_URL (no credentials in source — AD-47)."""

from __future__ import annotations

import os

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


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. APX reads it from the environment (AD-47). "
            "e.g. postgresql+psycopg://apx:...@localhost:5432/apx"
        )
    return _normalise(url)


def make_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=create_engine(database_url(), future=True))
