"""AI Day Planner — orchestrates the full tourist workflow.

discover → ML ranking → feasibility optimizer → travel legs + meal breaks →
costed timeline + local safety context. The LLM narrates the result
downstream; it never invents places, prices or hours here.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any

from .ml import predictor as ml_predictor
from .provider_summary import provider_summary
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
        "data_source": p.get("data_source"),
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
                # Best-effort name lookup with a HARD time budget: the live
                # food provider sweeps up to 5 Overpass mirrors before giving
                # up (~40s when the network is bad), which would stall the
                # whole itinerary. Meal naming is cosmetic — generic label
                # + estimated price is always acceptable.
                nearby_food: list[dict[str, Any]] = []
                # NOTE: shutdown(wait=False) — the context-manager form would
                # BLOCK on exit until the abandoned sweep finishes, defeating
                # the timeout entirely (observed: +40s per meal window).
                pool = ThreadPoolExecutor(max_workers=1)
                fut = pool.submit(
                    food_provider.fetch_nearby,
                    origin[0], origin[1], radius_km=3.0, limit=1,
                )
                try:
                    nearby_food = fut.result(timeout=8.0) or []
                except Exception:  # noqa: BLE001 — timeout or provider error
                    nearby_food = []
                finally:
                    pool.shutdown(wait=False)
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
    days = max(1, min(int(getattr(req, "days", 1) or 1), 7))

    # ── 1. Discover candidates near the tourist ──
    radius = 12.0 if hours >= 5 else 8.0
    candidates = places_provider.fetch_nearby(lat, lon, radius_km=radius, limit=30)
    if req.interests:
        wanted = {i.lower() for i in req.interests}
        matched = [p for p in candidates if wanted & {t.lower() for t in p["tags"]}]
        candidates = matched or candidates  # fall back to all if interest too narrow
    if not candidates:
        raise ValueError(
            "No places available near this location right now — live OpenStreetMap "
            "is unreachable from this network and the offline dataset only covers "
            "demo cities (Mumbai area). Try again shortly, pick a Demo Mode city, "
            "or choose a different location."
        )

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
    # Multi-day: the ranked list is consumed day by day — each day's
    # optimizer starts where the previous day stopped, so no place repeats
    # and the trip extends until places or days run out.
    from .ml.itinerary import build_itinerary

    max_stops = 2 if hours <= 2 else 3 if hours <= 4 else 4 if hours <= 5.5 else 6
    ranked_pool = list(ranked_places)
    day_plans: list[dict[str, Any]] = []
    all_stops: list[dict[str, Any]] = []
    optimizer_name = ""
    for day_no in range(1, days + 1):
        if not ranked_pool:
            break
        plan = build_itinerary(
            ranked_pool,
            available_hours=hours,
            budget=budget_per_person,
            interests=req.interests or [],
            max_stops=max_stops,
        )
        optimizer_name = plan["optimizer"]
        stops = plan["stops"]
        if not stops:
            break
        day_plans.append({"day": day_no, "stops": stops, "skipped": plan.get("skipped", [])})
        all_stops.extend(stops)
        used = {s["place_id"] for s in stops}
        ranked_pool = [p for p in ranked_pool if p["place_id"] not in used]
    plan = {"stops": all_stops, "optimizer": optimizer_name or "greedy", "skipped": [], "days": day_plans}
    chosen_ids = {s["place_id"] for s in plan["stops"]}

    # ── 4. Build the timeline with travel legs, per day ──
    start_time = req.start_time or "09:00"
    try:
        start_dt = datetime.strptime(start_time, "%H:%M")
    except ValueError:
        start_dt = datetime.strptime("09:00", "%H:%M")

    items: list[dict[str, Any]] = []
    day_items: list[list[dict[str, Any]]] = []
    cursor = (lat, lon)
    travel_total = 0.0
    transport_total = 0.0

    for day_idx, day in enumerate(plan["days"]):
        day_start_items: list[dict[str, Any]] = []
        # Each day begins again at the tourist's base (hotel/home).
        day_cursor = (lat, lon)
        for stop in day["stops"]:
            dest = next(
                (p for p in opt_places if p["place_id"] == stop["place_id"]), None
            )
            if dest is None:
                continue
            leg = transport_provider.estimate(day_cursor, (dest["lat"], dest["lon"]), mode="taxi")
            travel_total += leg["duration_min"]
            transport_total += leg["estimated_fare_inr"] * transport_provider.vehicles_for(travelers)
            day_start_items.append(
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
                    "day": day["day"],
                }
            )
            day_cursor = (dest["lat"], dest["lon"])
            visit_min = dest["visit_duration_hours"] * 60.0
            item_reasons = reasons_by_id.get(dest["place_id"], {}).get("reasons", [])
            day_start_items.append(
                {
                    "type": "attraction",
                    "name": dest["name"],
                    "category": dest["category"],
                    "place_id": dest["place_id"],
                    "detail": dest.get("opening_status", "unknown"),
                    "data_source": dest.get("data_source"),
                    "duration_min": round(visit_min),
                    "travel_time_min": round(
                        sum(
                            i["duration_min"]
                            for i in day_start_items
                            if i["type"] == "travel" and i.get("to_place_id") == dest["place_id"]
                        )
                    ),
                    "cost_inr": round(dest["entry_fee"] * travelers),
                    "ticket_required": dest.get("ticket_required"),
                    # The place's real provenance (LIVE from wikipedia/osm or DEMO) —
                    # never hardcode a label; the UI shows it per item.
                    "data_status": dest.get("data_status", "DEMO"),
                    "safety": _safety_band(dest["safety_context"]),
                    "recommendation_score": stop.get("recommendation_score"),
                    "reasons": item_reasons,
                    "latitude": dest["lat"],
                    "longitude": dest["lon"],
                    "day": day["day"],
                }
            )

        # Meal windows reset per day (lunch/dinner possible every day), then
        # the day's clock times are assigned from the day's start.
        day_items_list, _ = _insert_meals(day_start_items, (lat, lon), travelers, start_dt)
        running_day = 0.0
        for item in day_items_list:
            item["time"] = _clock(start_dt, running_day)
            running_day += item.get("duration_min", 0)
        day_items.append(day_items_list)
        items.extend(day_items_list)

    total_min = sum(i.get("duration_min", 0) for i in items)
    food_total = sum(i["cost_inr"] for i in items if i["type"] == "meal")
    tickets_total = round(
        sum(
            (next((p for p in opt_places if p["place_id"] == s["place_id"]), {}) or {}).get("entry_fee", 0) * travelers
            for s in plan["stops"]
        )
    )

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
            "days": days,
            "days_scheduled": len(day_items),
            "items": items,
            "per_day": [
                {
                    "day": idx + 1,
                    "places": sum(1 for i in lst if i["type"] == "attraction"),
                    "time_min": round(sum(i.get("duration_min", 0) for i in lst)),
                    "cost_inr": round(sum(i.get("cost_inr", 0) for i in lst)),
                }
                for idx, lst in enumerate(day_items)
            ],
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
        # Report the ACTUAL mix of what was served, derived from the
        # attractions' real per-item provenance (costs keep their own
        # ESTIMATED labels in line_status).
        "data_status": (
            "LIVE"
            if any(i.get("data_status") == "LIVE" for i in items if i["type"] == "attraction")
            else "DEMO"
        ),
        "provider_summary": provider_summary(
            [i for i in items if i["type"] == "attraction"],
            fallback_line="TravelGuard demo dataset (live discovery unavailable)",
        ),
    }


def local_safety_context(
    lat: float, lon: float, hour: int, wx: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Local safety context for a point — reuses the existing ML safety model.

    Assembles weather / emergency-proximity / activity features and calls
    ml_predictor.predict_safety. Shared by the day planner and the
    /api/safety/local endpoint so there is exactly one safety pipeline.
    """
    # Emergency-proximity lookup with a HARD time budget: the services
    # provider sweeps up to 5 Overpass mirrors (~40s when the network is
    # bad). A hospital name is a nice-to-have — the ML safety model scores
    # fine without it.
    def _nearest() -> Any:
        return services_provider.nearest_by_type(lat, lon, "hospital")

    # shutdown(wait=False) — see the meal-lookup note above.
    pool = ThreadPoolExecutor(max_workers=1)
    fut = pool.submit(_nearest)
    try:
        hospital = fut.result(timeout=8.0)
    except Exception:  # noqa: BLE001 — timeout or provider error
        hospital = None
    finally:
        pool.shutdown(wait=False)
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
