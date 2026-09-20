"""Deterministic demo dataset.

Known city pairs resolve to real coordinates and a plausible polyline route.
Unknown pairs fall back to a generic interpolated route so the demo always
works without external APIs.
"""
from __future__ import annotations

import math
from typing import Optional

from .schemas import Coordinate

# Rough city coordinates (lat, lon)
CITY_COORDS: dict[str, Coordinate] = {
    "mumbai": Coordinate(lat=19.0760, lon=72.8777),
    "pune": Coordinate(lat=18.5204, lon=73.8567),
    "nashik": Coordinate(lat=19.9975, lon=73.7898),
    "lonavala": Coordinate(lat=18.7546, lon=73.4062),
    "lonavla": Coordinate(lon=73.4062, lat=18.7546),
    "satara": Coordinate(lat=17.6868, lon=74.0208),
    "kolhapur": Coordinate(lat=16.7050, lon=74.2433),
    "delhi": Coordinate(lat=28.6139, lon=77.2090),
    "jaipur": Coordinate(lat=26.9124, lon=75.7873),
    "agra": Coordinate(lat=27.1767, lon=78.0081),
    "bengaluru": Coordinate(lat=12.9716, lon=77.5946),
    "bangalore": Coordinate(lat=12.9716, lon=77.5946),
    "mysuru": Coordinate(lat=12.2955, lon=76.6394),
    "mysore": Coordinate(lat=12.2955, lon=76.6394),
    "chennai": Coordinate(lat=13.0827, lon=80.2707),
    "hyderabad": Coordinate(lat=17.3850, lon=78.4867),
    "kolkata": Coordinate(lat=22.5726, lon=88.3639),
    "ahmedabad": Coordinate(lat=23.0225, lon=72.5714),
    "surat": Coordinate(lat=21.1702, lon=72.8311),
    "goa": Coordinate(lat=15.2993, lon=74.1240),
    "panaji": Coordinate(lat=15.4909, lon=73.8278),
    "nagpur": Coordinate(lat=21.1458, lon=79.0882),
    "indore": Coordinate(lat=22.7196, lon=75.8577),
    "bhopal": Coordinate(lat=23.2599, lon=77.4126),
    "lucknow": Coordinate(lat=26.8467, lon=80.9462),
    "kanpur": Coordinate(lat=26.4499, lon=80.3319),
    "patna": Coordinate(lat=25.5941, lon=85.1376),
    "kochi": Coordinate(lat=9.9312, lon=76.2673),
    "coimbatore": Coordinate(lat=11.0168, lon=76.9558),
    "visakhapatnam": Coordinate(lat=17.6868, lon=83.2185),
    "varanasi": Coordinate(lat=25.3176, lon=82.9739),
    "amritsar": Coordinate(lat=31.6340, lon=74.8723),
    "chandigarh": Coordinate(lat=30.7333, lon=76.7794),
    "shimla": Coordinate(lat=31.1048, lon=77.1734),
    "manali": Coordinate(lat=32.2432, lon=77.1892),
    "udaipur": Coordinate(lat=24.5854, lon=73.7125),
    "rishikesh": Coordinate(lat=30.0869, lon=78.2676),
}

# Named polyline waypoints (lat, lon) for headline demo routes.
ROUTES: dict[tuple[str, str], list[tuple[float, float]]] = {
    ("mumbai", "pune"): [
        (19.0670, 72.9970),   # Vikhroli east
        (19.0330, 73.0290),   # Teen Hath Naka
        (18.9700, 73.1100),   # Bhiwandi bypass
        (18.8450, 73.3200),   # Lonavala approach
        (18.7546, 73.4062),   # Lonavala ghat section
        (18.7100, 73.5900),   # Talegaon
        (18.5900, 73.7400),   # Wakad
        (18.5204, 73.8567),   # Pune
    ],
    ("delhi", "jaipur"): [
        (28.6139, 77.2090),
        (28.4226, 76.8500),   # Manesar
        (28.0800, 76.5200),   # Rewari
        (27.7000, 76.2000),   # Kot Putli
        (27.2000, 76.0000),   # Shahpura
        (26.9124, 75.7873),   # Jaipur
    ],
    ("bengaluru", "mysuru"): [
        (12.9716, 77.5946),
        (12.9000, 77.4800),   # Kengeri
        (12.7500, 77.2500),   # Channapatna
        (12.5800, 77.0000),   # Maddur
        (12.2955, 76.6394),   # Mysuru
    ],
    ("pune", "mumbai"): [
        (18.5900, 73.7400),
        (18.7100, 73.5900),
        (18.7546, 73.4062),
        (18.8450, 73.3200),
        (19.0330, 73.1100),
        (19.0670, 72.9970),
        (19.0760, 72.8777),
   ],
    ("jaipur", "delhi"): [
        (26.9124, 75.7873),
        (27.2000, 76.0000),
        (27.7000, 76.2000),
        (28.0800, 76.5200),   # Kot Putli
        (28.4226, 76.8500),
        (28.6139, 77.2090),
    ],
    ("bengaluru", "chennai"): [
        (12.9716, 77.5946),
        (12.8500, 78.1000),
        (12.9000, 78.6000),
        (13.0827, 80.2707),
    ],
}

DEFAULT_SPEED_KMPH = 60.0
GENERIC_DISTANCE_KM = 180.0


def _haversine_km(a: Coordinate, b: Coordinate) -> float:
    R = 6371.0088
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dphi = p2 - p1
    dl = math.radians(b.lon - a.lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def lookup_city(name: str) -> Optional[Coordinate]:
    return CITY_COORDS.get(name.strip().lower())


def get_route(origin_name: str, destination_name: str) -> Optional[list[Coordinate]]:
    key = (origin_name.strip().lower(), destination_name.strip().lower())
    return ROUTES.get(key)


def build_generic_route(origin: Coordinate, destination: Coordinate) -> list[Coordinate]:
    """Interpolated arc for unknown pairs so the demo always has a route."""
    n = 8
    pts: list[Coordinate] = []
    for i in range(n + 1):
        t = i / n
        lat = origin.lat + (destination.lat - origin.lat) * t
        lon = origin.lon + (destination.lon - origin.lon) * t
        # gentle arc so the line doesn't look perfectly straight
        bow = math.sin(math.pi * t) * max(0.35, abs(origin.lat - destination.lat) * 0.08)
        pts.append(Coordinate(lat=lat + bow, lon=lon + bow * 0.6))
    return pts


def route_length_km(path: list[Coordinate]) -> float:
    return round(sum(_haversine_km(path[i], path[i + 1]) for i in range(len(path) - 1)), 1)


def demo_distance_km(origin_name: str, destination_name: str, path: list[Coordinate]) -> float:
    """Plausible road distance: polyline length scaled to feel like real roads."""
    straight = _haversine_km(path[0], path[-1])
    road = route_length_km(path)
    # Road distance ≈ 1.25 × straight line, clamped to at least the polyline length.
    est = max(road, straight * 1.25)
    return round(est, 1)
