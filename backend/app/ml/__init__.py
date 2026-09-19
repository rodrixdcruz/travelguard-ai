"""ML intelligence layer for TravelGuard AI.

Hybrid architecture:
- ML handles contextual risk prediction and personalized place ranking.
- The deterministic risk engine remains the fallback + sanity check.
- The LLM only explains results; it never produces numeric predictions.
"""
