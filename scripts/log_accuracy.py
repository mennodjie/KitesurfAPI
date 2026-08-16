"""Logs forecast-vs-actual for the current hour, for every spot.

Run manually with: python scripts/log_accuracy.py
Runs on the same schedule as scripts/check_alerts.py (see .github/workflows/wind-alert.yml).
"""

import asyncio
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kitesurf.accuracy import AccuracySample, append_log
from kitesurf.observations import get_observations
from kitesurf.spots import SPOTS
from kitesurf.weather import get_forecasts

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "accuracy_log.jsonl"


async def main() -> None:
    forecasts, observations = await asyncio.gather(
        get_forecasts(SPOTS, use_cache=False),
        get_observations(SPOTS),
    )

    now_hour = pd.Timestamp.now(tz="Europe/Amsterdam").tz_localize(None).floor("h")
    samples = []
    for spot in SPOTS:
        obs = observations.get(spot.id)
        if obs is None or obs.wind_kn is None:
            continue
        matching_hour = next(
            (h for h in forecasts[spot.id].hours if pd.to_datetime(h.time) == now_hour),
            None,
        )
        if matching_hour is None or matching_hour.wind_speed_kn is None:
            continue
        samples.append(
            AccuracySample(
                timestamp=now_hour.isoformat(),
                spot_id=spot.id,
                forecast_wind_kn=matching_hour.wind_speed_kn,
                observed_wind_kn=obs.wind_kn,
                forecast_dir_deg=matching_hour.wind_direction_deg,
                observed_dir_deg=obs.dir_deg,
            )
        )

    if not samples:
        print("No samples logged (no matching forecast hour or no live observation).")
        return

    append_log(LOG_PATH, samples)
    print(f"Logged {len(samples)} accuracy sample(s) for {now_hour.isoformat()}.")


if __name__ == "__main__":
    asyncio.run(main())
