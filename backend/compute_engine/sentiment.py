"""
DoomsBlerg Zero-RAM Financial Sentiment Engine
==============================================
Lightweight domain-tuned financial headline scorer (0 MB ML model overhead,
0 LLM API calls) designed specifically for low-end laptops.
"""

import re
from typing import Any, Dict, List

POSITIVE_WEIGHTS = {
    "beat": 2.0, "beats": 2.0, "surge": 2.2, "surges": 2.2, "soar": 2.3,
    "soars": 2.3, "rally": 2.0, "rallies": 2.0, "upgrade": 2.1, "upgraded": 2.1,
    "outperform": 1.9, "bullish": 2.0, "record": 1.6, "growth": 1.5, "strong": 1.4,
    "profit": 1.5, "profits": 1.5, "breakout": 1.8, "raises": 1.7, "raised": 1.7,
    "buyback": 1.8, "repurchase": 1.7, "dividend": 1.3, "boom": 1.9, "approval": 1.8,
    "approved": 1.8, "partnership": 1.4, "contract": 1.4, "momentum": 1.3,
    "gain": 1.4, "gains": 1.4, "jump": 1.8, "jumps": 1.8, "overweight": 1.6,
    "rebound": 1.5, "optimistic": 1.6, "accelerate": 1.5, "exceeded": 1.9,
}

NEGATIVE_WEIGHTS = {
    "miss": -2.0, "misses": -2.0, "missed": -2.0, "plunge": -2.4, "plunges": -2.4,
    "crash": -2.5, "crashes": -2.5, "slump": -2.0, "slumps": -2.0, "downgrade": -2.2,
    "downgraded": -2.2, "underperform": -1.9, "bearish": -2.0, "loss": -1.7, "losses": -1.7,
    "cut": -1.6, "cuts": -1.6, "warn": -1.9, "warning": -2.0, "warnings": -2.0,
    "lawsuit": -2.0, "sued": -2.0, "investigation": -2.0, "probe": -1.8, "fraud": -2.8,
    "bankruptcy": -3.0, "default": -2.5, "recall": -1.9, "layoffs": -1.8, "decline": -1.6,
    "declines": -1.6, "drop": -1.5, "drops": -1.5, "fall": -1.4, "falls": -1.4,
    "tariff": -1.4, "tariffs": -1.4, "sanctions": -1.8, "shortage": -1.5, "delay": -1.4,
    "weak": -1.6, "disappointing": -1.9, "debt": -1.1, "inflation": -0.9, "selloff": -2.1,
}

NEGATIONS = {"not", "no", "never", "without", "fails", "failed", "neither", "unlikely"}
_WORD_RE = re.compile(r"[a-zA-Z]+")


def score_text(text: str) -> Dict[str, Any]:
    """Score a single headline or sentence in [-1.0, +1.0]."""
    tokens = [t.lower() for t in _WORD_RE.findall(text or "")]
    if not tokens:
        return {"score": 0.0, "label": "neutral", "drivers": []}

    raw_sum = 0.0
    drivers: List[str] = []
    for idx, tok in enumerate(tokens):
        weight = POSITIVE_WEIGHTS.get(tok) or NEGATIVE_WEIGHTS.get(tok)
        if weight is None:
            continue
        # Check up to 2 words back for simple negation flip
        window = set(tokens[max(0, idx - 2) : idx])
        if window & NEGATIONS:
            weight = -0.8 * weight
            drivers.append(f"!{tok}")
        else:
            drivers.append(tok)
        raw_sum += weight

    # Smooth normalization into [-1, +1]
    norm = raw_sum / (abs(raw_sum) + 3.0) if raw_sum != 0 else 0.0
    label = "bullish" if norm >= 0.15 else ("bearish" if norm <= -0.15 else "neutral")
    return {"score": round(norm, 3), "label": label, "drivers": drivers}


def score_headlines(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate sentiment across a list of article dicts containing 'title'."""
    if not articles:
        return {"overall_score": 0.0, "label": "neutral", "count": 0, "bullish_count": 0, "bearish_count": 0, "scored": []}

    scored = []
    total = 0.0
    bull_cnt = 0
    bear_cnt = 0
    for art in articles:
        title = art.get("title") or ""
        res = score_text(title)
        total += res["score"]
        if res["label"] == "bullish":
            bull_cnt += 1
        elif res["label"] == "bearish":
            bear_cnt += 1
        scored.append({"title": title, "source": art.get("source"), "score": res["score"], "label": res["label"]})

    avg = total / len(scored)
    overall_label = "bullish" if avg >= 0.10 else ("bearish" if avg <= -0.10 else "neutral")
    return {
        "overall_score": round(avg, 3),
        "label": overall_label,
        "count": len(scored),
        "bullish_count": bull_cnt,
        "bearish_count": bear_cnt,
        "scored": scored,
    }
