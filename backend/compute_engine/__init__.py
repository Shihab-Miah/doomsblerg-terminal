"""
DoomsBlerg Pure Compute Engine (Phase 2)
========================================
IRON RULE: Zero LLMs run inside this module. Every calculation is deterministic Python math.
"""

from .fundamentals import (
    compute_altman_z_score,
    compute_dcf,
    compute_fundamental_snapshot,
    compute_piotroski_f_score,
    compute_wacc,
)
from .options_math import analyze_options_chain, black_scholes, implied_volatility
from .portfolio_risk import analyze_stock_risk, compute_bond_metrics, compute_portfolio_risk
from .quant_ranker import score_stock, screen_watchlist
from .sentiment import score_headlines, score_text
from .technicals import analyze_technicals, atr, bollinger_bands, macd, rsi, sma, vwap

__all__ = [
    "compute_wacc",
    "compute_dcf",
    "compute_altman_z_score",
    "compute_piotroski_f_score",
    "compute_fundamental_snapshot",
    "black_scholes",
    "implied_volatility",
    "analyze_options_chain",
    "sma",
    "rsi",
    "macd",
    "bollinger_bands",
    "atr",
    "vwap",
    "analyze_technicals",
    "compute_bond_metrics",
    "compute_portfolio_risk",
    "analyze_stock_risk",
    "score_text",
    "score_headlines",
    "score_stock",
    "screen_watchlist",
]
