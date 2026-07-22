"""Engine and session factory, from DATABASE_URL (no credentials in source — AD-47)."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. APX reads it from the environment (AD-47). "
            "e.g. postgresql+psycopg://apx:...@localhost:5432/apx"
        )
    return url


def make_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=create_engine(database_url(), future=True))
