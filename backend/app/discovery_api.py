"""Tourist discovery & day-planning API.

All responses carry data_status so the UI can label every record honestly.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from .planner import plan_day, local_safety_context
from .providers.demo_mumbai import VERIFIED_EMERGENCY_NUMBERS
from .providers import food as food_provider
from .providers import places as places_provider
from .providers import services as services_provider
from .providers.transport import RATES
from .schemas import DayPlanRequest

router = APIRouter(prefix="/api", tags=["discovery"])


# ── Places ──────────────────────────────────────────────────────────────

@router.get("/places/nearby")
async def places_nearby(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10.0, gt=0, le=60),
    category: Optional[str] = Query(None),
    interest: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
) -> dict[str, Any]:
    # Providers do synchronous HTTP (OSM Overpass, demo dataset). Run them
    # in a threadpool so a slow upstream can never stall the event loop —
    # a blocked loop starves /health and Render evicts the instance.
    items = await asyncio.to_thread(
        places_provider.fetch_nearby,
        latitude, longitude, radius_km=radius_km, category=category,
        interest=interest, limit=limit,
    )
    # Report the ACTUAL status of what was served, never a hardcoded claim.
    statuses = {i.get("data_status", "DEMO") for i in items}
    sources = {i.get("data_source", "") for i in items} - {""}
    if statuses == {"LIVE"}:
        resp_status = "LIVE"
        source = "+".join(sorted(sources)) or "live_providers"
    elif "LIVE" in statuses:
        resp_status = "MIXED"
        source = "+".join(sorted(sources)) + "+travelguard_demo_dataset"
    else:
        resp_status, source = "DEMO", "travelguard_demo_dataset"
    return {
        "origin": {"latitude": latitude, "longitude": longitude},
        "radius_km": radius_km,
        "count": len(items),
        "places": items,
        "data_status": resp_status,
        "data_source": source,
    }


@router.get("/places/{place_id}")
async def place_details(place_id: str) -> dict[str, Any]:
    place = places_provider.fetch_by_id(place_id)
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found in current dataset")
    return {**place, "data_status": "DEMO"}


# ── Food ────────────────────────────────────────────────────────────────

@router.get("/food/nearby")
async def food_nearby(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(8.0, gt=0, le=40),
    vegetarian: Optional[bool] = Query(None),
    budget: Optional[int] = Query(None, ge=0),
    cuisine: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
) -> dict[str, Any]:
    items = await asyncio.to_thread(
        food_provider.fetch_nearby,
        latitude, longitude, radius_km=radius_km, vegetarian=vegetarian,
        budget=budget, cuisine=cuisine, limit=limit,
    )
    statuses = {i.get("data_status", "DEMO") for i in items}
    if statuses == {"LIVE"}:
        resp_status, source = "LIVE", "openstreetmap_overpass"
    elif "LIVE" in statuses:
        resp_status, source = "MIXED", "openstreetmap_overpass+travelguard_demo_dataset"
    else:
        resp_status, source = "DEMO", "travelguard_demo_dataset"
    return {
        "origin": {"latitude": latitude, "longitude": longitude},
        "radius_km": radius_km,
        "count": len(items),
        "food": items,
        "data_status": resp_status,
        "data_source": source,
        "note": "Per-person spend estimates are ESTIMATED from price class.",
    }


# ── Services ────────────────────────────────────────────────────────────

@router.get("/services/nearby")
async def services_nearby(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(8.0, gt=0, le=40),
    service_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
) -> dict[str, Any]:
    items = await asyncio.to_thread(
        services_provider.fetch_nearby,
        latitude, longitude, radius_km=radius_km, service_type=service_type, limit=limit,
    )
    statuses = {i.get("data_status", "DEMO") for i in items}
    if statuses == {"LIVE"}:
        resp_status, source = "LIVE", "openstreetmap_overpass"
    elif "LIVE" in statuses:
        resp_status, source = "MIXED", "openstreetmap_overpass+travelguard_demo_dataset"
    else:
        resp_status, source = "DEMO", "travelguard_demo_dataset"
    return {
        "origin": {"latitude": latitude, "longitude": longitude},
        "radius_km": radius_km,
        "count": len(items),
        "services": items,
        "data_status": resp_status,
        "data_source": source,
        "note": "Phone numbers are omitted unless verifiably available — never fabricated.",
    }


@router.get("/sos/info")
async def sos_info(
    latitude: Optional[float] = Query(None, ge=-90, le=90),
    longitude: Optional[float] = Query(None, ge=-180, le=180),
) -> dict[str, Any]:
    """SOS center payload: verified emergency numbers + nearest safety services.

    Only verified, government-published numbers are returned. Anything else is
    omitted so the UI can say "unavailable in current data" instead of guessing.
    """
    nearest: dict[str, Any] = {}
    if latitude is not None and longitude is not None:
        for stype in ("hospital", "police", "pharmacy"):
            item = await asyncio.to_thread(services_provider.nearest_by_type, latitude, longitude, stype)
            if item:
                nearest[stype] = item
    return {
        "emergency_numbers": VERIFIED_EMERGENCY_NUMBERS,
        "nearest": nearest,
        "data_status": "DEMO",
        "note": "Local station numbers are omitted unless verifiably available — never fabricated.",
    }


@router.get("/safety/local")
async def safety_local(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    hour: Optional[int] = Query(None, ge=0, le=23),
) -> dict[str, Any]:
    """Local safety context for a point — the existing ML safety model, reused.

    Decision-support score, not accident probability; trained on synthetic
    demonstration data (see /api/ml/info).
    """
    from datetime import datetime

    h = hour if hour is not None else datetime.now().hour
    prediction = await asyncio.to_thread(local_safety_context, latitude, longitude, h)
    return {
        **prediction,
        "disclaimer": "Decision-support score, not accident probability. Trained on synthetic demonstration data.",
        "data_status": "DEMO",
    }


@router.get("/transport/modes")
async def transport_modes() -> dict[str, Any]:
    """Available transport modes with their ESTIMATED rate model."""
    return {
        "modes": [
            {"mode": mode, "per_km_inr": cfg["per_km"], "min_fare_inr": cfg["min_fare"],
             "data_status": "ESTIMATED"}
            for mode, cfg in RATES.items()
        ]
    }


# ── AI day planner ──────────────────────────────────────────────────────

@router.post("/plan/day")
async def plan_day_endpoint(req: DayPlanRequest) -> dict[str, Any]:
    """ML ranking → optimizer → costed itinerary + safety context."""
    try:
        return await asyncio.to_thread(plan_day, req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
