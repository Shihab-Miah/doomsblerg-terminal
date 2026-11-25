"""
DoomsBlerg 8-Agent Buy/Sell Investment Council
==============================================
Combines Phase 1 live data + Phase 2 pure Python math + Phase 3 4-Cloud AI Router.
No LLM calculates numbers; agents debate deterministic data and issue clear
plain-English Buy/Hold/Sell verdicts with stop-losses and price targets.
"""

from concurrent.futures import ThreadPoolExecutor
import json
from typing import Any, Dict, List, Optional

from backend.compute_engine.quant_ranker import score_stock, screen_watchlist
from backend.data_engine.commodities_geo import (
    get_crypto_perps,
    get_energy_inventories,
    get_market_news,
)
from backend.data_engine.equities import get_company_overview
from backend.data_engine.macro_bonds import get_macro_dashboard
from geospatial.earth_events import get_recent_earthquakes, scan_commodity_wildfires

from .filing_rag import extract_key_filing_snippets
from .llm_router import llm_router


def _geospatial_sector_signal(sector: str) -> Dict[str, Any]:
    """Deterministic Python check mapping live fires, quakes, and oil stocks to sector context."""
    sector_low = (sector or "").lower()
    notes: List[str] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        quake_fut = pool.submit(get_recent_earthquakes, 4.5, 3)
        fire_fut = pool.submit(scan_commodity_wildfires)
        oil_fut = pool.submit(get_energy_inventories, 2)

        quakes = quake_fut.result()
        fires = fire_fut.result()
        oil = oil_fut.result()

    hub_alerts = quakes.get("critical_hub_alerts") or []
    if hub_alerts:
        places = [f"M{q['magnitude']} near {q['region_name']}" for q in hub_alerts[:3]]
        notes.append(f"Seismic alerts near critical supply hubs: {', '.join(places)}")

    if fires.get("oil_fire_count", 0) > 0:
        notes.append(f"{fires['oil_fire_count']} satellite fire detections near oil hubs.")
    if fires.get("farm_fire_count", 0) > 0:
        notes.append(f"{fires['farm_fire_count']} satellite fire detections near major crop belts.")

    delta = oil.get("latest_week_change_mbbl")
    if delta is not None:
        direction = oil.get("latest_direction") or ("build" if delta > 0 else "draw")
        notes.append(f"US Commercial Crude Oil inventory weekly change (WCESTUS1): {delta:+} MBBL ({direction}).")

    relevant = "high" if (
        ("tech" in sector_low and any("Taiwan" in str(q) or "Japan" in str(q) for q in hub_alerts))
        or ("energy" in sector_low and (fires.get("oil_fire_count", 0) > 0 or records))
    ) else "background"

    return {"sector_relevance": relevant, "physical_world_signals": notes}


def debate_stock(ticker: str) -> Dict[str, Any]:
    """
    Run the full 8-Agent Investment Committee on a ticker:
      1. Pure-Python Quant + Technicals + Risk (0 LLM tokens)
      2. Pure-Python Geospatial Supply Check (0 LLM tokens)
      3. Macro Economist Agent (Cloud Bucket 1)
      4. Sentiment & Insider Scout (Cloud Bucket 2)
      5. Bull Case Advocate (Cloud Bucket 3)
      6. Bear Case Advocate (Cloud Bucket 4)
      7. Fundamental Auditor Brief (included in dossier / cross-checked)
      8. Risk Officer Judge (Final Plain-English Buy/Sell Verdict)
    """
    ticker = ticker.upper().strip()

    # Stage 1 & 2: Gather all math + macro + overview + SEC risk excerpts concurrently (0 LLM tokens)
    with ThreadPoolExecutor(max_workers=4) as pool:
        quant_fut = pool.submit(score_stock, ticker)
        macro_fut = pool.submit(get_macro_dashboard)
        ov_fut = pool.submit(get_company_overview, ticker)
        sec_fut = pool.submit(extract_key_filing_snippets, ticker, 2, 1100)

        quant = quant_fut.result()
        macro_raw = macro_fut.result()
        try:
            overview_sector = ov_fut.result().get("sector", "")
        except Exception:
            overview_sector = ""
        try:
            sec_snippets = sec_fut.result().get("snippets", [])
        except Exception:
            sec_snippets = []

    geo = _geospatial_sector_signal(overview_sector)
    dossier = quant["compact_ai_dossier"]
    yc = macro_raw.get("yield_curve") or {}
    macro_compact = {
        "fed_funds": (macro_raw.get("interest rate") or {}).get("value"),
        "vix": (macro_raw.get("vix") or {}).get("value"),
        "10y_2y_spread": yc.get("spread_10y_minus_2y"),
        "curve_inverted": yc.get("curve_inverted"),
        "high_yield_spread": (macro_raw.get("high yield spread") or {}).get("value"),
    }

    context_blob = json.dumps(
        {
            "stock_dossier": dossier,
            "sec_filing_risk_excerpts": sec_snippets,
            "macro": macro_compact,
            "geospatial": geo,
        },
        separators=(",", ":"),
    )

    # Stage 3: Run 5 specialist AI agents in parallel across separate cloud buckets
    def _run_auditor() -> Dict[str, Any]:
        return llm_router.generate(
            role="auditor",
            system_prompt="You are a Fundamental SEC Auditor. In 2 plain-English sentences, judge the company's DCF valuation gap, cash flow quality (F-Score), bankruptcy safety (Z-Score), and SEC risk excerpts.",
            user_prompt=context_blob,
            max_tokens=500,
            temperature=0.15,
        )

    def _run_macro() -> Dict[str, Any]:
        return llm_router.generate(
            role="macro",
            system_prompt="You are a Macro Economist. Speak plain English, no jargon. In 2 short sentences, explain whether current interest rates, VIX, and yield curve help or hurt this stock.",
            user_prompt=context_blob,
            max_tokens=500,
            temperature=0.2,
        )

    def _run_sentiment() -> Dict[str, Any]:
        return llm_router.generate(
            role="sentiment",
            system_prompt="You are a Market Mood & Insider Scout. Speak plain English. In 2 short sentences, interpret the news headlines, sentiment score, and insider buying/selling.",
            user_prompt=context_blob,
            max_tokens=500,
            temperature=0.2,
        )

    def _run_bull() -> Dict[str, Any]:
        return llm_router.generate(
            role="bull",
            system_prompt="You are the Bull Case Advocate. Using ONLY the provided numbers (never invent metrics), give 3 concise plain-English reasons why an investor should BUY this stock now.",
            user_prompt=context_blob,
            max_tokens=1000,
            temperature=0.3,
        )

    def _run_bear() -> Dict[str, Any]:
        return llm_router.generate(
            role="bear",
            system_prompt="You are the Bear Case Advocate. Attack this stock using ONLY the provided numbers (valuation gap, insider selling, macro risks, volatility, SEC risks). Give 3 concise plain-English reasons to AVOID or SELL.",
            user_prompt=context_blob,
            max_tokens=1000,
            temperature=0.3,
        )

    with ThreadPoolExecutor(max_workers=5) as pool:
        f_aud = pool.submit(_run_auditor)
        f_macro = pool.submit(_run_macro)
        f_sent = pool.submit(_run_sentiment)
        f_bull = pool.submit(_run_bull)
        f_bear = pool.submit(_run_bear)

        aud_res = f_aud.result()
        macro_res = f_macro.result()
        sent_res = f_sent.result()
        bull_res = f_bull.result()
        bear_res = f_bear.result()

    # Stage 4: Risk Officer (Judge) synthesizes final structured Buy/Sell decision
    judge_prompt = (
        f"STOCK DATA: {context_blob}\n\n"
        f"FUNDAMENTAL AUDITOR ({aud_res['provider_used']}): {aud_res['text']}\n\n"
        f"MACRO ECONOMIST ({macro_res['provider_used']}): {macro_res['text']}\n\n"
        f"SENTIMENT SCOUT ({sent_res['provider_used']}): {sent_res['text']}\n\n"
        f"BULL ADVOCATE ({bull_res['provider_used']}): {bull_res['text']}\n\n"
        f"BEAR ADVOCATE ({bear_res['provider_used']}): {bear_res['text']}"
    )
    judge_sys = (
        "You are the Chief Risk Officer (Judge) of DoomsBlerg Terminal. Speak in clear everyday English. "
        "Weigh the deterministic math, Fundamental Audit, Bull vs Bear arguments, Macro, and Physical World signals. "
        "Return strictly valid JSON with keys: "
        "\"action\" (\"STRONG BUY\"|\"BUY\"|\"HOLD\"|\"SELL\"|\"STRONG SELL\"), "
        "\"confidence_pct\" (integer 0-100), "
        "\"time_horizon\" (e.g. \"1-3 months swing\" or \"6-12 months value\"), "
        "\"plain_english_verdict\" (3 simple sentences explaining what to do and why), "
        "\"biggest_risk\" (1 clear sentence), "
        "\"what_would_change_my_mind\" (1 clear sentence)."
    )
    judge_res = llm_router.generate(
        role="judge",
        system_prompt=judge_sys,
        user_prompt=judge_prompt,
        max_tokens=1100,
        temperature=0.15,
        expect_json=True,
    )

    verdict = judge_res["json"] or {"plain_english_verdict": judge_res["text"]}
    verdict["computed_entry_price"] = dossier.get("price")
    verdict["computed_stop_loss"] = dossier.get("stop_loss")
    verdict["computed_target_price"] = dossier.get("target_price")
    verdict["quant_score_100"] = dossier.get("quant_score_100")

    return {
        "ticker": ticker,
        "verdict": verdict,
        "agents": {
            "1_quant_and_technicals_python": quant["score_breakdown"],
            "2_geospatial_scout_python": geo,
            "3_fundamental_auditor": {"provider": f"{aud_res['provider_used']}:{aud_res['model_used']}", "note": aud_res["text"]},
            "4_macro_economist": {"provider": f"{macro_res['provider_used']}:{macro_res['model_used']}", "note": macro_res["text"]},
            "5_sentiment_scout": {"provider": f"{sent_res['provider_used']}:{sent_res['model_used']}", "note": sent_res["text"]},
            "6_bull_advocate": {"provider": f"{bull_res['provider_used']}:{bull_res['model_used']}", "case": bull_res["text"]},
            "7_bear_advocate": {"provider": f"{bear_res['provider_used']}:{bear_res['model_used']}", "case": bear_res["text"]},
            "8_risk_officer_judge": {"provider": f"{judge_res['provider_used']}:{judge_res['model_used']}"},
        },
        "numbers_dossier": dossier,
    }


def daily_pick_scan(tickers: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Answer 'what is best to buy right now vs what to avoid':
    1. Pure-Python Quant Ranker screens the entire list for 0 AI tokens.
    2. Top ranked stock gets a full AI Risk Officer synthesis.
    """
    watchlist = tickers or ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META"]
    ranked = screen_watchlist(watchlist)
    valid = [r for r in ranked if r.get("quant_score_100", -1) >= 0]
    if not valid:
        return {"error": "No stocks successfully scored.", "raw": ranked}

    top_pick = valid[0]
    weakest = valid[-1]
    debate = debate_stock(top_pick["ticker"])

    return {
        "watchlist_ranked_by_python": [
            {
                "ticker": r["ticker"],
                "quant_score_100": r["quant_score_100"],
                "signal": r["quant_signal"],
                "price": r["price"],
                "dcf_fair_value": r["dcf_fair_value"],
                "trend": r["trend"],
            }
            for r in valid
        ],
        "top_buy_candidate": {"ticker": top_pick["ticker"], **debate["verdict"]},
        "weakest_candidate_watch_out": {
            "ticker": weakest["ticker"],
            "quant_score_100": weakest["quant_score_100"],
            "signal": weakest["quant_signal"],
            "dcf_upside_pct": weakest.get("dcf_upside_pct"),
        },
    }


def morning_briefing() -> Dict[str, Any]:
    """Generate a plain-English daily command center briefing uniting macro, news, crypto, and God's Eye geo."""
    with ThreadPoolExecutor(max_workers=5) as pool:
        mac_fut = pool.submit(get_macro_dashboard)
        news_fut = pool.submit(get_market_news, None, 8)
        perps_fut = pool.submit(get_crypto_perps, ["BTC", "ETH"])
        fire_fut = pool.submit(scan_commodity_wildfires)
        quake_fut = pool.submit(get_recent_earthquakes, 5.0, 2)
        oil_fut = pool.submit(get_energy_inventories, 2)

        macro = mac_fut.result()
        headlines = [n["title"] for n in news_fut.result()]
        crypto = perps_fut.result()
        fires = fire_fut.result()
        quakes = quake_fut.result()
        oil = oil_fut.result()

    summary_payload = {
        "yield_curve": macro.get("yield_curve"),
        "fed_funds": (macro.get("interest rate") or {}).get("value"),
        "vix": (macro.get("vix") or {}).get("value"),
        "crypto": crypto,
        "oil_stocks_mbbl": oil.get("records"),
        "geo_oil_fires": fires.get("oil_fire_count"),
        "geo_farm_fires": fires.get("farm_fire_count"),
        "geo_hub_quakes": quakes.get("critical_hub_alerts"),
        "headlines": headlines,
    }
    resp = llm_router.generate(
        role="macro",
        system_prompt=(
            "You are the DoomsBlerg Morning Anchor. Explain today's markets in simple, everyday English "
            "(no Wall Street slang). Summarize: (1) Interest rates & market fear (VIX), "
            "(2) Top stock/crypto news, (3) Physical world shocks (oil stocks, fires, earthquakes), "
            "and (4) One clear thing traders should watch today."
        ),
        user_prompt=json.dumps(summary_payload, separators=(",", ":")),
        max_tokens=500,
        temperature=0.25,
    )
    return {
        "briefing": resp["text"],
        "provider_used": f"{resp['provider_used']}:{resp['model_used']}",
        "raw_snapshot": summary_payload,
    }
