"""provider_summary: one honest provenance line per response.

Pure-function tests plus endpoint checks that the field is present and
derived from what was actually served (never a hardcoded LIVE claim).
"""
import pytest

from app.provider_summary import provider_summary


def _item(status: str, source: str) -> dict:
    return {"data_status": status, "data_source": source}


def test_all_live_reports_live_with_source_names():
    s = provider_summary([_item("LIVE", "wikipedia_geosearch"), _item("LIVE", "openstreetmap_overpass")])
    assert s["status"] == "LIVE"
    assert s["sources"] == ["OpenStreetMap", "Wikipedia geosearch"]
    assert s["line"] == "LIVE from OpenStreetMap + Wikipedia geosearch"


def test_live_plus_demo_is_mixed():
    s = provider_summary([_item("LIVE", "wikipedia_geosearch"), _item("DEMO", "demo")])
    assert s["status"] == "MIXED"
    assert "demo dataset" in s["line"]
    assert "Wikipedia geosearch" in s["line"]


def test_all_demo_reports_demo_with_fallback_line():
    s = provider_summary([_item("DEMO", "demo")], fallback_line="TravelGuard demo dataset")
    assert s["status"] == "DEMO"
    assert s["line"] == "TravelGuard demo dataset"


def test_empty_pool_is_demo_not_live():
    s = provider_summary([])
    assert s["status"] == "DEMO"


def test_estimated_only_reports_estimated():
    s = provider_summary([_item("ESTIMATED", "rate_model")])
    assert s["status"] == "ESTIMATED"
    assert "modeled rates" in s["line"]


def test_unknown_sources_pass_through_readable():
    s = provider_summary([_item("LIVE", "some_new_provider")])
    assert s["sources"] == ["some new provider"]
    assert "some new provider" in s["line"]


def test_missing_status_items_are_ignored():
    s = provider_summary([{"name": "no status here"}, _item("LIVE", "wikipedia_geosearch")])
    assert s["status"] == "LIVE"


# ── Endpoint wiring ─────────────────────────────────────────────────────

def test_places_nearby_carries_provider_summary(client):
    r = client.get("/api/places/nearby", params={"latitude": 18.9220, "longitude": 72.8347, "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert set(body["provider_summary"]) == {"status", "sources", "line"}
    # The status must equal the derived status of the returned items.
    assert body["provider_summary"]["status"] == provider_summary(body["places"])["status"]


def test_plan_day_provider_summary_is_hermetic(client):
    # CI runs with live providers disabled → the summary must say DEMO from
    # the demo dataset, never claim LIVE.
    r = client.post("/api/plan/day", json={
        "latitude": 18.9220, "longitude": 72.8347, "location_name": "Gateway of India",
        "duration": "half_day", "budget": "moderate", "interests": ["history"], "travelers": 1,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["provider_summary"]["status"] == "DEMO"
    assert body["data_status"] == "DEMO"
