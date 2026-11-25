"""
DoomsBlerg Macroeconomics & Bond Yields Module
=============================================
Pulls identical Federal Reserve (FRED) series and US Treasury daily yield curves
as Bloomberg ECO, ECST, BTMM, and YCRV — mapped to plain English names.
"""

from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional

from .config import get_key
from .http_client import fetch_json, fetch_text

PLAIN_TO_FRED = {
    "inflation": "CPIAUCSL",
    "cpi": "CPIAUCSL",
    "core inflation": "PCEPILFE",
    "core pce": "PCEPILFE",
    "interest rate": "FEDFUNDS",
    "fed funds": "FEDFUNDS",
    "unemployment": "UNRATE",
    "gdp": "A191RL1Q225SBEA",
    "10 year treasury": "GS10",
    "2 year treasury": "GS2",
    "3 month tbill": "DTB3",
    "sofr": "SOFR",
    "mortgage rate": "MORTGAGE30US",
    "dollar index": "DTWEXBGS",
    "vix": "VIXCLS",
    "high yield spread": "BAMLH0A0HYM2",
    "investment grade spread": "BAMLC0A0CM",
    "m2 money supply": "M2SL",
    "retail sales": "RSAFS",
    "consumer sentiment": "UMCSENT",
}


def get_macro_indicator(plain_name_or_id: str, limit: int = 24) -> Dict[str, Any]:
    """Fetch any Federal Reserve macro series by plain English name or FRED ID."""
    fred_key = get_key("FRED_API_KEY")
    if not fred_key:
        raise RuntimeError("FRED_API_KEY is required for Federal Reserve data.")

    lookup = plain_name_or_id.lower().strip()
    series_id = PLAIN_TO_FRED.get(lookup, plain_name_or_id.upper().strip())

    data = fetch_json(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": series_id,
            "api_key": fred_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        },
        ttl_seconds=3600,
    )
    observations = []
    for obs in data.get("observations", []):
        val = obs.get("value")
        if val == ".":
            continue
        observations.append({"date": obs["date"], "value": float(val)})

    return {
        "query": plain_name_or_id,
        "fred_series_id": series_id,
        "latest": observations[0] if observations else None,
        "history": observations,
    }


TREASURY_FRED_SERIES = {
    "1 Mo": "DGS1MO",
    "3 Mo": "DGS3MO",
    "6 Mo": "DGS6MO",
    "1 Yr": "DGS1",
    "2 Yr": "DGS2",
    "5 Yr": "DGS5",
    "7 Yr": "DGS7",
    "10 Yr": "DGS10",
    "20 Yr": "DGS20",
    "30 Yr": "DGS30",
}


def _yield_curve_from_fred() -> Dict[str, Any]:
    """Fallback yield curve built from FRED daily constant-maturity Treasury yields."""
    yields: Dict[str, float] = {}
    latest_date: Optional[str] = None
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {tenor: pool.submit(get_macro_indicator, sid, 2) for tenor, sid in TREASURY_FRED_SERIES.items()}
        for tenor, fut in futs.items():
            res = fut.result()
            obs = res.get("latest")
            if obs:
                yields[tenor] = obs["value"]
                latest_date = latest_date or obs["date"]
    if not yields:
        raise RuntimeError("No Treasury yields returned from FRED fallback.")
    return {"date": latest_date, "source": "fred", "yields_pct": yields}


def get_yield_curve(year: Optional[int] = None) -> Dict[str, Any]:
    """
    Fetch official US Treasury daily yield curve (1M to 30Y) and compute
    recession inversion spreads (10Y-2Y and 10Y-3M). Replaces Bloomberg YCRV.
    Uses current-month Treasury CSV first (fast) and falls back to FRED DGS* series.
    """
    now = datetime.now(timezone.utc)
    target_year = year or now.year
    target_month = f"{target_year}{now.month:02d}"
    url = (
        f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/all/{target_month}"
    )

    date_str: Optional[str] = None
    source = "us_treasury"
    yields: Dict[str, float] = {}
    try:
        raw_csv = fetch_text(
            url,
            params={
                "type": "daily_treasury_yield_curve",
                "field_tdr_date_value_month": target_month,
                "_format": "csv",
            },
            ttl_seconds=3600,
            timeout=4,
        )
        rows = list(csv.DictReader(StringIO(raw_csv)))
        if rows:
            latest = rows[0]
            date_str = latest.get("Date")
            yields = {
                tenor: float(val)
                for tenor, val in latest.items()
                if tenor != "Date" and val not in ("", None)
            }
    except Exception:
        pass

    if not yields:
        fred_curve = _yield_curve_from_fred()
        date_str = fred_curve["date"]
        source = fred_curve["source"]
        yields = fred_curve["yields_pct"]

    spread_10y_2y = round(yields["10 Yr"] - yields["2 Yr"], 3) if "10 Yr" in yields and "2 Yr" in yields else None
    spread_10y_3m = round(yields["10 Yr"] - yields["3 Mo"], 3) if "10 Yr" in yields and "3 Mo" in yields else None

    return {
        "date": date_str,
        "source": source,
        "yields_pct": yields,
        "spread_10y_minus_2y": spread_10y_2y,
        "spread_10y_minus_3m": spread_10y_3m,
        "curve_inverted": bool(
            (spread_10y_2y is not None and spread_10y_2y < 0)
            or (spread_10y_3m is not None and spread_10y_3m < 0)
        ),
    }


def get_macro_dashboard() -> Dict[str, Any]:
    """Fetch complete US macro snapshot in parallel (inflation, rates, jobs, VIX, credit spreads)."""
    targets = [
        "interest rate",
        "sofr",
        "inflation",
        "core inflation",
        "unemployment",
        "vix",
        "high yield spread",
    ]
    results: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        curve_fut = pool.submit(get_yield_curve)
        futs = {name: pool.submit(get_macro_indicator, name, 2) for name in targets}
        for name, fut in futs.items():
            try:
                res = fut.result()
                results[name] = res.get("latest")
            except Exception as exc:
                results[name] = {"error": str(exc)}
        try:
            results["yield_curve"] = curve_fut.result()
        except Exception as exc:
            results["yield_curve"] = {"error": str(exc)}
    return results
