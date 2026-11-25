"""
DoomsBlerg Strategy Backtesting & Alpaca Paper Execution (Phase 6/7 Core)
=========================================================================
Pure-Python zero-lookahead historical backtester + safe Alpaca Paper Trading
brokerage client with pre-trade risk checks and portfolio stress testing.
"""

from .backtester import SUPPORTED_STRATEGIES, run_backtest
from .paper_broker import (
    cancel_paper_order,
    check_portfolio_risk,
    get_paper_account,
    get_paper_orders,
    get_paper_positions,
    place_paper_order,
    preview_paper_order,
)

__all__ = [
    "SUPPORTED_STRATEGIES",
    "run_backtest",
    "get_paper_account",
    "get_paper_positions",
    "get_paper_orders",
    "preview_paper_order",
    "place_paper_order",
    "cancel_paper_order",
    "check_portfolio_risk",
]
