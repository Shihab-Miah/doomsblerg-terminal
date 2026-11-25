"""
DoomsBlerg Ship Tracker — Maritime Intelligence
===============================================
Tracks cargo ships, oil tankers, container vessels, and bulk carriers
via AISStream.io WebSocket API, with resilient error handling when `websockets`
is optional or upstream stream times out.
"""

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.data_engine.config import get_key

AISSTREAM_WS_URL = "wss://stream.aisstream.io/v0/stream"

MAJOR_CHOKEPOINTS = {
    "Strait of Hormuz": [[25.0, 56.0], [27.0, 58.5]],
    "Strait of Malacca": [[0.5, 100.0], [5.5, 104.5]],
    "Suez Canal": [[29.5, 32.0], [31.5, 33.0]],
    "Panama Canal": [[8.5, -80.0], [9.5, -79.0]],
    "Port of LA / Long Beach": [[33.5, -118.5], [34.0, -118.0]],
    "Rotterdam": [[51.8, 3.9], [52.0, 4.6]],
    "Singapore": [[1.0, 103.5], [1.5, 104.5]],
    "Gulf of Mexico (US)": [[25.0, -97.0], [30.0, -88.0]],
    "Black Sea": [[41.0, 28.0], [46.5, 41.5]],
}


def parse_ship_message(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize raw AIS message into clean terminal dictionary."""
    msg_type = raw.get("MessageType")
    meta = raw.get("MetaData") or {}

    if msg_type == "PositionReport":
        pos = (raw.get("Message") or {}).get("PositionReport") or {}
        return {
            "type": "position",
            "mmsi": meta.get("MMSI"),
            "ship_name": (meta.get("ShipName") or "").strip(),
            "latitude": meta.get("latitude"),
            "longitude": meta.get("longitude"),
            "speed_knots": pos.get("Sog"),
            "heading_degrees": pos.get("TrueHeading"),
            "nav_status": pos.get("NavigationalStatus"),
            "timestamp": meta.get("time_utc"),
        }

    if msg_type == "ShipStaticData":
        static = (raw.get("Message") or {}).get("ShipStaticData") or {}
        dim = static.get("Dimension") or {}
        return {
            "type": "static_info",
            "mmsi": meta.get("MMSI"),
            "ship_name": (meta.get("ShipName") or "").strip(),
            "callsign": static.get("CallSign"),
            "imo_number": static.get("ImoNumber"),
            "ship_type": static.get("Type"),
            "destination": (static.get("Destination") or "").strip(),
            "draught": static.get("MaximumStaticDraught"),
            "length_meters": (dim.get("A") or 0) + (dim.get("B") or 0),
            "timestamp": meta.get("time_utc"),
        }

    return None


def get_chokepoint_bounding_box(chokepoint_name: str) -> Optional[List[List[float]]]:
    """Return geographic bounding box for a major maritime trade chokepoint."""
    return MAJOR_CHOKEPOINTS.get(chokepoint_name)


async def watch_ships_in_area(
    bounding_boxes: List[List[List[float]]],
    on_message: Callable,
    api_key: Optional[str] = None,
    message_types: Optional[List[str]] = None,
) -> None:
    """Stream live ship positions using `websockets` when installed."""
    try:
        import websockets  # Optional runtime package for continuous WebSocket daemon
    except ImportError as exc:
        raise RuntimeError(
            "Install `websockets` (`pip install websockets`) to run continuous AIS streaming."
        ) from exc

    key = api_key or get_key("AISSTREAM_API_KEY")
    if not key:
        raise RuntimeError("AISSTREAM_API_KEY is missing from environment.")

    payload = {
        "APIKey": key,
        "BoundingBoxes": bounding_boxes,
        "FilterMessageTypes": message_types or ["PositionReport", "ShipStaticData"],
    }
    async with websockets.connect(AISSTREAM_WS_URL, open_timeout=15) as ws:
        await ws.send(json.dumps(payload))
        async for raw_message in ws:
            parsed = parse_ship_message(json.loads(raw_message))
            if parsed:
                await on_message(parsed)
