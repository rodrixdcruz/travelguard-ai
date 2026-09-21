"""Response-level provider provenance summary.

Every discovery/plan response carries a `provider_summary` so the UI can
render ONE consistent data-source line describing what actually served the
request. It is always DERIVED from the items' own data_status / data_source
fields — never a hardcoded claim — so a silent fallback can't hide behind a
stale label.
"""
from __future__ import annotations

from typing import Any

# Human-readable names for the source slugs providers stamp on items.
_SOURCE_LABELS = {
    "wikipedia_geosearch": "Wikipedia geosearch",
    "openstreetmap_overpass": "OpenStreetMap",
    "met-norway": "MET Norway",
    "open-meteo": "Open-Meteo",
    "osm_nominatim": "OSM Nominatim",
    "travelguard_demo_dataset": "TravelGuard demo dataset",
    "demo": "demo dataset",
}


def _label(source: str) -> str:
    return _SOURCE_LABELS.get(source, source.replace("_", " "))


def provider_summary(
    items: list[dict[str, Any]],
    *,
    fallback_line: str = "TravelGuard demo dataset",
) -> dict[str, Any]:
    """Derive ``{status, sources, line}`` from the items actually served.

    status: LIVE when every status-bearing item is LIVE, MIXED when LIVE and
    DEMO are both present, DEMO when only DEMO, ESTIMATED when only modeled
    (ESTIMATED) rows, and DEMO for an empty pool (matches the historical
    endpoint behavior of "nothing live was served").
    """
    statuses = [str(i.get("data_status", "")).upper() for i in items if i.get("data_status")]
    live = "LIVE" in statuses
    demo = "DEMO" in statuses

    if live and not demo:
        status = "LIVE"
    elif live and demo:
        status = "MIXED"
    elif demo:
        status = "DEMO"
    elif "ESTIMATED" in statuses:
        status = "ESTIMATED"
    else:
        status = "DEMO"

    sources = sorted({_label(str(i["data_source"])) for i in items if i.get("data_source")})

    if status == "LIVE":
        line = "LIVE from " + (" + ".join(sources) if sources else "live providers")
    elif status == "MIXED":
        live_srcs = sorted({_label(str(i["data_source"])) for i in items
                            if str(i.get("data_status", "")).upper() == "LIVE" and i.get("data_source")})
        line = ("LIVE from " + " + ".join(live_srcs) if live_srcs else "Partly LIVE") + \
               " · remainder from demo dataset"
    elif status == "ESTIMATED":
        line = "ESTIMATED — modeled rates, not live data"
    else:
        line = fallback_line

    return {"status": status, "sources": sources, "line": line}
