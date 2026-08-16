"""Tracks how far the forecast median was from what actually happened.

Compares the forecast that was made for "this hour" against the live
station observation fetched at roughly the same time -- a nowcast check,
not a measure of lead-time accuracy (that would need storing forecasts
made hours/days in advance and revisiting them later, which this project
doesn't do). Still a useful signal: if a spot's nowcast is consistently
off, the models are probably struggling with that specific microclimate.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

MIN_SAMPLES_FOR_SUMMARY = 5


@dataclass
class AccuracySample:
    timestamp: str
    spot_id: str
    forecast_wind_kn: float
    observed_wind_kn: float
    forecast_dir_deg: float | None
    observed_dir_deg: float | None


def circular_diff(a: float | None, b: float | None) -> float | None:
    """Smallest angle (0-180) between two compass directions."""
    if a is None or b is None:
        return None
    diff = abs(a - b) % 360
    return min(diff, 360 - diff)


def load_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_log(path: Path, samples: list[AccuracySample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for sample in samples:
            f.write(json.dumps(asdict(sample)) + "\n")


def summarize(rows: list[dict]) -> pd.DataFrame:
    """Per-spot mean absolute error, only for spots with enough samples to mean anything."""
    if not rows:
        return pd.DataFrame(columns=["spot_id", "samples", "mean_wind_error_kn", "mean_dir_error_deg"])

    df = pd.DataFrame(rows)
    df["wind_error_kn"] = (df["forecast_wind_kn"] - df["observed_wind_kn"]).abs()
    df["dir_error_deg"] = df.apply(lambda r: circular_diff(r["forecast_dir_deg"], r["observed_dir_deg"]), axis=1)

    grouped = df.groupby("spot_id").agg(
        samples=("wind_error_kn", "count"),
        mean_wind_error_kn=("wind_error_kn", "mean"),
        mean_dir_error_deg=("dir_error_deg", "mean"),
    ).reset_index()
    grouped["mean_wind_error_kn"] = grouped["mean_wind_error_kn"].round(1)
    grouped["mean_dir_error_deg"] = grouped["mean_dir_error_deg"].round(0)
    return grouped[grouped["samples"] >= MIN_SAMPLES_FOR_SUMMARY]
