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
from sqlalchemy.orm import sessionmaker, declarative_base

# ── Database path (same file as raw sqlite3 layer uses) ───────────────────────
_DB_PATH = os.environ.get(
    "DATABASE_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "examlens.db")
)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_DB_PATH}"

# ── SQLAlchemy engine & session (for Member 5 / ORM users) ───────────────────
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite
)

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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
