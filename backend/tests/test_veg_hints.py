"""Conservative veg hints — vocabulary, veto rules, and strictness.

The hint must never leak into the strict ``vegetarian`` filter: only the
explicit ``veg_hint`` field carries it, and only when no real diet tags
were mapped.
"""
import pytest

from app.providers import food as food_provider
from app.providers import geoapify_places
from app.providers.veg_hints import apply_veg_hint, infer_veg_hint


# ── infer_veg_hint: positive vocabulary ──────────────────────────────────


@pytest.mark.parametrize("name", [
    "Shree Krishna Pure Veg",
    "Gupta Veg Restaurant",
    "Jain Bhojanalaya",
    "Sattvik Kitchen",
    "Shakahari Rasoi",
    "Shuddh Desi Khana",
    "Saravana Bhavan (Veg)",
])
def test_veg_names_hint_true(name):
    assert infer_veg_hint(name) is True


@pytest.mark.parametrize("name", [
    "Bademiya Seekh Kebab",
    "Chicken Center",
    "Biryani House",
    "Kebab and juices",       # mixed name → veto wins
    "Non Veg Express",
    "Non-Veg Express",
    "Egg & Eggless Bakes",    # 'egg' matches; 'eggless' alone would not
    "Tandoori Nights",
])
def test_nonveg_names_hint_false_or_none(name):
    assert infer_veg_hint(name) in (False,)


@pytest.mark.parametrize("name", [
    "Cafe Leopold",
    "Starbucks",
    "McDonald's",
    "Ambazari Lake Dhaba",     # dhaba is deliberately NOT a veg hint
    "PizzaExpress",
])
def test_neutral_names_get_no_hint(name):
    assert infer_veg_hint(name) is None


# ── apply_veg_hint: field behavior ───────────────────────────────────────


def _live_row(name, **over):
    row = {
        "id": "g-1", "name": name, "cuisine": "Restaurant",
        "vegetarian": False, "non_vegetarian": True,
        "price_range": None, "rating": None, "latitude": 21.14,
        "longitude": 79.08, "address": "", "opening_status": "unknown",
        "data_source": "geoapify_places", "data_status": "LIVE",
    }
    row.update(over)
    return row


def test_apply_hint_true_clears_non_vegetarian_default():
    row = apply_veg_hint(_live_row("Jain Bhojanalaya"), diet_tagged=False)
    assert row["veg_hint"] is True
    assert row["non_vegetarian"] is False
    assert row["vegetarian"] is False          # strict flag untouched


def test_apply_hint_false_keeps_flags():
    row = apply_veg_hint(_live_row("Chicken Center"), diet_tagged=False)
    assert row["veg_hint"] is False
    assert row["non_vegetarian"] is True
    assert row["vegetarian"] is False


def test_diet_tagged_rows_never_get_a_hint():
    row = apply_veg_hint(_live_row("Jain Bhojanalaya"), diet_tagged=True)
    assert row["veg_hint"] is None


def test_demo_rows_never_get_a_hint():
    row = apply_veg_hint(_live_row("Jain Bhojanalaya", data_status="DEMO"), diet_tagged=False)
    assert row["veg_hint"] is None


def test_hint_never_satisfies_strict_vegetarian_filter():
    """The backend vegetarian filter must stay strict — hints don't count."""
    results = [
        _live_row("Jain Bhojanalaya"),
        _live_row("Cafe Leopold"),
    ]
    for r in results:
        apply_veg_hint(r, diet_tagged=False)
    veg = [f for f in results if f["vegetarian"]]
    assert veg == []  # strict filter unaffected by hints


def test_food_chain_attaches_hints_via_geoapify(monkeypatch):
    """The real Geoapify fetcher (not a stub of it) must attach hints.

    Stubbing food_provider.geoapify_fetch_food would bypass the hint
    application entirely — the hint lives inside geoapify fetch_food, so
    the network layer (_search) is what gets stubbed here.
    """
    monkeypatch.delenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", raising=False)
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    features = [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [79.08, 21.14]},
         "properties": {"name": "Jain Bhojanalaya", "categories": ["catering", "catering.restaurant.indian"],
                        "place_id": "v-1"}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [79.09, 21.15]},
         "properties": {"name": "Cafe Leopold", "categories": ["catering", "catering.cafe"],
                        "place_id": "v-2"}},
    ]
    monkeypatch.setattr(geoapify_places, "_search", lambda *a, **k: features)
    out = food_provider.fetch_nearby(21.1458, 79.0882, radius_km=10, limit=5)
    hints = {f["name"]: f.get("veg_hint") for f in out}
    assert hints["Jain Bhojanalaya"] is True
    assert hints["Cafe Leopold"] is None
