"""
app/database/__init__.py
========================
Exports both database interfaces used by different members:

  Raw sqlite3 (Member 3's layer):
    - Access via app.database.db  (init_db, insert_question, etc.)

  SQLAlchemy (Member 5's analytics layer):
    - engine       → SQLAlchemy Engine instance
    - SessionLocal → session factory
    - Base         → declarative base for ORM models
    - get_db()     → FastAPI dependency that yields a DB session

This file is the bridge so that:
    from app.database import engine, get_db       # Member 5's import
    from app.database.db import init_db           # Member 3's import
both work after branches are merged.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

# ── Database path (same file as raw sqlite3 layer uses) ───────────────────────
_FALLBACK_DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "examlens.db")
_engine_cache: dict[str, Engine] = {}


def _configured_db_path() -> str:
    return os.environ.get("DATABASE_PATH", _FALLBACK_DB_PATH)


def get_engine() -> Engine:
    """SQLAlchemy engine for the currently configured DATABASE_PATH."""
    path = _configured_db_path()
    cached = _engine_cache.get(path)
    if cached is None:
        cached = create_engine(
            f"sqlite:///{path}",
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )
        _engine_cache[path] = cached
    return cached


def dispose_engines() -> None:
    """Release SQLite file handles so tests can delete temporary databases."""
    for cached in list(_engine_cache.values()):
        cached.dispose()
    _engine_cache.clear()


def _sqlalchemy_database_url() -> str:
    return f"sqlite:///{_configured_db_path()}"


SQLALCHEMY_DATABASE_URL = _sqlalchemy_database_url()
engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that yields a SQLAlchemy Session.

    Usage in a route:
        from app.database import get_db
        from sqlalchemy.orm import Session

        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    Session = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    db = Session()
    try:
        yield db
    finally:
        db.close()
