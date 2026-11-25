"""
DoomsBlerg Phase 1 Terminal CLI
===============================
Run plain-English financial & geospatial queries straight from your shell.

Examples:
    python3 backend/cli.py price AAPL
    python3 backend/cli.py about NVDA
    python3 backend/cli.py yield_curve
    python3 backend/cli.py macro
    python3 backend/cli.py energy
    python3 backend/cli.py wildfires
    python3 backend/cli.py flights nyc
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.data_engine.router import router


COMMANDS = {
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
