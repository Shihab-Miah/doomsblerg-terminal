"""
DoomsBlerg Ship Tracker — Maritime Intelligence
================================================
Tracks cargo ships, oil tankers, container vessels, and bulk carriers
in real time using AIS (Automatic Identification System) data.

Why this matters for trading:
- Oil tanker routes → crude oil supply/demand signals
- Container ships at ports → supply chain stress → retail/manufacturing stocks
- Grain bulk carriers → agricultural commodity futures
- LNG tankers changing course → natural gas price moves
- "Dark ships" turning off transponders → potential sanctions evasion

Data source: AISStream.io (Free tier — WebSocket based)
"""

import asyncio
import json
import websockets
from typing import Optional, Callable, List


AISSTREAM_WS_URL = "wss://stream.aisstream.io/v0/stream"


async def watch_ships_in_area(
    api_key: str,
    bounding_boxes: List[List[List[float]]],
    on_message: Callable,
    message_types: Optional[List[str]] = None,
):
    """
    Stream live ship positions within a geographic area.

    Args:
        api_key: Your AISStream.io API key (free at aisstream.io)
        bounding_boxes: List of [min_lat, min_lon], [max_lat, max_lon] pairs
        on_message: Callback function called for each ship position update
        message_types: Filter to specific AIS message types
            Options: "PositionReport", "ShipStaticData", "StandardClassBPositionReport"

    Example bounding boxes for key chokepoints:
        Strait of Hormuz:    [[25.0, 56.0], [27.0, 58.5]]
        Strait of Malacca:   [[0.5, 100.0], [5.5, 104.5]]
        Suez Canal:          [[29.5, 32.0], [31.5, 33.0]]
        Panama Canal:        [[8.5, -80.0], [9.5, -79.0]]
        Port of LA/LB:       [[33.5, -118.5], [34.0, -118.0]]
        Rotterdam:           [[51.8, 3.9], [52.0, 4.6]]
    """
    if message_types is None:
        message_types = ["PositionReport", "ShipStaticData"]

    subscription_payload = {
        "APIKey": api_key,
        "BoundingBoxes": bounding_boxes,
        "FilterMessageTypes": message_types,
    }

    async with websockets.connect(
        AISSTREAM_WS_URL, extra_headers={"permessage-deflate": ""}
    ) as ws:
        await ws.send(json.dumps(subscription_payload))
        print(f"[Ship Tracker] Connected — watching {len(bounding_boxes)} area(s)...")

        async for raw_message in ws:
            message = json.loads(raw_message)
            ship_data = parse_ship_message(message)
            if ship_data:
                await on_message(ship_data)


def parse_ship_message(raw: dict) -> Optional[dict]:
    """
    Clean up raw AIS message into a simple, usable format.
    Returns None for message types we don't need.
    """
    msg_type = raw.get("MessageType")

    if msg_type == "PositionReport":
        meta = raw.get("MetaData", {})
        pos = raw.get("Message", {}).get("PositionReport", {})
        return {
            "type": "position",
            "mmsi": meta.get("MMSI"),
            "ship_name": meta.get("ShipName", "").strip(),
            "latitude": meta.get("latitude"),
            "longitude": meta.get("longitude"),
            "speed_knots": pos.get("Sog"),           # Speed Over Ground
            "heading_degrees": pos.get("TrueHeading"),
            "nav_status": pos.get("NavigationalStatus"),  # e.g., "Under Way Using Engine"
            "timestamp": meta.get("time_utc"),
        }

    elif msg_type == "ShipStaticData":
        meta = raw.get("MetaData", {})
        static = raw.get("Message", {}).get("ShipStaticData", {})
        return {
            "type": "static_info",
            "mmsi": meta.get("MMSI"),
            "ship_name": meta.get("ShipName", "").strip(),
            "callsign": static.get("CallSign"),
            "imo_number": static.get("ImoNumber"),
            "ship_type": static.get("Type"),
            "destination": static.get("Destination", "").strip(),
            "draught": static.get("MaximumStaticDraught"),  # How deep ship sits (load indicator)
            "length_meters": static.get("Dimension", {}).get("A", 0) + static.get("Dimension", {}).get("B", 0),
            "timestamp": meta.get("time_utc"),
        }

    return None


# ─────────────────────────────────────────────────────────────
# TRADING SIGNAL HELPERS
# ─────────────────────────────────────────────────────────────

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

OIL_TANKER_TYPES = {
    "VLCC": "Very Large Crude Carrier — 2 million barrels",
    "Suezmax": "Suezmax Tanker — 1 million barrels",
    "Aframax": "Aframax Tanker — 500K–750K barrels",
    "LNG Carrier": "Liquefied Natural Gas Tanker",
    "Chemical Tanker": "Chemical or Product Tanker",
}


def get_chokepoint_bounding_box(chokepoint_name: str) -> Optional[List[List[float]]]:
    """
    Get the lat/lon bounding box for a major global trade chokepoint.
    Use this to watch ships passing through strategic locations.
    """
    return MAJOR_CHOKEPOINTS.get(chokepoint_name)
