"""
DoomsBlerg Geospatial Intelligence Package (God's Eye View)
===========================================================
Unites NASA FIRMS wildfires, USGS earthquakes, ADS-B aviation, CelesTrak
satellites, AISStream maritime tracking, and physical-world trading triggers.
"""

from .earth_events import (
    get_active_satellites,
    get_active_wildfires,
    get_recent_earthquakes,
    scan_commodity_wildfires,
)
from .flight_tracker import PRESET_AIRSPACE, get_flights_in_preset, get_flights_near
from .gods_eye import scan_gods_eye_triggers
from .ship_tracker import (
    MAJOR_CHOKEPOINTS,
    collect_ships_snapshot,
    get_chokepoint_bounding_box,
    parse_ship_message,
)

__all__ = [
    "get_active_wildfires",
    "scan_commodity_wildfires",
    "get_recent_earthquakes",
    "get_active_satellites",
    "get_flights_near",
    "get_flights_in_preset",
    "PRESET_AIRSPACE",
    "MAJOR_CHOKEPOINTS",
    "get_chokepoint_bounding_box",
    "parse_ship_message",
    "collect_ships_snapshot",
    "scan_gods_eye_triggers",
]
