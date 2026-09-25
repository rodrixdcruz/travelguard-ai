"""Conservative veg-likelihood hints from eatery names — never presented as data.

OpenStreetMap rarely carries diet:* tags in India, so the VEG filter empties
entire live datasets (observed live in Nagpur/Colaba). A deliberately small
vocabulary of UNAMBIGUOUS Indian naming conventions lets live tiers attach an
``veg_hint`` INFERRED from the name alone:

- only when the row has no real diet tags (tags always win),
- never merged into the ``vegetarian`` flag — the UI shows a separate
  "inferred" badge and a tooltip, and the backend vegetarian filter stays
  strict (hints never satisfy ``vegetarian=True``),
- meat words in a name veto the hint (chicken, biryani, kebab, …),
- "dhaba", cuisine styles and regional words are deliberately NOT hints —
  dhabas and many regional eateries serve meat, so guessing veg from them
  would be wrong more often than right.
"""
from __future__ import annotations

import re
from typing import Any, Optional

# Explicit meat words and non-veg claims — a match vetoes any veg hint.
# Word boundaries keep "eggless" (an explicit NO-egg claim) and "Hamburg"
# from matching egg/ham.
NONVEG_NAME_PATTERN = re.compile(
    r"non\s*[- ]?\s*veg|chicken|mutton|fish|prawn|prawns|shrimp|beef|pork"
    r"|\bham\b|\blamb\b|crab|\beggs?\b|kebab|seekh|tikka|tandoori|biryani"
    r"|kheema|keema"
)

# Unambiguous vegetarian claims used in Indian eatery names. "Veg" alone
# counts ONLY because the non-veg pattern above already excluded "Non-Veg".
VEG_NAME_PATTERN = re.compile(
    r"pure\s*veg|\bveg\b|\bvegetarian\b|\bjain\b|\bshakahari\b"
    r"|\bshuddh\b|\bsatvik\b|\bsattvik\b"
)


def infer_veg_hint(name: str) -> Optional[bool]:
    """Veg likelihood from a name: True/False claim, or None = no claim."""
    lowered = (name or "").lower()
    if NONVEG_NAME_PATTERN.search(lowered):
        return False
    if VEG_NAME_PATTERN.search(lowered):
        return True
    return None


def apply_veg_hint(row: dict[str, Any], diet_tagged: bool) -> dict[str, Any]:
    """Attach ``veg_hint`` to a LIVE food row when no diet tags were mapped.

    ``diet_tagged`` means real OSM diet tags governed the flags — the name
    stays silent then. A True hint also clears the ``non_vegetarian``
    default so a "Pure Veg" row cannot surface under the NON-VEG filter.
    """
    if row.get("data_status") != "LIVE" or diet_tagged:
        row.setdefault("veg_hint", None)
        return row
    hint = infer_veg_hint(row.get("name", ""))
    row["veg_hint"] = hint
    if hint is True:
        row["non_vegetarian"] = False
    return row
