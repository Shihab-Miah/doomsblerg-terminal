"""
DoomsBlerg Plain English Command Interpreter (Phase 4)
======================================================
Deterministic pattern parser first (< 1ms, 0 AI tokens), with optional light
multi-cloud LLM intent classification fallback for free-form natural questions.
Also gently maps legacy Bloomberg codes (`DES`, `FA`, `YCRV`, etc.) to plain English.
"""

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.agents import (
    audit_filing,
    daily_pick_scan,
    debate_stock,
    llm_router,
    morning_briefing,
)
from backend.compute_engine import (
    analyze_options_chain,
    analyze_stock_risk,
    analyze_technicals,
    compute_bond_metrics,
    compute_fundamental_snapshot,
    score_headlines,
    score_stock,
    screen_watchlist,
)
from backend.data_engine.router import router
from geospatial.gods_eye import scan_gods_eye_triggers

COMPANY_NAME_TO_TICKER: Dict[str, str] = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "amazon": "AMZN",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "meta": "META",
    "facebook": "META",
    "netflix": "NFLX",
    "amd": "AMD",
    "intel": "INTC",
    "tsmc": "TSM",
    "taiwan semiconductor": "TSM",
    "broadcom": "AVGO",
    "palantir": "PLTR",
    "coinbase": "COIN",
    "jpmorgan": "JPM",
    "goldman": "GS",
    "exxon": "XOM",
    "chevron": "CVX",
    "walmart": "WMT",
    "costco": "COST",
    "target": "TGT",
    "disney": "DIS",
    "boeing": "BA",
    "fedex": "FDX",
    "ups": "UPS",
    "s&p": "SPY",
    "s&p 500": "SPY",
    "nasdaq": "QQQ",
    "bitcoin": "BTC",
    "btc": "BTC",
    "ethereum": "ETH",
    "eth": "ETH",
    "solana": "SOL",
}

BLOOMBERG_TO_PLAIN: Dict[str, Tuple[str, str]] = {
    "des": ("about", "Company Overview"),
    "fa": ("financials", "Financial Statements"),
    "gp": ("history", "Price Chart"),
    "ee": ("forecasts", "Earnings & Analyst Forecasts"),
    "ern": ("forecasts", "Earnings Summary & Ratings"),
    "insdr": ("insiders", "Insider Form 4 Activity"),
    "cf": ("filings", "SEC Company Filings"),
    "rv": ("compare", "Relative Peer Valuation"),
    "srch": ("best_picks", "Quant Stock Screener"),
    "dcf": ("valuation", "Discounted Cash Flow Fair Value"),
    "wacc": ("valuation", "Cost of Capital & Fair Value"),
    "beta": ("risk", "Beta & Risk Analytics"),
    "omon": ("options", "Options Chain Monitor"),
    "ovme": ("options_greeks", "Options Greeks & Implied Volatility"),
    "eco": ("macro", "Economic Macro Dashboard"),
    "ecst": ("macro", "Inflation & Jobs Stats"),
    "btmm": ("macro", "Interest Rates & SOFR"),
    "ycrv": ("yield_curve", "US Treasury Yield Curve"),
    "fxc": ("fx", "FX Currency Rates"),
    "coms": ("commodities", "Commodities Monitor"),
    "top": ("news", "Top Financial Headlines"),
    "n": ("news", "Financial News"),
}

_STOPWORDS = {
    "I", "A", "AN", "THE", "IS", "ARE", "DO", "DOES", "DID", "CAN", "COULD", "WOULD", "SHOULD",
    "WHAT", "WHICH", "WHO", "WHERE", "WHEN", "WHY", "HOW", "SHOW", "ME", "TELL", "CHECK", "GET",
    "GIVE", "RUN", "OPEN", "WATCH", "FIND", "LOOK", "COMPARE", "VS", "VERSUS", "TO", "AND", "OR",
    "FOR", "OF", "ON", "IN", "AT", "BY", "WITH", "ABOUT", "TODAY", "NOW", "THIS", "MY", "STOCK",
    "STOCKS", "SHARE", "SHARES", "PRICE", "CHART", "BUY", "SELL", "HOLD", "DEBATE", "AUDIT",
    "RISK", "MACRO", "NEWS", "OIL", "GOLD", "CORN", "WHEAT", "RATES", "RATE", "INFLATION",
    "CPI", "GDP", "USD", "EUR", "GBP", "JPY", "CAD", "CHF", "AUD", "CNY", "NYC", "DC", "LA",
    "FIRE", "FIRES", "QUAKES", "SHIPS", "FLIGHTS", "HELP", "COMMANDS", "US", "UK", "EU", "AI",
    "ETF", "ALL", "HIGH", "LOW", "BEST", "TOP", "PICKS", "MOOD", "MARKET", "WORLD", "GLOBE",
    "REPORT", "REPORTS", "FILING", "FILINGS", "FORM", "EARNINGS", "FORECAST", "FORECASTS",
    "FINANCIALS", "FAIR", "VALUE", "VALUATION", "OPTIONS", "CALLS", "PUTS", "GREEKS", "VOLATILITY",
    "INVERTED", "CURVE", "YIELD", "TREASURY", "WEATHER", "CLIMATE", "SATELLITES", "CHOKEPOINTS",
    "HORMUZ", "SUEZ", "PANAMA", "SINGAPORE", "TAIWAN", "LONDON", "DUBAI", "BULL", "BEAR",
    "TECHNICALS", "SCORE", "SCREEN", "BOND", "CRYPTO", "PERPS", "FUNDING",
}

_CRYPTO_TICKERS = {"BTC", "ETH", "SOL", "DOGE", "XRP", "AVAX"}
_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CAD", "CHF", "AUD", "CNY", "INR", "KRW"}
_PRESET_FLIGHT_HUBS = ("nyc", "dc", "la", "london", "taiwan", "dubai")
_CHOKEPOINT_TERMS = ("hormuz", "malacca", "suez", "panama", "la", "rotterdam", "singapore", "gulf", "black sea")
_MACRO_TERMS = (
    ("core inflation", "core inflation"),
    ("core pce", "core pce"),
    ("inflation", "inflation"),
    ("cpi", "cpi"),
    ("interest rate", "interest rate"),
    ("fed funds", "fed funds"),
    ("fed rate", "interest rate"),
    ("unemployment", "unemployment"),
    ("jobs", "unemployment"),
    ("gdp", "gdp"),
    ("sofr", "sofr"),
    ("vix", "vix"),
    ("fear index", "vix"),
    ("mortgage", "mortgage rate"),
    ("high yield", "high yield spread"),
    ("credit spread", "high yield spread"),
    ("dollar index", "dollar index"),
    ("m2", "m2 money supply"),
    ("retail sales", "retail sales"),
    ("consumer sentiment", "consumer sentiment"),
)


def _extract_tickers(text: str) -> List[str]:
    """Extract ordered stock/crypto tickers from explicit symbols or company names."""
    found: List[str] = []
    seen = set()

    def _add(sym: str) -> None:
        if sym not in seen:
            seen.add(sym)
            found.append(sym)

    # 1. Explicit $TICKER tags first
    for m in re.findall(r"\$([A-Za-z]{1,5})", text):
        _add(m.upper())

    # 2. Match known company names ordered left-to-right (longest alias wins on overlaps)
    low = text.lower()
    name_matches: List[Tuple[int, str]] = []
    occupied: set[int] = set()
    for name in sorted(COMPANY_NAME_TO_TICKER.keys(), key=len, reverse=True):
        for m in re.finditer(rf"\b{re.escape(name)}\b", low):
            span_idxs = set(range(m.start(), m.end()))
            if span_idxs & occupied:
                continue
            occupied.update(span_idxs)
            name_matches.append((m.start(), COMPANY_NAME_TO_TICKER[name]))
    for _, sym in sorted(name_matches, key=lambda x: x[0]):
        _add(sym)

    # 3. Uppercase standalone ticker tokens in user's input (excluding stopwords/currencies/Bloomberg mnemonics)
    for tok in re.findall(r"\b[A-Z]{2,5}(?:-[A-Z])?\b", text):
        if tok not in _STOPWORDS and tok.lower() not in BLOOMBERG_TO_PLAIN and tok not in _CURRENCIES:
            _add(tok)

    # 4. Also handle short lowercase command syntax like "price aapl" or "compare aapl msft"
    words = re.findall(r"\b[a-zA-Z]{2,5}\b", text)
    if not found and 2 <= len(words) <= 4:
        for w in words[1:]:
            up = w.upper()
            if up not in _STOPWORDS and w.lower() not in BLOOMBERG_TO_PLAIN and up not in _CURRENCIES:
                _add(up)

    return found


def _has_any(low: str, phrases: Tuple[str, ...]) -> bool:
    """Word-boundary matcher preventing substring false positives like 'rsi' in 'inversion'."""
    for raw_p in phrases:
        p = raw_p.strip()
        if p.endswith("*"):
            pat = rf"\b{re.escape(p[:-1])}"
        else:
            pat = rf"\b{re.escape(p)}\b"
        if re.search(pat, low):
            return True
    return False


def parse_plain_command(query_text: str) -> Optional[Dict[str, Any]]:
    """
    Deterministically map a plain English query (or Bloomberg legacy code) to an exact
    DoomsBlerg intent + arguments. Returns None if unrecognized so AI fallback can classify it.
    """
    raw = (query_text or "").strip()
    if not raw:
        return {"intent": "help", "args": [], "hint": "Show all available plain-English commands."}

    low = raw.lower()
    tokens = re.findall(r"[a-zA-Z0-9$=/-]+", low)
    tickers = _extract_tickers(raw)
    lead_ticker = tickers[0] if tickers else None

    # 1. Exact legacy Bloomberg code support (e.g. "DES AAPL", "FA TSLA", "YCRV")
    first_tok = tokens[0] if tokens else ""
    if first_tok in BLOOMBERG_TO_PLAIN and len(tokens) <= 4:
        mapped_intent, desc = BLOOMBERG_TO_PLAIN[first_tok]
        return {
            "intent": mapped_intent,
            "args": tickers or tokens[1:],
            "hint": f"Mapped Bloomberg '{first_tok.upper()}' -> Plain English: {desc}",
        }

    # 2. Help / system status
    if _has_any(low, ("help", "what can you do", "list commands", "show commands", "command dictionary")):
        return {"intent": "help", "args": [], "hint": "Plain-English Command Directory"}
    if _has_any(low, ("ai health", "gateway health", "model status", "cooldown", "cooldowns")):
        return {"intent": "ai_health", "args": [], "hint": "4-Cloud AI Gateway & Circuit-Breaker Status"}
    if _has_any(low, ("api keys", "key inventory", "check keys")) or low == "keys":
        return {"intent": "keys", "args": [], "hint": "Configured Free API Keys"}

    # 3. AI Agent Council (high priority before generic stock info)
    if _has_any(low, ("morning briefing", "what should i watch*", "daily briefing", "briefing")):
        return {"intent": "briefing", "args": [], "hint": "Morning Command Center Briefing"}
    if _has_any(low, ("best pick*", "what should i buy", "top pick*", "stock screener", "screen", "best stocks", "what to buy")):
        return {"intent": "best_picks", "args": tickers, "hint": "Quant Pre-Filter + AI Top Pick"}
    if _has_any(low, ("debate", "bull vs bear", "buy or sell", "should i buy", "should i sell", "investment committee")):
        return {"intent": "debate", "args": [lead_ticker or "AAPL"], "hint": "8-Agent Buy/Sell Committee Debate"}
    if _has_any(low, ("audit filing", "read 10k", "read 10-k", "10-k red flag*", "10q red flag*", "red flags")) or first_tok == "audit":
        return {"intent": "audit", "args": [lead_ticker or "AAPL"], "hint": "AI SEC 10-K/10-Q Risk Auditor"}

    # 4. Geospatial / God's Eye View
    if _has_any(low, ("gods eye", "god's eye", "open globe", "world map", "watch the world", "physical signal*")):
        return {"intent": "gods_eye", "args": [], "hint": "God's Eye View Physical-World Alpha Scanner"}
    if _has_any(low, ("wildfire*", "on fire", "fires near", "bushfire*")):
        return {"intent": "wildfires", "args": [], "hint": "NASA FIRMS Commodity & Oil Wildfire Monitor"}
    if _has_any(low, ("earthquake*", "quake*", "seismic")):
        return {"intent": "earthquakes", "args": [], "hint": "USGS Seismic Disruption Watch"}
    if _has_any(low, ("flight*", "aircraft", "executive jet*", "corporate jet*", "adsb", "plane*")):
        hub = next((h for h in _PRESET_FLIGHT_HUBS if re.search(rf"\b{h}\b", low)), "taiwan" if "taiwan" in low else ("dc" if "washington" in low else "nyc"))
        return {"intent": "flights", "args": [hub], "hint": f"Live ADS-B Flight & Executive Jet Radar ({hub.upper()})"}
    if _has_any(low, ("chokepoint*", "suez", "panama canal", "malacca")):
        return {"intent": "chokepoints", "args": [], "hint": "Maritime Trade Chokepoints"}
    if _has_any(low, ("ship*", "tanker*", "vessel*", "ais", "port traffic", "hormuz", "singapore")):
        cp = next((c for c in _CHOKEPOINT_TERMS if re.search(rf"\b{re.escape(c)}\b", low)), "Singapore")
        return {"intent": "ships", "args": [cp], "hint": f"AIS Maritime Vessel Snapshot ({cp})"}
    if _has_any(low, ("satellite*", "celestrak", "starlink", "orbit*")):
        return {"intent": "satellites", "args": ["stations"], "hint": "CelesTrak Satellite Orbital Catalog"}
    if _has_any(low, ("climate dataset*", "noaa")):
        return {"intent": "climate", "args": [], "hint": "NOAA Climate Data Online Catalog"}
    if _has_any(low, ("weather", "rain", "temperature", "drought")):
        return {"intent": "weather", "args": [], "hint": "Open-Meteo Global / Corn Belt 7-Day Forecast"}

    # 5. Macro, FX, Energy, Crops, Crypto
    if _has_any(low, ("yield curve", "inverted", "treasury curve")):
        return {"intent": "yield_curve", "args": [], "hint": "US Treasury Daily Yield Curve & Recession Spreads"}
    if _has_any(low, ("oil inventory", "oil stocks", "crude inventory", "eia", "petroleum stocks")):
        return {"intent": "energy", "args": [], "hint": "EIA Weekly Commercial Crude Oil Inventories"}
    if _has_any(low, ("corn", "soybean*", "usda", "crop*")) and not _has_any(low, ("commodit*",)):
        crop = "SOYBEANS" if "soy" in low else ("WHEAT" if "wheat" in low else "CORN")
        return {"intent": "crops", "args": [crop], "hint": f"USDA NASS Crop Report ({crop})"}
    if _has_any(low, ("commodit*", "oil price", "gold price", "silver price", "natural gas", "copper price", "wheat price")):
        return {"intent": "commodities", "args": [], "hint": "Global Energy, Metals & Agriculture Prices"}

    fx_match = re.search(r"\b([a-z]{3})\s*(?:to|/|vs)\s*([a-z]{3})\b", low)
    if fx_match and fx_match.group(1).upper() in _CURRENCIES and fx_match.group(2).upper() in _CURRENCIES:
        return {"intent": "fx", "args": [fx_match.group(1).upper(), fx_match.group(2).upper()], "hint": "Live FX Exchange Rates"}
    if _has_any(low, ("forex", "fx", "currency", "currencies", "exchange rate*")):
        return {"intent": "fx", "args": ["USD"], "hint": "FX Currency Rate Matrix"}

    for phrase, series_name in _MACRO_TERMS:
        if _has_any(low, (f"{phrase}*",)) and not lead_ticker:
            return {"intent": "macro", "args": [series_name], "hint": f"Federal Reserve Macro Indicator ({series_name})"}
    if _has_any(low, ("macro dashboard", "economy", "economic")) or first_tok == "macro":
        return {"intent": "macro", "args": ["dashboard"], "hint": "US Federal Reserve Macro Dashboard"}

    if _has_any(low, ("crypto", "perp*", "funding rate*")) or (lead_ticker in _CRYPTO_TICKERS and first_tok not in ("news", "sentiment")):
        c_syms = [t for t in tickers if t in _CRYPTO_TICKERS] or ["BTC", "ETH", "SOL"]
        return {"intent": "crypto", "args": c_syms, "hint": "Hyperliquid Crypto Perpetuals"}

    # 6. Peer comparison & equity workflows
    if _has_any(low, ("compare", "vs", "versus", "rivals", "peers")) and len(tickers) >= 2:
        return {"intent": "compare", "args": tickers, "hint": "Peer Comparison & Relative Valuation"}
    if _has_any(low, ("market mood", "sentiment", "fear and greed")):
        return {"intent": "sentiment", "args": [lead_ticker] if lead_ticker else [], "hint": "Financial News Sentiment Score"}
    if _has_any(low, ("news", "headline*")):
        return {"intent": "news", "args": [lead_ticker] if lead_ticker else [], "hint": "Real-Time Financial Headlines"}
    if _has_any(low, ("insider*", "who is buying", "executives buying", "form 4")):
        return {"intent": "insiders", "args": [lead_ticker or "AAPL"], "hint": "SEC Form 4 Insider Transactions"}
    if _has_any(low, ("annual report*", "10k", "10-k", "10q", "10-q", "filing*")):
        return {"intent": "filings", "args": [lead_ticker or "AAPL"], "hint": "Official SEC EDGAR Filings"}
    if _has_any(low, ("financial*", "income statement", "balance sheet", "cash flow", "revenue")):
        return {"intent": "financials", "args": [lead_ticker or "AAPL"], "hint": "Financial Statements"}
    if _has_any(low, ("forecast*", "analyst*", "wall street expect*", "price target*", "earnings")):
        return {"intent": "forecasts", "args": [lead_ticker or "AAPL"], "hint": "Wall Street Consensus & Ratios"}
    if _has_any(low, ("greeks", "implied volatility", "black scholes", "black-scholes")):
        return {"intent": "options_greeks", "args": [lead_ticker or "AAPL"], "hint": "Options Greeks & Implied Volatility"}
    if _has_any(low, ("option*", "calls and puts", "call and put", "calls", "puts")):
        return {"intent": "options", "args": [lead_ticker or "AAPL"], "hint": "Live Options Chain"}
    if _has_any(low, ("dcf", "fair value", "intrinsic", "wacc", "cost of capital", "undervalued", "overvalued", "valuation")):
        return {"intent": "valuation", "args": [lead_ticker or "AAPL"], "hint": "DCF Fair Value, WACC, Z-Score & F-Score"}
    if _has_any(low, ("technical*", "rsi", "macd", "bollinger", "vwap", "moving average*", "support", "resistance", "atr")):
        return {"intent": "technicals", "args": [lead_ticker or "AAPL"], "hint": "Technical Indicators & Stop-Loss Levels"}
    if _has_any(low, ("risk", "sharpe", "drawdown", "var", "beta", "volatile", "volatility")):
        return {"intent": "risk", "args": [lead_ticker or "AAPL"], "hint": "Risk & Volatility vs S&P 500"}
    if _has_any(low, ("score",)) and lead_ticker:
        return {"intent": "score", "args": [lead_ticker], "hint": "Quant 0-100 Score & Dossier"}
    if _has_any(low, ("about", "who is", "overview", "profile")) and lead_ticker:
        return {"intent": "about", "args": [lead_ticker], "hint": "Company Profile"}
    if _has_any(low, ("chart*", "candle*", "history", "historical")) and lead_ticker:
        return {"intent": "history", "args": [lead_ticker, "3mo"], "hint": "Historical OHLCV Price Bars"}
    if first_tok == "bond" or _has_any(low, ("bond duration", "bond price")):
        return {"intent": "bond", "args": [], "hint": "Fixed-Income Bond Pricing & Duration"}
    if lead_ticker and _has_any(low, ("price", "quote", "how much", "trading at")):
        return {"intent": "price", "args": [lead_ticker], "hint": "Cross-Verified Stock Quote"}
    if len(tokens) == 1 and lead_ticker:
        return {"intent": "score", "args": [lead_ticker], "hint": f"Complete Quant & Summary Snapshot for {lead_ticker}"}

    return None


def list_supported_commands() -> Dict[str, Any]:
    """Return user-friendly plain English command directory & legacy code aliases."""
    return {
        "examples": [
            "price AAPL",
            "about Nvidia",
            "financials Apple",
            "compare AAPL to MSFT NVDA",
            "fair value Tesla",
            "technicals NVDA",
            "options greeks AAPL",
            "who is buying TSLA",
            "audit filing AAPL",
            "debate Tesla",
            "best picks AAPL NVDA MSFT",
            "morning briefing",
            "yield curve",
            "show inflation",
            "usd to eur",
            "commodities",
            "oil inventory",
            "what is on fire",
            "recent quakes near taiwan",
            "flights near nyc",
            "ships near hormuz",
            "gods eye view",
        ],
        "legacy_bloomberg_aliases": {k.upper(): v[1] for k, v in BLOOMBERG_TO_PLAIN.items()},
    }


def _execute_intent(intent: str, args: List[str]) -> Any:
    sym = args[0] if args else "AAPL"
    handlers: Dict[str, Callable[[], Any]] = {
        "help": list_supported_commands,
        "keys": router.key_inventory,
        "ai_health": llm_router.gateway_health,
        "price": lambda: router.price(sym),
        "about": lambda: router.about(sym),
        "history": lambda: router.history(sym, range_str=args[1] if len(args) > 1 else "3mo"),
        "financials": lambda: router.financials(sym),
        "forecasts": lambda: router.forecasts(sym),
        "compare": lambda: router.peers(args if len(args) >= 2 else ["AAPL", "MSFT", "NVDA"]),
        "options": lambda: router.options(sym, limit=15),
        "options_greeks": lambda: analyze_options_chain(sym, limit=12),
        "filings": lambda: router.filings(sym),
        "insiders": lambda: router.insiders(sym),
        "valuation": lambda: compute_fundamental_snapshot(sym),
        "technicals": lambda: analyze_technicals(sym, range_str=args[1] if len(args) > 1 else "6mo"),
        "risk": lambda: analyze_stock_risk(sym, benchmark=args[1] if len(args) > 1 else "SPY"),
        "sentiment": lambda: score_headlines(router.news(args[0] if args else None, limit=15)),
        "score": lambda: score_stock(sym)["compact_ai_dossier"],
        "screen": lambda: screen_watchlist(args or ["AAPL", "NVDA", "MSFT"]),
        "yield_curve": router.yield_curve,
        "macro": lambda: router.macro(" ".join(args) if args else "dashboard"),
        "fx": lambda: router.fx(
            base=args[0] if args else "USD",
            targets=[args[1]] if len(args) > 1 else None,
        ),
        "commodities": router.commodities,
        "energy": router.energy_inventories,
        "crops": lambda: router.crops(args[0] if args else "CORN"),
        "climate": router.climate,
        "weather": router.weather,
        "wildfires": router.wildfires,
        "earthquakes": router.earthquakes,
        "flights": lambda: router.flights(args[0] if args else "nyc"),
        "ships": lambda: router.ships(args[0] if args else "Singapore"),
        "chokepoints": router.chokepoints,
        "satellites": lambda: router.satellites(args[0] if args else "stations"),
        "gods_eye": scan_gods_eye_triggers,
        "news": lambda: router.news(args[0] if args else None, limit=15),
        "crypto": lambda: router.crypto_perps(args or None),
        "bond": lambda: compute_bond_metrics(),
        "debate": lambda: debate_stock(sym),
        "audit": lambda: audit_filing(sym),
        "briefing": morning_briefing,
        "best_picks": lambda: daily_pick_scan(args or None),
    }
    if intent not in handlers:
        raise ValueError(f"Unsupported command intent: {intent}")
    return handlers[intent]()


def _classify_with_ai(query_text: str) -> Dict[str, Any]:
    """Use the light 4-cloud router ONLY when deterministic plain-English parsing finds no match."""
    sys_prompt = (
        "Classify the financial/market question into JSON ONLY with keys: "
        '{"intent": one of ["price","about","financials","forecasts","compare","valuation","technicals",'
        '"options","options_greeks","risk","sentiment","insiders","filings","yield_curve","macro","fx",'
        '"commodities","energy","crops","weather","wildfires","earthquakes","flights","ships","satellites",'
        '"gods_eye","news","crypto","debate","audit","briefing","best_picks","help"], '
        '"args": list of strings such as ticker symbols or macro indicator names}.'
    )
    resp = llm_router.generate(
        role="macro",
        system_prompt=sys_prompt,
        user_prompt=query_text,
        max_tokens=200,
        temperature=0.0,
        expect_json=True,
    )
    parsed = resp.get("json") or {}
    return {
        "intent": parsed.get("intent", "help"),
        "args": parsed.get("args") or [],
        "hint": f"Classified via {resp['provider_used']}:{resp['model_used']}",
    }


def run_command(query_text: str, allow_ai_fallback: bool = True) -> Dict[str, Any]:
    """Parse a natural plain-English command and execute the corresponding DoomsBlerg subsystem."""
    parsed = parse_plain_command(query_text)
    match_mode = "deterministic_rules"

    if parsed is None:
        if not allow_ai_fallback:
            return {
                "query": query_text,
                "intent": "unknown",
                "match_mode": "unmatched",
                "error": "Could not match plain-English query.",
                "suggestions": list_supported_commands()["examples"],
            }
        try:
            parsed = _classify_with_ai(query_text)
            match_mode = "ai_intent_classifier"
        except Exception as exc:
            return {
                "query": query_text,
                "intent": "unknown",
                "match_mode": "unmatched",
                "error": str(exc),
                "suggestions": list_supported_commands()["examples"],
            }

    intent = parsed["intent"]
    args = [str(a) for a in (parsed.get("args") or [])]
    result = _execute_intent(intent, args)
    return {
        "query": query_text,
        "intent": intent,
        "args": args,
        "match_mode": match_mode,
        "plain_english_hint": parsed.get("hint", ""),
        "result": result,
    }
