"""Optional FastAPI interface -- same core logic as the Streamlit app.

Run locally with: uvicorn kitesurf.api.main:app --reload
"""

from fastapi import FastAPI, HTTPException

from kitesurf.scoring import score_hour
from kitesurf.spots import SPOTS, SPOTS_BY_ID
from kitesurf.weather import get_forecast, get_forecasts

app = FastAPI(
    title="KiteScout API",
    description="Open weather/marine data combined into a kitesurf spot ranking. Planning aid, not safety advice.",
)


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
