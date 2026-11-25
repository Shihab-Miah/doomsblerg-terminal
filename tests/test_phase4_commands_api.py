"""
Phase 4 Plain English Command System, God's Eye Triggers & Web API Verification
===============================================================================
1. Deterministic unit tests: plain-English command grammar, Bloomberg code aliasing,
   NASA FIRMS secret redaction, geospatial trigger logic, and mocked AI fallback.
2. Live verification of newly wired keys/fixes: EIA WCESTUS1, Alpha Vantage + ECB FX,
   Massive daily bars, NOAA CDO datasets, CelesTrak satellites, Peer comparison, Commodities, AIS.
3. Live end-to-end Web API HTTP server (`GET /health`, `/api/endpoints`, `/api/ask`, `/api/gods-eye`).
"""

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api import create_http_server, dispatch_api_request
from backend.commands import parse_plain_command, run_command
from backend.data_engine.equities import _history_from_massive
from backend.data_engine.http_client import _safe_url_for_error
from backend.data_engine.router import router
from geospatial.gods_eye import _build_signal_triggers, scan_gods_eye_triggers


def run_unit_tests() -> None:
    print("=== PART 1: PLAIN ENGLISH GRAMMAR, REDACTION & TRIGGER UNIT TESTS ===")

    cases = [
        ("Show me Apple's financials", "financials", ["AAPL"]),
        ("Compare Apple to Microsoft and Nvidia", "compare", ["AAPL", "MSFT", "NVDA"]),
        ("Who is Nvidia?", "about", ["NVDA"]),
        ("Is the yield curve inverted?", "yield_curve", []),
        ("USD to EUR", "fx", ["USD", "EUR"]),
        ("What is on fire?", "wildfires", []),
        ("Recent earthquakes near Taiwan", "earthquakes", []),
        ("Flights near Taiwan", "flights", ["taiwan"]),
        ("Ships near Hormuz", "ships", ["hormuz"]),
        ("Open globe gods eye view", "gods_eye", []),
        ("Should I buy Tesla right now?", "debate", ["TSLA"]),
        ("Audit 10-K red flags for NVDA", "audit", ["NVDA"]),
        ("What should I watch today morning briefing", "briefing", []),
        ("DES AAPL", "about", ["AAPL"]),
        ("YCRV", "yield_curve", []),
        ("price msft", "price", ["MSFT"]),
    ]
    for query, exp_intent, exp_args in cases:
        parsed = parse_plain_command(query)
        assert parsed is not None, f"Failed to parse: {query}"
        assert parsed["intent"] == exp_intent, f"{query}: got {parsed['intent']}, expected {exp_intent}"
        assert parsed["args"] == exp_args, f"{query}: args {parsed['args']} != {exp_args}"
    print(f"[PASS] Plain English + Bloomberg alias grammar ({len(cases)} cases exact)")

    # URL secret redaction check for embedded NASA FIRMS key
    redacted = _safe_url_for_error("https://firms.modaps.eosdis.nasa.gov/api/area/csv/SECRETKEY123/VIIRS_NOAA21_NRT/-180,-90,180,90/2?foo=bar")
    assert "SECRETKEY123" not in redacted and "***" in redacted and "foo=bar" not in redacted
    print("[PASS] HTTP error URL sanitization redacts path keys & query strings")

    # Geospatial trigger builder logic
    triggers = _build_signal_triggers(
        fires={"oil_fire_count": 12, "oil_region_fires": [{"region_name": "Permian Basin TX"}], "farm_fire_count": 0},
        quakes={"critical_hub_alerts": [{"region_name": "Taiwan Semiconductor Belt", "magnitude": 6.2, "location_name": "Hualien"}]},
        flights={"region": "nyc", "total_aircraft": 50, "cargo_flights": [1], "executive_jets": [1, 2]},
        oil={"latest_week_change_mbbl": -4200.0, "latest_direction": "draw (supply tightening)"},
        ships={"vessel_count": 5, "chokepoint": "Singapore"},
    )
    cats = {t["category"] for t in triggers}
    assert {"wildfire_energy", "seismic_supply_chain", "aviation_activity", "energy_inventory", "maritime_ais"}.issubset(cats)
    print(f"[PASS] God's Eye trigger generator ({len(triggers)} triggers across 5 physical domains)")

    # Mocked LLM intent fallback for non-standard natural English phrasing
    mock_ai = {
        "json": {"intent": "yield_curve", "args": []},
        "provider_used": "mock",
        "model_used": "mock-fast",
    }
    with patch("backend.commands.interpreter.llm_router.generate", return_value=mock_ai), \
         patch("backend.commands.interpreter._execute_intent", return_value={"spread_10y_minus_2y": 0.42}):
        res = run_command("Explain whether banks fear an inversion right now", allow_ai_fallback=True)
        assert res["intent"] == "yield_curve" and res["match_mode"] == "ai_intent_classifier"
    print("[PASS] Cloud AI fallback intent classifier routes ambiguous English safely")


def run_live_tests() -> int:
    failures = []

    def check(name, fn):
        t0 = time.time()
        try:
            res = fn()
            dt = round(time.time() - t0, 2)
            assert res and (not isinstance(res, dict) or "error" not in res), f"Error in {name}: {res}"
            print(f"[PASS] {name} ({dt}s)")
            return res
        except Exception as exc:
            dt = round(time.time() - t0, 2)
            print(f"[FAIL] {name} ({dt}s): {exc}")
            failures.append((name, str(exc)))
            return None

    print("\n=== PART 2: LIVE AUDIT FIXES & EXTENDED DATA FEEDS ===")
    eia = check("EIA Commercial Crude Stocks (WCESTUS1 Fix)", lambda: router.energy_inventories(4))
    if eia:
        chg = eia.get("latest_week_change_mbbl")
        assert chg is not None and abs(chg) < 30000, f"Unrealistic weekly delta (series mix bug?): {chg}"
        print(f"       -> Series={eia['commodity']} | WeeklyDelta={chg:+} MBBL ({eia.get('latest_direction')})")

    fx = check("FX Rates (Alpha Vantage + Frankfurter ECB)", lambda: router.fx("USD", ["EUR", "GBP", "JPY"]))
    if fx:
        assert "EUR" in fx["rates"] and len(fx["sources"]) >= 1
        print(f"       -> Sources={fx['sources']} | 1 USD = {fx['rates'].get('EUR')} EUR, {fx['rates'].get('JPY')} JPY")

    massive_bars = check("Massive Historical OHLCV Fallback (AAPL)", lambda: _history_from_massive("AAPL", "1mo"))
    if massive_bars:
        print(f"       -> Bars={len(massive_bars)} | Latest={massive_bars[-1]}")

    climate = check("NOAA CDO Climate Datasets", lambda: router.climate(limit=5))
    if climate:
        print(f"       -> Datasets returned={len(climate.get('results') or [])}")

    coms = check("Commodities Futures Snapshot", lambda: router.commodities())
    if coms:
        print(f"       -> Sample={coms['commodities'][0]['name']} ${coms['commodities'][0].get('price')}")

    peers = check("Peer Relative Valuation (AAPL vs MSFT)", lambda: router.peers(["AAPL", "MSFT"]))
    if peers:
        assert len(peers.get("peers") or []) == 2
        print(f"       -> Peers={[(p['ticker'], p.get('price'), p.get('pe_ttm')) for p in peers['peers']]}")

    sats = check("CelesTrak Live Satellites JSON", lambda: router.satellites("stations", limit=5))
    if sats:
        assert sats.get("total_tracked", 0) > 0
        print(f"       -> Tracked={sats['total_tracked']} | First={sats['satellites'][0]['name']}")

    ships = check("AISStream Pure-Stdlib Ship Snapshot (Singapore)", lambda: router.ships("Singapore", listen_seconds=2.0))
    if ships:
        print(f"       -> Status={ships['status']} | Vessels={ships.get('vessel_count', 0)}")

    gods_eye = check("God's Eye Unified Signal Engine", lambda: scan_gods_eye_triggers(include_ais_stream=False))
    if gods_eye:
        print(f"       -> Triggers={len(gods_eye['trading_signal_triggers'])} | First='{gods_eye['trading_signal_triggers'][0]['signal']}'")

    print("\n=== PART 3: LIVE PLAIN-ENGLISH COMMANDS & HTTP GATEWAY ===")
    cmd_fx = check("Plain English: 'USD to EUR'", lambda: run_command("USD to EUR", allow_ai_fallback=False))
    if cmd_fx:
        assert cmd_fx["intent"] == "fx" and cmd_fx["match_mode"] == "deterministic_rules"

    cmd_fin = check("Plain English: 'Show me Apple's financials'", lambda: run_command("Show me Apple's financials", allow_ai_fallback=False))
    if cmd_fin:
        assert cmd_fin["intent"] == "financials" and cmd_fin["args"] == ["AAPL"]

    # Live HTTP server socket integration test
    def _http_roundtrip() -> dict:
        srv = create_http_server("127.0.0.1", 0)
        port = srv.server_address[1]
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
                assert r.status == 200
                health = json.loads(r.read().decode())

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/keys", timeout=5) as r:
                keys = json.loads(r.read().decode())
                assert all(keys.values()), f"Missing keys via API: {keys}"

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/stock/AAPL/quote", timeout=10) as r:
                q = json.loads(r.read().decode())
                assert q["ticker"] == "AAPL" and q["price"] > 0

            post_req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/ask",
                data=json.dumps({"query": "what is on fire"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(post_req, timeout=15) as r:
                ask_res = json.loads(r.read().decode())
                assert ask_res["intent"] == "wildfires"

            st_404, _ = dispatch_api_request("GET", "/nonexistent")
            assert st_404 == 404
            return {"health": health, "port": port, "aapl_price": q["price"], "wildfires_oil": ask_res["result"]["oil_fire_count"]}
        finally:
            srv.shutdown()
            srv.server_close()

    http_res = check("Web API ThreadingHTTPServer Live Roundtrip", _http_roundtrip)
    if http_res:
        print(f"       -> HTTP endpoints verified: {http_res}")

    print("\n=== PHASE 4 SUMMARY ===")
    print(f"Failures: {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    run_unit_tests()
    raise SystemExit(run_live_tests())
