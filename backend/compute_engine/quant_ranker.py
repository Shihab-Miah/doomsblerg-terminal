"""
DoomsBlerg Deterministic Quant Stock Ranker (Stage 1 Funnel)
============================================================
Filters and scores stocks 0-100 using ONLY pure Python math — zero AI tokens!
Produces both human-readable Buy/Hold/Sell signals and a compact ~500-token
JSON dossier ready for Phase 3's 4-Cloud AI Council.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from backend.data_engine.commodities_geo import get_market_news
from backend.data_engine.equities import get_analyst_forecasts
from backend.data_engine.sec_intelligence import get_insider_activity

from .fundamentals import compute_fundamental_snapshot
from .portfolio_risk import analyze_stock_risk
from .sentiment import score_headlines
from .technicals import analyze_technicals


def _score_valuation(dcf: Dict[str, Any]) -> float:
    """0-25 pts based on DCF upside %."""
    upside = dcf.get("upside_pct")
    if upside is None:
        return 10.0
    # -30% upside -> 0 pts, 0% -> 12.5 pts, +30%+ upside -> 25 pts
    clamped = max(-30.0, min(float(upside), 30.0))
    return round(((clamped + 30.0) / 60.0) * 25.0, 2)


def _score_quality(f_score_res: Dict[str, Any], z_score_res: Dict[str, Any]) -> float:
    """0-20 pts from Piotroski F-Score (0-12) + Altman Z-Score safety (0-8)."""
    f_val = f_score_res.get("f_score")
    f_pts = (float(f_val) / 9.0) * 12.0 if f_val is not None else 6.0

    z_zone = z_score_res.get("zone")
    z_pts = 8.0 if z_zone == "safe_zone" else (4.0 if z_zone == "grey_zone" else (0.0 if z_zone == "distress_zone" else 4.0))
    return round(f_pts + z_pts, 2)


def _score_technicals(tech: Dict[str, Any]) -> float:
    """0-20 pts from trend alignment, RSI sweet spot, and MACD direction."""
    pts = 0.0
    trend = tech.get("trend")
    pts += 8.0 if trend == "bullish" else (4.0 if trend == "mixed" else 0.0)

    rsi_val = tech.get("rsi_14")
    if rsi_val is not None:
        # Ideal momentum without extreme overbought; oversold bounce also rewarded
        if 40 <= rsi_val <= 65:
            pts += 6.0
        elif 30 <= rsi_val < 40:
            pts += 5.0
        elif rsi_val < 30:
            pts += 4.5
        elif 65 < rsi_val <= 75:
            pts += 3.0
        else:
            pts += 1.0
    else:
        pts += 3.0

    macd_trend = (tech.get("macd") or {}).get("trend")
    pts += 6.0 if macd_trend == "bullish" else 1.5
    return round(pts, 2)


def _score_smart_money(insiders: Dict[str, Any], forecasts: Dict[str, Any]) -> float:
    """0-20 pts from SEC Form 4 insider net flow + Wall Street analyst consensus."""
    pts = 0.0
    sig = insiders.get("signal")
    pts += 9.0 if sig == "bullish_insider_buying" else (5.0 if sig == "neutral" else 2.0)

    rec = forecasts.get("latest_analyst_ratings") or {}
    sb = rec.get("strongBuy") or 0
    b = rec.get("buy") or 0
    h = rec.get("hold") or 0
    s = (rec.get("sell") or 0) + (rec.get("strongSell") or 0)
    total = sb + b + h + s
    if total > 0:
        bull_ratio = (sb + 0.8 * b + 0.4 * h) / total
        pts += round(bull_ratio * 11.0, 2)
    else:
        pts += 5.5
    return round(pts, 2)


def _score_sentiment_and_risk(sent: Dict[str, Any], risk: Dict[str, Any]) -> float:
    """0-15 pts from news sentiment (-1..+1 -> 0-8 pts) and Sharpe ratio (0-7 pts)."""
    s_val = float(sent.get("overall_score") or 0.0)
    s_pts = ((max(-1.0, min(s_val, 1.0)) + 1.0) / 2.0) * 8.0

    sharpe = risk.get("sharpe_ratio")
    if sharpe is not None:
        sh_clamped = max(-0.5, min(float(sharpe), 2.5))
        r_pts = ((sh_clamped + 0.5) / 3.0) * 7.0
    else:
        r_pts = 3.5
    return round(s_pts + r_pts, 2)


def score_stock(ticker: str) -> Dict[str, Any]:
    """
    Run full Phase 2 deterministic analysis on a stock and compute a 0-100 Quant Score
    plus a compact ~500-token dossier for the Phase 3 AI Council.
    """
    ticker = ticker.upper().strip()
    with ThreadPoolExecutor(max_workers=5) as pool:
        fund_fut = pool.submit(compute_fundamental_snapshot, ticker)
        tech_fut = pool.submit(analyze_technicals, ticker, "6mo")
        risk_fut = pool.submit(analyze_stock_risk, ticker, "SPY", "1y")
        ins_fut = pool.submit(get_insider_activity, ticker, 15)
        fc_fut = pool.submit(get_analyst_forecasts, ticker)
        news_fut = pool.submit(get_market_news, ticker, 10)

        fund = fund_fut.result()
        tech = tech_fut.result()
        risk = risk_fut.result()
        try:
            insiders = ins_fut.result()
        except Exception as exc:
            insiders = {"signal": "neutral", "net_insider_shares": 0, "error": str(exc)}
        try:
            forecasts = fc_fut.result()
        except Exception as exc:
            forecasts = {"latest_analyst_ratings": None, "error": str(exc)}
        try:
            articles = news_fut.result()
        except Exception:
            articles = []

    sent = score_headlines(articles)

    dcf = fund.get("dcf_valuation") or {}
    f_score_res = fund.get("piotroski_f_score") or {}
    z_score_res = fund.get("altman_z_score") or {}

    breakdown = {
        "valuation_25": _score_valuation(dcf),
        "quality_safety_20": _score_quality(f_score_res, z_score_res),
        "technical_momentum_20": _score_technicals(tech),
        "smart_money_consensus_20": _score_smart_money(insiders, forecasts),
        "sentiment_risk_15": _score_sentiment_and_risk(sent, risk),
    }
    total_score = round(sum(breakdown.values()), 2)

    if total_score >= 75:
        action = "STRONG BUY CANDIDATE"
    elif total_score >= 60:
        action = "BUY / ACCUMULATE"
    elif total_score >= 45:
        action = "HOLD / WATCH"
    else:
        action = "CAUTION / AVOID"

    # Compact ~500-token JSON payload to send to Phase 3 AI Council
    compact_dossier = {
        "ticker": ticker,
        "quant_score_100": total_score,
        "quant_signal": action,
        "price": fund.get("current_price"),
        "dcf_fair_value": dcf.get("fair_value_per_share"),
        "dcf_upside_pct": dcf.get("upside_pct"),
        "wacc_pct": (fund.get("wacc") or {}).get("wacc_pct"),
        "piotroski_f": f_score_res.get("f_score"),
        "altman_z": z_score_res.get("z_score"),
        "altman_zone": z_score_res.get("zone"),
        "trend": tech.get("trend"),
        "rsi_14": tech.get("rsi_14"),
        "macd_trend": (tech.get("macd") or {}).get("trend"),
        "stop_loss": tech.get("suggested_atr_stop_loss"),
        "target_price": tech.get("suggested_atr_target"),
        "sharpe": risk.get("sharpe_ratio"),
        "max_drawdown_pct": risk.get("max_drawdown_pct"),
        "beta": risk.get("beta_vs_benchmark"),
        "insider_signal": insiders.get("signal"),
        "net_insider_shares": insiders.get("net_insider_shares"),
        "analyst_ratings": forecasts.get("latest_analyst_ratings"),
        "news_sentiment": sent.get("overall_score"),
        "top_headlines": [a.get("title") for a in articles[:5]],
    }

    return {
        "ticker": ticker,
        "quant_score": total_score,
        "signal": action,
        "score_breakdown": breakdown,
        "compact_ai_dossier": compact_dossier,
        "details": {
            "fundamentals": fund,
            "technicals": tech,
            "risk": risk,
            "sentiment": {k: v for k, v in sent.items() if k != "scored"},
        },
    }


def screen_watchlist(tickers: List[str]) -> List[Dict[str, Any]]:
    """Rank multiple tickers in parallel by their 0-100 Quant Score (0 LLM tokens used)."""
    ranked: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(len(tickers), 5)) as pool:
        futs = {t: pool.submit(score_stock, t) for t in tickers}
        for t, fut in futs.items():
            try:
                res = fut.result()
                ranked.append(res["compact_ai_dossier"])
            except Exception as exc:
                ranked.append({"ticker": t.upper(), "quant_score_100": -1, "error": str(exc)})

    ranked.sort(key=lambda x: x.get("quant_score_100", -1), reverse=True)
    return ranked
