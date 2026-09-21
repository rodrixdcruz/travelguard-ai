"""In-memory weather cache behavior in app.providers.weather_live."""
import pytest

from app.providers import weather_live
from app.providers.weather_live import WeatherUnavailable, current_conditions


@pytest.fixture(autouse=True)
def _clean_cache_and_env(monkeypatch):
    weather_live._CACHE.clear()
    monkeypatch.setenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "")  # enable live path
    yield
    weather_live._CACHE.clear()


def test_cache_hit_skips_provider(monkeypatch):
    calls = {"n": 0}

    def fake_met(lat, lon):
        calls["n"] += 1
        return {"condition": "Clear", "data_source": "met-norway", "data_status": "LIVE"}

    monkeypatch.setattr(weather_live, "_met_conditions", fake_met)
    first = current_conditions(21.1458, 79.0882)
    second = current_conditions(21.1458, 79.0882)
    assert calls["n"] == 1
    assert first == second


def test_nearby_points_share_entry(monkeypatch):
    calls = {"n": 0}

    def fake_met(lat, lon):
        calls["n"] += 1
        return {"condition": "Rain"}

    monkeypatch.setattr(weather_live, "_met_conditions", fake_met)
    current_conditions(21.14581, 79.08821)
    current_conditions(21.14579, 79.08819)
    assert calls["n"] == 1  # both rounded to the same ~1.1 km key


def test_expired_entry_refetches(monkeypatch):
    calls = {"n": 0}

    def fake_met(lat, lon):
        calls["n"] += 1
        return {"condition": "Clear"}

    monkeypatch.setattr(weather_live, "_met_conditions", fake_met)
    current_conditions(21.1458, 79.0882)

    # Age the single entry past the TTL.
    key = weather_live._cache_key(21.1458, 79.0882)
    ts, val = weather_live._CACHE[key]
    weather_live._CACHE[key] = (ts - weather_live.CACHE_TTL_SECONDS - 1, val)
    current_conditions(21.1458, 79.0882)
    assert calls["n"] == 2


def test_failure_is_not_cached(monkeypatch):
    calls = {"n": 0}

    def failing(lat, lon):
        calls["n"] += 1
        raise WeatherUnavailable("down")

    monkeypatch.setattr(weather_live, "_met_conditions", failing)
    monkeypatch.setattr(weather_live, "_open_meteo_conditions", failing)
    with pytest.raises(WeatherUnavailable):
        current_conditions(21.1458, 79.0882)
    with pytest.raises(WeatherUnavailable):
        current_conditions(21.1458, 79.0882)
    assert calls["n"] == 2  # retried, not cached


def test_fallback_result_is_cached_too(monkeypatch):
    def met_down(lat, lon):
        raise WeatherUnavailable("met down")

    met_down.__name__ = "met_down"

    def om(lat, lon):
        return {"condition": "Fair", "data_source": "open-meteo", "data_status": "LIVE"}

    monkeypatch.setattr(weather_live, "_met_conditions", met_down)
    monkeypatch.setattr(weather_live, "_open_meteo_conditions", om)
    a = current_conditions(21.1458, 79.0882)
    b = current_conditions(21.1458, 79.0882)
    assert a["data_source"] == "open-meteo"
    assert a == b


def test_kill_switch_bypasses_cache(monkeypatch):
    weather_live._CACHE[weather_live._cache_key(21.1458, 79.0882)] = (
        weather_live.time.monotonic(),
        {"condition": "Stale"},
    )
    monkeypatch.setenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "1")
    # Serving a stale cached value would violate the kill-switch contract,
    # so the env check must short-circuit before any cache lookup.
    with pytest.raises(WeatherUnavailable):
        current_conditions(21.1458, 79.0882)


def test_returned_dict_is_a_copy(monkeypatch):
    monkeypatch.setattr(weather_live, "_met_conditions", lambda lat, lon: {"condition": "Clear"})
    a = current_conditions(21.1458, 79.0882)
    a["condition"] = "MUTATED"
    b = current_conditions(21.1458, 79.0882)
    assert b["condition"] == "Clear"  # shared entry not corrupted
