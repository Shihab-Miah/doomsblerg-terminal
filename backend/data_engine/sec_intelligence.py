"""
DoomsBlerg SEC EDGAR & Insider Intelligence Module
==================================================
Direct access to official SEC filings, CIK resolution, and Form 4 insider activity.
"""

from typing import Any, Dict, List, Optional

from .config import get_key
from .http_client import fetch_json

SEC_HEADERS = {"Accept": "application/json"}


def resolve_cik(ticker: str) -> str:
    """Resolve a US stock ticker to its 10-digit zero-padded SEC CIK."""
    ticker = ticker.upper().strip()
    mapping = fetch_json(
        "https://www.sec.gov/files/company_tickers.json",
        headers=SEC_HEADERS,
        ttl_seconds=604800,  # 7 days
    )
    for entry in mapping.values():
        if entry.get("ticker", "").upper() == ticker:
            return str(entry["cik_str"]).zfill(10)
    raise ValueError(f"SEC CIK not found for ticker: {ticker}")


def get_recent_filings(
    ticker: str,
    forms: Optional[List[str]] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Fetch recent official SEC filings (10-K, 10-Q, 8-K, Form 4, 13D) with direct URLs."""
    cik = resolve_cik(ticker)
    data = fetch_json(
        f"https://data.sec.gov/submissions/CIK{cik}.json",
        headers=SEC_HEADERS,
        ttl_seconds=3600,
    )
    recent = (data.get("filings") or {}).get("recent") or {}
    form_list = recent.get("form") or []
    acc_list = recent.get("accessionNumber") or []
    date_list = recent.get("filingDate") or []
    doc_list = recent.get("primaryDocument") or []
    desc_list = recent.get("primaryDocDescription") or []

    allowed = {f.upper() for f in forms} if forms else None
    cik_int = str(int(cik))
    items: List[Dict[str, Any]] = []

    for idx, form_type in enumerate(form_list):
        if allowed and form_type.upper() not in allowed:
            continue
        acc = acc_list[idx]
        acc_clean = acc.replace("-", "")
        doc = doc_list[idx]
        items.append(
            {
                "form": form_type,
                "filing_date": date_list[idx],
                "description": desc_list[idx] if idx < len(desc_list) else "",
                "url": f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{doc}",
            }
        )
        if len(items) >= limit:
            break

    return {
        "ticker": ticker.upper(),
        "cik": cik,
        "entity_name": data.get("name"),
        "sic_description": data.get("sicDescription"),
        "filings": items,
    }


def get_insider_activity(ticker: str, limit: int = 15) -> Dict[str, Any]:
    """Fetch recent SEC Form 4 insider buys & sells and compute net sentiment."""
    ticker = ticker.upper().strip()
    key = get_key("FINNHUB_API_KEY")
    if not key:
        raise RuntimeError("FINNHUB_API_KEY is required for parsed Form 4 insider trades.")

    data = fetch_json(
        "https://finnhub.io/api/v1/stock/insider-transactions",
        params={"symbol": ticker, "token": key},
        ttl_seconds=1800,
    )
    txs = (data.get("data") or [])[:limit]
    buys = [t for t in txs if t.get("transactionCode") == "P"]
    sells = [t for t in txs if t.get("transactionCode") == "S"]
    net_shares = sum(int(t.get("change") or 0) for t in buys + sells)

    return {
        "ticker": ticker,
        "recent_transactions": txs,
        "open_market_buys_count": len(buys),
        "open_market_sells_count": len(sells),
        "net_insider_shares": net_shares,
        "signal": "bullish_insider_buying" if net_shares > 0 else ("insider_selling" if net_shares < 0 else "neutral"),
    }
