"""Database foundation (SQLAlchemy 2.0).

The app runs fully in demo mode without a database. If DATABASE_URL is set,
the engine is created and init_db() prepares the schema for the models that
will be added in later steps (User, Journey, Route, RouteSegment,
RiskAssessment, Alert).
"""
from __future__ import annotations

import logging
import os
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger("travelguard.database")

DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL") or None

if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        logger.info("Database engine configured.")
    except Exception as exc:  # pragma: no cover
        logger.warning("Database engine creation failed (%s); running without DB.", exc)
        engine = None  # type: ignore[assignment]
        SessionLocal = None  # type: ignore[assignment]
else:
    engine = None  # type: ignore[assignment]
    SessionLocal = None  # type: ignore[assignment]


class Base(DeclarativeBase):
    """Declarative base for future ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency. Yields a session only if a DB is configured."""
    if SessionLocal is None:
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def db_status() -> str:
    """'connected' | 'unavailable' | 'not-configured' for /health."""
    if engine is None:
        return "not-configured"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "connected"
    except Exception:
        return "unavailable"


def init_db() -> None:
    """Create tables for models registered on Base (none yet — future steps)."""
    if engine is None:
        return
    try:
        import app.models  # noqa: F401  (registers models when they exist)
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logger.warning("init_db skipped: %s", exc)
