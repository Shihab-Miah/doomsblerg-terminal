"""
DoomsBlerg Terminal CLI (Phase 1 Data + Phase 2 Compute)
========================================================
Run plain-English market queries, valuations, technicals, and watchlists
straight from your shell — zero cryptic Bloomberg abbreviations.

Examples:
    python3 backend/cli.py price AAPL
    python3 backend/cli.py valuation AAPL
    python3 backend/cli.py technicals NVDA
    python3 backend/cli.py risk AAPL
    python3 backend/cli.py score AAPL
    python3 backend/cli.py screen AAPL NVDA MSFT
    python3 backend/cli.py yield_curve
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


COMMANDS = {
    # Phase 1: Data Engine
    "price": lambda args: router.price(args[0]),
    "about": lambda args: router.about(args[0]),
    "history": lambda args: router.history(args[0], range_str=args[1] if len(args) > 1 else "1mo"),
    "financials": lambda args: router.financials(args[0]),
    "forecasts": lambda args: router.forecasts(args[0]),
    "options": lambda args: router.options(args[0], limit=15),
    "filings": lambda args: router.filings(args[0]),
    "insiders": lambda args: router.insiders(args[0]),
    "yield_curve": lambda args: router.yield_curve(),
    "macro": lambda args: router.macro(" ".join(args) if args else "dashboard"),
    "energy": lambda args: router.energy_inventories(),
    "crops": lambda args: router.crops(args[0] if args else "CORN"),
    "weather": lambda args: router.weather(),
    "wildfires": lambda args: router.wildfires(),
    "earthquakes": lambda args: router.earthquakes(),
    "flights": lambda args: router.flights(args[0] if args else "nyc"),
    "news": lambda args: router.news(args[0] if args else None),
    "crypto": lambda args: router.crypto_perps(args or None),
    "keys": lambda args: router.key_inventory(),
    # Phase 2: Pure Compute Engine
    "valuation": lambda args: compute_fundamental_snapshot(args[0]),
    "technicals": lambda args: analyze_technicals(args[0], range_str=args[1] if len(args) > 1 else "6mo"),
    "options_greeks": lambda args: analyze_options_chain(args[0], limit=12),
    "risk": lambda args: analyze_stock_risk(args[0], benchmark=args[1] if len(args) > 1 else "SPY"),
    "sentiment": lambda args: score_headlines(router.news(args[0] if args else None, limit=15)),
    "bond": lambda args: compute_bond_metrics(
        face_value=1000.0,
        coupon_rate=float(args[0]) if len(args) > 0 else 0.05,
        ytm=float(args[1]) if len(args) > 1 else 0.045,
        years_to_maturity=float(args[2]) if len(args) > 2 else 10.0,
    ),
    "score": lambda args: score_stock(args[0])["compact_ai_dossier"],
    "screen": lambda args: screen_watchlist(args if args else ["AAPL", "NVDA", "MSFT"]),
    "debate": lambda args: debate_stock(args[0] if args else "AAPL"),
    "audit": lambda args: audit_filing(args[0] if args else "AAPL"),
    "briefing": lambda args: morning_briefing(),
    "best_picks": lambda args: daily_pick_scan(args if args else None),
    "ai_health": lambda args: llm_router.gateway_health(),
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("DoomsBlerg CLI — Available commands:")
        print("  " + ", ".join(sorted(COMMANDS.keys())))
        return 0

    cmd = sys.argv[1].lower().strip()
    args = sys.argv[2:]
    if cmd not in COMMANDS:
        print(f"Unknown command '{cmd}'. Available: {', '.join(sorted(COMMANDS.keys()))}")
        return 1

    result = COMMANDS[cmd](args)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
