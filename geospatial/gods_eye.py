"""
DoomsBlerg God's Eye View — Unified Geospatial Market Signal Engine (Phase 4)
=============================================================================
Fuses satellite wildfires, USGS earthquakes, ADS-B cargo/executive flights,
CelesTrak orbital telemetry, EIA US crude oil stocks, agricultural weather,
and AIS maritime chokepoints into structured Physical-World Trading Triggers.
Runs cleanly in pure Python stdlib (< 30 MB RAM, 0 LLM tokens).
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from backend.data_engine.commodities_geo import get_energy_inventories, get_weather_forecast
from geospatial.earth_events import (
    get_active_satellites,
    get_recent_earthquakes,
    scan_commodity_wildfires,
)
from geospatial.flight_tracker import get_flights_in_preset
from geospatial.ship_tracker import MAJOR_CHOKEPOINTS, collect_ships_snapshot


def _build_signal_triggers(
    fires: Dict[str, Any],
    quakes: Dict[str, Any],
    flights: Dict[str, Any],
    oil: Dict[str, Any],
    ships: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Translate raw geospatial telemetry into plain-English market impact triggers."""
    triggers: List[Dict[str, Any]] = []

    oil_fires = fires.get("oil_fire_count", 0)
    if oil_fires > 0:
        regions = sorted({f.get("region_name", "Oil Hub") for f in fires.get("oil_region_fires", [])})
        triggers.append(
            {
                "category": "wildfire_energy",
                "severity": "high" if oil_fires >= 10 else "medium",
                "signal": f"{oil_fires} thermal fire detections near energy hubs ({', '.join(regions)}).",
                "market_implication": "Potential pipeline/wellhead disruption; bullish risk premium for WTI/Brent crude and refiners.",
                "watch_tickers": ["CL=F", "BZ=F", "USO", "XLE", "XOM", "CVX"],
            }
        )

    farm_fires = fires.get("farm_fire_count", 0)
    if farm_fires > 0:
        regions = sorted({f.get("region_name", "Crop Belt") for f in fires.get("farm_region_fires", [])})
        triggers.append(
            {
                "category": "wildfire_agriculture",
                "severity": "high" if farm_fires >= 15 else "medium",
                "signal": f"{farm_fires} satellite fire detections across global grain belts ({', '.join(regions)}).",
                "market_implication": "Crop/storage disruption risk; watch upside volatility in corn, wheat, and soybean futures.",
                "watch_tickers": ["ZC=F", "ZW=F", "ZS=F", "ADM", "BG"],
            }
        )

    hub_quakes = quakes.get("critical_hub_alerts") or []
    for q in hub_quakes[:4]:
        reg = q.get("region_name", "Supply Hub")
        mag = q.get("magnitude", 0)
        tickers = ["NVDA", "TSM", "AAPL", "AMD"] if "Taiwan" in reg or "Japan" in reg else ["HG=F", "FCX", "SCCO"]
        triggers.append(
            {
                "category": "seismic_supply_chain",
                "severity": "high" if (mag or 0) >= 6.0 else "medium",
                "signal": f"M{mag} earthquake near {reg} ({q.get('location_name')}).",
                "market_implication": "Physical risk to fabs/ports/mines; monitor semiconductor lead times or copper supply.",
                "watch_tickers": tickers,
            }
        )

    exec_cnt = len(flights.get("executive_jets") or [])
    cargo_cnt = len(flights.get("cargo_flights") or [])
    if exec_cnt > 0 or cargo_cnt > 0:
        triggers.append(
            {
                "category": "aviation_activity",
                "severity": "low" if exec_cnt < 5 else "medium",
                "signal": f"{flights.get('region', 'hub').upper()} airspace tracking {flights.get('total_aircraft', 0)} aircraft ({cargo_cnt} cargo, {exec_cnt} executive jets).",
                "market_implication": "Tracks freight lane congestion (FDX/UPS) and executive travel anomalies around financial centers.",
                "watch_tickers": ["FDX", "UPS", "DAL"],
            }
        )

    oil_delta = oil.get("latest_week_change_mbbl")
    if oil_delta is not None:
        direction = oil.get("latest_direction") or ("build" if oil_delta > 0 else "draw")
        bullish = oil_delta < 0
        triggers.append(
            {
                "category": "energy_inventory",
                "severity": "medium" if abs(oil_delta) >= 3000 else "low",
                "signal": f"US Commercial Crude Oil weekly inventory change: {oil_delta:+} MBBL ({direction}).",
                "market_implication": "Tightening domestic crude supply (bullish WTI)." if bullish else "Inventory build suggests near-term crude oversupply.",
                "watch_tickers": ["CL=F", "XLE", "USO"],
            }
        )

    if ships.get("vessel_count", 0) > 0:
        triggers.append(
            {
                "category": "maritime_ais",
                "severity": "low",
                "signal": f"Live AIS feed captured {ships['vessel_count']} vessels in {ships.get('chokepoint')}.",
                "market_implication": "Tracks tanker/container flow speed around key global chokepoints.",
                "watch_tickers": ["ZIM", "FRO", "STNG", "CL=F"],
            }
        )

    if not triggers:
        triggers.append(
            {
                "category": "baseline",
                "severity": "low",
                "signal": "No major anomaly triggers detected across sampled hubs.",
                "market_implication": "Physical supply chains operating within normal baseline.",
                "watch_tickers": ["SPY"],
            }
        )

    return triggers


def scan_gods_eye_triggers(
    flight_region: str = "nyc",
    ship_chokepoint: str = "Singapore",
    include_ais_stream: bool = True,
) -> Dict[str, Any]:
    """Run all physical-world intelligence feeds concurrently and synthesize trading triggers."""
    with ThreadPoolExecutor(max_workers=7) as pool:
        f_fires = pool.submit(scan_commodity_wildfires)
        f_quakes = pool.submit(get_recent_earthquakes, 4.5, 3)
        f_flights = pool.submit(get_flights_in_preset, flight_region)
        f_sats = pool.submit(get_active_satellites, "stations", 8)
        f_oil = pool.submit(get_energy_inventories, 4)
        f_wx = pool.submit(get_weather_forecast, 41.88, -93.10, 5)
        f_ships = pool.submit(collect_ships_snapshot, ship_chokepoint, 2.5, 10) if include_ais_stream else None

        def _safe(fut, fallback):
            try:
                return fut.result()
            except Exception as exc:
                return {"error": str(exc), **fallback}

        fires = _safe(f_fires, {"oil_fire_count": 0, "farm_fire_count": 0, "total_global_sampled": 0})
        quakes = _safe(f_quakes, {"count": 0, "critical_hub_alerts": []})
        flights = _safe(f_flights, {"total_aircraft": 0, "cargo_flights": [], "executive_jets": [], "region": flight_region})
        sats = _safe(f_sats, {"total_tracked": 0, "satellites": []})
        oil = _safe(f_oil, {"records": []})
        wx = _safe(f_wx, {})
        ships = _safe(f_ships, {"chokepoint": ship_chokepoint, "status": "skipped", "vessel_count": 0, "vessels": []}) if f_ships else {
            "chokepoint": ship_chokepoint,
            "status": "skipped",
            "vessel_count": 0,
            "vessels": [],
        }

    triggers = _build_signal_triggers(fires, quakes, flights, oil, ships)
    daily_wx = wx.get("daily") or {}
    fire_points = (fires.get("oil_region_fires") or [])[:20] + (fires.get("farm_region_fires") or [])[:20]
    quake_points = [
        {
            "latitude": q.get("latitude"),
            "longitude": q.get("longitude"),
            "magnitude": q.get("magnitude"),
            "location_name": q.get("location_name"),
        }
        for q in (quakes.get("earthquakes") or [])[:25]
        if q.get("latitude") is not None and q.get("longitude") is not None
    ]
    chokepoint_markers = [
        {
            "name": name,
            "latitude": round((box[0][0] + box[1][0]) / 2.0, 2),
            "longitude": round((box[0][1] + box[1][1]) / 2.0, 2),
        }
        for name, box in MAJOR_CHOKEPOINTS.items()
    ]
    return {
        "trading_signal_triggers": triggers,
        "wildfires": {
            "total_sampled": fires.get("total_global_sampled"),
            "oil_fire_count": fires.get("oil_fire_count", 0),
            "farm_fire_count": fires.get("farm_fire_count", 0),
            "points": fire_points,
        },
        "earthquakes": {
            "count": quakes.get("count", 0),
            "critical_hub_alerts": quakes.get("critical_hub_alerts", [])[:5],
            "top_event": (quakes.get("earthquakes") or [None])[0],
            "points": quake_points,
        },
        "aviation": {
            "region": flights.get("region", flight_region),
            "center": flights.get("center"),
            "total_aircraft": flights.get("total_aircraft", 0),
            "cargo_flights": len(flights.get("cargo_flights") or []),
            "executive_jets": len(flights.get("executive_jets") or []),
            "points": (flights.get("sampled") or [])[:30],
        },
        "maritime": {
            "chokepoint": ships.get("chokepoint"),
            "status": ships.get("status"),
            "vessel_count": ships.get("vessel_count", 0),
            "monitored_chokepoints": list(MAJOR_CHOKEPOINTS.keys()),
            "chokepoint_markers": chokepoint_markers,
        },
        "satellites": {
            "category": sats.get("category", "stations"),
            "total_tracked": sats.get("total_tracked", 0),
            "sample": (sats.get("satellites") or [])[:5],
        },
        "energy_and_crops": {
            "us_crude_change_mbbl": oil.get("latest_week_change_mbbl"),
            "us_crude_direction": oil.get("latest_direction"),
            "corn_belt_forecast_dates": (daily_wx.get("time") or [])[:3],
            "corn_belt_precip_mm": (daily_wx.get("precipitation_sum") or [])[:3],
        },
    }
