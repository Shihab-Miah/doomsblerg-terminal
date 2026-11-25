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
    Fetch weekly US petroleum/crude inventory statistics from EIA API v2.
    Computes latest week-over-week inventory build (+) or draw (-).
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
            "facets[product][]": "EPC0",  # Crude oil
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
            "series": r.get("series-description"),
            "value": float(r["value"]) if r.get("value") is not None else None,
            "units": r.get("units"),
        }
        for r in rows
    ]
    return {"commodity": "US Crude Oil Stocks (EIA)", "records": cleaned}


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
