"""
DoomsBlerg Web API Route Dispatcher (Zero-Dependency Core)
=========================================================
Pure-Python HTTP router handling REST requests for Phase 1–4 subsystems
(Plain English `/api/ask`, Stocks, Valuation, AI Council Debate, Macro,
FX, Commodities, and God's Eye Geospatial Triggers) without requiring
external frameworks on low-end / Termux runtimes.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.parse

from backend.agents import (
    audit_filing,
    daily_pick_scan,
    debate_stock,
    llm_router,
    morning_briefing,
)
from backend.commands import list_supported_commands, run_command
from backend.compute_engine import (
    analyze_options_chain,
    analyze_stock_risk,
    analyze_technicals,
    compute_fundamental_snapshot,
    score_stock,
)
from backend.data_engine.router import router
from backend.trading import (
    cancel_paper_order,
    check_portfolio_risk,
    get_paper_account,
    get_paper_orders,
    get_paper_positions,
    place_paper_order,
    run_backtest,
)
from geospatial.gods_eye import scan_gods_eye_triggers

API_CATALOG = {
    "GET /": "DoomsBlerg Interactive Web Terminal UI",
    "GET /health": "Gateway health & $0/month low-RAM status",
    "GET /api/endpoints": "List all HTTP endpoints and plain-English command examples",
    "GET /api/keys": "Configured API key readiness (booleans only, zero secrets)",
    "GET /api/ai/health": "4-Cloud AI Router status & active circuit-breaker cooldowns",
    "GET /api/ask?q=...": "Execute any plain-English question (or POST JSON {\"query\": \"...\"})",
    "GET /api/stock/{ticker}/quote": "Cross-verified multi-feed live stock quote",
    "GET /api/stock/{ticker}/overview": "Company profile & sector description",
    "GET /api/stock/{ticker}/history": "OHLCV price history bars (?range=3mo&interval=1d)",
    "GET /api/stock/{ticker}/financials": "Income statement, balance sheet, cash flow",
    "GET /api/stock/{ticker}/valuation": "Deterministic WACC, DCF fair value, Z-Score & F-Score",
    "GET /api/stock/{ticker}/technicals": "RSI, MACD, Bollinger Bands, ATR stop/target",
    "GET /api/stock/{ticker}/risk": "Sharpe, Sortino, Max Drawdown, VaR, Beta vs SPY",
    "GET /api/stock/{ticker}/options": "Options snapshots with Black-Scholes Greeks (?greeks=true)",
    "GET /api/stock/{ticker}/score": "Pure-Python 0-100 Quant Score + AI dossier",
    "GET /api/stock/{ticker}/debate": "Full 8-Agent Buy/Sell Council Verdict",
    "GET /api/stock/{ticker}/audit": "SEC 10-K/10-Q AI risk audit",
    "GET /api/compare?tickers=AAPL,MSFT,NVDA": "Side-by-side peer comparison",
    "GET /api/macro?q=dashboard": "Federal Reserve macro dashboard or specific indicator",
    "GET /api/yield-curve": "US Treasury daily yield curve & inversion spreads",
    "GET /api/fx?base=USD&symbols=EUR,GBP,JPY": "Live FX currency rates",
    "GET /api/commodities": "Energy, metals & grain futures + EIA crude oil delta",
    "GET /api/gods-eye": "Unified God's Eye View physical-world trading triggers",
    "GET /api/briefing": "AI Morning Command Center Briefing",
    "GET /api/best-picks?tickers=AAPL,NVDA,MSFT": "Python quant ranker + AI debate on #1 pick",
    "GET /api/backtest?ticker=AAPL&strategy=sma_cross&range=2y": "Historical strategy backtester vs Buy & Hold",
    "GET /api/paper/account": "Alpaca simulated paper account balances",
    "GET /api/paper/positions": "Open Alpaca paper positions",
    "GET /api/paper/orders": "Recent Alpaca paper orders",
    "GET /api/paper/risk": "Portfolio weighted Beta & crash/rate/oil stress scenarios",
    "POST /api/paper/order": "Preview (`confirm:false`) or execute (`confirm:true`) Alpaca paper order",
    "POST /api/paper/cancel": "Cancel an open Alpaca paper order (`{\"order_id\": \"...\"}`)",
}


def _qp(params: Dict[str, List[str]], key: str, default: str = "") -> str:
    vals = params.get(key)
    if not vals:
        return default
    return str(vals[0]).strip()


def dispatch_api_request(
    method: str,
    raw_path: str,
    query_params: Optional[Dict[str, List[str]]] = None,
    body: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Dict[str, Any]]:
    """
    Route an HTTP request (`method`, `raw_path`, `query_params`, `body`) to the
    corresponding DoomsBlerg handler and return `(status_code, json_payload)`.
    """
    method = method.upper().strip()
    parsed = urllib.parse.urlsplit(raw_path)
    path = parsed.path.rstrip("/") or "/"
    qp = query_params if query_params is not None else urllib.parse.parse_qs(parsed.query)
    payload = body or {}

    try:
        # System & catalog routes
        if method == "GET" and path == "/health":
            return 200, {
                "status": "ok",
                "service": "doomsblerg-terminal",
                "zero_local_ml": True,
                "monthly_cost_usd": 0,
            }
        if method == "GET" and path == "/api/endpoints":
            return 200, {"endpoints": API_CATALOG, "plain_english": list_supported_commands()}
        if method == "GET" and path == "/api/keys":
            return 200, router.key_inventory()
        if method == "GET" and path == "/api/ai/health":
            return 200, llm_router.gateway_health()

        # Plain-English command route
        if path == "/api/ask" and method in ("GET", "POST"):
            q = _qp(qp, "q") or str(payload.get("query") or payload.get("q") or "").strip()
            if not q:
                return 400, {"error": "Missing query text (`q` query param or JSON `query`)."}
            allow_ai = (_qp(qp, "ai_fallback", "true").lower() != "false")
            return 200, run_command(q, allow_ai_fallback=allow_ai)

        # Stock routes: /api/stock/{ticker}/{action}
        parts = [p for p in path.split("/") if p]
        if method == "GET" and len(parts) == 4 and parts[0] == "api" and parts[1] == "stock":
            ticker = parts[2].upper()
            action = parts[3].lower()
            stock_handlers: Dict[str, Callable[[], Any]] = {
                "quote": lambda: router.price(ticker),
                "overview": lambda: router.about(ticker),
                "history": lambda: router.history(
                    ticker,
                    range_str=_qp(qp, "range", "3mo"),
                    interval=_qp(qp, "interval", "1d"),
                ),
                "financials": lambda: router.financials(ticker, limit=int(_qp(qp, "limit", "4"))),
                "forecasts": lambda: router.forecasts(ticker),
                "filings": lambda: router.filings(ticker, limit=int(_qp(qp, "limit", "10"))),
                "insiders": lambda: router.insiders(ticker, limit=int(_qp(qp, "limit", "15"))),
                "valuation": lambda: compute_fundamental_snapshot(ticker),
                "technicals": lambda: analyze_technicals(ticker, range_str=_qp(qp, "range", "6mo")),
                "risk": lambda: analyze_stock_risk(
                    ticker,
                    benchmark=_qp(qp, "benchmark", "SPY"),
                    range_str=_qp(qp, "range", "1y"),
                ),
                "options": lambda: (
                    analyze_options_chain(ticker, limit=int(_qp(qp, "limit", "12")))
                    if _qp(qp, "greeks", "true").lower() == "true"
                    else router.options(ticker, limit=int(_qp(qp, "limit", "20")))
                ),
                "score": lambda: score_stock(ticker),
                "debate": lambda: debate_stock(ticker),
                "audit": lambda: audit_filing(ticker),
            }
            if action in stock_handlers:
                data = stock_handlers[action]()
                return 200, data if isinstance(data, dict) else {"ticker": ticker, action: data}

        # Macro, Market, FX, Commodities, Geospatial & AI Command Center routes
        if method == "GET" and path == "/api/compare":
            raw_tickers = _qp(qp, "tickers", "AAPL,MSFT,NVDA")
            tickers = [t.strip().upper() for t in raw_tickers.split(",") if t.strip()]
            return 200, router.peers(tickers)

        if method == "GET" and path == "/api/macro":
            return 200, router.macro(_qp(qp, "q", "dashboard"))

        if method == "GET" and path == "/api/yield-curve":
            return 200, router.yield_curve()

        if method == "GET" and path == "/api/fx":
            base = _qp(qp, "base", "USD")
            syms_raw = _qp(qp, "symbols", "")
            syms = [s.strip().upper() for s in syms_raw.split(",") if s.strip()] if syms_raw else None
            return 200, router.fx(base=base, targets=syms)

        if method == "GET" and path == "/api/commodities":
            return 200, router.commodities()

        if method == "GET" and path == "/api/gods-eye":
            region = _qp(qp, "region", "nyc")
            cp = _qp(qp, "chokepoint", "Singapore")
            include_ais = _qp(qp, "ais", "true").lower() != "false"
            return 200, scan_gods_eye_triggers(
                flight_region=region,
                ship_chokepoint=cp,
                include_ais_stream=include_ais,
            )

        if method == "GET" and path == "/api/briefing":
            return 200, morning_briefing()

        if method == "GET" and path == "/api/best-picks":
            raw_t = _qp(qp, "tickers", "")
            tickers = [t.strip().upper() for t in raw_t.split(",") if t.strip()] if raw_t else None
            return 200, daily_pick_scan(tickers)

        if method == "GET" and path == "/api/backtest":
            ticker = _qp(qp, "ticker", "AAPL")
            strategy = _qp(qp, "strategy", "sma_cross")
            range_str = _qp(qp, "range", "2y")
            capital = float(_qp(qp, "capital", "10000"))
            stop_raw = _qp(qp, "stop", "8")
            stop_pct = float(stop_raw) if stop_raw and float(stop_raw) > 0 else None
            return 200, run_backtest(
                ticker=ticker,
                strategy=strategy,
                range_str=range_str,
                initial_capital=capital,
                stop_loss_pct=stop_pct,
            )

        if method == "GET" and path == "/api/paper/account":
            return 200, get_paper_account()

        if method == "GET" and path == "/api/paper/positions":
            return 200, get_paper_positions()

        if method == "GET" and path == "/api/paper/orders":
            return 200, get_paper_orders(
                status=_qp(qp, "status", "all"),
                limit=int(_qp(qp, "limit", "20")),
            )

        if method == "GET" and path == "/api/paper/risk":
            return 200, check_portfolio_risk()

        if method == "POST" and path == "/api/paper/order":
            symbol = str(payload.get("symbol") or "").strip().upper()
            if not symbol:
                return 400, {"error": "Missing `symbol` in paper order request."}
            qty = float(payload["qty"]) if payload.get("qty") not in (None, "") else None
            notional = float(payload["notional"]) if payload.get("notional") not in (None, "") else None
            limit_px = float(payload["limit_price"]) if payload.get("limit_price") not in (None, "") else None
            return 200, place_paper_order(
                symbol=symbol,
                qty=qty,
                notional=notional,
                side=str(payload.get("side", "buy")),
                order_type=str(payload.get("type", "market")),
                limit_price=limit_px,
                time_in_force=str(payload.get("time_in_force", "day")),
                confirm=bool(payload.get("confirm", False)),
            )

        if method == "POST" and path == "/api/paper/cancel":
            oid = str(payload.get("order_id") or "").strip()
            return 200, cancel_paper_order(oid)

        return 404, {"error": f"Route not found: {method} {path}", "available": list(API_CATALOG.keys())}
    except ValueError as exc:
        return 400, {"error": str(exc)}
    except Exception as exc:
        return 500, {"error": str(exc)}
