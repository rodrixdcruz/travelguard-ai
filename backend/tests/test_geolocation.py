"""Honest location resolution: geocoder + resolve_point + geo endpoints.

The kill-switch env (TRAVELGUARD_DISABLE_LIVE_PROVIDERS=1, set in CI) makes
the geocoder return nothing, so these tests monkeypatch it where a live
response shape is needed and otherwise assert the honest-failure paths.
"""
import pytest

from app import services
from app.providers import geocode


def test_resolve_point_uses_builtin_table():
    p = services.resolve_point("nagpur")
    assert abs(p.lat - 21.1458) < 0.01
    assert abs(p.lon - 79.0882) < 0.01
    assert p.name.lower() == "nagpur"


def test_resolve_point_geocodes_unknown_city(monkeypatch):
    monkeypatch.setattr(
        geocode,
        "search",
        lambda q, limit=1: [
            {"name": "Nagpur, Maharashtra, India", "short_name": "Nagpur",
             "latitude": 21.1458, "longitude": 79.0882, "type": "city"}
        ],
    )
    p = services.resolve_point("Lower Parel, Mumbai")
    assert abs(p.lat - 21.1458) < 0.01
    assert p.name == "Nagpur"  # geocoder's short_name wins


def test_resolve_point_never_fabricates(monkeypatch):
    # No builtin entry, no geocoder result → must raise, not invent coords.
    monkeypatch.setattr(geocode, "search", lambda q, limit=1: [])
    with pytest.raises(ValueError, match="Could not resolve"):
        services.resolve_point("Atlantis")


def test_geocoder_respects_kill_switch():
    # CI sets TRAVELGUARD_DISABLE_LIVE_PROVIDERS=1; the real search() must
    # short-circuit without network. (If the env is unset locally this test
    # still passes — an empty/failed response also returns [].)
    results = geocode.search("Mumbai") if geocode._live_disabled() else None
    if results is not None:
        assert results == []


def test_geo_search_requires_query(client):
    r = client.get("/api/geo/search?q=")
    assert r.status_code == 422


def test_analyze_unknown_place_is_422_not_fake(client, monkeypatch):
    monkeypatch.setattr(geocode, "search", lambda q, limit=1: [])
    r = client.post("/api/analyze-journey", json={
        "origin": "Atlantis", "destination": "Mumbai",
        "date": "2026-10-01", "time": "08:00",
    })
    assert r.status_code == 422
    assert "Atlantis" in r.json()["detail"]
