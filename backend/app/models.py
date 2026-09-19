"""ORM models (SQLAlchemy 2.0).

PersistedJourney stores every analyzed journey so travelers can revisit
recent analyses. Tables are created by init_db() at startup — writes and
reads are best-effort (see app/store.py): when no DATABASE_URL is set the
API behaves exactly as the pure-demo deployment always has.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class PersistedJourney(Base):
    __tablename__ = "journeys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origin_name: Mapped[str] = mapped_column(String(200))
    origin_lat: Mapped[float] = mapped_column(Float)
    origin_lon: Mapped[float] = mapped_column(Float)
    destination_name: Mapped[str] = mapped_column(String(200))
    destination_lat: Mapped[float] = mapped_column(Float)
    destination_lon: Mapped[float] = mapped_column(Float)
    travel_date: Mapped[str] = mapped_column(String(10))   # YYYY-MM-DD
    travel_time: Mapped[str] = mapped_column(String(5))    # HH:MM
    distance_km: Mapped[float] = mapped_column(Float)
    duration_min: Mapped[float] = mapped_column(Float)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    intelligence_mode: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
    )
