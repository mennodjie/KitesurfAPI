"""Checks all spots for upcoming good windows and pushes a notification via ntfy.sh.

Run manually with: python scripts/check_alerts.py
Runs on a schedule via .github/workflows/wind-alert.yml.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kitesurf.alerts import find_new_alerts
from kitesurf.notify import NTFY_TOPIC, send_ntfy
from kitesurf.scoring import score_hour
from kitesurf.spots import SPOTS
from kitesurf.weather import get_forecasts
from kitesurf.windows import compute_good_windows

THRESHOLD = float(os.environ.get("ALERT_SCORE_THRESHOLD", "75"))
WITHIN_DAYS = int(os.environ.get("ALERT_WITHIN_DAYS", "3"))
MIN_HOURS = int(os.environ.get("ALERT_MIN_HOURS", "3"))
STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "alert_state.json"

# Matches the Streamlit app's "Daytime only" filter -- nobody's going out at 3am,
# so a window that only exists overnight shouldn't page anyone.
DAYLIGHT_START_HOUR = 7
DAYLIGHT_END_HOUR = 21


def amsterdam_now() -> pd.Timestamp:
    """Naive wall-clock time in Europe/Amsterdam, matching the (also naive) timestamps
    Open-Meteo returns for that timezone. GitHub Actions runners are UTC, so a plain
    pd.Timestamp.now() would be 1-2 hours off depending on DST."""
    return pd.Timestamp.now(tz="Europe/Amsterdam").tz_localize(None)


def load_state() -> set:
    if STATE_PATH.exists():
        return set(json.loads(STATE_PATH.read_text()).get("notified", []))
    return set()


def save_state(notified: set) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"notified": sorted(notified)}, indent=2) + "\n")


def send_test_notification() -> None:
    """Sends one synthetic alert via ntfy -- ignores real forecast data and dedupe state."""
    now = amsterdam_now()
    alert = {
        "key": "test|" + now.isoformat(),
        "spot_id": "test",
        "spot_name": "Test spot",
        "start": now,
        "end": now + pd.Timedelta(hours=3),
        "peak_score": 99,
        "wind_kn": 22,
        "dir_deg": 270,
        "hours": 3,
    }
    if not NTFY_TOPIC:
        print("NTFY_TOPIC is not configured -- nothing to send.")
        return

    print("Sending test push via ntfy...")
    send_ntfy(alert)
    print("Done. Check your phone. This did not touch data/alert_state.json.")


async def main() -> None:
    if os.environ.get("TEST_NOTIFICATION", "").lower() in ("1", "true", "yes"):
        send_test_notification()
        return

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
        spot_df = spot_df[
            (spot_df["time"].dt.hour >= DAYLIGHT_START_HOUR) & (spot_df["time"].dt.hour <= DAYLIGHT_END_HOUR)
        ]
        windows_by_spot[spot.id] = compute_good_windows(spot_df, threshold=THRESHOLD, min_hours=MIN_HOURS)

    notified = load_state()
    now = amsterdam_now()
    spot_names = {s.id: s.name for s in SPOTS}
    alerts = find_new_alerts(windows_by_spot, spot_names, THRESHOLD, WITHIN_DAYS, notified, now)

    if alerts and not NTFY_TOPIC:
        print("NTFY_TOPIC is not configured -- would have alerted:")

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
