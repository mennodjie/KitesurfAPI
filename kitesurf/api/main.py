"""Optional FastAPI interface -- same core logic as the Streamlit app.

Run locally with: uvicorn kitesurf.api.main:app --reload
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kitesurf.scoring import score_hour
from kitesurf.spots import SPOTS, SPOTS_BY_ID
from kitesurf.weather import get_forecast, get_forecasts

app = FastAPI(
    title="KiteScout API",
    description="Open weather/marine data combined into a kitesurf spot ranking. Planning aid, not safety advice.",
)

ROOT_DIR = Path(__file__).resolve().parents[2]
PWA_DIR = ROOT_DIR / "static" / "pwa"
STATIC_DIR = ROOT_DIR / "static"

app.mount("/pwa-assets", StaticFiles(directory=STATIC_DIR), name="pwa-assets")


@app.get("/", include_in_schema=False)
def pwa_index():
    return FileResponse(PWA_DIR / "index.html")


@app.get("/app", include_in_schema=False)
def pwa_index_alias():
    return FileResponse(PWA_DIR / "index.html")


@app.get("/app.css", include_in_schema=False)
def pwa_css():
    return FileResponse(PWA_DIR / "app.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
def pwa_js():
    return FileResponse(PWA_DIR / "app.js", media_type="application/javascript")


@app.get("/manifest.json", include_in_schema=False)
def pwa_manifest():
    return FileResponse(PWA_DIR / "manifest.json", media_type="application/manifest+json")


@app.get("/service-worker.js", include_in_schema=False)
def pwa_service_worker():
    return FileResponse(PWA_DIR / "service-worker.js", media_type="application/javascript")


@app.get("/offline.html", include_in_schema=False)
def pwa_offline():
    return FileResponse(PWA_DIR / "offline.html")


@app.get("/spots")
def list_spots():
    return [
        {"id": s.id, "name": s.name, "water_body": s.water_body, "is_coastal": s.is_coastal}
        for s in SPOTS
    ]


@app.get("/forecast/{spot_id}")
async def forecast(spot_id: str):
    spot = SPOTS_BY_ID.get(spot_id)
    if not spot:
        raise HTTPException(status_code=404, detail=f"Unknown spot_id '{spot_id}'")
    fc = await get_forecast(spot)
    return {
        "spot_id": spot.id,
        "name": spot.name,
        "model_status": fc.model_status,
        "marine_available": fc.marine_available,
        "hours": [
            {
                "time": h.time,
                "wind_speed_kn": h.wind_speed_kn,
                "wind_gust_kn": h.wind_gust_kn,
                "wind_direction_deg": h.wind_direction_deg,
                "precipitation_mm": h.precipitation_mm,
                "wave_height_m": h.wave_height_m,
                "score": score_hour(spot, h),
            }
            for h in fc.hours
        ],
    }


@app.get("/recommendations")
async def recommendations(limit: int = 5):
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
                }
            )
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:limit]
