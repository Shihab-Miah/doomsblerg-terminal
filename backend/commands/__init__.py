"""
DoomsBlerg Plain English Command Engine (Phase 4)
=================================================
Translates natural everyday English questions (and optional legacy Bloomberg
codes) directly into DoomsBlerg Data, Compute, AI Council, and God's Eye calls.
"""

from .interpreter import (
    BLOOMBERG_TO_PLAIN,
    COMPANY_NAME_TO_TICKER,
    list_supported_commands,
    parse_plain_command,
    run_command,
)

__all__ = [
    "BLOOMBERG_TO_PLAIN",
    "COMPANY_NAME_TO_TICKER",
    "list_supported_commands",
    "parse_plain_command",
    "run_command",
]
