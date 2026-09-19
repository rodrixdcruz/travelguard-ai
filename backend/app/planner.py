"""AI Day Planner — orchestrates the full tourist workflow.

discover → ML ranking → feasibility optimizer → travel legs + meal breaks →
costed timeline + local safety context. The LLM narrates the result
downstream; it never invents places, prices or hours here.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .ml import predictor as ml_predictor
from .providers import food as food_provider
from .providers import places as places_provider
from .providers import services as services_provider
from .providers import tickets as tickets_provider
from .providers import transport as transport_provider
from .providers import weather as weather_provider
from .schemas import DayPlanRequest

DURATION_MAP = {"2h": 2.0, "4h": 4.0, "half_day": 5.0, "full_day": 8.0}
BUDGET_MAP = {"budget": 800.0, "moderate": 2000.0, "premium": 5000.0}
TRAVELERS_MAP = {"1": 1, "2": 2, "family": 4, "group": 6}

MEAL_TRIGGERS = ((11.5, 13.5, "Lunch"), (18.0, 19.5, "Dinner"))
BREAKFAST_AT = 9.0
MEAL_MINUTES = 60


def _to_optimizer_place(p: dict[str, Any]) -> dict[str, Any]:
    """Map a normalized Place onto the optimizer/ML feature contract."""
    tags = list(p.get("tags", []))
    if "historical" in tags and "history" not in tags:
        tags.append("history")  # interest vocabulary alias
    return {
        "place_id": p["id"],
        "name": p["name"],
        "category": p["category"],
        "tags": tags,
        "distance_km": p.get("distance_km", 5.0),
        "estimated_cost": float(p.get("entry_fee", 0) or 0),   # per-person ticket
        "popularity": min(100.0, (p.get("rating") or 4.0) * 20.0),
        "visit_duration_hours": (p.get("estimated_visit_minutes", 60) or 60) / 60.0,
        "is_open": p.get("opening_status") != "closed",        # 'unknown' treated optimistically, flagged in output
        "opening_status": p.get("opening_status", "unknown"),
        "safety_context": float(p.get("safety_context", 75) or 75),
        "lat": p["latitude"],
        "lon": p["longitude"],
        "entry_fee": float(p.get("entry_fee", 0) or 0),
        "ticket_required": p.get("ticket_required"),
        "data_status": p.get("data_status", "DEMO"),
    }


def _clock(base: datetime, minutes: float) -> str:
    return (base + timedelta(minutes=minutes)).strftime("%H:%M")


def _insert_meals(
    items: list[dict[str, Any]],
    origin: tuple[float, float],
    travelers: int,
    start_dt: datetime,
) -> list[dict[str, Any]]:
    """Insert meal breaks when the running schedule crosses a meal window.

    Items carry no clock times yet — times are assigned by the caller's
    sequential pass after insertion, so meal shifts propagate correctly.
    """
    out: list[dict[str, Any]] = []
    cursor_min = 0.0
    meals_used: set[str] = set()

    for item in items:
        start_hour = (start_dt.hour + start_dt.minute / 60.0) + cursor_min / 60.0
        for lo, hi, label in MEAL_TRIGGERS:
            if label in meals_used:
                continue
            if lo <= start_hour <= hi:
                nearby_food = food_provider.fetch_nearby(origin[0], origin[1], radius_km=3.0, limit=1)
                per_person = (
                    food_provider.PRICE_CLASS_ESTIMATE.get(nearby_food[0]["price_range"], 400)
                    if nearby_food
                    else 300
                )
                out.append(
                    {
                        "type": "meal",
                        "name": f"{label} — {nearby_food[0]['name']}" if nearby_food else label,
                        "category": "meal",
                        "detail": "Estimated from price class (ESTIMATED data)",
                        "duration_min": MEAL_MINUTES,
                        "cost_inr": per_person * travelers,
                        "data_status": "ESTIMATED",
                        "safety": None,
                    }
                )
                meals_used.add(label)
                cursor_min += MEAL_MINUTES
                start_hour += MEAL_MINUTES / 60.0
        out.append(item)
        cursor_min += item.get("duration_min", 0)
    return out, cursor_min


def _parse_duration(duration: str) -> float:
    """Known presets or explicit numeric hours; anything else is an error."""
    d = str(duration).strip().lower()
    if d in DURATION_MAP:
        return DURATION_MAP[d]
    try:
        return float(d)
    except ValueError:
        raise ValueError("duration must be 2h, 4h, half_day, full_day, or custom hours like '5'") from None


def _parse_budget(budget: str | float | int) -> float:
    """Known presets or explicit numeric INR; anything else is an error."""
    b = str(budget).strip().lower()
    if b in BUDGET_MAP:
        return BUDGET_MAP[b]
    try:
        return float(b)
    except ValueError:
        raise ValueError("budget must be budget, moderate, premium, or custom INR amount") from None


def plan_day(req: DayPlanRequest) -> dict[str, Any]:
    lat, lon = req.latitude, req.longitude

    hours = _parse_duration(req.duration)
    if not 1.0 <= hours <= 14.0:
        raise ValueError("duration must resolve to 1–14 hours")
    budget_per_person = _parse_budget(req.budget)
    travelers = TRAVELERS_MAP.get(str(req.travelers), 2)

    # ── 1. Discover candidates near the tourist ──
    radius = 12.0 if hours >= 5 else 8.0
    candidates = places_provider.fetch_nearby(lat, lon, radius_km=radius, limit=30)
    if req.interests:
        wanted = {i.lower() for i in req.interests}
        matched = [p for p in candidates if wanted & {t.lower() for t in p["tags"]}]
        candidates = matched or candidates  # fall back to all if interest too narrow
    if not candidates:
        raise ValueError("No places found near this location in the current dataset")

    # ── 2. ML ranking (existing recommendation model — reused, not duplicated) ──
    opt_places = [_to_optimizer_place(p) for p in candidates]
    rec_prefs = {
        "interests": req.interests or [],
        "budget": budget_per_person,
        "available_hours": hours,
    }
    ranked = ml_predictor.recommend_places(opt_places, rec_prefs)
    ranked_places = ranked["places"]
    reasons_by_id = {
        p["place_id"]: {"reasons": p.get("reasons", []), "score": p.get("recommendation_score")}
        for p in ranked_places
    }

    # ── 3. Feasibility optimization (existing optimizer — reused) ──
    from .ml.itinerary import build_itinerary

    max_stops = 2 if hours <= 2 else 3 if hours <= 4 else 4 if hours <= 5.5 else 6
    plan = build_itinerary(
        ranked_places,
        available_hours=hours,
        budget=budget_per_person,
        interests=req.interests or [],
        max_stops=max_stops,
    )
    chosen_ids = {s["place_id"] for s in plan["stops"]}

    # ── 4. Build the timeline with travel legs ──
    start_time = req.start_time or "09:00"
    try:
        start_dt = datetime.strptime(start_time, "%H:%M")
    except ValueError:
        start_dt = datetime.strptime("09:00", "%H:%M")

    items: list[dict[str, Any]] = []
    cursor = (lat, lon)
    travel_total = 0.0
    transport_total = 0.0

    for stop in plan["stops"]:
        dest = next(
            (p for p in opt_places if p["place_id"] == stop["place_id"]), None
        )
        if dest is None:
            continue
        leg = transport_provider.estimate(cursor, (dest["lat"], dest["lon"]), mode="taxi")
        travel_total += leg["duration_min"]
        transport_total += leg["estimated_fare_inr"] * transport_provider.vehicles_for(travelers)
        items.append(
            {
                "type": "travel",
                "name": f"Travel to {dest['name']}",
                "category": "travel",
                "detail": f"~{leg['distance_km']} km by {leg['mode']} (ESTIMATED)",
                "duration_min": leg["duration_min"],
                "cost_inr": round(leg["estimated_fare_inr"] * transport_provider.vehicles_for(travelers)),
                "data_status": "ESTIMATED",
                "safety": None,
                "to_place_id": dest["place_id"],
                "to_name": dest["name"],
            }
        )
        cursor = (dest["lat"], dest["lon"])
        visit_min = dest["visit_duration_hours"] * 60.0
        item_reasons = reasons_by_id.get(dest["place_id"], {}).get("reasons", [])
        items.append(
            {
                "type": "attraction",
                "name": dest["name"],
                "category": dest["category"],
                "place_id": dest["place_id"],
                "detail": dest.get("opening_status", "unknown"),
                "duration_min": round(visit_min),
                "travel_time_min": round(
                    sum(
                        i["duration_min"]
                        for i in items
                        if i["type"] == "travel" and i.get("to_place_id") == dest["place_id"]
                    )
                ),
                "cost_inr": round(dest["entry_fee"] * travelers),
                "ticket_required": dest.get("ticket_required"),
                "data_status": "DEMO",
                "safety": _safety_band(dest["safety_context"]),
                "recommendation_score": stop.get("recommendation_score"),
                "reasons": item_reasons,
                "latitude": dest["lat"],
                "longitude": dest["lon"],
            }
        )

    # ── Meal breaks inserted at their clock-time windows, then times assigned ──
    items, _ = _insert_meals(items, (lat, lon), travelers, start_dt)

    # Single sequential pass: every item's clock time follows the running total.
    running = 0.0
    for item in items:
        item["time"] = _clock(start_dt, running)
        running += item.get("duration_min", 0)

    total_min = running
    food_total = sum(i["cost_inr"] for i in items if i["type"] == "meal")
    tickets_total = round(float(plan["cost_breakdown"]["tickets"]) * travelers)

    # ── 5. Local safety context (existing ML safety model — reused) ──
    wx = weather_provider.current_conditions(lat, lon)
    safety = local_safety_context(lat, lon, start_dt.hour, wx=wx)

    end_dt = start_dt + timedelta(minutes=total_min)
    total_cost = round(tickets_total + food_total + transport_total)

    return {
        "location": {"latitude": lat, "longitude": lon, "name": req.location_name},
        "preferences": {
            "duration": req.duration,
            "hours": hours,
            "budget_per_person": budget_per_person,
            "interests": req.interests,
            "travelers": travelers,
            "start_time": start_dt.strftime("%H:%M"),
        },
        "itinerary": {
            "start_time": start_dt.strftime("%H:%M"),
            "end_time": end_dt.strftime("%H:%M"),
            "items": items,
            "totals": {
                "places": len(plan["stops"]),
                "total_time_min": round(total_min),
                "total_estimated_cost_inr": total_cost,
                "within_budget": total_cost <= budget_per_person * travelers,
            },
        },
        "cost_breakdown": {
            "tickets": tickets_total,
            "food_estimate": round(food_total),
            "transport_estimate": round(transport_total),
            "total_estimate": total_cost,
            "budget_total": round(budget_per_person * travelers),
            "travelers": travelers,
            "line_status": {
                "tickets": "DEMO",
                "food_estimate": "ESTIMATED",
                "transport_estimate": "ESTIMATED",
            },
        },
        "safety": {
            "risk_score": safety["risk_score"],
            "risk_level": safety["risk_level"],
            "model_used": safety["model_used"],
            "model_version": safety["model_version"],
            "disclaimer": "Decision-support score, not accident probability. Trained on synthetic demonstration data.",
        },
        "ranking_model": ranked["ranking_model"],
        "optimizer": plan["optimizer"],
        "skipped": plan.get("skipped", []),
        "weather": wx,
        "data_status": "DEMO",
    }


def local_safety_context(
    lat: float, lon: float, hour: int, wx: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Local safety context for a point — reuses the existing ML safety model.

    Assembles weather / emergency-proximity / activity features and calls
    ml_predictor.predict_safety. Shared by the day planner and the
    /api/safety/local endpoint so there is exactly one safety pipeline.
    """
    hospital = services_provider.nearest_by_type(lat, lon, "hospital")
    if wx is None:
        wx = weather_provider.current_conditions(lat, lon)
    return ml_predictor.predict_safety(
        {
            "weather": {k: wx[k] for k in ("condition", "precip_mm", "visibility_km", "wind_kph")},
            "context": {"hour": hour, "tourist_area": True, "activity_level": 7.0},
            "location": {
                "incident_density": 0.6,
                "nearest_hospital_km": hospital["distance_km"] if hospital else 8.0,
                "service_density": 8.0,
            },
            "road": {"type": "urban", "surface": "good"},
        }
    )


def _safety_band(safety_context: float) -> str:
    if safety_context >= 78:
        return "LOW"
    if safety_context >= 68:
        return "MODERATE"
    return "HIGH"
