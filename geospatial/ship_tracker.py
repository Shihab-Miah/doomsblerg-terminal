"""
DoomsBlerg Ship Tracker — Maritime Intelligence
===============================================
Tracks cargo ships, oil tankers, container vessels, and bulk carriers
via AISStream.io WebSocket API, with resilient error handling when `websockets`
is optional or upstream stream times out.
"""

import base64
import json
import os
import socket
import ssl
import sys
import time
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
    """Return geographic bounding box for a major maritime trade chokepoint (case-insensitive partial match)."""
    if chokepoint_name in MAJOR_CHOKEPOINTS:
        return MAJOR_CHOKEPOINTS[chokepoint_name]
    low = chokepoint_name.lower().strip()
    for name, box in MAJOR_CHOKEPOINTS.items():
        if low in name.lower():
            return box
    return None


def _recv_ws_frame(sock: ssl.SSLSocket) -> Optional[str]:
    """Read one unmasked server WebSocket text frame using pure Python stdlib."""
    hdr = sock.recv(2)
    if len(hdr) < 2:
        return None
    opcode = hdr[0] & 0x0F
    length = hdr[1] & 0x7F
    if length == 126:
        ext = sock.recv(2)
        if len(ext) < 2:
            return None
        length = int.from_bytes(ext, "big")
    elif length == 127:
        ext = sock.recv(8)
        if len(ext) < 8:
            return None
        length = int.from_bytes(ext, "big")

    payload = bytearray()
    while len(payload) < length:
        chunk = sock.recv(min(4096, length - len(payload)))
        if not chunk:
            break
        payload.extend(chunk)
    if opcode == 0x8:  # close frame
        return None
    if opcode in (0x1, 0x2):
        return payload.decode("utf-8", errors="replace")
    return ""


def collect_ships_snapshot(
    chokepoint: str = "Singapore",
    listen_seconds: float = 4.0,
    max_ships: int = 15,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Capture a live snapshot of vessels via AISStream.io using pure-stdlib TLS WebSockets.
    Falls back cleanly with maritime chokepoint metadata if the upstream WS stream times out.
    """
    box = get_chokepoint_bounding_box(chokepoint)
    matched_name = next((n for n in MAJOR_CHOKEPOINTS if chokepoint.lower().strip() in n.lower()), chokepoint)
    if not box:
        box = MAJOR_CHOKEPOINTS["Singapore"]
        matched_name = "Singapore"

    key = api_key or get_key("AISSTREAM_API_KEY")
    if not key:
        return {
            "chokepoint": matched_name,
            "bounding_box": box,
            "status": "missing_api_key",
            "vessels": [],
            "available_chokepoints": list(MAJOR_CHOKEPOINTS.keys()),
        }

    vessels: Dict[str, Dict[str, Any]] = {}
    sock = None
    try:
        ctx = ssl.create_default_context()
        raw_sock = socket.create_connection(("stream.aisstream.io", 443), timeout=5.0)
        sock = ctx.wrap_socket(raw_sock, server_hostname="stream.aisstream.io")
        sock.settimeout(5.0)

        ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
        handshake = (
            "GET /v0/stream HTTP/1.1\r\n"
            "Host: stream.aisstream.io\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        sock.sendall(handshake)

        resp_buf = bytearray()
        while b"\r\n\r\n" not in resp_buf:
            chunk = sock.recv(1024)
            if not chunk:
                raise RuntimeError("AISStream closed connection during WebSocket upgrade")
            resp_buf.extend(chunk)
        status_line = resp_buf.split(b"\r\n", 1)[0].decode("utf-8", errors="replace")
        if "101" not in status_line:
            raise RuntimeError(f"AISStream WebSocket upgrade rejected: {status_line}")

        sub = json.dumps(
            {
                "APIKey": key,
                "BoundingBoxes": [box],
                "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
            }
        ).encode("utf-8")
        mask = os.urandom(4)
        length = len(sub)
        if length < 126:
            frame_hdr = bytes([0x81, 0x80 | length]) + mask
        else:
            frame_hdr = bytes([0x81, 0x80 | 126]) + length.to_bytes(2, "big") + mask
        sock.sendall(frame_hdr + bytes(b ^ mask[i % 4] for i, b in enumerate(sub)))

        deadline = time.time() + listen_seconds
        sock.settimeout(max(1.0, min(listen_seconds, 4.0)))
        while time.time() < deadline and len(vessels) < max_ships:
            msg_text = _recv_ws_frame(sock)
            if msg_text is None:
                break
            if not msg_text:
                continue
            parsed = parse_ship_message(json.loads(msg_text))
            if parsed and parsed.get("mmsi"):
                vessels[str(parsed["mmsi"])] = parsed

        return {
            "chokepoint": matched_name,
            "bounding_box": box,
            "status": "live" if vessels else "connected_quiet_window",
            "vessel_count": len(vessels),
            "vessels": list(vessels.values()),
        }
    except Exception as exc:
        return {
            "chokepoint": matched_name,
            "bounding_box": box,
            "status": "upstream_timeout_fallback",
            "note": f"AISStream live WS timed out or deferred upstream ({exc}); chokepoint telemetry ready.",
            "vessel_count": 0,
            "vessels": [],
            "available_chokepoints": list(MAJOR_CHOKEPOINTS.keys()),
        }
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


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
