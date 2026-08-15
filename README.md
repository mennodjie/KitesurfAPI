# Noord-Holland Kitesurf Weather

A weather-consensus ranking for 6 kitesurf spots: Muiderberg, Strand Horst,
Schellinkhout, IJmuiden, Wijk aan Zee, Zandvoort.

Combines wind data from 4 open weather models (ECMWF, GFS, ICON, KNMI
HARMONIE-AROME via Open-Meteo) plus marine wave data for the North Sea
spots, into a 0-100 score per hour for the next 3 days.

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

## Run it (API)

```bash
uvicorn kitesurf.api.main:app --reload
```

- `GET /spots`
- `GET /forecast/{spot_id}`
- `GET /recommendations?limit=5`

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
