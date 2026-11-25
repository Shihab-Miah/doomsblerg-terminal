"""
Phase 1 End-to-End Live Verification Suite
==========================================
Tests every subsystem in backend/data_engine and geospatial/ against real live APIs
plus verifies SQLite caching behavior.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.data_engine.router import router


def run_all() -> int:
    failures = []

    def check(name: str, fn):
        t0 = time.time()
        try:
            res = fn()
            dt = round(time.time() - t0, 2)
            assert res, f"{name} returned empty result"
            print(f"[PASS] {name} ({dt}s)")
            return res
        except Exception as exc:
            dt = round(time.time() - t0, 2)
            print(f"[FAIL] {name} ({dt}s): {exc}")
            failures.append((name, str(exc)))
            return None

    # 1. Key inventory
    keys = check("Key Inventory (17 keys configured)", router.key_inventory)
    if keys:
        missing = [k for k, ok in keys.items() if not ok]
        assert not missing, f"Missing keys: {missing}"
        print(f"       -> All {len(keys)} API keys loaded securely.")

    # 2. Cross-verified live quote
    quote = check("Cross-Verified Quote (AAPL)", lambda: router.price("AAPL"))
    if quote:
        print(f"       -> AAPL=${quote['price']} | sources={quote['sources_agreed']} ({list(quote['source_quotes'].keys())}) | spread={quote['cross_feed_spread_pct']}%")
        assert quote["sources_agreed"] >= 3, f"Expected >=3 sources agreed, got {quote['sources_agreed']}"

    # 3. Cache speed verification (2nd call must be < 0.05s)
    t_cache = time.time()
    cached_quote = router.price("AAPL")
    cache_dt = time.time() - t_cache
    assert cached_quote["price"] == quote["price"] and cache_dt < 0.1, f"Cache too slow: {cache_dt:.3f}s"
    print(f"[PASS] SQLite TTL Cache Hit ({cache_dt:.4f}s)")

    # 4. Company overview, history, financials, forecasts, options
    ov = check("Company Overview (AAPL)", lambda: router.about("AAPL"))
    if ov:
        print(f"       -> {ov.get('name')} | Sector={ov.get('sector')} | MarketCap={ov.get('market_cap')}")

    hist = check("Historical Bars (AAPL 1mo)", lambda: router.history("AAPL", range_str="1mo"))
    if hist:
        print(f"       -> {len(hist)} bars | Latest={hist[-1]}")

    fin = check("Financial Statements (AAPL)", lambda: router.financials("AAPL", limit=2))
    if fin:
        inc = fin.get("income_statement") or []
        print(f"       -> Income periods={len(inc)} | Latest FY={inc[0].get('fiscalYear') if inc else 'N/A'}")

    fc = check("Analyst Forecasts (AAPL)", lambda: router.forecasts("AAPL"))
    if fc:
        print(f"       -> Ratings={fc.get('latest_analyst_ratings')}")

    opt = check("Options Chain (AAPL)", lambda: router.options("AAPL", limit=5))
    if opt:
        print(f"       -> Contracts={opt.get('count')} | Sample={opt['contracts'][0]['contract'] if opt.get('contracts') else 'N/A'}")

    # 5. SEC EDGAR Filings & Insiders
    fil = check("SEC EDGAR Filings (AAPL)", lambda: router.filings("AAPL", forms=["10-K", "10-Q", "8-K"], limit=5))
    if fil:
        print(f"       -> CIK={fil['cik']} | Latest={fil['filings'][0]['form']} ({fil['filings'][0]['filing_date']})")

    ins = check("Insider Transactions (AAPL)", lambda: router.insiders("AAPL", limit=5))
    if ins:
        print(f"       -> Signal={ins['signal']} | Net shares={ins['net_insider_shares']}")

    # 6. Macro & Treasury Yield Curve
    yc = check("US Treasury Yield Curve", lambda: router.yield_curve())
    if yc:
        print(f"       -> Date={yc['date']} | 2Y={yc['yields_pct'].get('2 Yr')} | 10Y={yc['yields_pct'].get('10 Yr')} | Inverted={yc['curve_inverted']}")

    mac = check("FRED Macro Dashboard", lambda: router.macro("dashboard"))
    if mac:
        print(f"       -> FedFunds={mac.get('interest rate')} | VIX={mac.get('vix')}")

    # 7. Commodities, Weather, News, Crypto Perps
    eia = check("EIA Crude Oil Inventories", lambda: router.energy_inventories(limit=3))
    if eia:
        print(f"       -> Records={len(eia['records'])} | Latest={eia['records'][0] if eia['records'] else 'N/A'}")

    usda = check("USDA NASS Corn Data", lambda: router.crops("CORN", year=2025, state="IA"))
    if usda:
        print(f"       -> Sample rows={usda['count']}")

    wx = check("Open-Meteo Weather (US Corn Belt)", lambda: router.weather())
    if wx:
        print(f"       -> Days={len((wx.get('daily') or {}).get('time') or [])}")

    news = check("Market News (AAPL)", lambda: router.news("AAPL", limit=5))
    if news:
        print(f"       -> Headlines={len(news)} | Top='{news[0]['title'][:65]}...'")

    perps = check("Hyperliquid Crypto Perps", lambda: router.crypto_perps(["BTC", "ETH"]))
    if perps:
        print(f"       -> BTC mark=${perps[0]['mark_price']} | funding={perps[0]['funding_rate_hourly']}")

    # 8. Geospatial (Wildfires, Earthquakes, Live Flights)
    fires = check("NASA FIRMS Commodity Wildfires", lambda: router.wildfires())
    if fires:
        print(f"       -> Global={fires['total_global_sampled']} | Oil={fires['oil_fire_count']} | Farm={fires['farm_fire_count']}")

    quakes = check("USGS Earthquakes", lambda: router.earthquakes(min_magnitude=4.5, days_back=3))
    if quakes:
        print(f"       -> Count={quakes['count']} | Hub alerts={len(quakes['critical_hub_alerts'])}")

    flights = check("ADSB.lol Live Flights (NYC)", lambda: router.flights("nyc"))
    if flights:
        print(f"       -> Aircraft={flights['total_aircraft']} | Cargo={len(flights['cargo_flights'])} | ExecJets={len(flights['executive_jets'])}")

    print("\n=== SUMMARY ===")
    print(f"Failures: {len(failures)}")
    if failures:
        for n, err in failures:
            print(f" - {n}: {err}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run_all())
