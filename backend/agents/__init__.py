"""
DoomsBlerg AI Agent Council & 4-Cloud Switcher (Phase 3)
========================================================
Unites Google AI Studio, Groq LPU, OpenRouter, and Kilo AI Gateway
with pure-Python deterministic pre-filtering for $0/month low-RAM operation.
"""

from .council import daily_pick_scan, debate_stock, morning_briefing
from .filing_rag import audit_filing, extract_key_filing_snippets
from .llm_router import MultiCloudLLMRouter, clear_cooldowns, llm_router

__all__ = [
    "MultiCloudLLMRouter",
    "llm_router",
    "clear_cooldowns",
    "extract_key_filing_snippets",
    "audit_filing",
    "debate_stock",
    "daily_pick_scan",
    "morning_briefing",
]
