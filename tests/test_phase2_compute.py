"""
Phase 2 Compute Engine Verification Suite
=========================================
1. Exact mathematical & financial identity unit tests (Put-Call Parity, Bond Par Pricing,
   WACC, DCF, Altman Z-Score, Piotroski F-Score, RSI, MACD, Bollinger, ATR, Sharpe, MaxDD, VADER).
2. Live end-to-end tests running on real market feeds for AAPL + multi-ticker watchlist screening.
"""

import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.compute_engine import (
    analyze_options_chain,
    analyze_stock_risk,
    analyze_technicals,
    black_scholes,
    bollinger_bands,
    compute_altman_z_score,
    compute_bond_metrics,
    compute_dcf,
    compute_fundamental_snapshot,
    compute_piotroski_f_score,
    compute_portfolio_risk,
    compute_wacc,
    implied_volatility,
    macd,
    rsi,
    score_stock,
    score_text,
    screen_watchlist,
    sma,
    vwap,
)


def run_math_unit_tests() -> None:
    print("=== PART 1: MATHEMATICAL IDENTITY TESTS ===")

    # 1. Black-Scholes Put-Call Parity: C - P = S*e^(-qT) - K*e^(-rT)
    S, K, T, r, q, vol = 150.0, 145.0, 0.5, 0.045, 0.01, 0.28
    call = black_scholes(S, K, T, r, vol, "call", q)
    put = black_scholes(S, K, T, r, vol, "put", q)
    lhs = call["theoretical_price"] - put["theoretical_price"]
    rhs = S * math.exp(-q * T) - K * math.exp(-r * T)
    assert abs(lhs - rhs) < 1e-3, f"Put-Call Parity failed: {lhs} != {rhs}"
    assert 0 < call["delta"] < 1 and -1 < put["delta"] < 0
    assert abs((call["delta"] - put["delta"]) - math.exp(-q * T)) < 1e-3
    print(f"[PASS] Black-Scholes Put-Call Parity exact ({lhs:.4f} == {rhs:.4f})")

    # 2. Implied Volatility round-trip recovery
    iv_recovered = implied_volatility(call["theoretical_price"], S, K, T, r, "call", q)
    assert abs(iv_recovered - vol) < 1e-3, f"IV round-trip failed: {iv_recovered} != {vol}"
    print(f"[PASS] Implied Volatility Solver round-trip ({iv_recovered:.4f} == {vol:.4f})")

    # 3. Bond pricing identity: Coupon == YTM -> Clean Price == Face Value (1000.0)
    par_bond = compute_bond_metrics(face_value=1000.0, coupon_rate=0.05, ytm=0.05, years_to_maturity=10.0, freq=2)
    assert abs(par_bond["clean_price"] - 1000.0) < 1e-3
    assert 7.0 < par_bond["modified_duration_years"] < 8.5
    disc_bond = compute_bond_metrics(face_value=1000.0, coupon_rate=0.04, ytm=0.06, years_to_maturity=10.0, freq=2)
    assert disc_bond["clean_price"] < 1000.0
    print(f"[PASS] Bond Pricing & Duration (Par={par_bond['clean_price']}, ModDur={par_bond['modified_duration_years']}y)")

    # 4. WACC & DCF
    wacc = compute_wacc(market_cap=800.0, total_debt=200.0, beta=1.0, risk_free_rate=0.04, equity_risk_premium=0.05, interest_expense=10.0, tax_rate=0.20)
    # Ke=0.09 (80%), Kd_after=0.05*0.8=0.04 (20%) -> 0.8*0.09 + 0.2*0.04 = 0.072 + 0.008 = 0.08
    assert abs(wacc["wacc"] - 0.08) < 1e-4, f"WACC failed: {wacc}"
    dcf = compute_dcf([100.0, 95.0], shares_outstanding=100.0, total_cash=50.0, total_debt=50.0, current_price=15.0, wacc=0.08, growth_rate=0.05)
    assert dcf["fair_value_per_share"] > 15.0 and dcf["valuation_status"] == "undervalued"
    print(f"[PASS] WACC (8.00%) & DCF Fair Value (${dcf['fair_value_per_share']})")

    # 5. Altman Z-Score & Piotroski F-Score
    z_safe = compute_altman_z_score(
        {"totalAssets": 1000, "totalLiabilities": 300, "totalCurrentAssets": 500, "totalCurrentLiabilities": 200, "retainedEarnings": 400},
        {"operatingIncome": 200, "revenue": 1200},
        market_cap=2000,
    )
    assert z_safe["zone"] == "safe_zone" and z_safe["z_score"] > 2.99
    f_perfect = compute_piotroski_f_score(
        [{"netIncome": 120, "revenue": 1100, "grossProfit": 550, "weightedAverageShsOutDil": 100},
         {"netIncome": 80, "revenue": 900, "grossProfit": 400, "weightedAverageShsOutDil": 102}],
        [{"totalAssets": 1000, "longTermDebt": 100, "totalCurrentAssets": 400, "totalCurrentLiabilities": 150},
         {"totalAssets": 1000, "longTermDebt": 200, "totalCurrentAssets": 300, "totalCurrentLiabilities": 150}],
        [{"operatingCashFlow": 150}],
    )
    assert f_perfect["f_score"] == 9, f"Expected 9/9 Piotroski, got {f_perfect}"
    print(f"[PASS] Altman Z-Score ({z_safe['z_score']}) & Piotroski F-Score ({f_perfect['f_score']}/9)")

    # 6. Technicals & Risk Math
    up_series = [100.0 + i * 1.2 + (0.5 if i % 2 else -0.3) for i in range(60)]
    r_val = rsi(up_series, 14)
    m_val = macd(up_series)
    bb_val = bollinger_bands(up_series)
    assert r_val is not None and 50 < r_val <= 100
    assert m_val["macd"] is not None and bb_val["upper"] > bb_val["middle"] > bb_val["lower"]
    assert sma([10, 20, 30], 3) == 20.0
    assert vwap([{"high": 102, "low": 98, "close": 100, "volume": 1000}]) == 100.0

    known_ret = [0.01, -0.02, 0.015, 0.005, -0.03, 0.02, 0.01, -0.005, 0.012, 0.008, -0.01, 0.004]
    pr = compute_portfolio_risk(known_ret, known_ret)
    assert abs(pr["beta_vs_benchmark"] - 1.0) < 1e-3 and pr["max_drawdown_pct"] < 0
    print(f"[PASS] Technicals (RSI={r_val}) & Portfolio Risk (Beta={pr['beta_vs_benchmark']}, MaxDD={pr['max_drawdown_pct']}%)")

    # 7. Sentiment Lexicon & Negation
    bull = score_text("Apple beats earnings estimates with record profit growth")
    bear = score_text("Company faces fraud probe and slashes guidance on weak demand")
    neg = score_text("Company did not miss revenue expectations")
    assert bull["label"] == "bullish" and bear["label"] == "bearish" and neg["score"] > 0
    print(f"[PASS] Zero-RAM Sentiment Lexicon (bull={bull['score']}, bear={bear['score']}, neg_flip={neg['score']})")


def run_live_compute_tests() -> int:
    print("\n=== PART 2: LIVE MARKET COMPUTE TESTS ===")
    failures = []

    def check(name, fn):
        t0 = time.time()
        try:
            res = fn()
            dt = round(time.time() - t0, 2)
            assert res and "error" not in res, f"Error in {name}: {res}"
            print(f"[PASS] {name} ({dt}s)")
            return res
        except Exception as exc:
            dt = round(time.time() - t0, 2)
            print(f"[FAIL] {name} ({dt}s): {exc}")
            failures.append((name, str(exc)))
            return None

    fund = check("Live Fundamental Valuation (AAPL)", lambda: compute_fundamental_snapshot("AAPL"))
    if fund:
        dcf = fund["dcf_valuation"]
        print(f"       -> Price=${fund['current_price']} | DCF Fair=${dcf['fair_value_per_share']} ({dcf['upside_pct']}%) | WACC={fund['wacc']['wacc_pct']}% | Z={fund['altman_z_score']['z_score']} | F={fund['piotroski_f_score']['f_score']}/9")

    tech = check("Live Technical Analysis (AAPL)", lambda: analyze_technicals("AAPL", "6mo"))
    if tech:
        print(f"       -> Trend={tech['trend']} | RSI={tech['rsi_14']} ({tech['rsi_state']}) | MACD={tech['macd']['trend']} | Stop=${tech['suggested_atr_stop_loss']}")

    opt = check("Live Options Greeks & IV (AAPL)", lambda: analyze_options_chain("AAPL", limit=6))
    if opt:
        sample = opt["contracts"][0]
        print(f"       -> Spot=${opt['spot_price']} | Sample={sample['contract']} mid=${sample['market_mid']} | IV={sample['implied_vol_pct']}%")

    risk = check("Live Stock Risk vs SPY (AAPL)", lambda: analyze_stock_risk("AAPL", "SPY", "1y"))
    if risk:
        print(f"       -> AnnRet={risk['annualized_return_pct']}% | Sharpe={risk['sharpe_ratio']} | MaxDD={risk['max_drawdown_pct']}% | Beta={risk['beta_vs_benchmark']}")

    screen = check("Live Watchlist Quant Screener (AAPL, NVDA, MSFT)", lambda: {"ranked": screen_watchlist(["AAPL", "NVDA", "MSFT"])})
    if screen:
        for row in screen["ranked"]:
            print(f"       -> #{row.get('ticker')}: Score={row.get('quant_score_100')}/100 ({row.get('quant_signal')}) | Price=${row.get('price')} | DCF=${row.get('dcf_fair_value')}")

    print("\n=== PHASE 2 SUMMARY ===")
    print(f"Failures: {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    run_math_unit_tests()
    raise SystemExit(run_live_compute_tests())
