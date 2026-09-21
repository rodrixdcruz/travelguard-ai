"""Famous-first general discovery in places_osm.fetch_nearby."""
import pytest

from app.providers import places_osm
from app.providers.places_osm import OsmUnavailable, _normalize, fetch_nearby


@pytest.fixture(autouse=True)
def _allow_mocked_overpass(monkeypatch):
    """These tests stub overpass_query entirely (zero real HTTP), so the CI
    kill switch must be cleared for fetch_nearby to reach the mocked layer."""
    monkeypatch.delenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", raising=False)


def _el(eid, name, tags, lat=21.15, lon=79.09):
    return {"type": "node", "id": eid, "lat": lat, "lon": lon, "tags": {"name": name, **tags}}


def test_general_query_unions_all_tag_classes():
    seen = {}
    fake = {"elements": []}

    def fake_overpass(query, timeout=None):
        seen["q"] = query
        return fake["elements"]

    orig = places_osm.overpass_query
    places_osm.overpass_query = fake_overpass
    try:
        try:
            fetch_nearby(21.1458, 79.0882, radius_m=10000, limit=20)
        except OsmUnavailable:
            pass  # empty pool raises — fine, we only assert the query
    finally:
        places_osm.overpass_query = orig
    q = seen["q"]
    assert '["tourism"]["name"]' in q
    assert '["historic"]["name"]' in q
    assert "^(park|nature_reserve|garden|water_park)$" in q
    assert "^(water|wetland)$" in q
    assert "^(place_of_worship|marketplace|cinema|theatre|arts_centre)$" in q
    # generic shop flood-filter stays out of the union
    assert '["shop"]["name"]' not in q


def test_category_query_uses_single_tag():
    seen = {}

    def fake_overpass(query, timeout=None):
        seen["q"] = query
        return []

    orig = places_osm.overpass_query
    places_osm.overpass_query = fake_overpass
    try:
        try:
            fetch_nearby(21.1458, 79.0882, radius_m=5000, category="museum", limit=10)
        except OsmUnavailable:
            pass  # empty pool raises — fine, we only assert the query
    finally:
        places_osm.overpass_query = orig
    assert '["tourism"="museum"]["name"]' in seen["q"]
    assert "out center 10;" in seen["q"]


def test_ranking_famous_first():
    els = [
        _el(1, "Tiny Stall", {"shop": "kiosk"}, lat=21.140, lon=79.08),
        _el(2, "Ambazari Lake", {"leisure": "park", "wikidata": "Q123"}, lat=21.20, lon=79.10),
        _el(3, "Random Dhaba", {"amenity": "restaurant"}, lat=21.13, lon=79.07),
        _el(4, "Deekshabhoomi", {"historic": "memorial", "wikipedia": "en:Deekshabhoomi"}, lat=21.18, lon=79.07),
        _el(5, "Sitabuldi Fort", {"historic": "fort"}, lat=21.15, lon=79.09),
    ]

    def fake_overpass(query, timeout=None):
        return els

    orig = places_osm.overpass_query
    places_osm.overpass_query = fake_overpass
    try:
        out = fetch_nearby(21.1458, 79.0882, radius_m=10000, limit=5)
    finally:
        places_osm.overpass_query = orig
    names = [p["name"] for p in out]
    # wikidata/wikipedia-tagged places rank above untagged ones; the
    # generic shop/restaurant never beat tagged attractions.
    assert names.index("Ambazari Lake") < names.index("Sitabuldi Fort")
    assert "Tiny Stall" not in names
    assert "Random Dhaba" not in names
    # internal ranking field is stripped
    assert all("_notability" not in p for p in out)


def test_normalize_notability_scoring():
    wiki = _normalize(_el(1, "A", {"tourism": "attraction", "wikidata": "Q1"}), 0, 0)
    tagged = _normalize(_el(2, "B", {"historic": "memorial"}), 0, 0)
    plain = _normalize(_el(3, "C", {"leisure": "park"}), 0, 0)
    assert wiki["_notability"] == 5  # wikidata(3) + attraction(2)
    assert tagged["_notability"] == 2
    assert plain["_notability"] == 0
