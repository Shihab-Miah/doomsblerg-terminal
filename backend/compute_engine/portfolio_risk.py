"""
DoomsBlerg Fixed Income & Portfolio Risk Analytics Engine
=======================================================
Computes Bond Clean Price, Macaulay/Modified Duration, Convexity,
plus Portfolio Risk metrics: Sharpe, Sortino, Max Drawdown, VaR (95/99%), CVaR, and Beta.
"""

from concurrent.futures import ThreadPoolExecutor
import math
from typing import Any, Dict, List, Optional

from backend.data_engine.equities import get_historical_prices


def compute_bond_metrics(
    face_value: float = 1000.0,
    coupon_rate: float = 0.05,
    ytm: float = 0.05,
    years_to_maturity: float = 10.0,
    freq: int = 2,
) -> Dict[str, Any]:
    """Compute exact fixed-income bond price, Macaulay/Modified duration, and convexity."""
    periods = int(round(years_to_maturity * freq))
    if periods <= 0 or freq <= 0:
        raise ValueError("years_to_maturity and freq must be positive")

    c = face_value * coupon_rate / freq
    r = ytm / freq

    price = 0.0
    macaulay_num = 0.0
    convexity_num = 0.0

    for t in range(1, periods + 1):
        cf = c + (face_value if t == periods else 0.0)
        df = (1.0 + r) ** (-t)
        pv = cf * df
        price += pv
        t_years = t / freq
        macaulay_num += t_years * pv
        convexity_num += pv * t * (t + 1)

    macaulay_dur = macaulay_num / price if price > 0 else 0.0
    modified_dur = macaulay_dur / (1.0 + r) if (1.0 + r) > 0 else 0.0
    convexity = convexity_num / (price * ((1.0 + r) ** 2) * (freq ** 2)) if price > 0 else 0.0

    return {
        "clean_price": round(price, 4),
        "macaulay_duration_years": round(macaulay_dur, 4),
        "modified_duration_years": round(modified_dur, 4),
        "convexity": round(convexity, 4),
        "pct_price_drop_per_1pct_rate_hike": round(-modified_dur + 0.5 * convexity * 0.01, 2),
    }


def _daily_returns(closes: List[float]) -> List[float]:
    return [(closes[i] / closes[i - 1]) - 1.0 for i in range(1, len(closes)) if closes[i - 1] > 0]


def compute_portfolio_risk(
    daily_returns: List[float],
    benchmark_returns: Optional[List[float]] = None,
    risk_free_annual: float = 0.045,
) -> Dict[str, Any]:
    """Compute Sharpe, Sortino, Max Drawdown, 95%/99% Daily VaR, CVaR, and Beta."""
    n = len(daily_returns)
    if n < 10:
        return {"error": "At least 10 return observations required."}

    mean_d = sum(daily_returns) / n
    ann_return = mean_d * 252.0
    var_d = sum((r - mean_d) ** 2 for r in daily_returns) / max(n - 1, 1)
    vol_d = math.sqrt(var_d)
    ann_vol = vol_d * math.sqrt(252.0)

    sharpe = (ann_return - risk_free_annual) / ann_vol if ann_vol > 0 else 0.0

    rf_daily = risk_free_annual / 252.0
    downside = [min(0.0, r - rf_daily) for r in daily_returns]
    down_dev = math.sqrt(sum(d * d for d in downside) / n) * math.sqrt(252.0)
    sortino = (ann_return - risk_free_annual) / down_dev if down_dev > 0 else 0.0

    # Max Drawdown from cumulative wealth index
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in daily_returns:
        equity *= (1.0 + r)
        peak = max(peak, equity)
        dd = (equity - peak) / peak
        max_dd = min(max_dd, dd)

    sorted_r = sorted(daily_returns)
    idx_95 = max(0, int(math.floor(0.05 * n)))
    idx_99 = max(0, int(math.floor(0.01 * n)))
    var_95 = -sorted_r[idx_95]
    var_99 = -sorted_r[idx_99]
    tail_95 = sorted_r[: max(1, idx_95)]
    cvar_95 = -(sum(tail_95) / len(tail_95))

    beta = None
    if benchmark_returns and len(benchmark_returns) == n:
        bm_mean = sum(benchmark_returns) / n
        cov = sum((daily_returns[i] - mean_d) * (benchmark_returns[i] - bm_mean) for i in range(n)) / max(n - 1, 1)
        bm_var = sum((b - bm_mean) ** 2 for b in benchmark_returns) / max(n - 1, 1)
        if bm_var > 0:
            beta = round(cov / bm_var, 3)

    return {
        "observations": n,
        "annualized_return_pct": round(ann_return * 100, 2),
        "annualized_volatility_pct": round(ann_vol * 100, 2),
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "daily_var_95_pct": round(var_95 * 100, 2),
        "daily_var_99_pct": round(var_99 * 100, 2),
        "daily_cvar_95_pct": round(cvar_95 * 100, 2),
        "beta_vs_benchmark": beta,
    }


def analyze_stock_risk(ticker: str, benchmark: str = "SPY", range_str: str = "1y") -> Dict[str, Any]:
    """Compute live risk analytics for any ticker benchmarked against SPY."""
    ticker = ticker.upper().strip()
    benchmark = benchmark.upper().strip()
    with ThreadPoolExecutor(max_workers=2) as pool:
        s_fut = pool.submit(get_historical_prices, ticker, range_str, "1d")
        b_fut = pool.submit(get_historical_prices, benchmark, range_str, "1d")
        s_bars = s_fut.result()
        b_bars = b_fut.result()

    b_map = {b["date"]: b["close"] for b in b_bars}
    aligned_s: List[float] = []
    aligned_b: List[float] = []
    for bar in s_bars:
        if bar["date"] in b_map:
            aligned_s.append(bar["close"])
            aligned_b.append(b_map[bar["date"]])

    s_ret = _daily_returns(aligned_s)
    b_ret = _daily_returns(aligned_b)
    metrics = compute_portfolio_risk(s_ret, benchmark_returns=b_ret)
    metrics["ticker"] = ticker
    metrics["benchmark"] = benchmark
    return metrics
