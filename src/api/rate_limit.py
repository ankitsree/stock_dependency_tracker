"""Shared slowapi `Limiter` (production-roadmap.md §9.4).

A module-level singleton, not something built inside `create_app()`, because
route modules (e.g. `correlations.py`) need to import the same instance to
decorate individual endpoints with a stricter limit — building a fresh
`Limiter` per app would give each router a different one to register against.

In-memory storage (slowapi's default) is deliberate, not a placeholder: this
runs as a single Render instance with no multi-process/multi-region fanout,
so there is no shared state to coordinate. Revisit only if that changes.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Generous default for ordinary browsing (satellite table, graph, ticker
# detail) — high enough that normal frontend use never touches it, low
# enough to blunt casual scraping. Deliberately per-IP: `get_remote_address`
# reads the connecting client's address.
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
