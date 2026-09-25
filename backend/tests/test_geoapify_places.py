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
        _feature("Cafe Mocha", 21.15, 79.09, ["catering", "catering.cafe"],
                 extra={"raw": {"diet:vegetarian": "yes", "cuisine": "coffee_shop"}}),
        _feature("Vegan Corner", 21.16, 79.10, ["catering", "catering.restaurant"],
                 extra={"raw": {"diet:vegan": "only"}}),
    ]
    monkeypatch.setattr(
        geoapify_places, "_search", lambda *a, **k: features
    )
    out = geoapify_places.fetch_food(21.1458, 79.0882, radius_m=8000, limit=10)
    assert [o["name"] for o in out] == ["Haldiram", "Cafe Mocha", "Vegan Corner"]
    assert all(o["data_status"] == "LIVE" for o in out)
    assert all(o["data_source"] == "geoapify_places" for o in out)
    assert out[0]["cuisine"] == "Indian"
    assert out[1]["cuisine"] == "Cafe"
    # diet tags flow through so the VEG filter works on live data
    assert out[0]["vegetarian"] is False
    assert out[1]["vegetarian"] is True
    assert out[2]["vegetarian"] is True  # vegan=only implies vegetarian
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
        "service.police": [
            _feature("Sitabuldi Police Station", 21.16, 79.09,
                     ["service", "service.police"], place_id="pol-1"),
        ],
        "tourism.information": [
            _feature("Nagpur Tourist Info", 21.15, 79.08,
                     ["tourism", "tourism.information.office"], place_id="ti-1"),
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
    assert kinds["Sitabuldi Police Station"] == "police"
    assert kinds["Nagpur Tourist Info"] == "tourist_help"
    assert all(o["phone"] is None for o in out)  # never fabricated
    assert len(out) == 9  # every group contributed, none lost in the merge


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
        return []  # police / tourist info / financial / supermarket groups: empty here

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


# ── Transport discovery: paginated per-category fan-out ────────────────


def _tfeature(name, lat, lon, cats, raw=None, place_id=None):
    """A Geoapify Places feature shaped like real transit rows."""
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "name": name,
            "categories": cats,
            "place_id": place_id or f"pid-{abs(hash(name))}",
            "raw": raw or {},
        },
    }


def _transport_stub(pages_by_group):
    """_search stub returning one page per call, in order, per group."""
    calls = {g: 0 for g in pages_by_group}

    def _fake(categories, *args, **kwargs):
        if categories not in calls:
            return []
        page = calls[categories]
        calls[categories] += 1
        return pages_by_group[categories][page] if page < len(pages_by_group[categories]) else []

    return _fake


def _bus(name, i, place_id=None):
    return _tfeature(name, 21.1458 + i * 0.002, 79.0882,
                     ["public_transport", "public_transport.bus", "public_transport.platform"],
                     {"public_transport": "platform", "highway": "bus_stop"},
                     place_id=place_id or f"pid-{name}")


def test_transport_all_bus_stops_returned_up_to_cap(monkeypatch):
    """A: several bus stops in the area all come back, not a nearest sample."""
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(geoapify_places, "TRANSPORT_PAGE_SIZE", 3)  # force real pagination
    buses = [_bus(f"Bus Stop {i}", i) for i in range(5)]
    monkeypatch.setattr(geoapify_places, "_search", _transport_stub({
        "public_transport.bus": [buses[:3], buses[3:]],  # two pages
    }))
    out = geoapify_places.fetch_transport(21.1458, 79.0882, radius_m=5000)
    names = [s["name"] for s in out["stops"]]
    for i in range(5):
        assert f"Bus Stop {i}" in names
    assert out["failed_groups"] == []


def test_transport_metro_not_crowded_out_by_bus(monkeypatch):
    """B: a dense bus cluster cannot push metro stations out of the window."""
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    dense_bus = [_bus(f"Bus Stop {i}", i) for i in range(12)]
    metro = [
        _tfeature("Zero Mile metro", 21.1470, 79.0890,
                  ["public_transport", "public_transport.subway"],
                  {"public_transport": "station", "station": "subway"}),
        _tfeature("Kasturchand Park metro", 21.1490, 79.0900,
                  ["public_transport", "public_transport.subway"],
                  {"public_transport": "station", "station": "subway"}),
    ]
    monkeypatch.setattr(geoapify_places, "_search", _transport_stub({
        "public_transport.bus": [dense_bus],
        "public_transport.subway": [metro],
    }))
    out = geoapify_places.fetch_transport(21.1458, 79.0882, radius_m=5000)
    types = [s["transport_type"] for s in out["stops"]]
    assert types.count("bus_stop") == 12
    assert types.count("metro_station") == 2  # independent window, not shared


def test_transport_subtypes_from_provider_metadata(monkeypatch):
    """C: entrances, railway stations and bus terminals get precise subtypes."""
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    groups = {
        "public_transport.subway.entrance": [[
            _tfeature("Metro Gate 1", 21.1471, 79.0891,
                      ["public_transport", "public_transport.subway.entrance"],
                      {"public_transport": "entrance"}),
        ]],
        "public_transport.train": [[
            _tfeature("Nagpur Junction", 21.1530, 79.0930,
                      ["public_transport", "public_transport.train"],
                      {"public_transport": "station", "railway": "station"}),
        ]],
        "public_transport.bus": [[
            _tfeature("Sitabardi bus terminal", 21.1440, 79.0780,
                      ["public_transport", "public_transport.bus"],
                      {"amenity": "bus_station", "public_transport": "station", "bus": "yes"}),
        ]],
    }
    monkeypatch.setattr(geoapify_places, "_search", _transport_stub(groups))
    out = geoapify_places.fetch_transport(21.1458, 79.0882, radius_m=5000)
    kinds = {s["name"]: s["transport_type"] for s in out["stops"]}
    assert kinds["Metro Gate 1"] == "metro_entrance"
    assert kinds["Nagpur Junction"] == "railway_station"
    assert kinds["Sitabardi bus terminal"] == "bus_terminal"


def test_transport_pagination_stops_safely_at_cap(monkeypatch):
    """D: subsequent pages are followed and a runaway group stops at the cap."""
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(geoapify_places, "TRANSPORT_PAGE_SIZE", 2)
    monkeypatch.setattr(geoapify_places, "TRANSPORT_MAX_PER_GROUP", 5)

    def _runaway(categories, *args, **kwargs):
        # Always a FULL page (args[3] = requested page size — _search is called
        # as (categories, lat, lon, radius_m, page_size)): an implementation
        # without a cap would loop forever.
        return [_bus(f"Bus {categories}-{kwargs.get('offset', 0)}-{i}", i) for i in range(args[3])]

    monkeypatch.setattr(geoapify_places, "_search", _runaway)
    out = geoapify_places.fetch_transport(21.1458, 79.0882, radius_m=5000)
    # Every one of the 8 groups answered with endless full pages; each must
    # stop exactly at its own cap (5) and the loop must terminate.
    assert len(out["stops"]) == 8 * 5
    from collections import Counter
    per_group = Counter(s["id"].rsplit("-", 2)[0] for s in out["stops"])
    assert all(count == 5 for count in per_group.values())

    monkeypatch.setattr(geoapify_places, "TRANSPORT_MAX_PER_GROUP", 500)
    monkeypatch.setattr(geoapify_places, "_search", _transport_stub({
        "public_transport.bus": [[_bus(f"B{i}", i) for i in range(2)],
                                 [_bus(f"C{i}", i) for i in range(1)]],
    }))
    out = geoapify_places.fetch_transport(21.1458, 79.0882, radius_m=5000)
    assert len([s for s in out["stops"] if s["name"].startswith(("B", "C"))]) == 3


def test_transport_dedupes_by_provider_id_not_proximity(monkeypatch):
    """E: cross-group id duplicates merge; distinct nearby stops never merge."""
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    same_stop = _tfeature("One Stop", 21.1460, 79.0885,
                          ["public_transport", "public_transport.bus"],
                          {"public_transport": "platform", "highway": "bus_stop"},
                          place_id="same-1")
    same_stop_platform = {
        **same_stop,
        "properties": {**same_stop["properties"],
                       "categories": ["public_transport", "public_transport.platform"]},
    }
    distinct_close = _tfeature("Two Stop", 21.14601, 79.08851,
                               ["public_transport", "public_transport.bus"],
                               {"public_transport": "platform", "highway": "bus_stop"},
                               place_id="same-2")
    monkeypatch.setattr(geoapify_places, "_search", _transport_stub({
        "public_transport.bus": [[same_stop, distinct_close]],
        "public_transport.platform": [[same_stop_platform]],
    }))
    out = geoapify_places.fetch_transport(21.1458, 79.0882, radius_m=5000)
    names = [s["name"] for s in out["stops"]]
    assert names.count("One Stop") == 1      # same provider id → merged
    assert names.count("Two Stop") == 1      # ~1 m away, distinct id → kept


def test_transport_different_coordinates_different_results(monkeypatch):
    """F: the selected coordinates actually drive the query."""
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    seen: dict[tuple[float, float], list[str]] = {}

    def _fake(categories, lat, lon, *args, **kwargs):
        if categories == "public_transport.train":
            seen.setdefault((round(lat, 4), round(lon, 4)), []).append(
                "Nagpur Junction" if lat > 21.0 else "Mumbai CSMT")
        return []

    monkeypatch.setattr(geoapify_places, "_search", _fake)
    geoapify_places.fetch_transport(21.1458, 79.0882, radius_m=5000)
    geoapify_places.fetch_transport(18.9398, 72.8355, radius_m=5000)
    assert seen[(21.1458, 79.0882)] == ["Nagpur Junction"]
    assert seen[(18.9398, 72.8355)] == ["Mumbai CSMT"]


def test_transport_no_metro_mapped_returns_zero_metro(monkeypatch):
    """G: a metro-less area reports zero metro rows — nothing is fabricated."""
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(geoapify_places, "_search", _transport_stub({
        "public_transport.bus": [[_bus("Only Bus", 0)]],
        # subway / subway.entrance groups return [] — no metro exists here
    }))
    out = geoapify_places.fetch_transport(21.1458, 79.0882, radius_m=5000)
    assert [s["transport_type"] for s in out["stops"]].count("metro_station") == 0
    assert len(out["stops"]) == 1
    assert out["failed_groups"] == []  # empty ≠ failed: honestly reported


def test_transport_partial_group_failure_preserves_rest(monkeypatch):
    """H: a failed category is skipped and reported; others still serve."""
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")

    def _flaky(categories, *args, **kwargs):
        if categories == "public_transport.subway":
            raise GeoapifyUnavailable("geoapify places: 502 bad gateway")
        if categories == "public_transport.train":
            return [_tfeature("Nagpur Junction", 21.1530, 79.0930,
                              ["public_transport", "public_transport.train"],
                              {"public_transport": "station", "railway": "station"})]
        return []

    monkeypatch.setattr(geoapify_places, "_search", _flaky)
    out = geoapify_places.fetch_transport(21.1458, 79.0882, radius_m=5000)
    names = [s["name"] for s in out["stops"]]
    assert "Nagpur Junction" in names
    assert out["failed_groups"] == ["public_transport.subway"]


# ── Transport chain: services.fetch_transport_nearby ───────────────────


def test_transport_chain_geoapify_serves(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setattr(
        services_provider,
        "geoapify_fetch_transport",
        lambda *a, **k: {"stops": [{"id": "g-1", "name": "Zero Mile metro", "transport_type": "metro_station",
                                    "latitude": 21.147, "longitude": 79.089, "address": "",
                                    "distance_km": 0.4, "data_source": "geoapify_places", "data_status": "LIVE"}],
                         "failed_groups": [], "area_filter": "circle"},
    )
    data = services_provider.fetch_transport_nearby(21.1458, 79.0882, radius_km=5)
    assert data["stops"][0]["transport_type"] == "metro_station"
    assert data["failed_groups"] == []


def test_transport_chain_osm_fallback_maps_types(monkeypatch):
    monkeypatch.delenv("GEOAPIFY_API_KEY", raising=False)

    def _unavailable(*a, **k):
        raise GeoapifyUnavailable("no key")

    monkeypatch.setattr(services_provider, "geoapify_fetch_transport", _unavailable)
    monkeypatch.setattr(
        services_provider,
        "osm_fetch_nearby",
        lambda *a, **k: [
            {"id": "o-1", "name": "Bus Stop A", "service_type": "bus_stand", "latitude": 21.146,
             "longitude": 79.088, "address": "", "phone": None, "opening_status": "unknown",
             "data_source": "openstreetmap_overpass", "data_status": "LIVE"},
            {"id": "o-2", "name": "Nagpur Junction", "service_type": "railway_station", "latitude": 21.153,
             "longitude": 79.093, "address": "", "phone": None, "opening_status": "unknown",
             "data_source": "openstreetmap_overpass", "data_status": "LIVE"},
            {"id": "o-3", "name": "City Hospital", "service_type": "hospital", "latitude": 21.144,
             "longitude": 79.087, "address": "", "phone": None, "opening_status": "unknown",
             "data_source": "openstreetmap_overpass", "data_status": "LIVE"},
        ],
    )
    data = services_provider.fetch_transport_nearby(21.1458, 79.0882, radius_km=5)
    kinds = {s["name"]: s["transport_type"] for s in data["stops"]}
    assert kinds == {"Bus Stop A": "bus_stop", "Nagpur Junction": "railway_station"}
    # hospital correctly excluded — it is not transit
    assert "City Hospital" not in kinds


def test_transport_chain_both_tiers_down_serves_honest_empty(monkeypatch):
    monkeypatch.delenv("GEOAPIFY_API_KEY", raising=False)

    def _unavailable(*a, **k):
        raise GeoapifyUnavailable("no key")

    def _osm_down(*a, **k):
        raise services_provider.OsmUnavailable("no named service results in this area")

    monkeypatch.setattr(services_provider, "geoapify_fetch_transport", _unavailable)
    monkeypatch.setattr(services_provider, "osm_fetch_nearby", _osm_down)
    data = services_provider.fetch_transport_nearby(21.1458, 79.0882, radius_km=5)
    assert data["stops"] == []
    assert data["failed_groups"] == list(services_provider.TRANSPORT_GROUPS_ALL)
