"""Tide (water level) forecast for the North Sea spots, via Rijkswaterstaat.

IJmuiden, Wijk aan Zee, and Zandvoort are all close enough along the same
stretch of coast to share one real, live-measuring gauge (ijmuiden.buitenhaven)
as their tide reference -- the other nearby named locations in RWS's catalog
(wijkaanzee, zandvoortaanzee) exist but don't have active real-time telemetry.
Inland spots (IJmeer/Markermeer/Wolderwijd) are managed, non-tidal water levels,
so tides don't apply there.

Water levels are cm relative to NAP (Normaal Amsterdams Peil). High/low tide
times are derived from the forecast curve by finding local maxima/minima --
RWS's own "verwachting" (forecast) parameter no longer separately labels them.
"""

from dataclasses import dataclass

import httpx
import pandas as pd

WATERWEBSERVICES_URL = "https://ddapi20-waterwebservices.rijkswaterstaat.nl/ONLINEWAARNEMINGENSERVICES/OphalenWaarnemingen"
TIDE_STATION_CODE = "ijmuiden.buitenhaven"
TIDE_STATION_NAME = "IJmuiden (buitenhaven)"
# Every spot with is_coastal=True currently shares this one station; if a
# future coastal spot is added far enough away, give it its own station code
# instead of reusing this one.
FORECAST_DAYS = 3


@dataclass
class TideEvent:
    kind: str  # "high" or "low"
    time: pd.Timestamp
    height_cm: float


async def fetch_water_levels(client: httpx.AsyncClient, days: int = FORECAST_DAYS) -> pd.DataFrame:
    now = pd.Timestamp.now(tz="UTC")
    body = {
        "Locatie": {"Code": TIDE_STATION_CODE},
        "AquoPlusWaarnemingMetadata": {
            "AquoMetadata": {
                "Compartiment": {"Code": "OW"},
                "Grootheid": {"Code": "WATHTE"},
            }
        },
        "Periode": {
            "Begindatumtijd": now.strftime("%Y-%m-%dT%H:%M:%S.000+00:00"),
            "Einddatumtijd": (now + pd.Timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000+00:00"),
        },
    }
    try:
        resp = await client.post(WATERWEBSERVICES_URL, json=body, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return pd.DataFrame(columns=["time", "height_cm"])

    if not data.get("Succesvol"):
        return pd.DataFrame(columns=["time", "height_cm"])

    # RWS returns multiple series for the same station/parameter -- "verwachting"
    # (weather-influenced, includes wind-driven surge noise) and "astronomisch"
    # (pure tidal astronomy). Mixing them produces spurious extra peaks when
    # scanning for highs/lows, so use only the astronomical series: it's the
    # standard basis for tide *timing* (what tide tables actually show).
    rows = []
    for series in data.get("WaarnemingenLijst", []):
        if series.get("AquoMetadata", {}).get("ProcesType") != "astronomisch":
            continue
        for m in series.get("MetingenLijst", []):
            value = m.get("Meetwaarde", {}).get("Waarde_Numeriek")
            tijdstip = m.get("Tijdstip")
            if value is not None and tijdstip is not None:
                rows.append({"time": pd.to_datetime(tijdstip), "height_cm": value})
    if not rows:
        return pd.DataFrame(columns=["time", "height_cm"])
    return pd.DataFrame(rows).sort_values("time").reset_index(drop=True)


MIN_EVENT_GAP = pd.Timedelta(hours=2)


def find_tide_events(levels: pd.DataFrame) -> list[TideEvent]:
    """Local maxima/minima in the water-level curve -- high and low tide.

    Real semi-diurnal tides are ~6 hours apart, but a near-flat plateau at
    the actual peak can register as two adjacent candidate points a few
    minutes apart -- merged below by keeping only the most extreme candidate
    within any MIN_EVENT_GAP window of the same kind.
    """
    if len(levels) < 3:
        return []
    candidates = []
    heights = levels["height_cm"].to_numpy()
    times = levels["time"].to_numpy()
    for i in range(1, len(heights) - 1):
        if heights[i] >= heights[i - 1] and heights[i] >= heights[i + 1] and heights[i] > heights[i - 1]:
            candidates.append(TideEvent(kind="high", time=pd.Timestamp(times[i]), height_cm=float(heights[i])))
        elif heights[i] <= heights[i - 1] and heights[i] <= heights[i + 1] and heights[i] < heights[i - 1]:
            candidates.append(TideEvent(kind="low", time=pd.Timestamp(times[i]), height_cm=float(heights[i])))

    events: list[TideEvent] = []
    for c in candidates:
        prev = next((e for e in reversed(events) if e.kind == c.kind and c.time - e.time <= MIN_EVENT_GAP), None)
        if prev is None:
            events.append(c)
            continue
        more_extreme = c.height_cm > prev.height_cm if c.kind == "high" else c.height_cm < prev.height_cm
        if more_extreme:
            events[events.index(prev)] = c
    return events


async def get_tide_events(days: int = FORECAST_DAYS) -> list[TideEvent]:
    async with httpx.AsyncClient() as client:
        levels = await fetch_water_levels(client, days=days)
    return find_tide_events(levels)
