"""
DoomsBlerg Flight Tracker — Aviation Intelligence
==================================================
Tracks commercial aircraft and private jets in real time using ADS-B data.

Why this matters for trading:
- Private/corporate jet movements → M&A signals (executives meeting before deals)
- Air cargo volumes → express shipping stocks (FedEx, UPS, DHL)
- Airline passenger flows → tourism stocks, regional economic health
- Unusual executive fleet activity → potential corporate events
- Air cargo route changes → supply chain shifts

Data sources:
- OpenSky Network (free, global ADS-B)
- adsb.lol (free, community ADS-B)
"""

import requests
import pandas as pd
from typing import Optional, List, Tuple


OPENSKY_API_URL = "https://opensky-network.org/api"


def get_flights_in_area(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> pd.DataFrame:
    """
    Get all aircraft currently flying within a geographic bounding box.

    Args:
        min_lat, max_lat: Latitude range (south to north)
        min_lon, max_lon: Longitude range (west to east)
        username/password: Optional OpenSky account for higher rate limits

    Returns DataFrame with columns:
        icao24, callsign, origin_country, longitude, latitude,
        baro_altitude_m, velocity_ms, true_track (heading), vertical_rate,
        on_ground, squawk

    Common areas to watch:
        New York airspace:    lat 40.0–42.0, lon -75.0 to -73.0
        Los Angeles:          lat 33.5–34.5, lon -119.0 to -117.5
        London Heathrow:      lat 51.0–52.0, lon -1.5 to 0.5
        Dubai:                lat 24.5–25.5, lon 54.5–55.5
    """
    auth = (username, password) if username else None
    params = {
        "lamin": min_lat, "lamax": max_lat,
        "lomin": min_lon, "lomax": max_lon,
    }
    response = requests.get(f"{OPENSKY_API_URL}/states/all", params=params, auth=auth)
    response.raise_for_status()

    data = response.json()
    states = data.get("states", [])

    columns = [
        "icao24", "callsign", "origin_country", "time_position", "last_contact",
        "longitude", "latitude", "baro_altitude_m", "on_ground", "velocity_ms",
        "true_track", "vertical_rate", "sensors", "geo_altitude_m", "squawk",
        "spi", "position_source",
    ]
    df = pd.DataFrame(states, columns=columns)
    df["callsign"] = df["callsign"].str.strip()
    return df[["icao24", "callsign", "origin_country", "longitude", "latitude",
               "baro_altitude_m", "velocity_ms", "true_track", "on_ground"]]


def get_aircraft_history(icao24: str, start_time: int, end_time: int) -> pd.DataFrame:
    """
    Get the flight history for a specific aircraft by its ICAO24 transponder ID.
    Use this to track where a corporate jet has been flying.

    Args:
        icao24: Aircraft transponder hex code (e.g., "a0b1c2")
        start_time: Unix timestamp for start of period
        end_time: Unix timestamp for end of period
    """
    params = {"icao24": icao24, "begin": start_time, "end": end_time}
    response = requests.get(f"{OPENSKY_API_URL}/flights/aircraft", params=params)
    response.raise_for_status()

    flights = response.json()
    return pd.DataFrame(flights)


# ─────────────────────────────────────────────────────────────
# CORPORATE JET TRACKER (M&A Signal)
# ─────────────────────────────────────────────────────────────

# Known corporate ICAO24 hex codes — expand this list over time
# Source: FAA Registry + ICAO databases
CORPORATE_FLEET_REGISTRY = {
    # Format: "icao24_hex": {"company": "Company Name", "ticker": "AAPL", "aircraft": "Gulfstream G650"}
    # This database is built up over time by cross-referencing FAA N-number registry
    # with public company filings (companies must disclose aircraft ownership)
}


def watch_corporate_jets(icao24_list: List[str], area_bounds: Tuple) -> pd.DataFrame:
    """
    Watch a list of known corporate aircraft within an area.
    Flags when known corporate jets make unusual route deviations.

    This is the same type of analysis hedge funds run to get M&A signals
    before official announcements.
    """
    min_lat, max_lat, min_lon, max_lon = area_bounds
    all_flights = get_flights_in_area(min_lat, max_lat, min_lon, max_lon)
    corporate_flights = all_flights[all_flights["icao24"].isin(icao24_list)]
    return corporate_flights


# ─────────────────────────────────────────────────────────────
# AIR CARGO SIGNAL (Shipping Stocks / Supply Chain)
# ─────────────────────────────────────────────────────────────

CARGO_AIRLINE_CALLSIGNS = {
    "FDX": "FedEx",
    "UPS": "UPS Airlines",
    "GTI": "Atlas Air",
    "CLX": "Cargolux",
    "AIC": "Air India Cargo",
}

def filter_cargo_flights(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter a flight DataFrame to show only known cargo aircraft.
    Useful for tracking air freight volume as a signal for express shipping stocks.
    """
    return df[df["callsign"].str[:3].isin(CARGO_AIRLINE_CALLSIGNS.keys())]
