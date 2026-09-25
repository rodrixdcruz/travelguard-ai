"""Geoapify Places tier — keyed live provider + chain wiring.

Pure unit tests: the network layer (_search) is stubbed, so zero real HTTP
happens. Covers key handling, the CI kill switch, normalization into the
demo-dataset dict shapes, honest empty results, and the food/services/places
fallback chains (Geoapify → key-less OSM → labeled demo).
"""
import pytest

from app.providers import food as food_provider
from app.providers import geoapify_places
from app.providers import places as places_provider
from app.providers import places_wiki
from app.providers import services as services_provider
from app.providers.geoapify_places import GeoapifyUnavailable


@pytest.fixture(autouse=True)
def _clear_kill_switch(monkeypatch):
    monkeypatch.delenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", raising=False)


@pytest.fixture(autouse=True)
def _bypass_cache(monkeypatch):
    """The provider caches per-cell results; tests need isolated calls."""
    monkeypatch.setattr(
        geoapify_places, "cached", lambda _key, _ttl, fn: fn()
    )


# ── _search behaviour ────────────────────────────────────────────────────


def test_search_without_key_raises(monkeypatch):
    monkeypatch.delenv("GEOAPIFY_API_KEY", raising=False)
    with pytest.raises(GeoapifyUnavailable):
        geoapify_places._search("catering", 21.14, 79.08, 5000, 10)


def test_search_kill_switch_raises(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "1")
    with pytest.raises(GeoapifyUnavailable):
        geoapify_places._search("catering", 21.14, 79.08, 5000, 10)


def test_search_api_error_raises(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")

    class _Resp:
        def raise_for_status(self):
            raise RuntimeError("502 bad gateway")

        def json(self):  # pragma: no cover - raise happens first
            return {}

    monkeypatch.setattr(
        geoapify_places.httpx, "get", lambda *a, **k: _Resp()
    )
    with pytest.raises(GeoapifyUnavailable):
        geoapify_places._search("catering", 21.14, 79.08, 5000, 10)


# ── Feature normalization ────────────────────────────────────────────────


def _feature(name, lat, lon, cats, place_id="pid-1", extra=None):
    props = {"name": name, "categories": cats, "place_id": place_id}
    props.update(extra or {})
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


def test_fetch_food_shape(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    features = [
        _feature("Haldiram", 21.14, 79.08, ["catering", "catering.restaurant.indian"]),
        _feature("Cafe Mocha", 21.15, 79.09, ["catering", "catering.cafe"]),
    ]
    monkeypatch.setattr(
        geoapify_places, "_search", lambda *a, **k: features
    )
    out = geoapify_places.fetch_food(21.1458, 79.0882, radius_m=8000, limit=10)
    assert [o["name"] for o in out] == ["Haldiram", "Cafe Mocha"]
    assert all(o["data_status"] == "LIVE" for o in out)
    assert all(o["data_source"] == "geoapify_places" for o in out)
    assert out[0]["cuisine"] == "Indian"
    assert out[1]["cuisine"] == "Cafe"
    # honesty: fields the API does not carry stay None/defaults
    assert out[0]["price_range"] is None
    assert out[0]["rating"] is None


def test_fetch_food_honest_empty(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(geoapify_places, "_search", lambda *a, **k: [])
    assert geoapify_places.fetch_food(21.14, 79.08, 5000, 10) == []


def test_fetch_services_kind_mapping(monkeypatch):
    """Services are fetched per kind group; every kind must survive the merge."""
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    by_group = {
        "healthcare.hospital": [
            _feature("Indira Gandhi Govt Dental College", 21.14, 79.08,
                     ["healthcare", "healthcare.hospital"], place_id="h-1"),
        ],
        "healthcare.pharmacy": [
            _feature("Medical Square Pharmacy", 21.15, 79.08, ["healthcare.pharmacy"], place_id="p-1"),
        ],
        "service.financial": [
            _feature("SBI ATM Sitabuldi", 21.16, 79.08,
                     ["service", "service.financial", "service.financial.atm"], place_id="f-1"),
        ],
        "commercial.supermarket": [
            _feature("Dmart Sitabuldi", 21.17, 79.09, ["commercial", "commercial.supermarket"], place_id="s-1"),
        ],
        "public_transport": [
            _feature("Sitabuldi Metro Station", 21.15, 79.09,
                     ["public_transport", "public_transport.subway"], place_id="t-1"),
            _feature("Nagpur Railway Station", 21.15, 79.10,
                     ["public_transport", "public_transport.train"], place_id="t-2"),
            _feature("Gandhi Bus Stop", 21.15, 79.11,
                     ["public_transport", "public_transport.bus"], place_id="t-3"),
        ],
    }

    def _fake_search(categories, *args):
        return by_group.get(categories, [])

    monkeypatch.setattr(geoapify_places, "_search", _fake_search)
    out = geoapify_places.fetch_services(21.1458, 79.0882, radius_m=8000, limit=25)
    kinds = {o["name"]: o["service_type"] for o in out}
    assert kinds["Indira Gandhi Govt Dental College"] == "hospital"
    assert kinds["Medical Square Pharmacy"] == "pharmacy"
    assert kinds["SBI ATM Sitabuldi"] == "atm"
    assert kinds["Sitabuldi Metro Station"] == "metro_station"
    assert kinds["Nagpur Railway Station"] == "railway_station"
    assert kinds["Gandhi Bus Stop"] == "bus_stand"
    assert all(o["phone"] is None for o in out)  # never fabricated
    assert len(out) == 7  # every group contributed, none lost in the merge


def test_fetch_services_dense_kind_does_not_crowd_out_others(monkeypatch):
    """Regression: a hospital district must not fill the whole result window.

    Live in Nagpur: one combined query returned 19/19 hospitals, hiding
    pharmacies/ATMs/transit entirely. The per-group fan-out guarantees every
    kind gets its own window regardless of how dense one kind is.
    """
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    hospitals = [
        _feature(f"Hospital #{i}", 21.1458 + i * 0.001, 79.0882,
                 ["healthcare", "healthcare.hospital"], place_id=f"h-{i}")
        for i in range(20)
    ]

    def _fake_search(categories, _lat, _lon, _radius, lim):
        if categories == "healthcare.hospital":
            return hospitals[:lim]
        if categories == "healthcare.pharmacy":
            return [_feature("Lone Pharmacy", 21.1500, 79.0890, ["healthcare.pharmacy"], place_id="p-1")]
        return []

    monkeypatch.setattr(geoapify_places, "_search", _fake_search)
    out = geoapify_places.fetch_services(21.1458, 79.0882, radius_m=8000, limit=5)
    types = {o["service_type"] for o in out}
    names = [o["name"] for o in out]
    assert types == {"hospital", "pharmacy"}
    assert "Lone Pharmacy" in names


def test_fetch_places_leisure_categories(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    features = [
        _feature("Ambazari Lake", 21.14, 79.08, ["natural", "natural.water"]),
        _feature("Maharajbagh Zoo", 21.15, 79.09, ["leisure", "entertainment", "entertainment.zoo"]),
        _feature("Futala Lake", 21.16, 79.09, ["natural", "natural.water"]),
    ]
    monkeypatch.setattr(
        geoapify_places, "_search", lambda *a, **k: features
    )
    out = geoapify_places.fetch_places(21.1458, 79.0882, radius_m=10000, limit=10)
    cats = {o["name"]: o["category"] for o in out}
    assert cats["Ambazari Lake"] == "lake"
    assert cats["Maharajbagh Zoo"] == "zoo"
    assert all(o["data_status"] == "LIVE" for o in out)


# ── Fallback chains ──────────────────────────────────────────────────────


def test_food_chain_geoapify_wins(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(
        food_provider,
        "geoapify_fetch_food",
        lambda *a, **k: [{"id": "g-1", "name": "Geo Bistro", "cuisine": "Indian", "vegetarian": False,
                          "non_vegetarian": True, "price_range": None, "rating": None,
                          "latitude": 21.14, "longitude": 79.08, "address": "",
                          "opening_status": "unknown", "data_source": "geoapify_places",
                          "data_status": "LIVE"}],
    )
    called = {"osm": False}

    def _boom(*a, **k):
        called["osm"] = True
        raise food_provider.OsmUnavailable("should not be called")

    monkeypatch.setattr(food_provider, "osm_fetch_nearby", _boom)
    out = food_provider.fetch_nearby(21.1458, 79.0882, radius_km=10, limit=5)
    assert out[0]["name"] == "Geo Bistro"
    assert called["osm"] is False


def test_food_chain_overpass_fallback(monkeypatch):
    monkeypatch.delenv("GEOAPIFY_API_KEY", raising=False)

    def _unavailable(*a, **k):
        raise GeoapifyUnavailable("no key")

    monkeypatch.setattr(food_provider, "geoapify_fetch_food", _unavailable)
    monkeypatch.setattr(
        food_provider,
        "osm_fetch_nearby",
        lambda *a, **k: [{"id": "o-1", "name": "OSM Diner", "cuisine": "restaurant", "vegetarian": False,
                          "non_vegetarian": True, "price_range": None, "rating": None,
                          "latitude": 21.14, "longitude": 79.08, "address": "",
                          "opening_status": "unknown", "data_source": "openstreetmap_overpass",
                          "data_status": "LIVE"}],
    )
    out = food_provider.fetch_nearby(21.1458, 79.0882, radius_km=10, limit=5)
    assert out[0]["name"] == "OSM Diner"
    assert out[0]["data_status"] == "LIVE"


def test_services_chain_geoapify_wins(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(
        services_provider,
        "geoapify_fetch_services",
        lambda *a, **k: [{"id": "g-2", "name": "Geo Hospital", "service_type": "hospital",
                          "latitude": 21.14, "longitude": 79.08, "address": "", "phone": None,
                          "opening_status": "unknown", "data_source": "geoapify_places",
                          "data_status": "LIVE"}],
    )
    out = services_provider.fetch_nearby(21.1458, 79.0882, radius_km=10, limit=5)
    assert out[0]["name"] == "Geo Hospital"
    assert out[0]["service_type"] == "hospital"


def test_places_chain_fuses_geoapify_and_wiki(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(
        places_provider,
        "geoapify_fetch_places",
        lambda *a, **k: [{"id": "g-3", "name": "Ambazari Lake", "category": "lake",
                          "description": "", "latitude": 21.14, "longitude": 79.08,
                          "address": "", "opening_hours": "Unknown", "rating": None,
                          "tags": [], "data_source": "geoapify_places", "data_status": "LIVE"}],
    )
    monkeypatch.setattr(
        places_provider,
        "wiki_fetch_notable",
        lambda *a, **k: [{"id": "w-1", "name": "Sitabuldi Fort", "category": "historical",
                          "description": "", "latitude": 21.16, "longitude": 79.09,
                          "address": "", "opening_hours": "Unknown", "rating": None,
                          "tags": [], "data_source": "wikipedia_geosearch", "data_status": "LIVE"}],
    )
    out = places_provider.fetch_nearby(21.1458, 79.0882, radius_km=15, limit=10)
    names = [p["name"] for p in out]
    assert "Ambazari Lake" in names and "Sitabuldi Fort" in names
    # nearest-first ordering
    dists = [p["distance_km"] for p in out]
    assert dists == sorted(dists)


def test_places_chain_dedupes_nearby_duplicates(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(
        places_provider,
        "geoapify_fetch_places",
        lambda *a, **k: [{"id": "g-3", "name": "Ambazari Lake", "category": "lake",
                          "description": "", "latitude": 21.14, "longitude": 79.08,
                          "address": "", "opening_hours": "Unknown", "rating": None,
                          "tags": [], "data_source": "geoapify_places", "data_status": "LIVE"}],
    )
    monkeypatch.setattr(
        places_provider,
        "wiki_fetch_notable",
        lambda *a, **k: [{"id": "w-1", "name": "Ambazari Lake", "category": "lake",
                          "description": "", "latitude": 21.1400001, "longitude": 79.08,
                          "address": "", "opening_hours": "Unknown", "rating": None,
                          "tags": [], "data_source": "wikipedia_geosearch", "data_status": "LIVE"}],
    )
    out = places_provider.fetch_nearby(21.1458, 79.0882, radius_km=15, limit=10)
    names = [p["name"] for p in out]
    assert names.count("Ambazari Lake") == 1


def test_places_chain_dedupes_same_name_landmark_mapped_twice(monkeypatch):
    """Regression: Sitabuldi Fort exists as point + area on OSM (~80 m apart),
    so the 50 m coordinate rule alone left both copies in discovery."""
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(
        places_provider,
        "geoapify_fetch_places",
        lambda *a, **k: [{"id": "g-3", "name": "Sitabuldi Fort", "category": "historical",
                          "description": "", "latitude": 21.1562, "longitude": 79.0882,
                          "address": "", "opening_hours": "Unknown", "rating": None,
                          "tags": [], "data_source": "geoapify_places", "data_status": "LIVE"}],
    )
    monkeypatch.setattr(
        places_provider,
        "wiki_fetch_notable",
        lambda *a, **k: [{"id": "w-1", "name": "Sitabuldi Fort", "category": "historical",
                          "description": "", "latitude": 21.1570, "longitude": 79.0889,
                          "address": "", "opening_hours": "Unknown", "rating": None,
                          "tags": [], "data_source": "wikipedia_geosearch", "data_status": "LIVE"}],
    )
    out = places_provider.fetch_nearby(21.1458, 79.0882, radius_km=15, limit=10)
    names = [p["name"] for p in out]
    assert names.count("Sitabuldi Fort") == 1


# ── Wiki station exclusion ───────────────────────────────────────────────


def test_wiki_excludes_stations(monkeypatch):
    pages = [
        {"pageid": 1, "title": "Sitabuldi Fort", "lat": 21.15, "lon": 79.09},
        {"pageid": 2, "title": "Nagpur Metro Station", "lat": 21.14, "lon": 79.08},
        {"pageid": 3, "title": "Ajni Railway Station", "lat": 21.13, "lon": 79.08},
    ]

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"query": {"geosearch": pages}}

    monkeypatch.setattr(places_wiki.httpx, "get", lambda *a, **k: _Resp())
    out = places_wiki.fetch_notable(21.1458, 79.0882, radius_m=10000, limit=10)
    names = [p["name"] for p in out]
    assert "Sitabuldi Fort" in names
    assert "Nagpur Metro Station" not in names
    assert "Ajni Railway Station" not in names
