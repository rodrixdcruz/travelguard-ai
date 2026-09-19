"""TravelGuard AI — FastAPI application."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import ai, demo_data, risk_engine, services
from .config import settings
from .database import db_status, init_db
from .discovery_api import router as discovery_router
from .ml import predictor as ml_predictor
from .ml_api import router as ml_router
from .schemas import (
    Alert,
    AnalyzeRequest,
    AnalyzeResponse,
    ChatRequest,
    ChatResponse,
    Coordinate,
    ExplainRequest,
    Journey,
    OverallRisk,
    Recommendation,
    RiskLevel,
    RoutePoint,
    Segment,
    SegmentFactor,
)

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("travelguard")

SECTIONS_PER_ROUTE = 6  # demo segmentation granularity


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(ml_router)
app.include_router(discovery_router)

# CORS: explicit allowlist plus a pattern for Vercel preview deployments
# (https://<project>-<hash>.vercel.app) so preview builds work before the
# production domain exists. Production origin comes from FRONTEND_URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"^https://[a-z0-9-]+\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "database": db_status(),
        "time": datetime.utcnow().isoformat() + "Z",
    }


# ── Journey analysis ────────────────────────────────────────────────────

def _build_segments(
    path: list[Coordinate],
    is_known: bool,
    travel_dt: datetime,
    route_weather: dict,
) -> list[Segment]:
    """Split the route polyline into segments and score each one."""
    n = SECTIONS_PER_ROUTE
    chunks: list[list[Coordinate]] = []
    step = max(len(path) - 1, 1) / n
    for i in range(n):
        start_i = int(round(i * step))
        end_i = min(max(int(round((i + 1) * step)), start_i + 1), len(path) - 1)
        chunk = path[start_i : end_i + 1]
        if chunk and chunk not in chunks:
            chunks.append(chunk)

    segments: list[Segment] = []
    # Known demo polylines are compressed; scale to feel like real road distance.
    road_scale = 1.35 if is_known else 1.0
    for i, chunk in enumerate(chunks):
        pos = i / max(len(chunks) - 1, 1)
        is_ghat = is_known and 0.3 <= pos <= 0.6
        weather = services.segment_weather(route_weather, i, len(chunks), travel_dt, is_ghat)
        road = services.segment_road(i, len(chunks), is_known)
        acc = services.segment_accident_history(i, len(chunks), is_known)
        disr = services.segment_disruptions(i, len(chunks), is_known)

        w_score, w_why = risk_engine.weather_score(weather)
        a_score, a_why = risk_engine.accident_score(acc)
        r_score, r_why = risk_engine.road_score(road)
        d_score, d_why = risk_engine.disruption_score(disr)
        t_score, t_why = risk_engine.time_score(travel_dt)

        factors = [
            SegmentFactor(category="weather", score=w_score, weight=risk_engine.WEIGHTS["weather"], reason=w_why),
            SegmentFactor(category="accident", score=a_score, weight=risk_engine.WEIGHTS["accident"], reason=a_why),
            SegmentFactor(category="road", score=r_score, weight=risk_engine.WEIGHTS["road"], reason=r_why),
            SegmentFactor(category="disruption", score=d_score, weight=risk_engine.WEIGHTS["disruption"], reason=d_why),
            SegmentFactor(category="time", score=t_score, weight=risk_engine.WEIGHTS["time"], reason=t_why),
        ]
        score = risk_engine.aggregate(factors)
        level = risk_engine.level_from_score(score)

        # ── ML layer: contextual risk prediction, blended with the rule engine ──
        ml_pred = ml_predictor.predict_safety(
            {
                "weather": weather,
                "road": road,
                "context": {
                    "hour": travel_dt.hour,
                    "disruptions": disr,
                    "tourist_area": is_known and 0.3 <= pos <= 0.6,
                    "activity_level": 6.0 if is_known else 5.0,
                },
                "location": {
                    "incident_density": acc.get("accidents_per_km_year", 0.4),
                    "nearest_hospital_km": {
                        "ghat": 18.0, "rural": 14.0, "highway": 8.0,
                        "urban": 3.0, "expressway": 10.0,
                    }.get(str(road.get("type")), 8.0),
                    "service_density": 3.0 if road.get("type") in ("ghat", "rural") else 7.0,
                },
            }
        )
        ml_score = float(ml_pred["risk_score"])
        # Hybrid: ML leads (60%), deterministic engine cross-checks (40%).
        score = round(0.6 * ml_score + 0.4 * score, 1)
        level = risk_engine.level_from_score(score)

        segments.append(
            Segment(
                id=i,
                name=f"Segment {i + 1}",
                start=chunk[0],
                end=chunk[-1],
                path=chunk,
                distance_km=round(demo_data.route_length_km(chunk) * road_scale, 1),
                duration_min=services.segment_duration(chunk, road, weather, road_scale),
                score=score,
                level=level,
                factors=factors,
                weather=weather,
                road_condition=road,
                recommended_action=risk_engine.segment_recommended_action(level, factors),
                ml_score=ml_score,
                ml_model_used=str(ml_pred["model_used"]),
            )
        )
    return segments


def _build_alerts(segments: list[Segment]) -> list[Alert]:
    alerts: list[Alert] = []
    for seg in segments:
        if seg.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            top = max(seg.factors, key=lambda f: f.score, default=None)
            alerts.append(
                Alert(
                    id=f"alert-{seg.id}",
                    severity=seg.level,
                    title=f"{seg.level.value} risk on {seg.name}",
                    detail=top.reason if top else "Elevated risk factors on this stretch",
                    segment_id=seg.id,
                )
            )
        for f in seg.factors:
            if f.category == "disruption" and f.score >= 40:
                alerts.append(
                    Alert(
                        id=f"alert-disr-{seg.id}",
                        severity=RiskLevel.MODERATE,
                        title=f"Disruption on {seg.name}",
                        detail=f.reason,
                        segment_id=seg.id,
                    )
                )
    return alerts


def _build_recommendations(
    segments: list[Segment], overall: OverallRisk, eta: datetime, duration_min: float
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    worst = max(segments, key=lambda s: s.score)
    priority = 1
    if worst.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        recs.append(
            Recommendation(
                id=f"rec-{priority}",
                priority=priority,
                text=f"Extra caution through {worst.name} ({worst.level.value}): {worst.recommended_action}",
            )
        )
        priority += 1
    if overall.breakdown.get("weather", 0) >= 40:
        recs.append(
            Recommendation(
                id=f"rec-{priority}", priority=priority,
                text="Expect reduced visibility and braking performance; keep headlights on and slow down in rain.",
            )
        )
        priority += 1
    if any(f.category == "disruption" and f.score >= 40 for s in segments for f in s.factors):
        recs.append(
            Recommendation(
                id=f"rec-{priority}", priority=priority,
                text="Lane closures/diversions are active along the route — add buffer time and follow signage.",
            )
        )
        priority += 1
    if any(s.road_condition.get("type") == "ghat" for s in segments):
        recs.append(
            Recommendation(
                id=f"rec-{priority}", priority=priority,
                text="Use engine braking on ghat stretches and avoid overtaking on curves.",
            )
        )
        priority += 1
    hours, mins = divmod(int(duration_min), 60)
    recs.append(
        Recommendation(
            id=f"rec-{priority}", priority=priority,
            text=f"Planned duration {hours}h {mins:02d}m, ETA {eta.strftime('%H:%M')}. Take a break every 2 hours.",
        )
    )
    return recs


@app.post("/api/analyze-journey", response_model=AnalyzeResponse)
async def analyze_journey(req: AnalyzeRequest) -> AnalyzeResponse:
    if req.origin.strip().lower() == req.destination.strip().lower():
        raise HTTPException(status_code=422, detail="Origin and destination must differ.")

    origin = services.resolve_point(req.origin)
    destination = services.resolve_point(req.destination)
    path, is_known = services.resolve_route(origin, destination)

    try:
        travel_dt = datetime.strptime(f"{req.date} {req.time}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD and time must be HH:MM.")

    route_weather = await services.fetch_route_weather(req.origin, req.destination)
    segments = _build_segments(path, is_known, travel_dt, route_weather)

    total_distance = round(sum(s.distance_km for s in segments), 1)
    total_duration = round(sum(s.duration_min for s in segments), 1)
    eta = travel_dt + timedelta(minutes=total_duration)

    journey = Journey(
        origin=origin,
        destination=destination,
        date=req.date,
        time=req.time,
        distance_km=total_distance,
        duration_min=total_duration,
        eta=eta,
    )

    o_score, _ = risk_engine.overall_from_segments(segments)
    overall = OverallRisk(
        score=o_score,
        level=risk_engine.level_from_score(o_score),
        main_concern=risk_engine.main_concern_from_factors(segments),
        breakdown={
            cat: round(
                sum(f.score * f.weight for s in segments for f in s.factors if f.category == cat)
                / max(len(segments), 1),
                1,
            )
            for cat in ("weather", "accident", "road", "disruption", "time")
        },
    )

    data_mode = "demo" if not (settings.weather_api_key or settings.routing_api_url) else "live+demo"
    intelligence_mode = (
        "random_forest"
        if any(s.ml_model_used == "random_forest" for s in segments)
        else "rule_based_demo"
    )
    return AnalyzeResponse(
        journey=journey,
        overall_risk=overall,
        segments=segments,
        alerts=_build_alerts(segments),
        recommendations=_build_recommendations(segments, overall, eta, total_duration),
        briefing="",
        data_mode=data_mode,
        intelligence_mode=intelligence_mode,
        generated_at=datetime.utcnow(),
    )


# ── AI endpoints ────────────────────────────────────────────────────────

@app.post("/api/ai/explain")
async def ai_explain(req: ExplainRequest) -> dict:
    text, source = await ai.explain(req.context, "Explain the risks on this journey and what I should do.")
    return {"briefing": text, "source": source}


@app.post("/api/ai/chat", response_model=ChatResponse)
async def ai_chat(req: ChatRequest) -> ChatResponse:
    # Discovery-aware context: when the client supplies a day-plan payload the
    # assistant answers from that real data (deterministic fallback path, or
    # LLM with the same grounded context when an API key is configured).
    discovery = req.context.get("discovery") if isinstance(req.context, dict) else None
    if isinstance(discovery, dict):
        from .ai import fallback_discovery_answer

        return ChatResponse(answer=fallback_discovery_answer(req.question, discovery), source="fallback")
    text, source = await ai.explain(req.context, req.question)
    return ChatResponse(answer=text, source=source)
