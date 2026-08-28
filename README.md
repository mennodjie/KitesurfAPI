# KiteScout

A weather-consensus ranking for 6 kitesurf spots in Noord-Holland and
Flevoland: Muiderberg, Strand Horst, Schellinkhout, IJmuiden, Wijk aan
Zee, Zandvoort. Wind-direction preferences per spot are cross-checked
against real kitesurf spot guides, not just shoreline-orientation
guesses (see `kitesurf/spots.py`).

Combines wind data from 4 open weather models (ECMWF, GFS, ICON, KNMI
HARMONIE-AROME via Open-Meteo) plus marine wave data for the North Sea
spots, into a 0-100 score per hour for the next 7 days. Also pulls in,
where relevant: live station observations (actual current wind, not
forecast), tide times for the North Sea spots, and a running log of
how far the forecast has been from what actually happened.

Accuracy degrades the further out you look — treat days 4-7 as a rough
heads-up, not a plan. KNMI HARMONIE-AROME in particular only forecasts
~2-3 days out; beyond that the score falls back to whichever of the
other 3 models still cover that hour.

A single high-scoring hour isn't a session — the UI only counts
**windows of consecutive hours** above your chosen score threshold as
"good," consistently across the best-sessions list, the multi-day
overview, and the per-spot detail view. Both the score threshold and
the minimum window length (1-6 hours, default 3) are adjustable in the
sidebar.

**The score is a planning aid, not safety advice.** Always check local
wind, current, tide, spot rules, and your own safety margin.

## Run it (phone-facing, Streamlit)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open the printed `http://localhost:8501` URL. To use it on your phone
without building a native app: deploy to [Streamlit Community
Cloud](https://streamlit.io/cloud) (free — connect this GitHub repo,
point it at `streamlit_app.py`), then on Android open the deployed URL in
Chrome and use **⋮ → Add to Home Screen** for an app-like icon.

The forecast is cached for 15 minutes (`CACHE_TTL_SECONDS` in
`kitesurf/weather.py`); an open tab silently reloads on that same
interval so it picks up fresh data without a manual refresh.

## Push notifications

Streamlit Community Cloud has no background scheduler, and a phone
browser tab can't reliably push notifications on its own. Instead,
a free GitHub Actions cron job checks the forecast every 3 hours and
pushes via [ntfy.sh](https://ntfy.sh) (no account needed — just an
Android app and a topic name) whenever a spot gets a new **3+ hour
GO window (score ≥75) starting within the next 3 days**, restricted to
daylight hours (07:00-21:00) so a window that only exists overnight
doesn't page anyone. Already-sent alerts are deduplicated via
`data/alert_state.json`, committed back to the repo by the workflow.

Setup:

1. Install the **ntfy** app from the Play Store.
2. In the app, subscribe to a topic — pick something long and
   hard-to-guess (e.g. `nh-kite-<random-string>`), since ntfy.sh topics
   are public unless you self-host: anyone who knows the topic name can
   subscribe or publish to it.
3. In this repo's GitHub settings → **Secrets and variables → Actions**,
   add a repository secret named `NTFY_TOPIC` with that same topic name.
4. The workflow (`.github/workflows/wind-alert.yml`) runs automatically
   every 3 hours, or trigger it manually from the Actions tab
   ("Run workflow") to test it immediately.

Run it locally without waiting for the schedule:

```bash
NTFY_TOPIC=your-topic-name python scripts/check_alerts.py
```

## Extra data sources

Beyond the Open-Meteo forecast, the app pulls in a few free, keyless
sources when relevant:

- **Live station observations** (`kitesurf/observations.py`) — the
  nearest [Buienradar](https://www.buienradar.nl) weather station's
  *actual* current wind/gust/direction, shown alongside the forecast
  per spot. KNMI's own live-observation API is more authoritative but
  requires registering for an API key, which didn't fit this project's
  keyless approach -- Buienradar is a free stand-in.
- **Tide times** (`kitesurf/tides.py`) — for the three North Sea spots
  (IJmuiden, Wijk aan Zee, Zandvoort), next high/low tide from
  [Rijkswaterstaat](https://rijkswaterstaatdata.nl)'s open water-level
  API, using the one nearby station with live telemetry
  (`ijmuiden.buitenhaven`) as a shared reference for all three. The
  inland spots (IJmeer/Markermeer/Wolderwijd) are managed, non-tidal
  water, so tides don't apply there.
- **Forecast accuracy** (`kitesurf/accuracy.py`) — every ~3 hours,
  `scripts/log_accuracy.py` compares the forecast for "now" against
  the live observation fetched at the same time, and appends the
  difference to `data/accuracy_log.jsonl`. This is a *nowcast* check
  (forecast-for-now vs. actual-now), not a measure of how good a
  forecast was days in advance -- that would need storing predictions
  made ahead of time and revisiting them later, which this project
  doesn't do. Each spot's detail view shows a running average once it
  has 5+ logged samples.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Notes

- The Open-Meteo free endpoints are for non-commercial use with no SLA —
  fine for a personal tool. Attribution: Weather and marine data:
  Open-Meteo, CC BY 4.0.
- Wind-model set is configurable via the `WEATHER_MODELS` env var
  (comma-separated Open-Meteo model ids).
- Per-spot "good wind direction" ranges in `kitesurf/spots.py` are rough
  approximations — tune them against your own local knowledge of each
  spot's shoreline.
- Forecast range is configurable via `FORECAST_DAYS` in `kitesurf/weather.py`
  (currently 7; Open-Meteo supports more for some models, but wind
  accuracy for kiteability is not meaningfully useful much past a week).

## Adding a spot

Repo is public, so anyone can open a pull request. To add a spot, add
one `Spot(...)` entry to the `SPOTS` list in `kitesurf/spots.py` with
its coordinates, water body, `is_coastal` flag (True only for open
North Sea, for marine wave data), and a `good_wind_dir` range tuned to
that spot's shoreline orientation. No other code changes needed — the
Streamlit UI picks up new spots automatically.
