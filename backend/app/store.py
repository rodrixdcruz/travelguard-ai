"""Best-effort journey persistence.

save_journey() / recent_journeys() no-op cleanly when no database is
configured (demo deployments keep working exactly as before); when one is
configured they persist every analysis and power GET /api/journeys/recent.
Persistence failures never fail an analysis — a traveler must always get
their risk briefing, database or not.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from .models import PersistedJourney

logger = logging.getLogger("travelguard.store")


def _origin_destination(journey: Any) -> dict[str, Any]:
    """Extract plain data from the pydantic Journey model."""
    return {
        "origin_name": journey.origin.name,
        "origin_lat": journey.origin.lat,
        "origin_lon": journey.origin.lon,
        "destination_name": journey.destination.name,
        "destination_lat": journey.destination.lat,
        "destination_lon": journey.destination.lon,
        "travel_date": journey.date,
        "travel_time": journey.time,
        "distance_km": journey.distance_km,
        "duration_min": journey.duration_min,
    }


def save_journey(
    db: Session,
    journey: Any,
    risk_score: float,
    risk_level: str,
    intelligence_mode: str,
) -> None:
    """Persist one analyzed journey. Raises on DB errors — caller wraps."""
    row = PersistedJourney(
        **_origin_destination(journey),
        risk_score=risk_score,
        risk_level=risk_level,
        intelligence_mode=intelligence_mode,
    )
    db.add(row)
    db.commit()


def recent_journeys(db: Session, limit: int = 10) -> list[dict[str, Any]]:
    """The latest journeys, newest first."""
    rows = (
        db.query(PersistedJourney)
        .order_by(PersistedJourney.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "origin": {"name": r.origin_name, "lat": r.origin_lat, "lon": r.origin_lon},
            "destination": {"name": r.destination_name, "lat": r.destination_lat, "lon": r.destination_lon},
            "date": r.travel_date,
            "time": r.travel_time,
            "distance_km": r.distance_km,
            "duration_min": r.duration_min,
            "risk_score": r.risk_score,
            "risk_level": r.risk_level,
            "intelligence_mode": r.intelligence_mode,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
