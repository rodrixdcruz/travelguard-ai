"""Provider architecture for tourist discovery data.

Normalized models (schemas.py) + provider modules per domain. Each provider
reports its data_status honestly: LIVE (real provider), DEMO (deterministic
demo dataset), ESTIMATED (derived approximation), UNAVAILABLE.

No provider fabricates prices, opening hours, phone numbers or booking URLs.
"""
