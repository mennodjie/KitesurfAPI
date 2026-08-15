"""Fetches and combines Open-Meteo forecast + marine data for a spot.

Multiple weather models are queried for wind; the hourly consensus is the
median across whichever models responded. A model outage degrades
gracefully -- model_status records what actually answered.
"""

import asyncio
import os
import statistics
import time
from dataclasses import dataclass, field

import httpx

from kitesurf.spots import Spot

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

DEFAULT_MODELS = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless", "knmi_harmonie_arome_europe"]
MODELS = [m.strip() for m in os.environ.get("WEATHER_MODELS", ",".join(DEFAULT_MODELS)).split(",") if m.strip()]

FORECAST_DAYS = 3
CACHE_TTL_SECONDS = 15 * 60
_CONCURRENCY = asyncio.Semaphore(4)

_cache: dict[str, tuple[float, "SpotForecast"]] = {}


@dataclass
class HourPoint:
    time: str
    wind_speed_kn: float | None
    wind_gust_kn: float | None
    wind_direction_deg: float | None
    precipitation_mm: float | None
    wave_height_m: float | None


@dataclass
class SpotForecast:
    spot_id: str
    hours: list[HourPoint]
    model_status: dict[str, bool] = field(default_factory=dict)
    marine_available: bool = False


async def _get_json(client: httpx.AsyncClient, url: str, params: dict) -> dict | None:
    try:
        async with _CONCURRENCY:
            resp = await client.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError):
        return None


def _median(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(statistics.median(clean), 1)


async def _fetch_forecast(client: httpx.AsyncClient, spot: Spot) -> tuple[list[HourPoint], dict[str, bool]]:
    params = {
        "latitude": spot.latitude,
        "longitude": spot.longitude,
        "hourly": "wind_speed_10m,wind_gusts_10m,wind_direction_10m,precipitation",
        "models": ",".join(MODELS),
        "wind_speed_unit": "kn",
        "timezone": "Europe/Amsterdam",
        "forecast_days": FORECAST_DAYS,
    }
    data = await _get_json(client, FORECAST_URL, params)
    model_status = {m: False for m in MODELS}
    if not data or "hourly" not in data:
        return [], model_status

    hourly = data["hourly"]
    times = hourly.get("time", [])

    per_model_present = {}
    for model in MODELS:
        key = f"wind_speed_10m_{model}"
        if key in hourly and any(v is not None for v in hourly[key]):
            model_status[model] = True
            per_model_present[model] = True

    hours = []
    for i, t in enumerate(times):
        speeds = [hourly.get(f"wind_speed_10m_{m}", [None] * len(times))[i] for m in MODELS if model_status[m]]
        gusts = [hourly.get(f"wind_gusts_10m_{m}", [None] * len(times))[i] for m in MODELS if model_status[m]]
        dirs = [hourly.get(f"wind_direction_10m_{m}", [None] * len(times))[i] for m in MODELS if model_status[m]]
        precs = [hourly.get(f"precipitation_{m}", [None] * len(times))[i] for m in MODELS if model_status[m]]
        hours.append(
            HourPoint(
                time=t,
                wind_speed_kn=_median(speeds),
                wind_gust_kn=_median(gusts),
                wind_direction_deg=_median(dirs),
                precipitation_mm=_median(precs),
                wave_height_m=None,
            )
        )
    return hours, model_status


async def _fetch_marine(client: httpx.AsyncClient, spot: Spot) -> dict[str, float]:
    if not spot.is_coastal:
        return {}
    params = {
        "latitude": spot.latitude,
        "longitude": spot.longitude,
        "hourly": "wave_height",
        "timezone": "Europe/Amsterdam",
        "forecast_days": FORECAST_DAYS,
    }
    data = await _get_json(client, MARINE_URL, params)
    if not data or "hourly" not in data:
        return {}
    hourly = data["hourly"]
    times = hourly.get("time", [])
    heights = hourly.get("wave_height", [])
    return {t: h for t, h in zip(times, heights) if h is not None}


async def get_forecast(spot: Spot, use_cache: bool = True) -> SpotForecast:
    if use_cache:
        cached = _cache.get(spot.id)
        if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

    async with httpx.AsyncClient() as client:
        (hours, model_status), wave_by_time = await asyncio.gather(
            _fetch_forecast(client, spot),
            _fetch_marine(client, spot),
        )

    for hp in hours:
        hp.wave_height_m = wave_by_time.get(hp.time)

    forecast = SpotForecast(
        spot_id=spot.id,
        hours=hours,
        model_status=model_status,
        marine_available=bool(wave_by_time),
    )
    _cache[spot.id] = (time.time(), forecast)
    return forecast


async def get_forecasts(spots: list[Spot], use_cache: bool = True) -> dict[str, SpotForecast]:
    results = await asyncio.gather(*[get_forecast(s, use_cache=use_cache) for s in spots])
    return {f.spot_id: f for f in results}
