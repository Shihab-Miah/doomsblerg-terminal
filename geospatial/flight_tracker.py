"""
DoomsBlerg Flight Tracker — Aviation Intelligence (Zero-Dependency)
===================================================================
Tracks commercial aircraft, cargo planes, and private jets via adsb.lol (primary)
and OpenSky Network (fallback) without third-party HTTP/Pandas dependencies.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.data_engine.http_client import fetch_json

PRESET_AIRSPACE = {
    "nyc": (40.7128, -74.0060, 40),
    "dc": (38.9072, -77.0369, 40),
    "la": (34.0522, -118.2437, 40),
    "london": (51.5074, -0.1278, 40),
    "taiwan": (25.0330, 121.5654, 60),
    "dubai": (25.2048, 55.2708, 40),
}

CARGO_CALLSIGN_PREFIXES = {
    "FDX": "FedEx",
    "UPS": "UPS Airlines",
    "GTI": "Atlas Air",
    "CLX": "Cargolux",
    "ABX": "ABX Air",
}

EXECUTIVE_JET_TYPES = {"GL5T", "GL6T", "G650", "GLF6", "GLF5", "GLEX", "C750", "CL60", "FA7X", "FA8X"}


def get_flights_near(lat: float, lon: float, radius_nm: int = 35, limit: int = 100) -> Dict[str, Any]:
    """Fetch live ADS-B aircraft positions around coordinates via adsb.lol."""
    data = fetch_json(
        f"https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{radius_nm}",
        ttl_seconds=30,
    )
    raw_ac = data.get("ac") or []
    aircraft: List[Dict[str, Any]] = []
    cargo_hits: List[Dict[str, Any]] = []
    exec_hits: List[Dict[str, Any]] = []

    for ac in raw_ac[:limit]:
        callsign = (ac.get("flight") or "").strip()
        ac_type = (ac.get("t") or "").strip().upper()
        item = {
            "hex": ac.get("hex"),
            "callsign": callsign,
            "registration": ac.get("r"),
            "aircraft_type": ac_type,
            "lat": ac.get("lat"),
            "lon": ac.get("lon"),
            "altitude_ft": ac.get("alt_baro"),
            "ground_speed_kt": ac.get("gs"),
            "heading": ac.get("track"),
        }
        aircraft.append(item)
        if callsign[:3] in CARGO_CALLSIGN_PREFIXES:
            item_copy = dict(item)
            item_copy["operator"] = CARGO_CALLSIGN_PREFIXES[callsign[:3]]
            cargo_hits.append(item_copy)
        if ac_type in EXECUTIVE_JET_TYPES:
            exec_hits.append(item)

    return {
        "center": {"lat": lat, "lon": lon, "radius_nm": radius_nm},
        "total_aircraft": len(raw_ac),
        "sampled": aircraft,
        "cargo_flights": cargo_hits,
        "executive_jets": exec_hits,
    }


def get_flights_in_preset(region_name: str = "nyc") -> Dict[str, Any]:
    """Convenience wrapper for common financial/geopolitical hubs."""
    key = region_name.lower().strip()
    if key not in PRESET_AIRSPACE:
        raise ValueError(f"Unknown preset '{region_name}'. Options: {list(PRESET_AIRSPACE.keys())}")
    lat, lon, dist = PRESET_AIRSPACE[key]
    res = get_flights_near(lat, lon, dist)
    res["region"] = key
    return res
