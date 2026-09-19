"""Demo tourist dataset for Mumbai — deterministic, clearly DEMO-status.

Recognizable real locations with approximate coordinates. Prices, ratings,
opening hours and safety context are PLAUSIBLE DEMO ESTIMATES, marked
data_status="DEMO". Phone numbers are deliberately omitted (never
fabricated). This is not a live POI feed.
"""
from __future__ import annotations

from typing import Any

DATA_SOURCE = "travelguard_demo_dataset"
DATA_STATUS = "DEMO"

# Pan-India official emergency number (ERSS). Verified government-published
# number, safe to display. Individual local station numbers are NOT invented —
# they remain omitted ("unavailable in current data") until a live provider
# supplies them.
VERIFIED_EMERGENCY_NUMBERS: dict[str, dict[str, str]] = {
    "all_in_one": {
        "number": "112",
        "label": "National Emergency (Police / Fire / Medical)",
        "source": "India ERSS — government-published",
        "data_status": "DEMO",
    }
}


def _place(
    id: str,
    name: str,
    category: str,
    description: str,
    lat: float,
    lon: float,
    address: str,
    *,
    entry_fee: int = 0,
    ticket_required: bool | None = False,
    opening_status: str = "unknown",
    opening_hours: str = "Unknown (DEMO)",
    visit_minutes: int = 60,
    rating: float | None = None,
    tags: list[str] | None = None,
    safety_context: int = 75,
) -> dict[str, Any]:
    return {
        "id": id,
        "name": name,
        "category": category,
        "description": description,
        "latitude": lat,
        "longitude": lon,
        "address": address,
        "entry_fee": entry_fee,
        "ticket_required": ticket_required,
        "opening_status": opening_status,
        "opening_hours": opening_hours,
        "estimated_visit_minutes": visit_minutes,
        "rating": rating,
        "tags": tags or [category],
        "safety_context": safety_context,
        "data_source": DATA_SOURCE,
        "data_status": DATA_STATUS,
    }


DEMO_PLACES: list[dict[str, Any]] = [
    _place("p-gateway", "Gateway of India", "historical",
           "Iconic 1924 basalt arch on the harbour waterfront, built to commemorate King George V's visit.",
           18.9220, 72.8347, "Apollo Bandar, Colaba, Mumbai",
           entry_fee=0, ticket_required=False, opening_status="open", opening_hours="Open area, all day (DEMO)",
           visit_minutes=60, rating=4.6, tags=["historical", "photography", "culture", "attraction"], safety_context=80),
    _place("p-csmt", "Chhatrapati Shivaji Maharaj Terminus", "historical",
           "UNESCO-listed Victorian Gothic railway terminus — best viewed from outside; still an active station.",
           18.9398, 72.8355, "Fort, Mumbai",
           entry_fee=0, ticket_required=False, opening_status="open", opening_hours="Exterior anytime (DEMO)",
           visit_minutes=45, rating=4.5, tags=["historical", "photography", "attraction"], safety_context=72),
    _place("p-marine", "Marine Drive (Queen's Necklace)", "attraction",
           "Curved seaside promenade with Art Deco skyline views; spectacular after sunset.",
           18.9440, 72.8230, "Netaji Subhash Chandra Bose Road, Mumbai",
           entry_fee=0, ticket_required=False, opening_status="open", opening_hours="Promenade, all day (DEMO)",
           visit_minutes=90, rating=4.7, tags=["attraction", "photography", "nature", "family"], safety_context=78),
    _place("p-colaba", "Colaba Causeway Market", "market",
           "Bustling street market for clothing, handicrafts and jewellery. Bargaining expected.",
           18.9186, 72.8310, "Colaba Causeway, Mumbai",
           entry_fee=0, ticket_required=False, opening_status="unknown", opening_hours="Approx. 10:00–22:00 (DEMO)",
           visit_minutes=90, rating=4.3, tags=["market", "shopping", "culture"], safety_context=74),
    _place("p-elephanta", "Elephanta Caves", "historical",
           "UNESCO rock-cut cave temples on Elephanta Island; reached by ferry from Gateway of India.",
           18.9636, 72.9314, "Elephanta Island, Mumbai Harbour",
           entry_fee=40, ticket_required=True, opening_status="unknown",
           opening_hours="Ferry ~09:00–14:00 from Gateway; closed Mondays (DEMO)",
           visit_minutes=180, rating=4.4, tags=["historical", "culture", "nature", "experience"],
           safety_context=65),
    _place("p-csmvs", "Chhatrapati Shivaji Maharaj Vastu Sangrahalaya", "museum",
           "Mumbai's leading museum of art, archaeology and natural history in an Indo-Saracenic landmark.",
           18.9270, 72.8338, "Kala Ghoda, Fort, Mumbai",
           entry_fee=700, ticket_required=True, opening_status="unknown", opening_hours="Approx. 10:15–18:00, closed some holidays (DEMO)",
           visit_minutes=120, rating=4.6, tags=["museum", "culture", "historical", "family"], safety_context=80),
    _place("p-manibhavan", "Mani Bhavan Gandhi Sangrahalaya", "museum",
           "Gandhi's Mumbai headquarters 1917–1934; museum and library across his India-era years.",
           18.9538, 72.8133, "Laburnum Road, Gamdevi, Mumbai",
           entry_fee=10, ticket_required=True, opening_status="unknown", opening_hours="Approx. 09:30–18:00 (DEMO)",
           visit_minutes=60, rating=4.5, tags=["museum", "historical", "culture"], safety_context=82),
    _place("p-hanging", "Hanging Gardens", "park",
           "Terraced hilltop gardens on Malabar Hill with topiary and city views.",
           18.9546, 72.8103, "Malabar Hill, Mumbai",
           entry_fee=0, ticket_required=False, opening_status="unknown", opening_hours="Daylight hours (DEMO)",
           visit_minutes=45, rating=4.2, tags=["park", "nature", "family", "photography"], safety_context=84),
    _place("p-banganga", "Banganga Tank", "religious",
           "Ancient temple-tank complex amid Walkeshwar's heritage lanes.",
           18.9517, 72.8107, "Walkeshwar, Malabar Hill, Mumbai",
           entry_fee=0, ticket_required=False, opening_status="open", opening_hours="Temple precinct, daytime (DEMO)",
           visit_minutes=30, rating=4.3, tags=["religious", "culture", "historical", "photography"], safety_context=80),
    _place("p-siddhivinayak", "Siddhivinayak Temple", "religious",
           "One of Mumbai's most-visited Ganesha temples; expect queues, especially Tuesdays.",
           19.0170, 72.8298, "Dadar West, Mumbai",
           entry_fee=0, ticket_required=False, opening_status="unknown", opening_hours="Early morning to evening; check locally (DEMO)",
           visit_minutes=45, rating=4.6, tags=["religious", "culture"], safety_context=76),
    _place("p-hajiali", "Haji Ali Dargah", "religious",
           "Mosque and dargah on an islet, reached by a causeway (tide-dependent).",
           18.9829, 72.8083, "Haji Ali, Worli, Mumbai",
           entry_fee=0, ticket_required=False, opening_status="unknown", opening_hours="Causeway open at low tide (DEMO)",
           visit_minutes=45, rating=4.5, tags=["religious", "culture", "photography"], safety_context=70),
    _place("p-crawford", "Crawford Market", "market",
           "Colonial-era market hall for produce, spices, pets and imports.",
           18.9487, 72.8372, "Dhobi Talao, Fort, Mumbai",
           entry_fee=0, ticket_required=False, opening_status="unknown", opening_hours="Approx. 10:00–20:00, closed Sundays (DEMO)",
           visit_minutes=60, rating=4.1, tags=["market", "shopping", "culture"], safety_context=70),
    _place("p-juhu", "Juhu Beach", "nature",
           "Famous long beach with street-food stalls and sunset crowds.",
           19.1075, 72.8263, "Juhu, Mumbai",
           entry_fee=0, ticket_required=False, opening_status="open", opening_hours="Beach, all day (DEMO)",
           visit_minutes=120, rating=4.2, tags=["nature", "family", "food", "photography"], safety_context=68),
    _place("p-sgnp", "Sanjay Gandhi National Park", "nature",
           "Large urban national park with lakes, trails, and the Kanheri Caves inside.",
           19.2147, 72.9102, "Borivali East, Mumbai",
           entry_fee=85, ticket_required=True, opening_status="unknown", opening_hours="Approx. 07:30–18:00, closed Mondays (DEMO)",
           visit_minutes=240, rating=4.4, tags=["nature", "family", "experience", "photography"], safety_context=72),
    _place("p-sealink", "Bandra–Worli Sea Link Viewpoint", "photography",
           "Cable-stayed bridge over the bay — best photographed from Bandra fort area at dusk.",
           19.0284, 72.8203, "Bandra West, Mumbai",
           entry_fee=0, ticket_required=False, opening_status="open", opening_hours="Viewpoint, all day (DEMO)",
           visit_minutes=30, rating=4.4, tags=["photography", "attraction"], safety_context=75),
    _place("p-dhobighat", "Dhobi Ghat", "photography",
           "World's largest open-air laundromat — a working heritage spectacle; view from the bridge.",
           18.9889, 72.8367, "Mahalaxmi, Mumbai",
           entry_fee=0, ticket_required=False, opening_status="open", opening_hours="Working hours, mornings liveliest (DEMO)",
           visit_minutes=30, rating=4.1, tags=["photography", "culture", "experience"], safety_context=68),
    _place("p-nehru", "Nehru Science Centre", "museum",
           "Interactive science museum — good for families with children.",
           19.0022, 72.8384, "Worli, Mumbai",
           entry_fee=70, ticket_required=True, opening_status="unknown", opening_hours="Approx. 09:30–18:00 (DEMO)",
           visit_minutes=120, rating=4.2, tags=["museum", "family", "culture"], safety_context=78),
    _place("p-kanheri", "Kanheri Caves", "historical",
           "Ancient Buddhist rock-cut monastic complex inside Sanjay Gandhi National Park.",
           19.2083, 72.9083, "SGNP, Borivali East, Mumbai",
           entry_fee=100, ticket_required=True, opening_status="unknown", opening_hours="With park hours; park closed Mondays (DEMO)",
           visit_minutes=150, rating=4.3, tags=["historical", "culture", "nature"], safety_context=70),
]


def _food(
    id: str, name: str, cuisine: str, *, vegetarian: bool, non_vegetarian: bool,
    price_range: str, rating: float | None, lat: float, lon: float, address: str,
    opening_status: str = "unknown",
) -> dict[str, Any]:
    return {
        "id": id, "name": name, "cuisine": cuisine, "vegetarian": vegetarian,
        "non_vegetarian": non_vegetarian, "price_range": price_range, "rating": rating,
        "latitude": lat, "longitude": lon, "address": address,
        "opening_status": opening_status,
        "data_source": DATA_SOURCE, "data_status": DATA_STATUS,
    }


DEMO_FOOD: list[dict[str, Any]] = [
    _food("f-bademiya", "Bademiya", "Mughlai, Kebabs", vegetarian=False, non_vegetarian=True,
          price_range="₹₹", rating=4.3, lat=18.9225, lon=72.8332, address="Behind Taj Hotel, Colaba, Mumbai",
          opening_status="unknown"),
    _food("f-leopold", "Leopold Cafe", "Cafe, Continental", vegetarian=True, non_vegetarian=True,
          price_range="₹₹₹", rating=4.3, lat=18.9217, lon=72.8320, address="Colaba Causeway, Mumbai"),
    _food("f-mondegar", "Cafe Mondegar", "Cafe, Pizza", vegetarian=True, non_vegetarian=True,
          price_range="₹₹", rating=4.2, lat=18.9228, lon=72.8326, address="Metro House, Colaba, Mumbai"),
    _food("f-baghdadi", "Baghdadi", "North Indian, Mughlai", vegetarian=False, non_vegetarian=True,
          price_range="₹₹", rating=4.2, lat=18.9253, lon=72.8321, address="Colaba, Mumbai"),
    _food("f-khyber", "Khyber", "North Indian, Mughlai", vegetarian=False, non_vegetarian=True,
          price_range="₹₹₹", rating=4.4, lat=18.9316, lon=72.8333, address="Fort, Mumbai"),
    _food("f-cannon", "Cannon Pav Bhaji", "Street Food, Maharashtrian", vegetarian=True, non_vegetarian=False,
          price_range="₹", rating=4.3, lat=18.9327, lon=72.8337, address="Chhatrapati Shivaji Terminus area, Fort",
          opening_status="open"),
    _food("f-aaram", "Aaram Vada Pav", "Street Food, Maharashtrian", vegetarian=True, non_vegetarian=False,
          price_range="₹", rating=4.2, lat=18.9398, lon=72.8356, address="Near CSMT, Mumbai"),
    _food("f-chowpatty", "Girgaum Chowpatty Stalls", "Street Food, Chaat", vegetarian=True, non_vegetarian=False,
          price_range="₹", rating=4.2, lat=18.9533, lon=72.8117, address="Girgaum Chowpatty, Mumbai",
          opening_status="open"),
    _food("f-marzorin", "Marz-o-rin", "Cafe, Sandwiches", vegetarian=True, non_vegetarian=False,
          price_range="₹₹", rating=4.2, lat=18.9310, lon=72.8330, address="Clock Tower Building, Fort, Mumbai"),
    _food("f-prakash", "Prakash Shiv Sagar", "Maharashtrian, Udupi", vegetarian=True, non_vegetarian=False,
          price_range="₹₹", rating=4.3, lat=19.0186, lon=72.8443, address="Dadar West, Mumbai"),
    _food("f-mohammedali", "Mohammed Ali Road Stalls", "Street Food, Mughlai", vegetarian=False, non_vegetarian=True,
          price_range="₹", rating=4.2, lat=18.9695, lon=72.8295, address="Mohammed Ali Road, Bhendi Bazaar, Mumbai",
          opening_status="unknown"),
    _food("f-thetable", "The Table", "Global, Fine Dining", vegetarian=True, non_vegetarian=True,
          price_range="₹₹₹₹", rating=4.5, lat=18.9255, lon=72.8345, address="Colaba, Mumbai"),
]


def _service(
    id: str, name: str, service_type: str, lat: float, lon: float, address: str,
    *, opening_status: str = "unknown",
) -> dict[str, Any]:
    return {
        "id": id, "name": name, "service_type": service_type,
        "latitude": lat, "longitude": lon, "address": address,
        "phone": None,  # never fabricate phone numbers
        "opening_status": opening_status,
        "data_source": DATA_SOURCE, "data_status": DATA_STATUS,
    }


DEMO_SERVICES: list[dict[str, Any]] = [
    _service("s-stgeorge", "St George Hospital", "hospital", 18.9432, 72.8376, "P D'Mello Road, Fort, Mumbai", opening_status="open"),
    _service("s-gokuldas", "Gokuldas Tejpal Hospital", "hospital", 18.9479, 72.8360, "G T Hospital Compound, Dhobi Talao, Mumbai", opening_status="open"),
    _service("s-colabapolice", "Colaba Police Station", "police", 18.9130, 72.8310, "Colaba, Mumbai", opening_status="open"),
    _service("s-csmtpolice", "CSMT Railway Police Station", "police", 18.9410, 72.8358, "CSMT, Fort, Mumbai", opening_status="open"),
    _service("s-apollopharma", "Apollo Pharmacy, Colaba", "pharmacy", 18.9200, 72.8335, "Colaba Causeway, Mumbai", opening_status="open"),
    _service("s-fortpharma", "Fort Pharmacy", "pharmacy", 18.9300, 72.8330, "Fort, Mumbai", opening_status="open"),
    _service("s-sbiatm", "SBI ATM, CSMT", "atm", 18.9395, 72.8355, "CSMT Station, Fort, Mumbai", opening_status="open"),
    _service("s-hdfcatm", "HDFC Bank ATM, Colaba", "atm", 18.9210, 72.8325, "Colaba Causeway, Mumbai", opening_status="open"),
    _service("s-mtdc", "MTDC Tourist Information Centre", "tourist_help", 18.9340, 72.8365, "Near CSMT, Fort, Mumbai", opening_status="unknown"),
    _service("s-csmt", "CSMT Railway Station", "transport", 18.9398, 72.8355, "Fort, Mumbai", opening_status="open"),
    _service("s-bestcolaba", "BEST Bus Stop, Colaba", "transport", 18.9160, 72.8330, "Colaba, Mumbai", opening_status="open"),
    _service("s-firecolaba", "Fire Station, Colaba", "fire", 18.9180, 72.8345, "Colaba, Mumbai", opening_status="open"),
    _service("s-fuelfort", "Fuel Station, Fort", "fuel", 18.9350, 72.8390, "Fort, Mumbai", opening_status="open"),
    _service("s-natures", "Nature's Basket, Colaba", "supermarket", 18.9222, 72.8328, "Colaba Causeway, Mumbai", opening_status="unknown"),
    _service("s-taxicolaba", "Taxi Stand, Colaba", "taxi", 18.9195, 72.8332, "Colaba, Mumbai", opening_status="open"),
]
