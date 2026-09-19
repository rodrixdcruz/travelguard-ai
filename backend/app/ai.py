"""AI explanation layer.

If AI_API_KEY is configured, generates explanations via an OpenAI-compatible
chat endpoint. Otherwise uses a deterministic fallback that composes text
from the calculated risk data — never fabricates facts.
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

from .risk_engine import level_from_score

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


def _settings() -> dict[str, Optional[str]]:
    return {
        "key": os.getenv("AI_API_KEY") or None,
        "model": os.getenv("AI_MODEL", "gpt-4o-mini"),
        "base_url": os.getenv("AI_BASE_URL", "https://api.openai.com/v1"),
    }


# ── Deterministic fallback (always available) ───────────────────────────

def fallback_briefing(data: dict[str, Any]) -> str:
    overall = data.get("overall_risk", {})
    segments = data.get("segments", [])
    level = overall.get("level", "UNKNOWN")
    concern = overall.get("main_concern", "no dominant concern identified")

    watch: list[str] = []
    seen: set[str] = set()
    actions: list[str] = []
    for seg in segments:
        for f in seg.get("factors", []):
            if f.get("score", 0) >= 50:
                cat = f.get("category", "").capitalize()
                entry = f"{cat}: {f.get('reason')}"
                if entry not in seen:
                    seen.add(entry)
                    watch.append(entry)
        act = seg.get("recommended_action", "")
        if act and act not in actions:
            actions.append(act)

    worst = max(segments, key=lambda s: s.get("score", 0)) if segments else None
    lines = [
        "JOURNEY SAFETY BRIEFING",
        f"Overall Risk: {level} ({overall.get('score', 0)}/100)",
        f"Main concern: {concern}",
        "",
        "Watch for:",
    ]
    lines += [f"• {w}" for w in watch[:5]] or ["• No elevated factors detected"]
    lines += ["", "Recommended:"]
    lines += [f"• {a}" for a in actions[:4]] or ["• Maintain normal safe driving habits"]
    if worst:
        lines += [
            "",
            f"Careful segment: {worst.get('name')} "
            f"({worst.get('level')} — {worst.get('score')}/100)",
        ]
    return "\n".join(lines)


def fallback_answer(question: str, data: dict[str, Any]) -> str:
    q = question.lower()
    segments = data.get("segments", [])
    overall = data.get("overall_risk", {})
    journey = data.get("journey", {})

    if not segments:
        return "No journey analysis available yet. Analyze a journey first."

    worst = max(segments, key=lambda s: s.get("score", 0))
    best = min(segments, key=lambda s: s.get("score", 0))
    eta = str(journey.get("eta", "unknown"))

    if "biggest" in q or "main" in q or "top" in q:
        top = max(worst.get("factors", []), key=lambda f: f.get("score", 0), default=None)
        if top:
            return (
                f"The biggest risk is on {worst.get('name')} ({worst.get('level')}, "
                f"{worst.get('score')}/100): {top.get('reason')}."
            )
    if "segment" in q or "where" in q or "careful" in q:
        return (
            f"Be most careful on {worst.get('name')} — {worst.get('level')} risk "
            f"({worst.get('score')}/100). {worst.get('recommended_action')}"
        )
    if "what should i do" in q or "recommend" in q or "advice" in q:
        actions = []
        for s in sorted(segments, key=lambda s: s.get("score", 0), reverse=True):
            a = s.get("recommended_action", "")
            if a and a not in actions:
                actions.append(a)
        return "Recommended actions, in order of risk:\n" + "\n".join(f"• {a}" for a in actions[:4])
    if "why" in q or "risky" in q:
        return (
            f"This route is rated {overall.get('level')} ({overall.get('score')}/100). "
            f"{overall.get('main_concern', '')} The calmest stretch is {best.get('name')} "
            f"({best.get('score')}/100)."
        )
    if "eta" in q or "time" in q or "long" in q:
        return (
            f"Estimated duration is {journey.get('duration_min', '?')} minutes with an ETA "
            f"of {eta}, already adjusted for current segment conditions."
        )
    # Generic deterministic answer
    return fallback_briefing(data)


# ── Live LLM (optional) ─────────────────────────────────────────────────

def _build_context_text(data: dict[str, Any]) -> str:
    seg_lines = [
        f"- {s.get('name')}: {s.get('level')} ({s.get('score')}/100); "
        + "; ".join(f"{f.get('category')}: {f.get('reason')}" for f in s.get("factors", []) if f.get("score", 0) >= 40)
        for s in data.get("segments", [])
    ]
    return (
        f"Journey: {data.get('journey', {}).get('origin', {}).get('name')} → "
        f"{data.get('journey', {}).get('destination', {}).get('name')} on "
        f"{data.get('journey', {}).get('date')} at {data.get('journey', {}).get('time')}.\n"
        f"Overall: {data.get('overall_risk', {}).get('level')} "
        f"({data.get('overall_risk', {}).get('score')}/100). "
        f"Main concern: {data.get('overall_risk', {}).get('main_concern')}.\n"
        f"Segments:\n" + "\n".join(seg_lines)
    )


SYSTEM_PROMPT = (
    "You are TravelGuard AI, a road-safety assistant. Answer ONLY from the "
    "structured risk data provided. Never invent weather, roads, or incidents. "
    "Be concise, practical, and safety-focused. Use short bullet points where helpful."
)


async def live_explain(data: dict[str, Any], question: str) -> Optional[str]:
    """Call an OpenAI-compatible API. Returns None on any failure."""
    cfg = _settings()
    if not cfg["key"] or httpx is None:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{cfg['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {cfg['key']}"},
                json={
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": f"Risk data:\n{_build_context_text(data)}\n\nQuestion: {question}",
                        },
                    ],
                    "max_tokens": 500,
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            content = payload["choices"][0]["message"]["content"]
            return str(content).strip()
    except Exception:
        return None  # graceful degradation to fallback


async def explain(data: dict[str, Any], question: str) -> tuple[str, str]:
    """Returns (text, source). source is 'ai' or 'fallback'."""
    live = await live_explain(data, question)
    if live:
        return live, "ai"
    return fallback_answer(question, data), "fallback"


# ── Discovery-aware assistant (tourist context) ─────────────────────────


def _fmt_hours(mins: float) -> str:
    return f"{int(mins // 60)}h {int(mins % 60)}m" if mins >= 60 else f"{int(mins)} min"


def fallback_discovery_answer(question: str, discovery: dict[str, Any]) -> str:
    """Deterministic answers grounded ONLY in the provided discovery payload.

    The payload (built by the caller from /api/plan/day responses) contains the
    itinerary, cost breakdown, safety context and place reasons. Anything not
    present is answered with 'unavailable' — never invented.
    """
    q = question.lower()
    places = discovery.get("places", [])
    itinerary = discovery.get("itinerary") or {}
    costs = discovery.get("cost_breakdown") or {}
    safety = discovery.get("safety") or {}

    if not any([places, itinerary, costs, safety]):
        return (
            "No discovery data available yet. Pick a place and generate a day plan, "
            "then ask about it."
        )

    total_cost = costs.get("total_estimate")

    # Budget questions: “what can I do for ~₹1,000?” (strip commas: 1,000 → 1000)
    m = re.search(r"[₹]?\s*(\d{3,6})", q.replace(",", ""))
    if m and any(w in q for w in ("₹", "rupee", "budget", "cost", "afford", "for")):
        amount = int(m.group(1))
        affordable = [p for p in places if (p.get("entry_fee") or 0) * discovery.get("travelers", 1) <= amount]
        if not affordable:
            return (
                f"Nothing in the current demo dataset fits ₹{amount:,} — the cheapest "
                f"option is ₹{min((p.get('entry_fee') or 0) for p in places):,} per person "
                "(plus transport, which is an estimate)."
            )
        names = ", ".join(p["name"] for p in affordable[:5])
        return (
            f"Within ₹{amount:,} per person, the current dataset suggests: {names}. "
            "Ticket figures are DEMO data; transport and food are ESTIMATED."
        )

    # Itinerary / plan questions
    if any(w in q for w in ("plan", "itinerary", "day", "schedule", "first", "next")):
        items = itinerary.get("items", [])
        if not items:
            return "No itinerary generated yet. Use Plan My Day, then ask about the schedule."
        attractions = [i for i in items if i.get("type") == "attraction"]
        lines = [
            f"Your plan: {itinerary.get('start_time', '?')}–{itinerary.get('end_time', '?')} "
            f"with {len(attractions)} place(s), estimated total ₹{total_cost:,} "
            f"({costs.get('travelers', 1)} travelers) — tickets DEMO, food and transport ESTIMATED."
        ]
        for item in attractions[:4]:
            lines.append(f"• {item.get('time')} {item.get('name')} ({_fmt_hours(item.get('duration_min', 0))})")
        if len(attractions) > 4:
            lines.append(f"• … and {len(attractions) - 4} more stop(s)")
        return "\n".join(lines)

    # “What is the first stop?” / “Where do we go?”
    if any(w in q for w in ("where", "which place", "visit", "see", "go")):
        items = itinerary.get("items", [])
        attractions = [i for i in items if i.get("type") == "attraction"]
        if attractions:
            names = " → ".join(i["name"] for i in attractions)
            return f"Your day covers: {names}."
        if places:
            names = ", ".join(p["name"] for p in places[:5])
            return f"Top-ranked nearby: {names}."

    # Safety questions
    if any(w in q for w in ("safe", "safety", "risk", "danger")):
        if not safety:
            return "Safety context unavailable in current data — generate a plan or open Local Safety."
        return (
            f"Contextual travel risk is {safety.get('risk_level', 'UNKNOWN')} "
            f"({safety.get('risk_score', '?')}/100) from the {safety.get('model_used', 'demo')} model. "
            "This is a decision-support score, not an accident probability."
        )

    # Why-this-place / recommendation questions
    if any(w in q for w in ("why", "recommend", "suggest", "best")):
        first = places[0] if places else None
        if first and first.get("reasons"):
            reasons = "; ".join(first["reasons"][:3])
            return (
                f"{first['name']} ranks first ({first.get('recommendation_score', '?')}/100): {reasons}."
            )
        if first:
            return f"Top-ranked nearby: {first['name']} ({first.get('recommendation_score', '?')}/100)."
        return "No ranked places available in the current context."

    # Food
    if any(w in q for w in ("eat", "food", "lunch", "dinner", "hungry")):
        meals = [i for i in itinerary.get("items", []) if i.get("type") == "meal"]
        if meals:
            return (
                f"Your plan includes {meals[0].get('name')} at {meals[0].get('time')} "
                "— cost ESTIMATED from price class."
            )
        return "No food stops in the current plan — check Find Food for nearby options (DEMO data)."

    # Fallback: compact summary of what we actually have
    parts: list[str] = []
    if places:
        parts.append(f"{len(places)} ranked place(s) nearby")
    if itinerary.get("items"):
        attractions = [i for i in itinerary["items"] if i.get("type") == "attraction"]
        parts.append(f"an itinerary with {len(attractions)} stop(s)")
    if total_cost is not None:
        parts.append(f"an estimated total of ₹{total_cost:,}")
    if safety:
        parts.append(f"{safety.get('risk_level', '?')} contextual risk")
    return (
        "I can answer from your current TravelGuard data: "
        + ", ".join(parts)
        + ". Ask about your plan, budget, food, or safety."
    )
