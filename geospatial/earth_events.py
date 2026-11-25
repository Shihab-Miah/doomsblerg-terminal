"""
DoomsBlerg Earth Events — Natural Event Intelligence (Zero-Dependency)
======================================================================
Tracks wildfires, earthquakes, and satellites using pure Python stdlib
so it runs cleanly on low-end laptops and Termux without heavy packages.
"""

import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.data_engine.config import get_key
from backend.data_engine.http_client import fetch_json, fetch_text

NASA_FIRMS_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
USGS_EARTHQUAKE_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"

OIL_REGIONS = [
    {"name": "Permian Basin TX", "lat_min": 31.0, "lat_max": 33.0, "lon_min": -104.0, "lon_max": -100.0},
    {"name": "Alberta Oil Sands", "lat_min": 55.0, "lat_max": 58.0, "lon_min": -115.0, "lon_max": -109.0},
    {"name": "Gulf Coast Refineries", "lat_min": 28.0, "lat_max": 31.0, "lon_min": -97.0, "lon_max": -88.0},
    {"name": "West Siberia Russia", "lat_min": 55.0, "lat_max": 70.0, "lon_min": 60.0, "lon_max": 90.0},
]

FARM_REGIONS = [
    {"name": "US Corn Belt", "lat_min": 37.0, "lat_max": 47.0, "lon_min": -97.0, "lon_max": -83.0},
    {"name": "Brazilian Cerrado (Soy)", "lat_min": -18.0, "lat_max": -5.0, "lon_min": -55.0, "lon_max": -44.0},
    {"name": "Black Sea Wheat", "lat_min": 44.0, "lat_max": 52.0, "lon_min": 24.0, "lon_max": 40.0},
    {"name": "Australian Wheat Belt", "lat_min": -35.0, "lat_max": -28.0, "lon_min": 116.0, "lon_max": 124.0},
]

TECH_RISK_ZONES = [
    {"name": "Taiwan Semiconductor Belt", "lat_min": 22.0, "lat_max": 25.5, "lon_min": 119.5, "lon_max": 122.5},
    {"name": "Japan Industrial & Ports", "lat_min": 31.0, "lat_max": 38.0, "lon_min": 130.0, "lon_max": 141.5},
    {"name": "Chile Copper Belt", "lat_min": -35.0, "lat_max": -18.0, "lon_min": -72.0, "lon_max": -67.0},
]


def get_active_wildfires(
    api_key: Optional[str] = None,
    area: str = "-180,-90,180,90",
    days: int = 2,
    source: str = "VIIRS_NOAA21_NRT",
    date_str: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """Fetch active wildfire thermal detections from NASA FIRMS satellite feeds."""
    key = api_key or get_key("NASA_FIRMS_API_KEY")
    if not key:
        raise RuntimeError("NASA_FIRMS_API_KEY is required for NASA FIRMS.")

    if date_str is None:
        # Use yesterday UTC as anchor when querying multi-day window so rollover never returns empty
        date_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    url = f"{NASA_FIRMS_BASE}/{key}/{source}/{area}/{days}/{date_str}"
    raw_csv = fetch_text(url, ttl_seconds=1800, timeout=20)
    rows = list(csv.DictReader(StringIO(raw_csv)))

    detections: List[Dict[str, Any]] = []
    for r in rows[:limit]:
        try:
            detections.append(
                {
                    "latitude": float(r["latitude"]),
                    "longitude": float(r["longitude"]),
                    "brightness_k": float(r.get("bright_ti4") or r.get("brightness") or 0),
                    "frp_mw": float(r.get("frp") or 0),
                    "date": r.get("acq_date"),
                    "time": r.get("acq_time"),
                    "satellite": r.get("satellite"),
                    "confidence": r.get("confidence"),
                }
            )
        except (KeyError, ValueError):
            continue
    return detections


def _match_regions(items: List[Dict[str, Any]], regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matched: List[Dict[str, Any]] = []
    for item in items:
        lat = item.get("latitude", 0.0)
        lon = item.get("longitude", 0.0)
        for reg in regions:
            if reg["lat_min"] <= lat <= reg["lat_max"] and reg["lon_min"] <= lon <= reg["lon_max"]:
                copy = dict(item)
                copy["region_name"] = reg["name"]
                matched.append(copy)
                break
    return matched


def scan_commodity_wildfires(api_key: Optional[str] = None) -> Dict[str, Any]:
    """Scan global satellite fires and group hits over major oil and crop regions."""
    fires = get_active_wildfires(api_key=api_key, limit=2000)
    oil_hits = _match_regions(fires, OIL_REGIONS)
    farm_hits = _match_regions(fires, FARM_REGIONS)
    return {
        "total_global_sampled": len(fires),
        "oil_region_fires": oil_hits[:50],
        "oil_fire_count": len(oil_hits),
        "farm_region_fires": farm_hits[:50],
        "farm_fire_count": len(farm_hits),
    }


def get_recent_earthquakes(min_magnitude: float = 4.5, days_back: int = 3) -> Dict[str, Any]:
    """Fetch recent earthquakes from USGS and flag impacts near tech/port/mining hubs."""
    now = datetime.now(timezone.utc)
    start_time = (now - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S")
    end_time = now.strftime("%Y-%m-%dT%H:%M:%S")

    data = fetch_json(
        USGS_EARTHQUAKE_API,
        params={
            "format": "geojson",
            "starttime": start_time,
            "endtime": end_time,
            "minmagnitude": min_magnitude,
            "orderby": "magnitude",
            "limit": 50,
        },
        ttl_seconds=600,
    )
    quakes: List[Dict[str, Any]] = []
    for feat in data.get("features", []):
        props = feat.get("properties") or {}
        coords = (feat.get("geometry") or {}).get("coordinates") or [0, 0, 0]
        quakes.append(
            {
                "magnitude": props.get("mag"),
                "location_name": props.get("place"),
                "time_utc": datetime.fromtimestamp(props["time"] / 1000, tz=timezone.utc).isoformat()
                if props.get("time")
                else None,
                "longitude": coords[0],
                "latitude": coords[1],
                "depth_km": coords[2],
                "url": props.get("url"),
            }
        )

    critical_hits = _match_regions(quakes, TECH_RISK_ZONES)
    return {
        "count": len(quakes),
        "earthquakes": quakes,
        "critical_hub_alerts": critical_hits,
    }


def get_active_satellites(category: str = "stations", limit: int = 20) -> Dict[str, Any]:
    """Fetch live orbital element catalog from CelesTrak (keyless JSON feed)."""
    data = fetch_json(
        "https://celestrak.org/NORAD/elements/gp.php",
        params={"GROUP": category, "FORMAT": "json"},
        ttl_seconds=21600,
    )
    if not isinstance(data, list):
        return {"category": category, "count": 0, "satellites": []}
    sats = [
        {
            "name": s.get("OBJECT_NAME"),
            "object_id": s.get("OBJECT_ID"),
            "norad_cat_id": s.get("NORAD_CAT_ID"),
            "epoch": s.get("EPOCH"),
            "inclination_deg": s.get("INCLINATION"),
            "mean_motion_rev_day": s.get("MEAN_MOTION"),
        }
        for s in data[:limit]
    ]
    return {"category": category, "total_tracked": len(data), "satellites": sats}
