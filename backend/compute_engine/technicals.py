"""
DoomsBlerg Pure-Python Technical Analysis Engine
================================================
Computes SMA, EMA, Wilder's RSI, MACD, Bollinger Bands, ATR, VWAP, and Support/Resistance
without heavy pandas-ta or C-extension dependencies.
"""

import math
from typing import Any, Dict, List, Optional

from backend.data_engine.equities import get_historical_prices


def sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period or period <= 0:
        return None
    return round(sum(values[-period:]) / period, 4)


def ema_series(values: List[float], period: int) -> List[float]:
    """Compute Exponential Moving Average series."""
    if len(values) < period or period <= 0:
        return []
    k = 2.0 / (period + 1.0)
    seed = sum(values[:period]) / period
    out = [seed]
    for price in values[period:]:
        out.append(price * k + out[-1] * (1.0 - k))
    return out


def rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Compute Wilder's Relative Strength Index (0-100)."""
    if len(closes) <= period:
        return None

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas[:period]]
    losses = [max(-d, 0.0) for d in deltas[:period]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    for d in deltas[period:]:
        gain = max(d, 0.0)
        loss = max(-d, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def macd(closes: List[float], fast: int = 12, slow: int = 26, signal_period: int = 9) -> Dict[str, Any]:
    """Compute MACD line, signal line, and histogram."""
    if len(closes) < slow + signal_period:
        return {"macd": None, "signal": None, "histogram": None, "trend": "insufficient_data"}

    ema_fast = ema_series(closes, fast)
    ema_slow = ema_series(closes, slow)
    offset = slow - fast
    macd_line = [ema_fast[i + offset] - ema_slow[i] for i in range(len(ema_slow))]
    sig_line = ema_series(macd_line, signal_period)
    hist = macd_line[-1] - sig_line[-1]

    return {
        "macd": round(macd_line[-1], 4),
        "signal": round(sig_line[-1], 4),
        "histogram": round(hist, 4),
        "trend": "bullish" if hist > 0 else "bearish",
    }


def bollinger_bands(closes: List[float], period: int = 20, num_std: float = 2.0) -> Dict[str, Any]:
    """Compute Bollinger Bands, bandwidth %, and %B price position."""
    if len(closes) < period:
        return {}
    window = closes[-period:]
    mid = sum(window) / period
    var = sum((x - mid) ** 2 for x in window) / period
    std = math.sqrt(var)
    upper = mid + num_std * std
    lower = mid - num_std * std
    bandwidth_pct = ((upper - lower) / mid) * 100.0 if mid > 0 else 0.0
    pct_b = (closes[-1] - lower) / (upper - lower) if upper > lower else 0.5
    return {
        "upper": round(upper, 2),
        "middle": round(mid, 2),
        "lower": round(lower, 2),
        "bandwidth_pct": round(bandwidth_pct, 2),
        "percent_b": round(pct_b, 3),
    }


def atr(bars: List[Dict[str, Any]], period: int = 14) -> Optional[float]:
    """Compute Wilder's Average True Range (ATR) for stop-loss sizing."""
    if len(bars) <= period:
        return None
    trs: List[float] = []
    for i in range(1, len(bars)):
        h = bars[i].get("high") or bars[i]["close"]
        l = bars[i].get("low") or bars[i]["close"]
        prev_c = bars[i - 1]["close"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    val = sum(trs[:period]) / period
    for tr in trs[period:]:
        val = (val * (period - 1) + tr) / period
    return round(val, 4)


def vwap(bars: List[Dict[str, Any]]) -> Optional[float]:
    """Compute Volume-Weighted Average Price across the given bars."""
    pv_sum = 0.0
    vol_sum = 0.0
    for b in bars:
        vol = b.get("volume") or 0
        if vol <= 0:
            continue
        h = b.get("high") or b["close"]
        l = b.get("low") or b["close"]
        tp = (h + l + b["close"]) / 3.0
        pv_sum += tp * vol
        vol_sum += vol
    return round(pv_sum / vol_sum, 4) if vol_sum > 0 else None


def analyze_technicals(ticker: str, range_str: str = "6mo") -> Dict[str, Any]:
    """Compute complete technical indicator suite and plain-English levels for a stock."""
    ticker = ticker.upper().strip()
    bars = get_historical_prices(ticker, range_str=range_str, interval="1d")
    if len(bars) < 35:
        raise RuntimeError(f"Insufficient price history for {ticker} ({len(bars)} bars)")

    closes = [float(b["close"]) for b in bars]
    last_close = closes[-1]
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    sma200 = sma(closes, 200)
    rsi14 = rsi(closes, 14)
    macd_res = macd(closes)
    bb_res = bollinger_bands(closes)
    atr14 = atr(bars, 14)
    vwap_val = vwap(bars[-20:])

    recent_30 = bars[-30:]
    support = min((b.get("low") or b["close"]) for b in recent_30)
    resistance = max((b.get("high") or b["close"]) for b in recent_30)

    if rsi14 is not None and rsi14 >= 70:
        rsi_state = "overbought"
    elif rsi14 is not None and rsi14 <= 30:
        rsi_state = "oversold"
    else:
        rsi_state = "neutral"

    trend_state = "bullish" if (sma20 and sma50 and last_close > sma20 > sma50) else (
        "bearish" if (sma20 and sma50 and last_close < sma20 < sma50) else "mixed"
    )

    suggested_stop = round(last_close - 2.0 * atr14, 2) if atr14 else round(support, 2)
    suggested_target = round(last_close + 3.0 * atr14, 2) if atr14 else round(resistance, 2)

    return {
        "ticker": ticker,
        "last_date": bars[-1]["date"],
        "last_close": round(last_close, 2),
        "trend": trend_state,
        "moving_averages": {"sma_20": sma20, "sma_50": sma50, "sma_200": sma200},
        "rsi_14": rsi14,
        "rsi_state": rsi_state,
        "macd": macd_res,
        "bollinger_bands": bb_res,
        "atr_14": atr14,
        "vwap_20d": vwap_val,
        "support_30d": round(support, 2),
        "resistance_30d": round(resistance, 2),
        "suggested_atr_stop_loss": suggested_stop,
        "suggested_atr_target": suggested_target,
    }
