"""Pydantic schemas for TravelGuard AI (API + ML layers)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnalyzeRequest(BaseModel):
    origin: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=200)
    date: str = Field(min_length=8, max_length=10)      # YYYY-MM-DD
    time: str = Field(min_length=4, max_length=5)       # HH:MM (24h)


class Coordinate(BaseModel):
    lat: float
    lon: float


class RoutePoint(Coordinate):
    name: str


class SegmentFactor(BaseModel):
    """One scored factor for a segment."""
    category: str            # weather | accident | road | disruption | time
    score: float             # 0..100 contribution
    weight: float            # weight used in the segment score
    reason: str


class Segment(BaseModel):
    id: int
    name: str
    start: Coordinate
    end: Coordinate
    path: list[Coordinate]
    distance_km: float
    duration_min: float
    score: float                       # 0..100
    level: RiskLevel
    factors: list[SegmentFactor]
    weather: dict[str, Any] = Field(default_factory=dict)
    road_condition: dict[str, Any] = Field(default_factory=dict)
    recommended_action: str
    ml_score: Optional[float] = None            # raw ML prediction (pre-blend)
    ml_model_used: Optional[str] = None         # random_forest | rule_based_demo


class Alert(BaseModel):
    id: str
    severity: RiskLevel
    title: str
    detail: str
    segment_id: Optional[int] = None


class Recommendation(BaseModel):
    id: str
    priority: int                 # 1 = do this first
    text: str


class OverallRisk(BaseModel):
    score: float
    level: RiskLevel
    main_concern: str
    breakdown: dict[str, float]   # category -> weighted contribution


class Journey(BaseModel):
    origin: RoutePoint
    destination: RoutePoint
    date: str
    time: str
    distance_km: float
    duration_min: float
    eta: datetime


class AnalyzeResponse(BaseModel):
    journey: Journey
    overall_risk: OverallRisk
    segments: list[Segment]
    alerts: list[Alert]
    recommendations: list[Recommendation]
    briefing: str
    data_mode: str = "demo"                  # demo | live
    intelligence_mode: str = "rule_based_demo"  # random_forest | rule_based_demo
    generated_at: datetime


class ExplainRequest(BaseModel):
    context: dict[str, Any]
    question: str


class ChatRequest(BaseModel):
    context: dict[str, Any]
    question: str


class ChatResponse(BaseModel):
    answer: str
    source: str                   # ai | fallback


# ── ML endpoints ────────────────────────────────────────────────────────

class MlSafetyRequest(BaseModel):
    """Free-form structured context; the feature pipeline applies defaults."""
    weather: dict[str, Any] = Field(default_factory=dict)
    location: dict[str, Any] = Field(default_factory=dict)
    road: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class MlRecommendRequest(BaseModel):
    user_preferences: dict[str, Any] = Field(default_factory=dict)
    places: list[dict[str, Any]] = Field(default_factory=list)


class MlItineraryRequest(BaseModel):
    user_preferences: dict[str, Any] = Field(default_factory=dict)
    places: list[dict[str, Any]] = Field(default_factory=list)


class DayPlanRequest(BaseModel):
    """AI day planner input — tourist location + preferences."""
    latitude: float
    longitude: float
    location_name: Optional[str] = None
    duration: str = "half_day"          # 2h | 4h | half_day | full_day | custom hours e.g. "5"
    budget: str | float = "moderate"    # budget | moderate | premium | custom INR per person
    interests: list[str] = Field(default_factory=list)
    travelers: str | int = "2"          # 1 | 2 | family | group
    start_time: Optional[str] = None    # HH:MM, default 09:00
