"""
DoomsBlerg Terminal CLI (Phases 1-4 Unified Command Center)
===========================================================
Run plain-English market queries, valuations, AI council debates, God's Eye
geospatial triggers, and the Web API gateway straight from your shell.

Examples:
    python3 backend/cli.py ask "Show me Apple's financials"
    python3 backend/cli.py "what is on fire"
    python3 backend/cli.py debate AAPL
    python3 backend/cli.py gods_eye
    python3 backend/cli.py fx USD EUR
    python3 backend/cli.py compare AAPL MSFT NVDA
    python3 backend/cli.py serve 8000
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
from backend.api import serve_forever
from backend.commands import list_supported_commands, run_command
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
    # Phase 4: Plain English Commands, God's Eye & Extended Market Feeds
    "ask": lambda args: run_command(" ".join(args)),
    "fx": lambda args: router.fx(base=args[0] if args else "USD", targets=args[1:] or None),
    "commodities": lambda args: router.commodities(),
    "climate": lambda args: router.climate(),
    "satellites": lambda args: router.satellites(args[0] if args else "stations"),
    "ships": lambda args: router.ships(args[0] if args else "Singapore"),
    "compare": lambda args: router.peers(args if len(args) >= 2 else ["AAPL", "MSFT", "NVDA"]),
    "gods_eye": lambda args: scan_gods_eye_triggers(
        flight_region=args[0] if len(args) > 0 else "nyc",
        ship_chokepoint=args[1] if len(args) > 1 else "Singapore",
    ),
    "commands": lambda args: list_supported_commands(),
    # Phase 6/7: Backtesting & Alpaca Paper Execution
    "backtest": lambda args: run_backtest(
        args[0] if len(args) > 0 else "AAPL",
        strategy=args[1] if len(args) > 1 else "sma_cross",
        range_str=args[2] if len(args) > 2 else "2y",
    ),
    "account": lambda args: get_paper_account(),
    "positions": lambda args: get_paper_positions(),
    "orders": lambda args: get_paper_orders(),
    "portfolio_risk": lambda args: check_portfolio_risk(),
    "stress_test": lambda args: check_portfolio_risk(),
    "trade_preview": lambda args: place_paper_order(
        symbol=args[0] if len(args) > 0 else "AAPL",
        qty=float(args[1]) if len(args) > 1 else 1.0,
        side=args[2] if len(args) > 2 else "buy",
        confirm=False,
    ),
    "cancel_order": lambda args: cancel_paper_order(args[0]),
}


def _interactive_loop() -> int:
    print("DoomsBlerg Interactive Plain-English Terminal (type 'exit' to quit, 'help' for examples)")
    while True:
        try:
            line = input("\nDoomsBlerg> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line.lower() in ("exit", "quit", "q"):
            return 0
        print(json.dumps(run_command(line), indent=2, default=str))


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("DoomsBlerg CLI — Available commands:")
        print("  " + ", ".join(sorted([*COMMANDS.keys(), "interactive", "serve"])))
        print("Or pass any plain-English sentence directly, e.g.:")
        print('  python3 backend/cli.py "Show me Apple\'s financials"')
        return 0

    cmd = sys.argv[1].lower().strip()
    args = sys.argv[2:]

    if cmd == "interactive":
        return _interactive_loop()
    if cmd == "serve":
        port = int(args[0]) if args else 8000
        host = args[1] if len(args) > 1 else "127.0.0.1"
        serve_forever(host=host, port=port)
        return 0

    if cmd not in COMMANDS:
        # Seamless plain-English execution even without typing `ask`
        full_query = " ".join(sys.argv[1:])
        result = run_command(full_query)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("intent") != "unknown" else 1

    result = COMMANDS[cmd](args)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
