"""
DoomsBlerg Lightweight SEC 10-K / 10-Q Filing Extractor (Zero Local ML)
=======================================================================
Pulls the latest official SEC filing via Phase 1, strips HTML using Python stdlib,
and extracts only the highest-signal risk/debt/guidance paragraphs (~450 tokens)
for the AI Auditor — avoiding 200-page PDF token explosions and zero laptop RAM bloat.
"""

from html.parser import HTMLParser
import re
from typing import Any, Dict, List

from backend.data_engine.http_client import fetch_text
from backend.data_engine.sec_intelligence import get_recent_filings

from .llm_router import llm_router

RISK_KEYWORDS = {
    "risk factor": 3.0,
    "material weakness": 4.0,
    "litigation": 2.5,
    "regulatory": 2.0,
    "tariff": 2.5,
    "china": 2.0,
    "supply chain": 2.0,
    "gross margin": 2.2,
    "liquidity": 2.0,
    "debt": 1.8,
    "guidance": 2.0,
    "outlook": 2.0,
    "competition": 1.5,
    "concentration": 2.5,
    "impairment": 3.0,
    "investigation": 3.0,
    "ai": 1.4,
}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = False
        self._chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("script", "style", "ix:header", "ix:hidden"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "ix:header", "ix:hidden"):
            self._skip = False
        elif tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            clean = data.strip()
            if clean:
                self._chunks.append(clean + " ")

    def text(self) -> str:
        return "".join(self._chunks)


def extract_key_filing_snippets(ticker: str, max_snippets: int = 5, max_chars: int = 2400) -> Dict[str, Any]:
    """Fetch latest 10-K or 10-Q from SEC EDGAR and extract highest-risk/catalyst paragraphs."""
    filings_meta = get_recent_filings(ticker, forms=["10-K", "10-Q"], limit=3)
    filings = filings_meta.get("filings") or []
    if not filings:
        return {"ticker": ticker.upper(), "error": "No 10-K or 10-Q filing found."}

    latest = filings[0]
    url = latest["url"]
    # Fetch filing HTML (cached 24h in SQLite; read up to 450KB to keep low-end laptop RAM tiny)
    raw_html = fetch_text(url, ttl_seconds=86400, timeout=18)[:450000]

    parser = _HTMLTextExtractor()
    parser.feed(raw_html)
    plain = parser.text()

    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in plain.split("\n")]
    scored_paras = []
    for p in paragraphs:
        if len(p) < 120 or len(p) > 1200:
            continue
        low = p.lower()
        score = sum(w for kw, w in RISK_KEYWORDS.items() if kw in low)
        if score > 0:
            scored_paras.append((score, p))

    scored_paras.sort(key=lambda x: x[0], reverse=True)
    snippets: List[str] = []
    total_len = 0
    for _, para in scored_paras[: max_snippets * 2]:
        if total_len + len(para) > max_chars:
            break
        snippets.append(para)
        total_len += len(para)
        if len(snippets) >= max_snippets:
            break

    return {
        "ticker": ticker.upper(),
        "form": latest["form"],
        "filing_date": latest["filing_date"],
        "url": url,
        "snippets_extracted": len(snippets),
        "snippets": snippets,
    }


def audit_filing(ticker: str) -> Dict[str, Any]:
    """Have the Fundamental Auditor AI read extracted SEC 10-K/10-Q risk snippets and report red flags."""
    ticker = ticker.upper().strip()
    extracted = extract_key_filing_snippets(ticker)
    if "error" in extracted:
        return extracted

    snippets_text = "\n\n".join(f"[{i+1}] {s}" for i, s in enumerate(extracted["snippets"]))
    if not snippets_text:
        return {**extracted, "audit": {"summary": "No risk excerpts matched in leading filing section."}}

    sys_prompt = (
        "You are an institutional SEC filing auditor explaining findings in plain English. "
        "Never use complex jargon. Return strictly valid JSON with keys: "
        "\"red_flags\" (list of up to 3 short strings), "
        "\"key_strengths_or_catalysts\" (list of up to 2 short strings), "
        "\"overall_risk_level\" (\"low\"|\"medium\"|\"high\"), "
        "\"plain_english_summary\" (2 clear sentences)."
    )
    user_prompt = (
        f"Company: {ticker} | Filing: {extracted['form']} ({extracted['filing_date']})\n"
        f"Excerpts:\n{snippets_text}"
    )

    resp = llm_router.generate(
        role="auditor",
        system_prompt=sys_prompt,
        user_prompt=user_prompt,
        max_tokens=900,
        temperature=0.1,
        expect_json=True,
    )

    return {
        "ticker": ticker,
        "form": extracted["form"],
        "filing_date": extracted["filing_date"],
        "filing_url": extracted["url"],
        "provider_used": f"{resp['provider_used']}:{resp['model_used']}",
        "audit": resp["json"],
    }
