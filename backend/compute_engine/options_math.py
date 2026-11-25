"""
DoomsBlerg Black-Scholes Options & Greeks Compute Engine
======================================================
Pure Python stdlib math (`math.erf`) — zero SciPy/NumPy required.
Computes exact option theoretical values, Delta, Gamma, Theta, Vega, Rho,
and Implied Volatility via Newton-Raphson + Bisection solver.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List

from backend.data_engine.equities import get_options_chain, get_quote_cross_verified
from backend.data_engine.macro_bonds import get_yield_curve

_INV_SQRT_2PI = 1.0 / math.sqrt(2.0 * math.pi)
_SQRT_2 = math.sqrt(2.0)


def _norm_pdf(x: float) -> float:
    return _INV_SQRT_2PI * math.exp(-0.5 * x * x)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / _SQRT_2))


def black_scholes(
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    sigma: float,
    option_type: str = "call",
    dividend_yield: float = 0.0,
) -> Dict[str, Any]:
    """Compute exact European Black-Scholes price and all 5 Greeks."""
    opt = option_type.lower().strip()
    if opt not in ("call", "put"):
        raise ValueError("option_type must be 'call' or 'put'")
    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive")

    T = max(time_years, 1e-6)
    vol = max(sigma, 1e-5)
    sqrt_t = math.sqrt(T)
    disc_q = math.exp(-dividend_yield * T)
    disc_r = math.exp(-rate * T)

    d1 = (math.log(spot / strike) + (rate - dividend_yield + 0.5 * vol * vol) * T) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t

    pdf_d1 = _norm_pdf(d1)
    if opt == "call":
        price = spot * disc_q * _norm_cdf(d1) - strike * disc_r * _norm_cdf(d2)
        delta = disc_q * _norm_cdf(d1)
        theta_annual = (
            -(spot * disc_q * pdf_d1 * vol) / (2.0 * sqrt_t)
            - rate * strike * disc_r * _norm_cdf(d2)
            + dividend_yield * spot * disc_q * _norm_cdf(d1)
        )
        rho_annual = strike * T * disc_r * _norm_cdf(d2)
    else:
        price = strike * disc_r * _norm_cdf(-d2) - spot * disc_q * _norm_cdf(-d1)
        delta = disc_q * (_norm_cdf(d1) - 1.0)
        theta_annual = (
            -(spot * disc_q * pdf_d1 * vol) / (2.0 * sqrt_t)
            + rate * strike * disc_r * _norm_cdf(-d2)
            - dividend_yield * spot * disc_q * _norm_cdf(-d1)
        )
        rho_annual = -strike * T * disc_r * _norm_cdf(-d2)

    gamma = (disc_q * pdf_d1) / (spot * vol * sqrt_t)
    vega_per_1pct = (spot * disc_q * pdf_d1 * sqrt_t) / 100.0
    theta_per_day = theta_annual / 365.0
    rho_per_1pct = rho_annual / 100.0

    return {
        "option_type": opt,
        "theoretical_price": round(price, 4),
        "delta": round(delta, 4),
        "gamma": round(gamma, 5),
        "theta_per_day": round(theta_per_day, 4),
        "vega_per_1pct_iv": round(vega_per_1pct, 4),
        "rho_per_1pct_rate": round(rho_per_1pct, 4),
        "moneyness": "ITM" if ((opt == "call" and spot > strike) or (opt == "put" and spot < strike)) else "OTM",
    }


def implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    option_type: str = "call",
    dividend_yield: float = 0.0,
) -> float:
    """Solve for implied volatility using hybrid Newton-Raphson + bisection."""
    if market_price <= 0 or spot <= 0 or strike <= 0 or time_years <= 0:
        return 0.0

    intrinsic = max(0.0, (spot - strike) if option_type.lower() == "call" else (strike - spot))
    if market_price <= intrinsic:
        return 0.0

    low, high = 0.005, 4.0
    sigma = 0.30

    for _ in range(40):
        bs = black_scholes(spot, strike, time_years, rate, sigma, option_type, dividend_yield)
        diff = bs["theoretical_price"] - market_price
        if abs(diff) < 1e-5:
            return round(sigma, 4)

        vega = bs["vega_per_1pct_iv"] * 100.0
        if diff > 0:
            high = sigma
        else:
            low = sigma

        if vega > 1e-4:
            candidate = sigma - diff / vega
            sigma = candidate if low < candidate < high else 0.5 * (low + high)
        else:
            sigma = 0.5 * (low + high)

    return round(sigma, 4)


def analyze_options_chain(ticker: str, limit: int = 20) -> Dict[str, Any]:
    """Enrich live Alpaca options snapshots with computed Black-Scholes Greeks & IV."""
    ticker = ticker.upper().strip()
    quote = get_quote_cross_verified(ticker)
    spot = float(quote["price"])
    yc = get_yield_curve()
    rf = float((yc.get("yields_pct") or {}).get("3 Mo", 4.35)) / 100.0

    chain = get_options_chain(
        ticker,
        limit=limit,
        strike_min=spot * 0.90,
        strike_max=spot * 1.10,
    )
    today = datetime.now(timezone.utc).date()
    enriched: List[Dict[str, Any]] = []
    calls, puts = 0, 0

    for c in chain.get("contracts", []):
        exp_date = datetime.strptime(c["expiry"], "%Y-%m-%d").date()
        days_to_exp = max((exp_date - today).days, 1)
        T = days_to_exp / 365.0
        bid = c.get("bid") or 0.0
        ask = c.get("ask") or 0.0
        mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else (c.get("last_price") or 0.0)
        iv = c.get("implied_volatility")
        if not iv and mid > 0:
            iv = implied_volatility(mid, spot, c["strike"], T, rf, c["type"])

        greeks = c.get("greeks") or {}
        computed = black_scholes(spot, c["strike"], T, rf, iv or 0.30, c["type"]) if mid > 0 else {}
        if c["type"] == "call":
            calls += 1
        else:
            puts += 1

        enriched.append(
            {
                "contract": c["contract"],
                "expiry": c["expiry"],
                "days_to_expiry": days_to_exp,
                "type": c["type"],
                "strike": c["strike"],
                "market_mid": round(mid, 2),
                "implied_vol_pct": round((iv or 0) * 100, 2) if iv else None,
                "computed_greeks": computed or greeks,
            }
        )

    return {
        "ticker": ticker,
        "spot_price": spot,
        "risk_free_3m_pct": round(rf * 100, 2),
        "sample_calls": calls,
        "sample_puts": puts,
        "contracts": enriched,
    }
