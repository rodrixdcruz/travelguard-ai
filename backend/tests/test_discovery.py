"""Discovery layer tests — filtering, sorting, planner, costs, data honesty."""
from __future__ import annotations

from app.providers import food as food_provider
from app.providers import places as places_provider
from app.providers import services as services_provider
from app.providers import tickets as tickets_provider
from app.providers.transport import estimate as transport_estimate

GATEWAY = (18.9220, 72.8347)


# ── Places provider ─────────────────────────────────────────────────────

def test_nearby_places_sorted_by_distance():
    items = places_provider.fetch_nearby(*GATEWAY, radius_km=10, limit=20)
    dists = [p["distance_km"] for p in items]
    assert dists == sorted(dists)
    assert items[0]["name"] == "Gateway of India"  # origin is Gateway itself


def test_category_filtering():
    museums = places_provider.fetch_nearby(*GATEWAY, radius_km=40, category="museum", limit=20)
    assert museums and all(p["category"] == "museum" for p in museums)
    # alias categories resolve
    shopping = places_provider.fetch_nearby(*GATEWAY, radius_km=40, category="shopping", limit=20)
    assert any(p["category"] in ("market", "shopping") for p in shopping)


def test_interest_filtering():
    photo = places_provider.fetch_nearby(*GATEWAY, radius_km=40, interest="photography", limit=20)
    assert photo and all("photography" in [t.lower() for t in p["tags"]] for p in photo)


def test_radius_excludes_far_places():
    items = places_provider.fetch_nearby(*GATEWAY, radius_km=2.0, limit=50)
    assert all(p["distance_km"] <= 2.0 for p in items)
    assert 0 < len(items) < 10


def test_every_place_has_honest_demo_status():
    for p in places_provider.all_places():
        assert p["data_status"] == "DEMO"
        assert p["data_source"]


def test_place_details_by_id():
    from app.providers.places import fetch_by_id
    place = fetch_by_id("p-elephanta")
    assert place and place["name"] == "Elephanta Caves"
    assert place["ticket_required"] is True
    assert place["data_status"] == "DEMO"


def test_place_details_missing_returns_none():
    from app.providers.places import fetch_by_id
    assert fetch_by_id("nope-404") is None


# ── Food provider ───────────────────────────────────────────────────────

def test_food_vegetarian_filter():
    veg = food_provider.fetch_nearby(*GATEWAY, radius_km=40, vegetarian=True, limit=30)
    assert veg and all(f["vegetarian"] for f in veg)
    nonveg = food_provider.fetch_nearby(*GATEWAY, radius_km=40, vegetarian=False, limit=30)
    assert all(f["non_vegetarian"] for f in nonveg)


def test_food_budget_filter_respects_price_class():
    cheap = food_provider.fetch_nearby(*GATEWAY, radius_km=40, budget=200, limit=30)
    assert cheap and all(f["price_range"] in ("₹", "₹₹") for f in cheap)


def test_food_budget_filter_keeps_unpriced_live_rows():
    """Unpriced rows (price_range=None — OSM has no price class) are budget-
    class, not silently excluded: with live data the BUDGET filter must not
    return empty where places exist."""
    results = [
        {"price_range": "₹"}, {"price_range": None}, {"price_range": "₹₹₹"},
    ]
    kept = [f for f in results
            if food_provider.PRICE_CLASS_ESTIMATE.get(f["price_range"],
                                                      food_provider.PRICE_CLASS_ESTIMATE["₹"]) <= 200]
    assert [f["price_range"] for f in kept] == ["₹", None]


def test_food_cuisine_filter():
    cafes = food_provider.fetch_nearby(*GATEWAY, radius_km=40, cuisine="cafe", limit=30)
    assert cafes and all("cafe" in f["cuisine"].lower() for f in cafes)


def test_food_sorted_by_distance():
    items = food_provider.fetch_nearby(*GATEWAY, radius_km=20, limit=20)
    dists = [f["distance_km"] for f in items]
    assert dists == sorted(dists)


# ── Services provider ───────────────────────────────────────────────────

def test_service_type_filter():
    hospitals = services_provider.fetch_nearby(*GATEWAY, radius_km=40, service_type="hospital", limit=10)
    assert hospitals and all(s["service_type"] == "hospital" for s in hospitals)


def test_sos_bundle_returns_safety_services():
    sos = services_provider.fetch_nearby(*GATEWAY, radius_km=40, service_type="sos", limit=20)
    types = {s["service_type"] for s in sos}
    assert types and types <= {"hospital", "police", "pharmacy", "ambulance", "fire"}


def test_no_fabricated_phone_numbers():
    for s in services_provider.fetch_nearby(*GATEWAY, radius_km=40, limit=50):
        assert s["phone"] is None  # demo data never invents numbers


# ── Transport & tickets ────────────────────────────────────────────────

def test_transport_estimate_labeled_estimated():
    est = transport_estimate(GATEWAY, (19.1075, 72.8263), mode="taxi")  # Juhu, far
    assert est["data_status"] == "ESTIMATED"
    assert est["distance_km"] > 10
    assert est["estimated_fare_inr"] > 100


def test_attraction_costs_sum():
    place = places_provider.fetch_by_id("p-elephanta")
    costs = tickets_provider.attraction_costs(place, GATEWAY, travelers=2)
    assert costs["entry_fee_per_person"] == 40
    assert costs["travelers"] == 2
    # transport fare in the response is already scaled to the party size
    assert costs["total_estimate_inr"] == (
        costs["entry_fee_per_person"] * costs["travelers"]
        + costs["transport"]["estimated_fare_inr"]
    )
    assert costs["entry_fee_data_status"] == "DEMO"


def test_meal_costs_estimated():
    meal = tickets_provider.meal_costs("₹₹", travelers=2)
    assert meal["per_person_inr"] == 400
    assert meal["total_inr"] == 800
    assert meal["data_status"] == "ESTIMATED"


# ── Day planner API ────────────────────────────────────────────────────

def test_plan_day_success(client: TestClient):
    resp = client.post("/api/plan/day", json={
        "latitude": GATEWAY[0], "longitude": GATEWAY[1],
        "duration": "half_day", "budget": 2000,
        "interests": ["history", "food", "photography"], "travelers": 2,
        "start_time": "09:00",
    })
    assert resp.status_code == 200
    body = resp.json()
    items = body["itinerary"]["items"]
    assert body["itinerary"]["totals"]["places"] >= 2
    # Times are sequential and non-decreasing
    times = [i["time"] for i in items]
    assert times == sorted(times)
    # Every item carries an honest data_status
    assert all(i["data_status"] in ("DEMO", "ESTIMATED") for i in items)
    # Costs add up
    cb = body["cost_breakdown"]
    assert cb["total_estimate"] == cb["tickets"] + cb["food_estimate"] + cb["transport_estimate"]
    assert cb["line_status"] == {"tickets": "DEMO", "food_estimate": "ESTIMATED", "transport_estimate": "ESTIMATED"}
    # Safety from the existing ML model
    assert body["safety"]["model_used"] in ("random_forest", "rule_based_demo")
    assert "not accident probability" in body["safety"]["disclaimer"]


def test_plan_day_meal_inserted_for_long_day(client: TestClient):
    resp = client.post("/api/plan/day", json={
        "latitude": GATEWAY[0], "longitude": GATEWAY[1],
        "duration": "full_day", "budget": 5000, "travelers": "family",
        "start_time": "09:00",
    })
    body = resp.json()
    types = [i["type"] for i in body["itinerary"]["items"]]
    assert "meal" in types


def test_plan_day_duration_maps(client: TestClient):
    for dur, expected_hours in (("2h", 2.0), ("4h", 4.0), ("half_day", 5.0), ("full_day", 8.0), ("6", 6.0)):
        resp = client.post("/api/plan/day", json={
            "latitude": GATEWAY[0], "longitude": GATEWAY[1], "duration": dur,
        })
        assert resp.status_code == 200
        assert resp.json()["preferences"]["hours"] == expected_hours


def test_plan_day_invalid_duration_rejected(client: TestClient):
    resp = client.post("/api/plan/day", json={
        "latitude": GATEWAY[0], "longitude": GATEWAY[1], "duration": "99h",
    })
    assert resp.status_code == 422
    resp = client.post("/api/plan/day", json={
        "latitude": GATEWAY[0], "longitude": GATEWAY[1], "duration": "fortnight",
    })
    assert resp.status_code == 422
    resp = client.post("/api/plan/day", json={
        "latitude": GATEWAY[0], "longitude": GATEWAY[1], "budget": "cheap",
    })
    assert resp.status_code == 422


def test_plan_day_uses_ml_ranking(client: TestClient):
    resp = client.post("/api/plan/day", json={
        "latitude": GATEWAY[0], "longitude": GATEWAY[1], "duration": "4h",
        "interests": ["history"],
    })
    body = resp.json()
    assert body["ranking_model"] in ("gradient_boosting", "heuristic_demo")
    # history interest should surface historical places among stops
    stop_names = " ".join(i["name"] for i in body["itinerary"]["items"] if i["type"] == "attraction")
    assert any(k in stop_names for k in ("Gateway", "Terminus", "Caves", "Mani Bhavan", "Banganga", "Kanheri"))


def test_plan_day_items_carry_reasons_and_travel_time(client: TestClient):
    """Attraction items expose ML reasons, category and travel time (UX polish contract)."""
    resp = client.post("/api/plan/day", json={
        "latitude": GATEWAY[0], "longitude": GATEWAY[1], "duration": "half_day",
        "interests": ["history"], "start_time": "09:00",
    })
    body = resp.json()
    attractions = [i for i in body["itinerary"]["items"] if i["type"] == "attraction"]
    assert attractions
    for item in attractions:
        assert isinstance(item.get("category"), str) and item["category"]
        assert isinstance(item.get("travel_time_min"), int) and item["travel_time_min"] >= 0
        assert isinstance(item.get("reasons"), list)
    # ML model path supplies real reasons (not fabricated per-item strings)
    if body["ranking_model"] == "gradient_boosting":
        assert any(i["reasons"] for i in attractions)


def test_discovery_ai_answer_is_grounded(client: TestClient):
    """Discovery chat answers ONLY from the provided payload — never invents."""
    plan = client.post("/api/plan/day", json={
        "latitude": GATEWAY[0], "longitude": GATEWAY[1], "duration": "4h",
        "interests": ["history"], "budget": 2000, "start_time": "09:00",
    }).json()
    payload = {
        "places": [],
        "itinerary": plan["itinerary"],
        "cost_breakdown": plan["cost_breakdown"],
        "safety": plan["safety"],
        "travelers": plan["cost_breakdown"]["travelers"],
    }
    resp = client.post("/api/ai/chat", json={
        "context": {"discovery": payload}, "question": "What is the plan for the day?",
    })
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert resp.json()["source"] == "fallback"
    # grounded: mentions a real stop from the itinerary
    stops = [i["name"] for i in plan["itinerary"]["items"] if i["type"] == "attraction"]
    assert any(s in answer for s in stops)


def test_discovery_ai_budget_answer(client: TestClient):
    plan = client.post("/api/plan/day", json={
        "latitude": GATEWAY[0], "longitude": GATEWAY[1], "duration": "4h",
        "start_time": "09:00",
    }).json()
    payload = {
        "places": [
            {"name": "Gateway of India", "entry_fee": 0},
            {"name": "Elephanta Caves", "entry_fee": 40},
            {"name": "Expensive Place", "entry_fee": 5000},
        ],
        "itinerary": plan["itinerary"],
        "cost_breakdown": plan["cost_breakdown"],
        "safety": plan["safety"],
        "travelers": 1,
    }
    resp = client.post("/api/ai/chat", json={
        "context": {"discovery": payload}, "question": "What can I do nearby for ₹1,000?",
    })
    answer = resp.json()["answer"]
    assert "Gateway of India" in answer
    assert "Elephanta Caves" in answer
    assert "Expensive Place" not in answer  # over budget → excluded


def test_discovery_ai_empty_context_is_honest(client: TestClient):
    resp = client.post("/api/ai/chat", json={
        "context": {"discovery": {}}, "question": "What can I do nearby?",
    })
    assert "No discovery data available" in resp.json()["answer"]


def test_safety_local_endpoint_shape(client: TestClient):
    resp = client.get("/api/safety/local", params={"latitude": GATEWAY[0], "longitude": GATEWAY[1]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_used"] in ("random_forest", "rule_based_demo")
    assert "not accident probability" in body["disclaimer"]
    assert body["data_status"] == "DEMO"


# ── Discovery API endpoints ────────────────────────────────────────────

def test_places_nearby_endpoint(client: TestClient):
    resp = client.get("/api/places/nearby", params={
        "latitude": GATEWAY[0], "longitude": GATEWAY[1], "radius_km": 5, "limit": 5,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] <= 5
    assert body["data_status"] == "DEMO"
    assert all({"id", "name", "category", "latitude", "longitude", "distance_km"} <= set(p) for p in body["places"])


def test_place_details_endpoint_404(client: TestClient):
    assert client.get("/api/places/p-gateway").status_code == 200
    assert client.get("/api/places/does-not-exist").status_code == 404


def test_food_nearby_endpoint(client: TestClient):
    resp = client.get("/api/food/nearby", params={
        "latitude": GATEWAY[0], "longitude": GATEWAY[1], "vegetarian": True, "limit": 5,
    })
    assert resp.status_code == 200
    assert all(f["vegetarian"] for f in resp.json()["food"])


def test_services_nearby_endpoint(client: TestClient):
    resp = client.get("/api/services/nearby", params={
        "latitude": GATEWAY[0], "longitude": GATEWAY[1], "service_type": "police",
    })
    assert resp.status_code == 200
    services = resp.json()["services"]
    assert services and all(s["service_type"] == "police" for s in services)
    assert all("phone" not in s or s["phone"] is None for s in services)


def test_existing_ml_endpoints_still_work(client: TestClient):
    assert client.get("/api/ml/info").status_code == 200
    resp = client.post("/api/ml/safety-predict", json={
        "weather": {"condition": "Clear"}, "context": {"hour": 12},
    })
    assert resp.status_code == 200
    assert client.get("/health").status_code == 200


# ── SOS endpoint ────────────────────────────────────────────────────────

def test_sos_only_verified_numbers(client: TestClient):
    """SOS returns only verified numbers (never fabricated) + nearest safety services.

    Demo data ships one verified pan-India ERSS number (112). Local station
    numbers stay omitted until a live provider supplies them.
    """
    resp = client.get("/api/sos/info")
    assert resp.status_code == 200
    data = resp.json()
    nums = data["emergency_numbers"]
    assert nums["all_in_one"]["number"] == "112"
    assert nums["all_in_one"]["data_status"] == "DEMO"

    resp2 = client.get("/api/sos/info", params={"latitude": GATEWAY[0], "longitude": GATEWAY[1]})
    nearest = resp2.json()["nearest"]
    assert "hospital" in nearest and "police" in nearest
    assert nearest["hospital"]["phone"] is None  # no invented numbers
