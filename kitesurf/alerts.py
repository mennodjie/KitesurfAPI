"""Decides which upcoming good windows are worth a push notification.

A window is alert-worthy once it starts within `within_days` of now, its
peak score clears `threshold`, and its (spot, start) key hasn't been
notified before -- dedup state is the caller's responsibility to load/save.
"""

import pandas as pd


def find_new_alerts(
    windows_by_spot: dict,
    spot_names: dict,
    threshold: float,
    within_days: int,
    already_notified: set,
    now: pd.Timestamp,
) -> list[dict]:
    cutoff = now + pd.Timedelta(days=within_days)
    alerts = []
    for spot_id, windows in windows_by_spot.items():
        if windows.empty:
            continue
        qualifying = windows[
            (windows["peak_score"] >= threshold) & (windows["start"] >= now) & (windows["start"] <= cutoff)
        ]
        for _, row in qualifying.iterrows():
            key = f"{spot_id}|{row['start'].isoformat()}"
            if key in already_notified:
                continue
            alerts.append(
                {
                    "key": key,
                    "spot_id": spot_id,
                    "spot_name": spot_names.get(spot_id, spot_id),
                    "start": row["start"],
                    "end": row["end"],
                    "peak_score": row["peak_score"],
                    "wind_kn": row["wind_kn"],
                    "dir_deg": row["dir_deg"],
                    "hours": row["hours"],
                }
            )
    return alerts
