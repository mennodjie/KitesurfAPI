"""Checks all spots for upcoming good windows and pushes a notification via ntfy.sh.

Run manually with: python scripts/check_alerts.py
Runs on a schedule via .github/workflows/wind-alert.yml.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kitesurf.alerts import find_new_alerts
from kitesurf.scoring import score_hour
from kitesurf.spots import SPOTS
from kitesurf.weather import get_forecasts
from kitesurf.windows import compute_good_windows

THRESHOLD = float(os.environ.get("ALERT_SCORE_THRESHOLD", "75"))
WITHIN_DAYS = int(os.environ.get("ALERT_WITHIN_DAYS", "3"))
MIN_HOURS = int(os.environ.get("ALERT_MIN_HOURS", "3"))
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "alert_state.json"


def load_state() -> set:
    if STATE_PATH.exists():
        return set(json.loads(STATE_PATH.read_text()).get("notified", []))
    return set()


def save_state(notified: set) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"notified": sorted(notified)}, indent=2) + "\n")


def send_ntfy(alert: dict) -> None:
    if not NTFY_TOPIC:
        print(f"NTFY_TOPIC not set -- would have alerted: {alert['key']}")
        return
    title = f"{alert['spot_name']}: GO ({alert['peak_score']:.0f})"
    body = (
        f"{alert['start'].strftime('%a %d %b %H:%M')}-{alert['end'].strftime('%H:%M')} · "
        f"{alert['wind_kn']:.0f} kn · {alert['hours']:.0f}u aaneengesloten"
    )
    resp = httpx.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        content=body.encode("utf-8"),
        headers={"Title": title, "Priority": "high", "Tags": "kite"},
        timeout=15,
    )
    resp.raise_for_status()


async def main() -> None:
    forecasts = await get_forecasts(SPOTS, use_cache=False)
    windows_by_spot = {}
    for spot in SPOTS:
        rows = [
            {
                "time": pd.to_datetime(h.time),
                "score": score_hour(spot, h),
                "wind_kn": h.wind_speed_kn,
                "gust_kn": h.wind_gust_kn,
                "dir_deg": h.wind_direction_deg,
            }
            for h in forecasts[spot.id].hours
        ]
        spot_df = pd.DataFrame(rows)
        windows_by_spot[spot.id] = compute_good_windows(spot_df, threshold=THRESHOLD, min_hours=MIN_HOURS)

    notified = load_state()
    now = pd.Timestamp.now()
    spot_names = {s.id: s.name for s in SPOTS}
    alerts = find_new_alerts(windows_by_spot, spot_names, THRESHOLD, WITHIN_DAYS, notified, now)

    for alert in alerts:
        send_ntfy(alert)
        notified.add(alert["key"])
        print(f"Alerted: {alert['key']}")

    if not alerts:
        print("No new qualifying windows.")

    # Drop state for windows that have already started, so the file doesn't grow forever.
    still_relevant = {k for k in notified if k.split("|", 1)[1] >= now.isoformat()}
    save_state(still_relevant)


if __name__ == "__main__":
    asyncio.run(main())
