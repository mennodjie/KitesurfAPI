"""Live (actual, not forecast) weather station observations near each spot.

Uses Buienradar's free public feed -- no API key, no signup. KNMI's own
live-observation API (dataplatform.knmi.nl) is more authoritative but
requires registering for an API key, which doesn't fit this project's
keyless-by-default approach; Buienradar is a reasonable free stand-in.
"""

import math
from dataclasses import dataclass

import httpx

from kitesurf.spots import Spot

FEED_URL = "https://data.buienradar.nl/2.0/feed/json"
MS_TO_KN = 1.943844
MAX_STATION_DISTANCE_KM = 40.0


@dataclass
class StationObservation:
    station_name: str
    distance_km: float
    wind_kn: float | None
    gust_kn: float | None
    dir_deg: float | None
    timestamp: str | None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def fetch_stations(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(FEED_URL, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()
    stations = data.get("actual", {}).get("stationmeasurements", [])
    return [s for s in stations if s.get("windspeed") is not None and s.get("lat") is not None]


def nearest_station(spot: Spot, stations: list[dict]) -> StationObservation | None:
    if not stations:
        return None
    best = min(stations, key=lambda s: _haversine_km(spot.latitude, spot.longitude, s["lat"], s["lon"]))
    distance = _haversine_km(spot.latitude, spot.longitude, best["lat"], best["lon"])
    if distance > MAX_STATION_DISTANCE_KM:
        return None
    wind_kn = best.get("windspeed")
    gust_kn = best.get("windgusts")
    return StationObservation(
        station_name=best.get("stationname", "Unknown"),
        distance_km=round(distance, 1),
        wind_kn=round(wind_kn * MS_TO_KN, 1) if wind_kn is not None else None,
        gust_kn=round(gust_kn * MS_TO_KN, 1) if gust_kn is not None else None,
        dir_deg=best.get("winddirectiondegrees"),
        timestamp=best.get("timestamp"),
    )


async def get_observations(spots: list[Spot]) -> dict[str, StationObservation | None]:
    async with httpx.AsyncClient() as client:
        stations = await fetch_stations(client)
    return {spot.id: nearest_station(spot, stations) for spot in spots}
