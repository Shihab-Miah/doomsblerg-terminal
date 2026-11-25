"""
DoomsBlerg Unified Data Router (Phase 1 Core)
============================================
Single plain-English entry point uniting all 17 keys + keyless feeds
across Equities, Options, Macro, SEC Filings, Energy, Agriculture, Weather,
Geospatial Telemetry, News, and Crypto Perpetuals.

Runs cleanly on Python 3.14 stdlib with zero third-party installs required.
"""

from typing import Any, Dict, List, Optional
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.data_engine import (
    commodities_geo,
    config,
    equities,
    http_client,
    macro_bonds,
    sec_intelligence,
)
from geospatial import earth_events, flight_tracker, ship_tracker


class DoomsBlergRouter:
    """Unified, plain-English financial and geospatial data router."""

    def price(self, ticker: str) -> Dict[str, Any]:
        """Cross-verified live stock quote across Alpaca, Finnhub, Tiingo, Twelve Data & Yahoo."""
        return equities.get_quote_cross_verified(ticker)

    def about(self, ticker: str) -> Dict[str, Any]:
        """Plain-English company profile (replaces Bloomberg DES)."""
        return equities.get_company_overview(ticker)

    def history(self, ticker: str, range_str: str = "3mo", interval: str = "1d") -> List[Dict[str, Any]]:
        """Historical OHLCV bars (replaces Bloomberg GP)."""
        return equities.get_historical_prices(ticker, range_str=range_str, interval=interval)

    def financials(self, ticker: str, limit: int = 4) -> Dict[str, Any]:
        """Income statement, balance sheet, and cash flows (replaces Bloomberg FA)."""
        return equities.get_financial_statements(ticker, limit=limit)

    def forecasts(self, ticker: str) -> Dict[str, Any]:
        """Wall Street analyst recommendations & key valuation ratios (replaces EE)."""
        return equities.get_analyst_forecasts(ticker)

    def options(self, ticker: str, limit: int = 30) -> Dict[str, Any]:
        """Live options chain snapshots with Greeks & IV (replaces OMON)."""
        return equities.get_options_chain(ticker, limit=limit)

    def filings(self, ticker: str, forms: Optional[List[str]] = None, limit: int = 10) -> Dict[str, Any]:
        """Direct SEC EDGAR filings with official URLs (replaces CF)."""
        return sec_intelligence.get_recent_filings(ticker, forms=forms, limit=limit)

    def insiders(self, ticker: str, limit: int = 15) -> Dict[str, Any]:
        """SEC Form 4 insider buying and selling summary (replaces INSDR)."""
        return sec_intelligence.get_insider_activity(ticker, limit=limit)

    def yield_curve(self, year: Optional[int] = None) -> Dict[str, Any]:
        """US Treasury daily yield curve & inversion spreads (replaces YCRV)."""
        return macro_bonds.get_yield_curve(year=year)

    def macro(self, query: str = "dashboard") -> Dict[str, Any]:
        """Macroeconomics snapshot or specific indicator by plain English name."""
        if query.lower().strip() == "dashboard":
            return macro_bonds.get_macro_dashboard()
        return macro_bonds.get_macro_indicator(query)

    def energy_inventories(self, limit: int = 8) -> Dict[str, Any]:
        """Weekly US crude oil stocks from EIA Open Data."""
        return commodities_geo.get_energy_inventories(limit=limit)

    def crops(self, commodity: str = "CORN", year: int = 2025, state: str = "IA") -> Dict[str, Any]:
        """Official USDA NASS crop statistics."""
        return commodities_geo.get_crop_progress(commodity=commodity, year=year, state=state)

    def weather(self, lat: float = 41.88, lon: float = -93.10, days: int = 7) -> Dict[str, Any]:
        """Global 7-day forecast (defaults to US Corn Belt)."""
        return commodities_geo.get_weather_forecast(lat=lat, lon=lon, days=days)

    def wildfires(self) -> Dict[str, Any]:
        """Global satellite fires filtered for oil hubs and crop belts (NASA FIRMS)."""
        return earth_events.scan_commodity_wildfires()

    def earthquakes(self, min_magnitude: float = 4.5, days_back: int = 3) -> Dict[str, Any]:
        """Real-time USGS earthquakes with semiconductor/port/mine alerts."""
        return earth_events.get_recent_earthquakes(min_magnitude=min_magnitude, days_back=days_back)

    def flights(self, region: str = "nyc") -> Dict[str, Any]:
        """Live ADS-B flights, air cargo, and executive jets via adsb.lol."""
        return flight_tracker.get_flights_in_preset(region)

    def chokepoints(self) -> Dict[str, Any]:
        """Return maritime chokepoint bounding boxes for God's Eye View."""
        return ship_tracker.MAJOR_CHOKEPOINTS

    def ships(self, chokepoint: str = "Singapore", listen_seconds: float = 3.5) -> Dict[str, Any]:
        """Capture a live AIS ship snapshot near a maritime chokepoint (with timeout fallback)."""
        return ship_tracker.collect_ships_snapshot(chokepoint=chokepoint, listen_seconds=listen_seconds)

    def satellites(self, category: str = "stations", limit: int = 15) -> Dict[str, Any]:
        """Fetch live CelesTrak satellite catalog (orbital station/navigation alerts)."""
        return earth_events.get_active_satellites(category=category, limit=limit)

    def fx(self, base: str = "USD", targets: Optional[List[str]] = None) -> Dict[str, Any]:
        """Live FX exchange rates via Frankfurter ECB + Alpha Vantage (replaces FXC)."""
        return commodities_geo.get_fx_rates(base=base, targets=targets)

    def commodities(self) -> Dict[str, Any]:
        """Global energy, metals & agricultural futures + EIA crude oil delta (replaces COMS)."""
        return commodities_geo.get_commodities_snapshot()

    def climate(self, limit: int = 10) -> Dict[str, Any]:
        """Official NOAA Climate Data Online datasets (NOAA_CDO_TOKEN)."""
        return commodities_geo.get_noaa_climate_datasets(limit=limit)

    def peers(self, tickers: List[str]) -> Dict[str, Any]:
        """Compare valuation ratios and price action across peers (replaces RV)."""
        return equities.compare_peers(tickers)

    def news(self, ticker: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        """Curated real-time financial news combining Finnhub + Google News RSS."""
        return commodities_geo.get_market_news(ticker=ticker, limit=limit)

    def crypto_perps(self, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Live Hyperliquid funding rates, mark prices, and open interest."""
        return commodities_geo.get_crypto_perps(symbols=symbols)

    def key_inventory(self) -> Dict[str, bool]:
        """Report which configured API keys are populated (without exposing secrets)."""
        names = [
            "FRED_API_KEY",
            "FINNHUB_API_KEY",
            "NASA_FIRMS_API_KEY",
            "ALPACA_API_KEY",
            "ALPACA_SECRET_KEY",
            "ALPHA_VANTAGE_API_KEY",
            "EIA_API_KEY",
            "USDA_NASS_API_KEY",
            "NOAA_CDO_TOKEN",
            "TWELVEDATA_API_KEY",
            "FMP_API_KEY",
            "MASSIVE_API_KEY",
            "TIINGO_API_KEY",
            "GROQ_API_KEY",
            "GEMINI_API_KEY",
            "OPENROUTER_API_KEY",
            "AISSTREAM_API_KEY",
        ]
        return {name: bool(config.get_key(name)) for name in names}


# Module-level singleton & convenience functions
router = DoomsBlergRouter()
clear_cache = http_client.clear_expired_cache
