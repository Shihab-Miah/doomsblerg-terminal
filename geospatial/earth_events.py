"""
DoomsBlerg Earth Events — Natural Event Intelligence
=====================================================
Tracks wildfires, earthquakes, and other physical events that move markets.

Why this matters for trading:
- Wildfires near oil fields → crude oil supply shock → energy stocks spike
- Wildfires near farmland → crop damage → agricultural futures (wheat, corn, soybeans)
- Earthquakes near ports → supply chain disruption → shipping stocks
- Earthquakes near tech manufacturing → semiconductor supply shock
- Major fires near timber → lumber futures
- Disasters near refineries → gasoline price spikes

Data sources (all FREE, all government):
- NASA FIRMS — wildfire tracking (same data Bloomberg's environmental desk uses)
- USGS Earthquake Hazards Program — real-time seismic monitoring
"""

import requests
import pandas as pd
from typing import Optional


# ─────────────────────────────────────────────────────────────
# WILDFIRE TRACKER (NASA FIRMS)
# ─────────────────────────────────────────────────────────────

NASA_FIRMS_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def get_active_wildfires(
    api_key: str,
    area: str = "-180,-90,180,90",
    days: int = 2,
    source: str = "VIIRS_NOAA21_NRT",
) -> pd.DataFrame:
    """
    Get all active fire detections worldwide in the last N days.
    Data comes from NASA MODIS and VIIRS satellite instruments.

    Args:
        api_key: NASA FIRMS API key (free at firms.modaps.eosdis.nasa.gov)
        area: Bounding box "lon_min,lat_min,lon_max,lat_max" (default global)
        days: How many days back to look (1-10)
        source: Satellite source
            "VIIRS_NOAA21_NRT" — Best resolution, near real-time (recommended)
            "VIIRS_NOAA20_NRT" — Alternate VIIRS satellite feed
            "MODIS_NRT" — Lower resolution but broader coverage

    Returns DataFrame with:
        latitude, longitude — location of fire
        bright_ti4 — fire brightness temperature (how hot = how big)
        frp — Fire Radiative Power in megawatts (intensity signal for traders)
        acq_date, acq_time — when the satellite detected it
        confidence — detection confidence (high/nominal/low)
        daynight — was it detected during day or night pass
    """
    url = f"{NASA_FIRMS_BASE}/{api_key}/{source}/{area}/{days}"
    response = requests.get(url)
    response.raise_for_status()

    # Parse CSV response
    from io import StringIO
    df = pd.read_csv(StringIO(response.text))
    return df


def get_wildfires_near_oil_infrastructure(fires_df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter fire detections to those near known oil and gas infrastructure.
    Major oil-producing regions to watch:
    - Permian Basin, TX: lat 31-33, lon -104 to -100
    - Alberta Oil Sands, Canada: lat 56-57, lon -112 to -110
    - Gulf Coast Refineries: lat 29-30, lon -95 to -89
    - Siberia (Russian oil): lat 55-70, lon 60-100
    - Middle East: lat 20-30, lon 44-56
    """
    OIL_REGIONS = [
        {"name": "Permian Basin TX", "lat_min": 31, "lat_max": 33, "lon_min": -104, "lon_max": -100},
        {"name": "Alberta Oil Sands", "lat_min": 55, "lat_max": 58, "lon_min": -115, "lon_max": -109},
        {"name": "Gulf Coast Refineries", "lat_min": 28, "lat_max": 31, "lon_min": -97, "lon_max": -88},
        {"name": "West Siberia Russia", "lat_min": 55, "lat_max": 70, "lon_min": 60, "lon_max": 90},
    ]

    results = []
    for region in OIL_REGIONS:
        nearby = fires_df[
            (fires_df["latitude"].between(region["lat_min"], region["lat_max"])) &
            (fires_df["longitude"].between(region["lon_min"], region["lon_max"]))
        ].copy()
        nearby["region_name"] = region["name"]
        results.append(nearby)

    if results:
        return pd.concat(results, ignore_index=True)
    return pd.DataFrame()


def get_wildfires_near_farmland(fires_df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter fire detections near major agricultural production zones.
    Key farming belts that move commodity futures:
    - US Corn Belt: lat 37-47, lon -97 to -83
    - Brazilian Cerrado (soybeans): lat -18 to -5, lon -55 to -44
    - Black Sea (wheat): lat 44-52, lon 24-40
    - Australian wheat belt: lat -35 to -28, lon 116 to 124
    """
    FARM_REGIONS = [
        {"name": "US Corn Belt", "lat_min": 37, "lat_max": 47, "lon_min": -97, "lon_max": -83},
        {"name": "Brazilian Cerrado (Soy)", "lat_min": -18, "lat_max": -5, "lon_min": -55, "lon_max": -44},
        {"name": "Black Sea Wheat", "lat_min": 44, "lat_max": 52, "lon_min": 24, "lon_max": 40},
        {"name": "Australian Wheat Belt", "lat_min": -35, "lat_max": -28, "lon_min": 116, "lon_max": 124},
    ]

    results = []
    for region in FARM_REGIONS:
        nearby = fires_df[
            (fires_df["latitude"].between(region["lat_min"], region["lat_max"])) &
            (fires_df["longitude"].between(region["lon_min"], region["lon_max"]))
        ].copy()
        nearby["region_name"] = region["name"]
        results.append(nearby)

    if results:
        return pd.concat(results, ignore_index=True)
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# EARTHQUAKE TRACKER (USGS)
# ─────────────────────────────────────────────────────────────

USGS_EARTHQUAKE_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def get_recent_earthquakes(
    min_magnitude: float = 4.0,
    days_back: int = 1,
    min_lat: Optional[float] = None,
    max_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lon: Optional[float] = None,
) -> pd.DataFrame:
    """
    Get recent earthquakes from the USGS real-time feed.
    Free government data — same source Bloomberg uses.

    Why earthquakes matter for markets:
    - Near semiconductor factories (Taiwan, Japan) → chip supply shock → tech stocks
    - Near ports (Japan, LA, Chile) → shipping disruption
    - Near oil infrastructure (Middle East, Alaska) → energy supply shock
    - Near refineries → gasoline/diesel price spikes
    - Major quakes → insurance/reinsurance stock moves, CAT bond triggers

    Args:
        min_magnitude: Minimum earthquake magnitude to include (4.0+ is notable)
        days_back: How many days back to look
    """
    from datetime import datetime, timedelta
    end_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    start_time = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S")

    params = {
        "format": "geojson",
        "starttime": start_time,
        "endtime": end_time,
        "minmagnitude": min_magnitude,
        "orderby": "magnitude",
    }
    if min_lat:
        params.update({"minlatitude": min_lat, "maxlatitude": max_lat,
                       "minlongitude": min_lon, "maxlongitude": max_lon})

    response = requests.get(USGS_EARTHQUAKE_API, params=params)
    response.raise_for_status()
    data = response.json()

    quakes = []
    for feature in data.get("features", []):
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]
        quakes.append({
            "magnitude": props["mag"],
            "location_name": props["place"],
            "time": pd.to_datetime(props["time"], unit="ms"),
            "longitude": coords[0],
            "latitude": coords[1],
            "depth_km": coords[2],
            "felt_reports": props.get("felt"),
            "usgs_url": props["url"],
        })

    return pd.DataFrame(quakes)


# ─────────────────────────────────────────────────────────────
# SATELLITE TRACKER (CelesTrak — same as Gods Eye View)
# ─────────────────────────────────────────────────────────────

CELESTRAK_BASE = "https://celestrak.org/SOCRATES/query.php"


def get_active_satellites(category: str = "stations") -> str:
    """
    Get current satellite orbital data in TLE format from CelesTrak.
    Categories: "stations", "weather", "resource", "sarsat", "dmc", "tdrss"

    Returns raw TLE (Two-Line Element) data for orbital propagation.
    Used to show satellite positions on the globe in real time.
    """
    url = f"https://celestrak.org/SOCRATES/query.php"
    tle_url = f"https://celestrak.org/pub/TLE/catalog.txt"

    # Simple TLE fetch by category name
    response = requests.get(f"https://celestrak.org/SOCRATES/{category}.txt")
    return response.text
