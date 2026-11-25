"""
DoomsBlerg Equities & Options Data Module
=========================================
Cross-verifies live stock prices across multiple free APIs (Alpaca IEX, Finnhub,
Tiingo, Twelve Data, FMP, Massive) and pulls standardized fundamentals,
historical bars, analyst forecasts, and live options chains.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import statistics
from typing import Any, Dict, List, Optional

from .config import get_key
from .http_client import fetch_json


def _alpaca_headers() -> Dict[str, str]:
    return {
        "APCA-API-KEY-ID": get_key("ALPACA_API_KEY"),
        "APCA-API-SECRET-KEY": get_key("ALPACA_SECRET_KEY"),
    }


def _quote_from_finnhub(ticker: str) -> Dict[str, Any]:
    key = get_key("FINNHUB_API_KEY")
    if not key:
        return {}
    data = fetch_json(
        "https://finnhub.io/api/v1/quote",
        params={"symbol": ticker, "token": key},
        ttl_seconds=30,
    )
    price = data.get("c")
    if not price:
        return {}
    return {
        "source": "finnhub",
        "price": float(price),
        "open": data.get("o"),
        "high": data.get("h"),
        "low": data.get("l"),
        "prev_close": data.get("pc"),
        "change": data.get("d"),
        "change_percent": data.get("dp"),
    }


def _quote_from_alpaca(ticker: str) -> Dict[str, Any]:
    if not get_key("ALPACA_API_KEY"):
        return {}
    data = fetch_json(
        f"https://data.alpaca.markets/v2/stocks/{ticker}/snapshot",
        params={"feed": "iex"},
        headers=_alpaca_headers(),
        ttl_seconds=20,
    )
    trade = data.get("latestTrade") or {}
    quote = data.get("latestQuote") or {}
    daily = data.get("dailyBar") or {}
    prev = data.get("prevDailyBar") or {}
    price = trade.get("p") or daily.get("c")
    if not price:
        return {}
    return {
        "source": "alpaca_iex",
        "price": float(price),
        "bid": quote.get("bp"),
        "ask": quote.get("ap"),
        "volume": daily.get("v"),
        "prev_close": prev.get("c"),
    }


def _quote_from_tiingo(ticker: str) -> Dict[str, Any]:
    key = get_key("TIINGO_API_KEY")
    if not key:
        return {}
    data = fetch_json(
        "https://api.tiingo.com/iex/",
        params={"tickers": ticker},
        headers={"Authorization": f"Token {key}"},
        ttl_seconds=30,
    )
    if not isinstance(data, list) or not data:
        return {}
    row = data[0]
    price = row.get("tngoLast") or row.get("last")
    if not price:
        return {}
    return {
        "source": "tiingo_iex",
        "price": float(price),
        "open": row.get("open"),
        "high": row.get("high"),
        "low": row.get("low"),
        "volume": row.get("volume"),
    }


def _quote_from_twelvedata(ticker: str) -> Dict[str, Any]:
    key = get_key("TWELVEDATA_API_KEY")
    if not key:
        return {}
    data = fetch_json(
        "https://api.twelvedata.com/price",
        params={"symbol": ticker, "apikey": key},
        ttl_seconds=30,
    )
    price = data.get("price")
    if not price:
        return {}
    return {"source": "twelvedata", "price": float(price)}


def _quote_from_yahoo(ticker: str) -> Dict[str, Any]:
    data = fetch_json(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
        params={"range": "1d", "interval": "1d"},
        headers={"User-Agent": "Mozilla/5.0"},
        ttl_seconds=30,
    )
    meta = ((data.get("chart") or {}).get("result") or [{}])[0].get("meta", {})
    price = meta.get("regularMarketPrice")
    if not price:
        return {}
    return {
        "source": "yahoo",
        "price": float(price),
        "prev_close": meta.get("chartPreviousClose"),
        "currency": meta.get("currency"),
        "exchange": meta.get("fullExchangeName"),
    }


def get_quote_cross_verified(ticker: str) -> Dict[str, Any]:
    """
    Fetch live stock quote from multiple independent feeds in parallel and
    cross-verify consensus price, spread, and feed agreement.
    """
    ticker = ticker.upper().strip()
    fetchers = [
        _quote_from_finnhub,
        _quote_from_alpaca,
        _quote_from_tiingo,
        _quote_from_twelvedata,
        _quote_from_yahoo,
    ]

    results: List[Dict[str, Any]] = []
    errors: List[str] = []
    with ThreadPoolExecutor(max_workers=len(fetchers)) as pool:
        futures = {pool.submit(fn, ticker): fn.__name__ for fn in fetchers}
        for fut, name in futures.items():
            try:
                res = fut.result()
                if res and res.get("price"):
                    results.append(res)
            except Exception as exc:
                errors.append(f"{name}: {exc}")

    if not results:
        raise RuntimeError(f"No live quote sources succeeded for {ticker}: {errors}")

    prices = [r["price"] for r in results]
    consensus_price = round(statistics.median(prices), 4)
    spread_pct = round(((max(prices) - min(prices)) / consensus_price) * 100, 4) if len(prices) > 1 else 0.0

    finnhub_data = next((r for r in results if r["source"] == "finnhub"), {})
    alpaca_data = next((r for r in results if r["source"] == "alpaca_iex"), {})

    return {
        "ticker": ticker,
        "price": consensus_price,
        "change": finnhub_data.get("change"),
        "change_percent": finnhub_data.get("change_percent"),
        "open": finnhub_data.get("open"),
        "high": finnhub_data.get("high"),
        "low": finnhub_data.get("low"),
        "prev_close": finnhub_data.get("prev_close") or alpaca_data.get("prev_close"),
        "bid": alpaca_data.get("bid"),
        "ask": alpaca_data.get("ask"),
        "volume": alpaca_data.get("volume"),
        "sources_agreed": len(results),
        "cross_feed_spread_pct": spread_pct,
        "confidence": "high" if len(results) >= 3 and spread_pct < 0.5 else "medium",
        "source_quotes": {r["source"]: r["price"] for r in results},
        "errors": errors,
    }


def get_company_overview(ticker: str) -> Dict[str, Any]:
    """Return plain-English company profile (replaces Bloomberg DES)."""
    ticker = ticker.upper().strip()
    profile: Dict[str, Any] = {"ticker": ticker}

    fmp_key = get_key("FMP_API_KEY")
    if fmp_key:
        try:
            rows = fetch_json(
                "https://financialmodelingprep.com/stable/profile",
                params={"symbol": ticker, "apikey": fmp_key},
                ttl_seconds=43200,
            )
            if isinstance(rows, list) and rows:
                r = rows[0]
                profile.update(
                    {
                        "name": r.get("companyName"),
                        "sector": r.get("sector"),
                        "industry": r.get("industry"),
                        "ceo": r.get("ceo"),
                        "description": r.get("description"),
                        "price": r.get("price"),
                        "market_cap": r.get("marketCap"),
                        "beta": r.get("beta"),
                        "52_week_range": r.get("range"),
                        "dividend_last": r.get("lastDividend"),
                        "employees": r.get("fullTimeEmployees"),
                        "website": r.get("website"),
                        "exchange": r.get("exchange"),
                        "country": r.get("country"),
                    }
                )
        except Exception:
            pass

    finnhub_key = get_key("FINNHUB_API_KEY")
    if finnhub_key and not profile.get("name"):
        fh = fetch_json(
            "https://finnhub.io/api/v1/stock/profile2",
            params={"symbol": ticker, "token": finnhub_key},
            ttl_seconds=43200,
        )
        profile.update(
            {
                "name": fh.get("name"),
                "industry": fh.get("finnhubIndustry"),
                "market_cap_millions": fh.get("marketCapitalization"),
                "shares_outstanding_millions": fh.get("shareOutstanding"),
                "ipo_date": fh.get("ipo"),
                "website": fh.get("weburl"),
                "exchange": fh.get("exchange"),
                "country": fh.get("country"),
            }
        )

    return profile


def _history_from_massive(ticker: str, range_str: str = "3mo") -> List[Dict[str, Any]]:
    """Fallback daily OHLCV bars from Massive (Polygon-compatible API)."""
    key = get_key("MASSIVE_API_KEY")
    if not key:
        return []
    from datetime import timedelta

    days_map = {"5d": 10, "1mo": 32, "3mo": 95, "6mo": 185, "1y": 370, "2y": 740, "5y": 1830}
    days = days_map.get(range_str, 95)
    end_d = datetime.now(timezone.utc).date()
    start_d = end_d - timedelta(days=days)
    data = fetch_json(
        f"https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{start_d.isoformat()}/{end_d.isoformat()}",
        params={"adjusted": "true", "sort": "asc", "apiKey": key},
        ttl_seconds=1800,
    )
    bars: List[Dict[str, Any]] = []
    for row in data.get("results") or []:
        ts_ms = row.get("t")
        if ts_ms is None or row.get("c") is None:
            continue
        bars.append(
            {
                "date": datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d"),
                "open": round(float(row["o"]), 4) if row.get("o") is not None else None,
                "high": round(float(row["h"]), 4) if row.get("h") is not None else None,
                "low": round(float(row["l"]), 4) if row.get("l") is not None else None,
                "close": round(float(row["c"]), 4),
                "volume": int(row.get("v") or 0),
            }
        )
    return bars


def get_historical_prices(ticker: str, range_str: str = "3mo", interval: str = "1d") -> List[Dict[str, Any]]:
    """Return clean OHLCV price history with Massive fallback (replaces Bloomberg GP)."""
    ticker = ticker.upper().strip()
    try:
        data = fetch_json(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
            params={"range": range_str, "interval": interval},
            headers={"User-Agent": "Mozilla/5.0"},
            ttl_seconds=1800,
        )
        result = ((data.get("chart") or {}).get("result") or [None])[0]
        if result:
            timestamps = result.get("timestamp") or []
            quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
            opens = quote.get("open") or []
            highs = quote.get("high") or []
            lows = quote.get("low") or []
            closes = quote.get("close") or []
            volumes = quote.get("volume") or []

            bars: List[Dict[str, Any]] = []
            for idx, ts in enumerate(timestamps):
                if closes[idx] is None:
                    continue
                bars.append(
                    {
                        "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                        "open": round(opens[idx], 4) if opens[idx] is not None else None,
                        "high": round(highs[idx], 4) if highs[idx] is not None else None,
                        "low": round(lows[idx], 4) if lows[idx] is not None else None,
                        "close": round(closes[idx], 4),
                        "volume": int(volumes[idx] or 0),
                    }
                )
            if bars:
                return bars
    except Exception:
        if interval != "1d":
            raise

    if interval == "1d":
        fallback = _history_from_massive(ticker, range_str=range_str)
        if fallback:
            return fallback
    raise RuntimeError(f"No historical chart data for {ticker}")


def get_financial_statements(ticker: str, limit: int = 4) -> Dict[str, Any]:
    """Return income statement, balance sheet, and cash flow (replaces Bloomberg FA)."""
    ticker = ticker.upper().strip()
    fmp_key = get_key("FMP_API_KEY")
    if not fmp_key:
        raise RuntimeError("FMP_API_KEY is required for FMP financial statements.")

    endpoints = {
        "income_statement": "https://financialmodelingprep.com/stable/income-statement",
        "balance_sheet": "https://financialmodelingprep.com/stable/balance-sheet-statement",
        "cash_flow": "https://financialmodelingprep.com/stable/cash-flow-statement",
    }
    output: Dict[str, Any] = {"ticker": ticker}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            name: pool.submit(
                fetch_json,
                url,
                params={"symbol": ticker, "limit": limit, "apikey": fmp_key},
                ttl_seconds=43200,
            )
            for name, url in endpoints.items()
        }
        for name, fut in futures.items():
            try:
                output[name] = fut.result()
            except Exception as exc:
                output[name] = {"error": str(exc)}
    return output


def get_analyst_forecasts(ticker: str) -> Dict[str, Any]:
    """Return Wall Street analyst ratings, valuation ratios, and 52w metrics (replaces EE)."""
    ticker = ticker.upper().strip()
    key = get_key("FINNHUB_API_KEY")
    if not key:
        raise RuntimeError("FINNHUB_API_KEY is required for analyst consensus.")

    with ThreadPoolExecutor(max_workers=2) as pool:
        rec_fut = pool.submit(
            fetch_json,
            "https://finnhub.io/api/v1/stock/recommendation",
            params={"symbol": ticker, "token": key},
            ttl_seconds=3600,
        )
        met_fut = pool.submit(
            fetch_json,
            "https://finnhub.io/api/v1/stock/metric",
            params={"symbol": ticker, "metric": "all", "token": key},
            ttl_seconds=3600,
        )
        recs = rec_fut.result()
        metrics = met_fut.result().get("metric", {})

    return {
        "ticker": ticker,
        "latest_analyst_ratings": recs[0] if isinstance(recs, list) and recs else None,
        "rating_history": recs[:4] if isinstance(recs, list) else [],
        "key_ratios": {
            "52_week_high": metrics.get("52WeekHigh"),
            "52_week_low": metrics.get("52WeekLow"),
            "pe_ttm": metrics.get("peTTM"),
            "ps_ttm": metrics.get("psTTM"),
            "pb_quarterly": metrics.get("pbQuarterly"),
            "roe_ttm": metrics.get("roeTTM"),
            "beta": metrics.get("beta"),
            "13_week_return_pct": metrics.get("13WeekPriceReturnDaily"),
            "52_week_return_pct": metrics.get("52WeekPriceReturnDaily"),
        },
    }


def _parse_occ_symbol(occ: str) -> Dict[str, Any]:
    """Parse OCC option symbol like AAPL261125C00270000 into expiry, type, strike."""
    # Last 15 chars: YYMMDD + C/P + 8-digit strike * 1000
    tail = occ[-15:]
    expiry_raw = tail[:6]
    opt_type = "call" if tail[6] == "C" else "put"
    strike = int(tail[7:]) / 1000.0
    expiry = f"20{expiry_raw[:2]}-{expiry_raw[2:4]}-{expiry_raw[4:6]}"
    return {"expiry": expiry, "type": opt_type, "strike": strike}


def get_options_chain(
    ticker: str,
    limit: int = 30,
    strike_min: Optional[float] = None,
    strike_max: Optional[float] = None,
) -> Dict[str, Any]:
    """Return live options chain snapshots with Greeks & IV from Alpaca (replaces OMON)."""
    ticker = ticker.upper().strip()
    if not get_key("ALPACA_API_KEY"):
        raise RuntimeError("ALPACA_API_KEY is required for live Alpaca options snapshots.")

    params: Dict[str, Any] = {"limit": limit}
    if strike_min is not None:
        params["strike_price_gte"] = round(strike_min, 2)
    if strike_max is not None:
        params["strike_price_lte"] = round(strike_max, 2)

    data = fetch_json(
        f"https://data.alpaca.markets/v1beta1/options/snapshots/{ticker}",
        params=params,
        headers=_alpaca_headers(),
        ttl_seconds=60,
    )
    snapshots = data.get("snapshots") or {}
    contracts: List[Dict[str, Any]] = []
    for sym, snap in snapshots.items():
        meta = _parse_occ_symbol(sym)
        quote = snap.get("latestQuote") or {}
        trade = snap.get("latestTrade") or {}
        greeks = snap.get("greeks") or {}
        contracts.append(
            {
                "contract": sym,
                "expiry": meta["expiry"],
                "type": meta["type"],
                "strike": meta["strike"],
                "last_price": trade.get("p"),
                "bid": quote.get("bp"),
                "ask": quote.get("ap"),
                "implied_volatility": snap.get("impliedVolatility"),
                "greeks": greeks,
            }
        )
    contracts.sort(key=lambda c: (c["expiry"], c["type"], c["strike"]))
    return {"ticker": ticker, "count": len(contracts), "contracts": contracts}


def compare_peers(tickers: List[str]) -> Dict[str, Any]:
    """Compare valuation multiples, growth, and market caps across peers (replaces Bloomberg RV)."""
    clean = [t.upper().strip() for t in tickers if t.strip()][:6]

    def _inspect(sym: str) -> Dict[str, Any]:
        with ThreadPoolExecutor(max_workers=3) as pool:
            q_f = pool.submit(get_quote_cross_verified, sym)
            ov_f = pool.submit(get_company_overview, sym)
            fc_f = pool.submit(get_analyst_forecasts, sym)
            q = q_f.result()
            ov = ov_f.result()
            fc = fc_f.result()
        ratios = fc.get("key_ratios") or {}
        return {
            "ticker": sym,
            "name": ov.get("name"),
            "sector": ov.get("sector"),
            "price": q.get("price"),
            "change_percent": q.get("change_percent"),
            "market_cap": ov.get("market_cap"),
            "pe_ttm": ratios.get("pe_ttm"),
            "ps_ttm": ratios.get("ps_ttm"),
            "pb_quarterly": ratios.get("pb_quarterly"),
            "roe_ttm": ratios.get("roe_ttm"),
            "beta": ratios.get("beta") or ov.get("beta"),
            "52w_return_pct": ratios.get("52_week_return_pct"),
            "analyst_ratings": fc.get("latest_analyst_ratings"),
        }

    with ThreadPoolExecutor(max_workers=min(len(clean), 4) or 1) as pool:
        futs = {t: pool.submit(_inspect, t) for t in clean}
        rows = []
        for t, f in futs.items():
            try:
                rows.append(f.result())
            except Exception as exc:
                rows.append({"ticker": t, "error": str(exc)})
    return {"peers": rows}
