"""
DoomsBlerg Alpaca Paper Trading & Portfolio Stress-Test Engine
==============================================================
Connects strictly to Alpaca's $0/month Paper Trading API (`paper-api.alpaca.markets`)
using stored `ALPACA_API_KEY` + `ALPACA_SECRET_KEY`. Includes dry-run order
validation (`confirm=False` default) and multi-scenario portfolio stress testing.
"""

from concurrent.futures import ThreadPoolExecutor
import json
from typing import Any, Dict, List, Optional

from backend.compute_engine.portfolio_risk import analyze_stock_risk
from backend.compute_engine.technicals import analyze_technicals
from backend.data_engine.config import get_key, require_key
from backend.data_engine.equities import get_quote_cross_verified
from backend.data_engine.http_client import fetch_json, fetch_text

ALPACA_PAPER_BASE = "https://paper-api.alpaca.markets/v2"


def _paper_headers() -> Dict[str, str]:
    api_key = require_key("ALPACA_API_KEY")
    secret = require_key("ALPACA_SECRET_KEY")
    if get_key("ALPACA_PAPER", "true").lower() == "false":
        raise RuntimeError(
            "Safety guard: Live order routing is disabled in Phase 4-7; set ALPACA_PAPER=true."
        )
    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret,
    }


def get_paper_account() -> Dict[str, Any]:
    """Fetch simulated Alpaca paper trading account balances and buying power."""
    data = fetch_json(f"{ALPACA_PAPER_BASE}/account", headers=_paper_headers(), ttl_seconds=0)
    equity = float(data.get("equity") or 0.0)
    last_eq = float(data.get("last_equity") or equity)
    day_pl = equity - last_eq
    day_pl_pct = (day_pl / last_eq) * 100.0 if last_eq > 0 else 0.0
    return {
        "mode": "PAPER_SIMULATED",
        "account_number": data.get("account_number"),
        "status": data.get("status"),
        "currency": data.get("currency", "USD"),
        "cash": round(float(data.get("cash") or 0.0), 2),
        "buying_power": round(float(data.get("buying_power") or 0.0), 2),
        "portfolio_value": round(float(data.get("portfolio_value") or 0.0), 2),
        "equity": round(equity, 2),
        "day_pnl": round(day_pl, 2),
        "day_pnl_pct": round(day_pl_pct, 2),
        "pattern_day_trader": bool(data.get("pattern_day_trader")),
        "trading_blocked": bool(data.get("trading_blocked")),
    }


def get_paper_positions() -> Dict[str, Any]:
    """Fetch currently held positions inside Alpaca paper account."""
    rows = fetch_json(f"{ALPACA_PAPER_BASE}/positions", headers=_paper_headers(), ttl_seconds=0)
    positions: List[Dict[str, Any]] = []
    for p in rows or []:
        positions.append(
            {
                "symbol": p.get("symbol"),
                "qty": float(p.get("qty") or 0),
                "side": p.get("side"),
                "avg_entry_price": round(float(p.get("avg_entry_price") or 0), 2),
                "current_price": round(float(p.get("current_price") or 0), 2),
                "market_value": round(float(p.get("market_value") or 0), 2),
                "unrealized_pl": round(float(p.get("unrealized_pl") or 0), 2),
                "unrealized_pl_pct": round(float(p.get("unrealized_plpc") or 0) * 100.0, 2),
            }
        )
    return {"count": len(positions), "positions": positions}


def get_paper_orders(status: str = "all", limit: int = 20) -> Dict[str, Any]:
    """Fetch recent paper orders (open, closed, or all)."""
    rows = fetch_json(
        f"{ALPACA_PAPER_BASE}/orders",
        params={"status": status, "limit": limit},
        headers=_paper_headers(),
        ttl_seconds=0,
    )
    orders = [
        {
            "id": o.get("id"),
            "symbol": o.get("symbol"),
            "side": o.get("side"),
            "qty": o.get("qty") or o.get("notional"),
            "type": o.get("type"),
            "time_in_force": o.get("time_in_force"),
            "status": o.get("status"),
            "filled_avg_price": o.get("filled_avg_price"),
            "created_at": o.get("created_at"),
        }
        for o in (rows or [])
    ]
    return {"count": len(orders), "orders": orders}


def preview_paper_order(
    symbol: str,
    qty: Optional[float] = None,
    notional: Optional[float] = None,
    side: str = "buy",
    order_type: str = "market",
    limit_price: Optional[float] = None,
    time_in_force: str = "day",
) -> Dict[str, Any]:
    """Run deterministic pre-trade valuation, buying-power check, and ATR stop sizing."""
    symbol = symbol.upper().strip()
    side = side.lower().strip()
    order_type = order_type.lower().strip()
    if side not in ("buy", "sell"):
        raise ValueError("side must be 'buy' or 'sell'")
    if order_type not in ("market", "limit"):
        raise ValueError("order_type must be 'market' or 'limit'")
    if order_type == "limit" and (limit_price is None or limit_price <= 0):
        raise ValueError("limit_price must be positive for limit orders")
    if (qty is None or qty <= 0) and (notional is None or notional <= 0):
        raise ValueError("Specify a positive `qty` or `notional` dollar amount.")

    with ThreadPoolExecutor(max_workers=3) as pool:
        acct_f = pool.submit(get_paper_account)
        quote_f = pool.submit(get_quote_cross_verified, symbol)
        tech_f = pool.submit(analyze_technicals, symbol, "6mo")
        acct = acct_f.result()
        quote = quote_f.result()
        try:
            tech = tech_f.result()
        except Exception:
            tech = {}

    ref_px = float(limit_price if order_type == "limit" and limit_price else quote["price"])
    est_shares = float(qty) if qty else round(float(notional) / ref_px, 4)
    est_cost = round(est_shares * ref_px, 2) if qty else round(float(notional), 2)
    portfolio_val = max(acct["equity"], 1.0)
    weight_pct = round((est_cost / portfolio_val) * 100.0, 2)
    buying_power_ok = True if side == "sell" else est_cost <= acct["buying_power"]

    payload: Dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "time_in_force": time_in_force,
    }
    if qty is not None:
        payload["qty"] = str(qty)
    else:
        payload["notional"] = str(round(float(notional), 2))
    if limit_price is not None and order_type == "limit":
        payload["limit_price"] = str(round(float(limit_price), 2))

    return {
        "submitted": False,
        "mode": "dry_run_preview",
        "order_payload": payload,
        "estimated_shares": est_shares,
        "reference_price": ref_px,
        "estimated_order_value": est_cost,
        "portfolio_weight_pct": weight_pct,
        "buying_power": acct["buying_power"],
        "buying_power_sufficient": buying_power_ok,
        "suggested_atr_stop_loss": tech.get("suggested_atr_stop_loss"),
        "suggested_atr_target": tech.get("suggested_atr_target"),
        "warning": (
            "Order exceeds 25% of simulated account equity; consider smaller position size."
            if weight_pct > 25.0
            else ("Insufficient paper buying power." if not buying_power_ok else None)
        ),
    }


def place_paper_order(
    symbol: str,
    qty: Optional[float] = None,
    notional: Optional[float] = None,
    side: str = "buy",
    order_type: str = "market",
    limit_price: Optional[float] = None,
    time_in_force: str = "day",
    confirm: bool = False,
) -> Dict[str, Any]:
    """
    Preview or execute a simulated Alpaca Paper order.
    Safety lock: defaults to `confirm=False` (preview only) unless explicitly confirmed.
    """
    preview = preview_paper_order(
        symbol=symbol,
        qty=qty,
        notional=notional,
        side=side,
        order_type=order_type,
        limit_price=limit_price,
        time_in_force=time_in_force,
    )
    if not confirm:
        preview["note"] = "Preview only — set confirm=True to submit this simulated paper order to Alpaca."
        return preview
    if not preview["buying_power_sufficient"]:
        raise RuntimeError(
            f"Paper buying power (${preview['buying_power']}) insufficient for ${preview['estimated_order_value']} order."
        )

    order = fetch_json(
        f"{ALPACA_PAPER_BASE}/orders",
        method="POST",
        headers=_paper_headers(),
        json_body=preview["order_payload"],
        ttl_seconds=0,
    )
    return {
        "submitted": True,
        "mode": "PAPER_SIMULATED",
        "order_id": order.get("id"),
        "symbol": order.get("symbol"),
        "side": order.get("side"),
        "qty": order.get("qty") or order.get("notional"),
        "type": order.get("type"),
        "status": order.get("status"),
        "estimated_order_value": preview["estimated_order_value"],
        "suggested_atr_stop_loss": preview["suggested_atr_stop_loss"],
    }


def cancel_paper_order(order_id: str) -> Dict[str, Any]:
    """Cancel an open simulated order in Alpaca Paper."""
    oid = (order_id or "").strip()
    if not oid:
        raise ValueError("order_id is required")
    raw = fetch_text(
        f"{ALPACA_PAPER_BASE}/orders/{oid}",
        method="DELETE",
        headers=_paper_headers(),
        ttl_seconds=0,
    )
    parsed = json.loads(raw) if raw.strip() else {}
    return {"canceled": True, "order_id": oid, "details": parsed}


def check_portfolio_risk(custom_holdings: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Audit portfolio concentration, weighted Beta, and stress-test open holdings under
    crash, rate-hike, and oil-shock scenarios (replaces command-dictionary Risk Check).
    """
    if custom_holdings is not None:
        holdings = custom_holdings
        equity = sum(float(h.get("market_value") or 0) for h in holdings) or 100000.0
        cash = 0.0
        source = "custom_holdings"
    else:
        acct = get_paper_account()
        pos_data = get_paper_positions()
        holdings = pos_data["positions"]
        equity = acct["equity"]
        cash = acct["cash"]
        source = "alpaca_paper_account"

    if not holdings:
        return {
            "source": source,
            "equity": round(equity, 2),
            "cash": round(cash, 2),
            "position_count": 0,
            "weighted_beta": 0.0,
            "concentration_alert": None,
            "stress_scenarios": {
                "market_crash_spy_minus_15pct": {"estimated_pnl": 0.0, "estimated_pct": 0.0},
                "rate_hike_100bps_tech_minus_10pct": {"estimated_pnl": 0.0, "estimated_pct": 0.0},
                "oil_supply_shock_spy_minus_8pct": {"estimated_pnl": 0.0, "estimated_pct": 0.0},
            },
            "plain_english_summary": (
                f"Your simulated portfolio currently holds ${cash:,.2f} in 100% cash with zero open stock exposure."
            ),
        }

    symbols = [h["symbol"] for h in holdings]
    risk_by_sym: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(len(symbols), 5)) as pool:
        futs = {s: pool.submit(analyze_stock_risk, s, "SPY", "1y") for s in symbols}
        for s, f in futs.items():
            try:
                risk_by_sym[s] = f.result()
            except Exception:
                risk_by_sym[s] = {"beta_vs_benchmark": 1.0, "annualized_volatility_pct": 25.0}

    weighted_beta = 0.0
    largest_weight = 0.0
    largest_sym = ""
    invested_value = 0.0
    enriched: List[Dict[str, Any]] = []
    for h in holdings:
        sym = h["symbol"]
        mv = abs(float(h.get("market_value") or 0.0))
        invested_value += mv
        weight = mv / equity if equity > 0 else 0.0
        beta = float((risk_by_sym.get(sym) or {}).get("beta_vs_benchmark") or 1.0)
        sign = -1.0 if h.get("side") == "short" else 1.0
        weighted_beta += sign * weight * beta
        if weight > largest_weight:
            largest_weight = weight
            largest_sym = sym
        enriched.append({"symbol": sym, "weight_pct": round(weight * 100, 1), "beta": round(beta, 2), "market_value": mv})

    crash_pct = round(weighted_beta * -15.0, 2)
    rate_pct = round(max(1.0, weighted_beta) * -8.5 * (invested_value / equity if equity > 0 else 0.0), 2)
    oil_pct = round(weighted_beta * -8.0, 2)

    return {
        "source": source,
        "equity": round(equity, 2),
        "cash": round(cash, 2),
        "position_count": len(holdings),
        "weighted_beta": round(weighted_beta, 3),
        "concentration_alert": (
            f"High concentration: {largest_sym} is {round(largest_weight * 100, 1)}% of total equity."
            if largest_weight >= 0.25
            else None
        ),
        "positions_risk": enriched,
        "stress_scenarios": {
            "market_crash_spy_minus_15pct": {
                "estimated_pnl": round(equity * crash_pct / 100.0, 2),
                "estimated_pct": crash_pct,
            },
            "rate_hike_100bps_shock": {
                "estimated_pnl": round(equity * rate_pct / 100.0, 2),
                "estimated_pct": rate_pct,
            },
            "oil_supply_shock_spy_minus_8pct": {
                "estimated_pnl": round(equity * oil_pct / 100.0, 2),
                "estimated_pct": oil_pct,
            },
        },
        "plain_english_summary": (
            f"Portfolio holds {len(holdings)} position(s) totaling ${invested_value:,.2f} with weighted S&P Beta {weighted_beta:.2f}. "
            f"A 15% market crash would move your account approximately {crash_pct:+.2f}% (${equity * crash_pct / 100.0:+,.2f})."
        ),
    }
