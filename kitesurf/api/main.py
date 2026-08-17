"""FastAPI backend for the standalone Render PWA (static/pwa).

Exposes the same forecasting engine used by streamlit_app.py -- scoring,
kite-size suggestion, good-window grouping, tides, live observations, and
forecast-accuracy tracking -- as JSON, so the vanilla-JS PWA can render
feature parity with the Streamlit app without any Python templating.
"""

import asyncio
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kitesurf.accuracy import load_log, summarize
from kitesurf.kitesize import recommend_kite_size
from kitesurf.observations import get_observations
from kitesurf.scoring import gust_ratio, model_confidence, score_hour
from kitesurf.spots import SPOTS, SPOTS_BY_ID
from kitesurf.tides import get_tide_events
from kitesurf.weather import SpotForecast, get_forecast, get_forecasts
from kitesurf.windows import compute_good_windows

app = FastAPI(
    title="KiteScout API",
    description="Open weather/marine data combined into a kitesurf spot ranking. Planning aid, not safety advice.",
)

ROOT_DIR = Path(__file__).resolve().parents[2]
PWA_DIR = ROOT_DIR / "static" / "pwa"
STATIC_DIR = ROOT_DIR / "static"
ACCURACY_LOG_PATH = ROOT_DIR / "data" / "accuracy_log.jsonl"

DEFAULT_RIDER_WEIGHT_KG = 73.0
DEFAULT_MIN_SCORE = 75.0
DEFAULT_MIN_HOURS = 3

app.mount("/pwa-assets", StaticFiles(directory=STATIC_DIR), name="pwa-assets")


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def pwa_index():
    return FileResponse(PWA_DIR / "index.html")


@app.api_route("/app", methods=["GET", "HEAD"], include_in_schema=False)
def pwa_index_alias():
    return FileResponse(PWA_DIR / "index.html")


@app.api_route("/app.css", methods=["GET", "HEAD"], include_in_schema=False)
def pwa_css():
    return FileResponse(PWA_DIR / "app.css", media_type="text/css")


@app.api_route("/app.js", methods=["GET", "HEAD"], include_in_schema=False)
def pwa_js():
    return FileResponse(PWA_DIR / "app.js", media_type="application/javascript")


@app.api_route("/manifest.json", methods=["GET", "HEAD"], include_in_schema=False)
def pwa_manifest():
    return FileResponse(PWA_DIR / "manifest.json", media_type="application/manifest+json")


@app.api_route("/service-worker.js", methods=["GET", "HEAD"], include_in_schema=False)
def pwa_service_worker():
    return FileResponse(PWA_DIR / "service-worker.js", media_type="application/javascript")


@app.api_route("/sw.js", methods=["GET", "HEAD"], include_in_schema=False)
def pwa_service_worker_alias():
    return FileResponse(PWA_DIR / "service-worker.js", media_type="application/javascript")


@app.api_route("/offline.html", methods=["GET", "HEAD"], include_in_schema=False)
def pwa_offline():
    return FileResponse(PWA_DIR / "offline.html")


@app.get("/spots")
def list_spots():
    return [
        {"id": s.id, "name": s.name, "water_body": s.water_body, "is_coastal": s.is_coastal}
        for s in SPOTS
    ]


def _hour_payload(spot, h, rider_weight_kg: float) -> dict:
    return {
        "time": h.time,
        "wind_speed_kn": h.wind_speed_kn,
        "wind_gust_kn": h.wind_gust_kn,
        "wind_direction_deg": h.wind_direction_deg,
        "gust_ratio": gust_ratio(h),
        "precipitation_mm": h.precipitation_mm,
        "wave_height_m": h.wave_height_m,
        "wind_speed_spread_kn": h.wind_speed_spread_kn,
        "confidence": model_confidence(h.wind_speed_spread_kn),
        "score": score_hour(spot, h),
        "kite_m": recommend_kite_size(rider_weight_kg, h.wind_speed_kn),
    }


def _windows_payload(spot, fc: SpotForecast, rider_weight_kg: float, min_score: float, min_hours: int) -> list[dict]:
    rows = [
        {
            "time": pd.to_datetime(h.time),
            "score": score_hour(spot, h),
            "wind_kn": h.wind_speed_kn,
            "gust_kn": h.wind_gust_kn,
            "dir_deg": h.wind_direction_deg,
            "confidence": model_confidence(h.wind_speed_spread_kn),
        }
        for h in fc.hours
    ]
    windows = compute_good_windows(pd.DataFrame(rows), threshold=min_score, min_hours=min_hours)
    return [
        {
            "start": w["start"].isoformat(),
            "end": w["end"].isoformat(),
            "peak_score": w["peak_score"],
            "avg_score": w["avg_score"],
            "wind_kn": w["wind_kn"],
            "gust_kn": w["gust_kn"],
            "dir_deg": w["dir_deg"],
            "hours": int(w["hours"]),
            "confidence": w["confidence"],
            "kite_m": recommend_kite_size(rider_weight_kg, w["wind_kn"]),
        }
        for _, w in windows.iterrows()
    ]


async def _empty_tide_events():
    return []


@app.get("/forecast/{spot_id}")
async def forecast(spot_id: str, rider_weight_kg: float = DEFAULT_RIDER_WEIGHT_KG):
    spot = SPOTS_BY_ID.get(spot_id)
    if not spot:
        raise HTTPException(status_code=404, detail=f"Unknown spot_id '{spot_id}'")
    fc = await get_forecast(spot)
    return {
        "spot_id": spot.id,
        "name": spot.name,
        "model_status": fc.model_status,
        "marine_available": fc.marine_available,
        "hours": [_hour_payload(spot, h, rider_weight_kg) for h in fc.hours],
    }


@app.get("/spot-detail/{spot_id}")
async def spot_detail(
    spot_id: str,
    rider_weight_kg: float = DEFAULT_RIDER_WEIGHT_KG,
    min_score: float = DEFAULT_MIN_SCORE,
    min_hours: int = DEFAULT_MIN_HOURS,
):
    spot = SPOTS_BY_ID.get(spot_id)
    if not spot:
        raise HTTPException(status_code=404, detail=f"Unknown spot_id '{spot_id}'")

    fc = await get_forecast(spot)
    tide_events, observations = await asyncio.gather(
        get_tide_events() if spot.is_coastal else _empty_tide_events(),
        get_observations([spot]),
    )
    observation = observations.get(spot.id)

    return {
        "spot_id": spot.id,
        "name": spot.name,
        "water_body": spot.water_body,
        "is_coastal": spot.is_coastal,
        "model_status": fc.model_status,
        "marine_available": fc.marine_available,
        "hours": [_hour_payload(spot, h, rider_weight_kg) for h in fc.hours],
        "windows": _windows_payload(spot, fc, rider_weight_kg, min_score, min_hours),
        "tide_events": [
            {"kind": e.kind, "time": e.time.isoformat(), "height_cm": e.height_cm} for e in tide_events
        ],
        "observation": (
            {
                "station_name": observation.station_name,
                "distance_km": observation.distance_km,
                "wind_kn": observation.wind_kn,
                "gust_kn": observation.gust_kn,
                "dir_deg": observation.dir_deg,
                "timestamp": observation.timestamp,
            }
            if observation
            else None
        ),
    }


@app.get("/accuracy")
def accuracy_summary():
    rows = load_log(ACCURACY_LOG_PATH)
    return summarize(rows).to_dict(orient="records")


@app.get("/recommendations")
async def recommendations(limit: int = 5, rider_weight_kg: float = DEFAULT_RIDER_WEIGHT_KG):
    forecasts = await get_forecasts(SPOTS)
    rows = []
    for spot in SPOTS:
        fc = forecasts[spot.id]
        for h in fc.hours:
            rows.append(
                {
                    "spot_id": spot.id,
                    "name": spot.name,
                    "time": h.time,
                    "score": score_hour(spot, h),
                    "wind_speed_kn": h.wind_speed_kn,
                    "wind_direction_deg": h.wind_direction_deg,
                    "gust_ratio": gust_ratio(h),
                    "confidence": model_confidence(h.wind_speed_spread_kn),
                    "kite_m": recommend_kite_size(rider_weight_kg, h.wind_speed_kn),
                }
            )
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:limit]
