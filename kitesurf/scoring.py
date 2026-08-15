"""Turns a raw forecast hour into a 0-100 "worth going" score.

This is a planning aid, not safety advice. Always check local wind,
current, tide, spot rules, and your own safety margin before going out.
"""

from kitesurf.spots import Spot
from kitesurf.weather import HourPoint

IDEAL_WIND_MIN_KN = 15
IDEAL_WIND_MAX_KN = 28
RIDEABLE_WIND_MIN_KN = 9
RIDEABLE_WIND_MAX_KN = 38

MAX_GUST_FACTOR = 1.6  # gust/mean ratio above which gustiness is scored 0
MAX_USEFUL_PRECIP_MM = 2.0  # precip at/above this scores 0
MAX_COMFORTABLE_WAVE_M = 1.4  # wave height at/above this scores 0

WEIGHTS_WITH_WAVE = {"speed": 0.40, "direction": 0.30, "gust": 0.15, "precip": 0.10, "wave": 0.05}
WEIGHTS_NO_WAVE = {"speed": 0.42, "direction": 0.33, "gust": 0.17, "precip": 0.08}


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _speed_score(speed_kn: float | None) -> float:
    if speed_kn is None:
        return 0.0
    if speed_kn < RIDEABLE_WIND_MIN_KN or speed_kn > RIDEABLE_WIND_MAX_KN:
        return 0.0
    if IDEAL_WIND_MIN_KN <= speed_kn <= IDEAL_WIND_MAX_KN:
        return 1.0
    if speed_kn < IDEAL_WIND_MIN_KN:
        return _clamp((speed_kn - RIDEABLE_WIND_MIN_KN) / (IDEAL_WIND_MIN_KN - RIDEABLE_WIND_MIN_KN))
    return _clamp((RIDEABLE_WIND_MAX_KN - speed_kn) / (RIDEABLE_WIND_MAX_KN - IDEAL_WIND_MAX_KN))


def _angular_distance(deg: float, lo: float, hi: float) -> float:
    """Degrees outside [lo, hi] (wrapping through 360), 0 if inside."""
    span = (hi - lo) % 360
    offset = (deg - lo) % 360
    if offset <= span:
        return 0.0
    return min(offset - span, 360 - offset)


def _direction_score(direction_deg: float | None, good_range: tuple[float, float]) -> float:
    if direction_deg is None:
        return 0.0
    dist = _angular_distance(direction_deg, *good_range)
    return _clamp(1.0 - dist / 60.0)  # full marks inside range, 0 once 60deg outside it


def _gust_score(speed_kn: float | None, gust_kn: float | None) -> float:
    if speed_kn is None or gust_kn is None or speed_kn <= 0:
        return 0.5  # unknown, don't punish or reward
    factor = gust_kn / speed_kn
    if factor <= 1.2:
        return 1.0
    return _clamp((MAX_GUST_FACTOR - factor) / (MAX_GUST_FACTOR - 1.2))


def _precip_score(precip_mm: float | None) -> float:
    if precip_mm is None:
        return 1.0
    return _clamp(1.0 - precip_mm / MAX_USEFUL_PRECIP_MM)


def _wave_score(wave_m: float | None) -> float | None:
    if wave_m is None:
        return None
    return _clamp(1.0 - wave_m / MAX_COMFORTABLE_WAVE_M)


def score_hour(spot: Spot, hour: HourPoint) -> float:
    speed = _speed_score(hour.wind_speed_kn)
    if speed == 0.0:
        return 0.0  # unrideable wind gates the score regardless of other factors

    direction = _direction_score(hour.wind_direction_deg, spot.good_wind_dir)
    gust = _gust_score(hour.wind_speed_kn, hour.wind_gust_kn)
    precip = _precip_score(hour.precipitation_mm)
    wave = _wave_score(hour.wave_height_m)

    if wave is None:
        weights = WEIGHTS_NO_WAVE
        total = speed * weights["speed"] + direction * weights["direction"] + gust * weights["gust"] + precip * weights["precip"]
    else:
        weights = WEIGHTS_WITH_WAVE
        total = (
            speed * weights["speed"]
            + direction * weights["direction"]
            + gust * weights["gust"]
            + precip * weights["precip"]
            + wave * weights["wave"]
        )

    return round(total * 100, 1)
