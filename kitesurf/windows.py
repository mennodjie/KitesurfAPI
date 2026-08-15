"""Detects runs of consecutive hours meeting a score threshold.

A single high-scoring hour surrounded by junk wind isn't a session --
this groups the hourly forecast into contiguous "good windows" so the
UI can require a minimum duration before calling something ridable.
"""

import pandas as pd

WINDOW_COLUMNS = ["start", "end", "peak_score", "avg_score", "wind_kn", "gust_kn", "dir_deg", "hours"]


def compute_good_windows(spot_df: pd.DataFrame, threshold: float, min_hours: int = 3) -> pd.DataFrame:
    d = spot_df.sort_values("time").reset_index(drop=True)
    if d.empty:
        return pd.DataFrame(columns=WINDOW_COLUMNS)

    gap = d["time"].diff().dt.total_seconds().div(3600).fillna(1.0) != 1.0
    is_good = d["score"] >= threshold
    run_id = (gap | (~is_good)).cumsum()

    windows = []
    good_rows = d[is_good]
    for _, grp in good_rows.groupby(run_id[is_good]):
        if len(grp) < min_hours:
            continue
        peak = grp.loc[grp["score"].idxmax()]
        windows.append(
            {
                "start": grp["time"].iloc[0],
                "end": grp["time"].iloc[-1] + pd.Timedelta(hours=1),
                "peak_score": float(grp["score"].max()),
                "avg_score": round(float(grp["score"].mean()), 1),
                "wind_kn": peak["wind_kn"],
                "gust_kn": peak["gust_kn"],
                "dir_deg": peak["dir_deg"],
                "hours": len(grp),
            }
        )
    return pd.DataFrame(windows, columns=WINDOW_COLUMNS)


def best_window_score(windows: pd.DataFrame) -> float:
    return float(windows["peak_score"].max()) if not windows.empty else 0.0
