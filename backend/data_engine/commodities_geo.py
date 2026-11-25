"""
DoomsBlerg Commodities, Weather, News & Crypto Perpetuals Module
=================================================================
Integrates EIA Energy Inventories, USDA NASS Crop Progress, NOAA Climate,
Open-Meteo Weather, Financial News + Google News RSS, and Hyperliquid Crypto Perps.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional
import urllib.parse
import xml.etree.ElementTree as ET

from .config import get_key
from .http_client import fetch_json, fetch_text


def get_energy_inventories(limit: int = 8) -> Dict[str, Any]:
    """
    Fetch weekly US commercial crude oil inventories (WCESTUS1, excluding SPR)
    from EIA API v2 and compute consecutive week-over-week change in MBBL.
    """
    eia_key = get_key("EIA_API_KEY")
    if not eia_key:
        raise RuntimeError("EIA_API_KEY is required for EIA energy inventories.")

    data = fetch_json(
        "https://api.eia.gov/v2/petroleum/stoc/wstk/data/",
        params={
            "api_key": eia_key,
            "frequency": "weekly",
            "data[0]": "value",
            "facets[duoarea][]": "NUS",
            "facets[product][]": "EPC0",
            "facets[series][]": "WCESTUS1",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": limit,
        },
        ttl_seconds=3600,
    )
    rows = (data.get("response") or {}).get("data") or []
    cleaned = [
        {
            "period": r.get("period"),
            "series": r.get("series"),
            "description": r.get("series-description"),
            "value": float(r["value"]) if r.get("value") is not None else None,
            "units": r.get("units"),
        }
        for r in rows
    ]
    change_mbbl = None
    direction = None
    if len(cleaned) >= 2 and cleaned[0].get("value") is not None and cleaned[1].get("value") is not None:
        change_mbbl = round(cleaned[0]["value"] - cleaned[1]["value"], 1)
        direction = "build (supply up)" if change_mbbl > 0 else ("draw (supply tightening)" if change_mbbl < 0 else "flat")

    return {
        "commodity": "US Commercial Crude Oil Stocks excl. SPR (EIA WCESTUS1)",
        "latest_week_change_mbbl": change_mbbl,
        "latest_direction": direction,
        "records": cleaned,
    }


def get_crop_progress(commodity: str = "CORN", year: int = 2025, state: str = "IA") -> Dict[str, Any]:
    """Fetch official agricultural statistics from USDA NASS QuickStats."""
    usda_key = get_key("USDA_NASS_API_KEY")
    if not usda_key:
        raise RuntimeError("USDA_NASS_API_KEY is required for USDA NASS QuickStats.")

    data = fetch_json(
        "https://quickstats.nass.usda.gov/api/api_GET/",
        params={
            "key": usda_key,
            "commodity_desc": commodity.upper(),
            "year": year,
            "state_alpha": state.upper(),
            "statisticcat_desc": "AREA PLANTED",
            "format": "JSON",
        },
        ttl_seconds=43200,
    )
    rows = (data.get("data") or [])[:15]
    return {
        "commodity": commodity.upper(),
        "state": state.upper(),
        "year": year,
        "count": len(rows),
        "sample": [
            {
                "location": r.get("location_desc"),
                "value": r.get("Value"),
                "unit": r.get("unit_desc"),
                "short_desc": r.get("short_desc"),
            }
            for r in rows
        ],
    }


def get_weather_forecast(lat: float, lon: float, days: int = 7) -> Dict[str, Any]:
    """Fetch free global 7-day forecast via Open-Meteo (no API key needed)."""
    data = fetch_json(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "forecast_days": days,
            "timezone": "UTC",
        },
        ttl_seconds=1800,
    )
    return data


def get_noaa_climate_datasets(limit: int = 10) -> Dict[str, Any]:
    """Fetch available historical climate datasets from NOAA CDO."""
    token = get_key("NOAA_CDO_TOKEN")
    if not token:
        raise RuntimeError("NOAA_CDO_TOKEN is required for NOAA CDO.")
    return fetch_json(
        "https://www.ncdc.noaa.gov/cdo-web/api/v2/datasets",
        params={"limit": limit},
        headers={"token": token},
        ttl_seconds=86400,
    )


def get_market_news(ticker: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
    """
    Fetch financial headlines combining Finnhub JSON news + Google News RSS.
    Deduplicates by headline title.
    """
    articles: List[Dict[str, Any]] = []
    seen_titles = set()

    def _add(title: str, source: str, url: str, published: Any) -> None:
        clean = (title or "").strip()
        if not clean or clean in seen_titles:
            return
        seen_titles.add(clean)
        articles.append(
            {"title": clean, "source": source, "url": url, "published": str(published)}
        )

    def _fetch_finnhub() -> None:
        key = get_key("FINNHUB_API_KEY")
        if not key:
            return
        if ticker:
            from datetime import datetime, timedelta, timezone
            end_d = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            start_d = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
            rows = fetch_json(
                "https://finnhub.io/api/v1/company-news",
                params={"symbol": ticker.upper(), "from": start_d, "to": end_d, "token": key},
                ttl_seconds=600,
            )
        else:
            rows = fetch_json(
                "https://finnhub.io/api/v1/news",
                params={"category": "general", "token": key},
                ttl_seconds=600,
            )
        for r in (rows or [])[:limit]:
            _add(r.get("headline", ""), r.get("source", "Finnhub"), r.get("url", ""), r.get("datetime", ""))

    def _fetch_google_rss() -> None:
        query = f"{ticker.upper()} stock" if ticker else "stock market economy"
        rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
        xml_text = fetch_text(rss_url, ttl_seconds=600)
        root = ET.fromstring(xml_text)
        for item in root.findall(".//item")[:limit]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub = item.findtext("pubDate", "")
            src = item.findtext("source", "Google News")
            _add(title, src, link, pub)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_fetch_finnhub)
        f2 = pool.submit(_fetch_google_rss)
        for fut in (f1, f2):
            try:
                fut.result()
            except Exception:
                pass

    return articles[:limit]


def get_crypto_perps(symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Fetch live crypto perpetual funding rates, mark prices, and OI from Hyperliquid (keyless)."""
    wanted = {s.upper() for s in (symbols or ["BTC", "ETH", "SOL"])}
    data = fetch_json(
        "https://api.hyperliquid.xyz/info",
        method="POST",
        json_body={"type": "metaAndAssetCtxs"},
        ttl_seconds=30,
    )
    universe = (data[0] or {}).get("universe", [])
    ctxs = data[1] or []
    out: List[Dict[str, Any]] = []
    for idx, meta in enumerate(universe):
        coin = meta.get("name", "").upper()
        if coin not in wanted or idx >= len(ctxs):
            continue
        ctx = ctxs[idx]
        out.append(
            {
                "symbol": coin,
                "mark_price": float(ctx.get("markPx") or 0),
                "funding_rate_hourly": float(ctx.get("funding") or 0),
                "open_interest": float(ctx.get("openInterest") or 0),
                "day_notional_volume": float(ctx.get("dayNtlVlm") or 0),
            }
        )
    return out


def get_fx_rates(base: str = "USD", targets: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Fetch FX currency matrix using Frankfurter ECB rates (fast batch) plus
    real-time primary pair verification via Alpha Vantage (replaces Bloomberg FXC).
    """
    base = base.upper().strip()
    syms = [s.upper().strip() for s in (targets or ["EUR", "GBP", "JPY", "CAD", "CHF", "AUD", "CNY"]) if s.upper().strip() != base]

    rates: Dict[str, float] = {}
    as_of: Optional[str] = None
    sources: List[str] = []

    try:
        frank = fetch_json(
            "https://api.frankfurter.dev/v1/latest",
            params={"base": base, "symbols": ",".join(syms)},
            ttl_seconds=600,
        )
        if isinstance(frank.get("rates"), dict):
            rates.update({k: float(v) for k, v in frank["rates"].items()})
            as_of = frank.get("date")
            sources.append("frankfurter_ecb")
    except Exception:
        pass

    av_key = get_key("ALPHA_VANTAGE_API_KEY")
    if av_key and syms:
        lead_target = syms[0]
        try:
            av = fetch_json(
                "https://www.alphavantage.co/query",
                params={
                    "function": "CURRENCY_EXCHANGE_RATE",
                    "from_currency": base,
                    "to_currency": lead_target,
                    "apikey": av_key,
                },
                ttl_seconds=300,
            )
            quote = av.get("Realtime Currency Exchange Rate") or {}
            rate_val = quote.get("5. Exchange Rate")
            if rate_val:
                rates[lead_target] = round(float(rate_val), 5)
                as_of = quote.get("6. Last Refreshed") or as_of
                sources.append("alpha_vantage_realtime")
        except Exception:
            pass

    if not rates:
        raise RuntimeError(f"Failed to retrieve FX rates for base={base}")

    return {"base": base, "as_of": as_of, "sources": sources, "rates": rates}


COMMODITY_FUTURES = {
    "Crude Oil (WTI)": ("CL=F", "USD/bbl"),
    "Crude Oil (Brent)": ("BZ=F", "USD/bbl"),
    "Natural Gas": ("NG=F", "USD/MMBtu"),
    "Gold": ("GC=F", "USD/oz"),
    "Silver": ("SI=F", "USD/oz"),
    "Copper": ("HG=F", "USD/lb"),
    "Corn": ("ZC=F", "USc/bu"),
    "Wheat": ("ZW=F", "USc/bu"),
    "Soybeans": ("ZS=F", "USc/bu"),
}


def get_commodities_snapshot() -> Dict[str, Any]:
    """Fetch major global energy, metals, and agriculture benchmark prices (replaces Bloomberg COMS)."""
    def _one(label: str, symbol: str, unit: str) -> Dict[str, Any]:
        try:
            data = fetch_json(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"range": "5d", "interval": "1d"},
                headers={"User-Agent": "Mozilla/5.0"},
                ttl_seconds=300,
            )
            meta = ((data.get("chart") or {}).get("result") or [{}])[0].get("meta", {})
            price = meta.get("regularMarketPrice")
            prev = meta.get("chartPreviousClose")
            chg_pct = round(((price - prev) / prev) * 100, 2) if (price and prev) else None
            return {"name": label, "symbol": symbol, "price": price, "change_pct": chg_pct, "unit": unit}
        except Exception as exc:
            return {"name": label, "symbol": symbol, "error": str(exc)}

    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = [pool.submit(_one, lbl, sym, unit) for lbl, (sym, unit) in COMMODITY_FUTURES.items()]
        items = [f.result() for f in futs]

    eia_summary: Dict[str, Any] = {}
    try:
        eia = get_energy_inventories(limit=2)
        eia_summary = {
            "latest_change_mbbl": eia.get("latest_week_change_mbbl"),
            "direction": eia.get("latest_direction"),
            "latest_period": (eia.get("records") or [{}])[0].get("period"),
        }
    except Exception:
        pass

    return {"commodities": items, "eia_us_crude_inventory": eia_summary}
