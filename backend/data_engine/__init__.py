"""
DoomsBlerg Terminal — Unified Data Engine (Phase 1)
===================================================
Zero-dependency data normalization, cross-verification, and SQLite TTL cache.
"""

from .router import DoomsBlergRouter, clear_cache, router

__all__ = ["DoomsBlergRouter", "router", "clear_cache"]
