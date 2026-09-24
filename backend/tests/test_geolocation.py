"""Honest location resolution: geocoder + resolve_point + geo endpoints.

The kill-switch env (TRAVELGUARD_DISABLE_LIVE_PROVIDERS=1, set in CI) makes
the geocoder return nothing, so these tests monkeypatch it where a live
response shape is needed and otherwise assert the honest-failure paths.

The geocoder is a two-tier chain: Geoapify when GEOAPIFY_API_KEY is set
(works from cloud egress where OSM throttles), OSM Nominatim key-less
otherwise. Fallback to Nominatim happens ONLY when the keyed provider
fails — a legitimate "no matches" from Geoapify is reported as such.
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
        lambda q, limit=1: (
            [
                {"name": "Nagpur, Maharashtra, India", "short_name": "Nagpur",
                 "latitude": 21.1458, "longitude": 79.0882, "type": "city"}
            ],
            "osm_nominatim",
        ),
    )
    p = services.resolve_point("Lower Parel, Mumbai")
    assert abs(p.lat - 21.1458) < 0.01
    assert p.name == "Nagpur"  # geocoder's short_name wins


def test_resolve_point_never_fabricates(monkeypatch):
    # No builtin entry, no geocoder result → must raise, not invent coords.
    monkeypatch.setattr(geocode, "search", lambda q, limit=1: ([], None))
    with pytest.raises(ValueError, match="Could not resolve"):
        services.resolve_point("Atlantis")


def test_geocoder_respects_kill_switch():
    # CI sets TRAVELGUARD_DISABLE_LIVE_PROVIDERS=1; the real search() must
    # short-circuit without network. (If the env is unset locally this check
    # is skipped — a live network call has no place in unit tests.)
    if geocode._live_disabled():
        assert geocode.search("Mumbai") == ([], None)


# ── Two-tier chain: Geoapify (keyed) → Nominatim (key-less) ─────────────


def _enable_live(monkeypatch):
    monkeypatch.delenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", raising=False)


def test_active_provider_prefers_keyed(monkeypatch):
    _enable_live(monkeypatch)
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    assert geocode.active_provider() == "geoapify"


def test_active_provider_keyless(monkeypatch):
    _enable_live(monkeypatch)
    monkeypatch.delenv("GEOAPIFY_API_KEY", raising=False)
    assert geocode.active_provider() == "osm_nominatim"


def test_active_provider_none_when_disabled(monkeypatch):
    monkeypatch.setenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "1")
    assert geocode.active_provider() is None


def test_search_uses_geoapify_when_key_set(monkeypatch):
    _enable_live(monkeypatch)
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    hit = [{"name": "Pune, Maharashtra, India", "short_name": "Pune",
            "latitude": 18.5204, "longitude": 73.8567, "type": "city"}]
    monkeypatch.setattr(geocode, "_search_geoapify", lambda q, limit, key: hit)

    def _no_nominatim(*a, **k):
        raise AssertionError("Nominatim must not be called when Geoapify answers")

    monkeypatch.setattr(geocode, "_search_nominatim", _no_nominatim)
    results, source = geocode.search("Pune", limit=3)
    assert source == "geoapify"
    assert results[0]["short_name"] == "Pune"


def test_search_falls_back_to_nominatim_on_geoapify_failure(monkeypatch):
    _enable_live(monkeypatch)
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(geocode, "_search_geoapify", lambda q, limit, key: None)  # provider failure
    monkeypatch.setattr(
        geocode,
        "_search_nominatim",
        lambda q, limit: [{"name": "Pune, India", "short_name": "Pune",
                           "latitude": 18.5204, "longitude": 73.8567, "type": "city"}],
    )
    results, source = geocode.search("Pune")
    assert source == "osm_nominatim"
    assert len(results) == 1


def test_search_no_fallback_on_legitimate_empty(monkeypatch):
    _enable_live(monkeypatch)
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(geocode, "_search_geoapify", lambda q, limit, key: [])  # honest "no matches"

    def _no_nominatim(*a, **k):
        raise AssertionError("A real 'no matches' must not be masked by the fallback")

    monkeypatch.setattr(geocode, "_search_nominatim", _no_nominatim)
    results, source = geocode.search("Nowhere Real Place")
    assert results == []
    assert source == "geoapify"


def test_search_no_key_goes_straight_to_nominatim(monkeypatch):
    _enable_live(monkeypatch)
    monkeypatch.delenv("GEOAPIFY_API_KEY", raising=False)
    monkeypatch.setattr(
        geocode,
        "_search_nominatim",
        lambda q, limit: [{"name": "Indore, India", "short_name": "Indore",
                           "latitude": 22.7196, "longitude": 75.8577, "type": "city"}],
    )

    def _no_geoapify(*a, **k):
        raise AssertionError("Geoapify must not be called without a key")

    monkeypatch.setattr(geocode, "_search_geoapify", _no_geoapify)
    results, source = geocode.search("Indore")
    assert source == "osm_nominatim"
    assert results[0]["short_name"] == "Indore"


def test_search_kill_switch_short_circuits_chain(monkeypatch):
    monkeypatch.setenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "1")
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    results, source = geocode.search("Mumbai")
    assert (results, source) == ([], None)


def test_reverse_chain_falls_back_on_geoapify_failure(monkeypatch):
    _enable_live(monkeypatch)
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(geocode, "_reverse_geoapify", lambda lat, lon, key: None)  # failure
    monkeypatch.setattr(geocode, "_reverse_nominatim", lambda lat, lon: "Nagpur")
    name, source = geocode.reverse(21.1458, 79.0882)
    assert (name, source) == ("Nagpur", "osm_nominatim")


def test_reverse_no_key_uses_nominatim(monkeypatch):
    _enable_live(monkeypatch)
    monkeypatch.delenv("GEOAPIFY_API_KEY", raising=False)
    monkeypatch.setattr(geocode, "_reverse_nominatim", lambda lat, lon: "Kochi")
    name, source = geocode.reverse(9.9312, 76.2673)
    assert (name, source) == ("Kochi", "osm_nominatim")


# ── Endpoint-level honesty ───────────────────────────────────────────────


def test_geo_search_requires_query(client):
    r = client.get("/api/geo/search?q=")
    assert r.status_code == 422


def test_analyze_unknown_place_is_422_not_fake(client, monkeypatch):
    monkeypatch.setattr(geocode, "search", lambda q, limit=1: ([], None))
    r = client.post("/api/analyze-journey", json={
        "origin": "Atlantis", "destination": "Mumbai",
        "date": "2026-10-01", "time": "08:00",
    })
    assert r.status_code == 422
    assert "Atlantis" in r.json()["detail"]


def test_geo_search_labels_active_geocoder(client, monkeypatch):
    _enable_live(monkeypatch)
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(
        geocode,
        "_search_geoapify",
        lambda q, limit, key: [{"name": "Pune, India", "short_name": "Pune",
                                "latitude": 18.5204, "longitude": 73.8567, "type": "city"}],
    )
    r = client.get("/api/geo/search?q=Pune")
    body = r.json()
    assert r.status_code == 200
    assert body["data_source"] == "Geoapify"
    assert body["data_status"] == "LIVE"
    assert "Geoapify" in body["provider_summary"]["line"]


def test_geo_search_unavailable_line_when_no_geocoder_answers(client, monkeypatch):
    monkeypatch.setenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "1")
    r = client.get("/api/geo/search?q=Mumbai")
    body = r.json()
    assert r.status_code == 200
    assert body["count"] == 0
    assert body["data_status"] == "UNAVAILABLE"
    assert body["provider_summary"]["line"] == "Geocoder unavailable — no results served"
