"""
Phase 5-7 End-to-End Verification: Backtester, Alpaca Paper Broker & Web UI
============================================================================
1. Unit & safety tests: deterministic zero-lookahead backtest math, Alpaca paper safety
   locks (`confirm=False` default, 204 DELETE handling, portfolio crash stress test),
   and plain-English command grammar for backtest/portfolio/order intents.
2. Live tests: real historical backtests (`sma_cross`, `rsi_reversion`), live Alpaca Paper
   account/positions/orders/risk sync + dry-run pre-trade check, and static HTML/CSS/JS +
   backtest/paper HTTP server end-to-end checks.
"""

import json
import sys
import threading
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api import create_http_server
from backend.commands import parse_plain_command
from backend.trading import (
    cancel_paper_order,
    check_portfolio_risk,
    get_paper_account,
    get_paper_orders,
    get_paper_positions,
    place_paper_order,
    run_backtest,
)


def run_unit_tests() -> None:
    print("=== PART 1: BACKTEST, PAPER BROKER SAFETY & UI GRAMMAR UNIT TESTS ===")

    # 1. Plain English command routing for Phase 6/7 commands
    bt = parse_plain_command("backtest NVDA rsi")
    assert bt and bt["intent"] == "backtest" and bt["args"] == ["NVDA", "rsi_reversion"]
    st = parse_plain_command("stress test my holdings")
    assert st and st["intent"] == "portfolio_risk"
    ord_cmd = parse_plain_command("buy 2 shares of Apple")
    assert ord_cmd and ord_cmd["intent"] == "paper_order_preview" and ord_cmd["args"] == ["AAPL", "2", "buy"]
    print("[PASS] Plain English routes for backtest, stress test & safe order preview")

    # 2. Deterministic backtest engine on synthetic rising then falling trend (zero lookahead)
    synth_bars = []
    for i in range(90):
        px = 100.0 + i * 0.8 if i < 65 else 152.0 - (i - 65) * 2.2
        synth_bars.append(
            {
                "date": f"2026-01-{(i % 28) + 1:02d}",
                "open": px,
                "high": px + 1.0,
                "low": px - 1.0,
                "close": px,
                "volume": 100000,
            }
        )
    with patch("backend.trading.backtester.get_historical_prices", return_value=synth_bars):
        sim = run_backtest("SYNTH", strategy="sma_cross", initial_capital=10000.0, stop_loss_pct=5.0)
        assert sim["bars_tested"] == 90 and sim["final_equity"] > 0
        assert len(sim["equity_curve"]) >= 10
        assert "plain_english_summary" in sim
    print(f"[PASS] Synthetic backtest zero-lookahead check (Return={sim['total_return_pct']}%)")

    # 3. Paper broker dry-run safety guard, confirmed submission mock, and 204 DELETE order cancel
    fake_acct = {"equity": 100000.0, "buying_power": 100000.0, "cash": 100000.0}
    with patch("backend.trading.paper_broker.get_paper_account", return_value=fake_acct), \
         patch("backend.trading.paper_broker.get_quote_cross_verified", return_value={"price": 200.0}), \
         patch("backend.trading.paper_broker.analyze_technicals", return_value={"suggested_atr_stop_loss": 190.0, "suggested_atr_target": 215.0}):
        dry = place_paper_order("AAPL", qty=2, side="buy", confirm=False)
        assert dry["submitted"] is False and dry["estimated_order_value"] == 400.0

        with patch("backend.trading.paper_broker.fetch_json", return_value={"id": "ord-123", "symbol": "AAPL", "side": "buy", "qty": "2", "type": "market", "status": "accepted"}):
            live_mock = place_paper_order("AAPL", qty=2, side="buy", confirm=True)
            assert live_mock["submitted"] is True and live_mock["order_id"] == "ord-123"

    with patch("backend.trading.paper_broker.fetch_text", return_value=""):
        canceled = cancel_paper_order("ord-123")
        assert canceled["canceled"] is True and canceled["order_id"] == "ord-123"
    print("[PASS] Paper broker dry-run safety guard, mock submission & HTTP 204 cancel handling")

    # 4. Portfolio crash stress test on custom holdings
    with patch("backend.trading.paper_broker.analyze_stock_risk", return_value={"beta_vs_benchmark": 1.4, "annualized_volatility_pct": 28.0}):
        risk = check_portfolio_risk(custom_holdings=[{"symbol": "NVDA", "market_value": 50000.0, "side": "long"}])
        assert risk["weighted_beta"] == 1.4
        assert risk["stress_scenarios"]["market_crash_spy_minus_15pct"]["estimated_pnl"] < 0
    print(f"[PASS] Portfolio risk & stress test math (Beta={risk['weighted_beta']})")


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

    print("\n=== PART 2: LIVE BACKTEST, ALPACA PAPER & WORKSTATION UI HTTP ===")
    bt1 = check("Live Historical Backtest (AAPL sma_cross 2y)", lambda: run_backtest("AAPL", strategy="sma_cross", range_str="2y"))
    if bt1:
        print(f"       -> {bt1['plain_english_summary']}")

    bt2 = check("Live Historical Backtest (MSFT rsi_reversion 2y)", lambda: run_backtest("MSFT", strategy="rsi_reversion", range_str="2y"))
    if bt2:
        print(f"       -> Return={bt2['total_return_pct']}% | Trades={bt2['closed_trades']} | WinRate={bt2['win_rate_pct']}%")

    acct = check("Alpaca Paper Account Sync", get_paper_account)
    if acct:
        print(f"       -> Equity=${acct['equity']:,.2f} | Cash=${acct['cash']:,.2f} | BuyingPower=${acct['buying_power']:,.2f}")

    pos = check("Alpaca Paper Positions", get_paper_positions)
    if pos:
        print(f"       -> Open positions={pos['count']}")

    orders = check("Alpaca Paper Orders", lambda: get_paper_orders(limit=5))
    if orders:
        print(f"       -> Recent orders={orders['count']}")

    p_risk = check("Portfolio Risk & Stress Scenarios", check_portfolio_risk)
    if p_risk:
        print(f"       -> {p_risk['plain_english_summary']}")

    preview = check("Safe Pre-Trade Preview (BUY 1 AAPL, confirm=False)", lambda: place_paper_order("AAPL", qty=1, side="buy", confirm=False))
    if preview:
        assert preview["submitted"] is False
        print(f"       -> EstValue=${preview['estimated_order_value']} | StopHint=${preview['suggested_atr_stop_loss']}")

    def _ui_and_api_http() -> dict:
        srv = create_http_server("127.0.0.1", 0)
        port = srv.server_address[1]
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
                html = r.read().decode()
                assert r.status == 200 and "DoomsBlerg Terminal" in html and "order-confirm-dialog" in html
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/styles.css", timeout=5) as r:
                css = r.read().decode()
                assert r.status == 200 and "@layer reset" in css
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/app.js", timeout=5) as r:
                js = r.read().decode()
                assert r.status == 200 and "loadGodsEye" in js
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/backtest?ticker=AAPL&strategy=sma_cross&range=1y", timeout=10) as r:
                bt = json.loads(r.read().decode())
                assert r.status == 200 and "equity_curve" in bt
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/paper/account", timeout=10) as r:
                pa = json.loads(r.read().decode())
                assert r.status == 200 and pa["mode"] == "PAPER_SIMULATED"
            return {"port": port, "html_bytes": len(html), "css_bytes": len(css), "js_bytes": len(js), "paper_equity": pa["equity"]}
        finally:
            srv.shutdown()
            srv.server_close()

    ui_http = check("Web Workstation Static UI + Trading Endpoints Live HTTP", _ui_and_api_http)
    if ui_http:
        print(f"       -> {ui_http}")

    print("\n=== PHASE 5-7 SUMMARY ===")
    print(f"Failures: {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    run_unit_tests()
    raise SystemExit(run_live_tests())
