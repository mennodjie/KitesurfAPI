"""Phone-facing UI. Run with: streamlit run streamlit_app.py

Deploy for free on Streamlit Community Cloud, then on Android open the URL
in Chrome and use "Add to Home Screen" for an app-like icon.
"""

import asyncio

import pandas as pd
import streamlit as st

from kitesurf.scoring import score_hour
from kitesurf.spots import SPOTS, SPOTS_BY_ID
from kitesurf.weather import get_forecasts

st.set_page_config(page_title="NH Kitesurf", page_icon="🪁", layout="wide")


@st.cache_data(ttl=900, show_spinner="Ophalen van weermodellen...")
def load_all_forecasts():
    forecasts = asyncio.run(get_forecasts(SPOTS))
    rows = []
    model_status = {}
    for spot in SPOTS:
        fc = forecasts[spot.id]
        model_status[spot.id] = fc.model_status
        for h in fc.hours:
            rows.append(
                {
                    "spot_id": spot.id,
                    "spot": spot.name,
                    "time": pd.to_datetime(h.time),
                    "score": score_hour(spot, h),
                    "wind_kn": h.wind_speed_kn,
                    "gust_kn": h.wind_gust_kn,
                    "dir_deg": h.wind_direction_deg,
                    "precip_mm": h.precipitation_mm,
                    "wave_m": h.wave_height_m,
                }
            )
    return pd.DataFrame(rows), model_status


st.title("🪁 Noord-Holland Kitesurf")
st.caption(
    "Muiderberg · Strand Horst · Schellinkhout · IJmuiden · Wijk aan Zee · Zandvoort — "
    "score is a planning aid, not safety advice. Check local wind, current, tide and spot rules yourself."
)

df, model_status = load_all_forecasts()

if df.empty:
    st.error("Geen data ontvangen van Open-Meteo. Probeer het later opnieuw.")
    st.stop()

only_daylight = st.sidebar.checkbox("Alleen overdag (07:00-21:00)", value=True)
min_score = st.sidebar.slider("Minimale score", 0, 100, 50)

view = df.copy()
if only_daylight:
    view = view[(view["time"].dt.hour >= 7) & (view["time"].dt.hour <= 21)]

st.subheader("Beste sessies (komende 3 dagen)")
best = view[view["score"] >= min_score].sort_values("score", ascending=False).head(15)
if best.empty:
    st.info("Geen sessies boven de gekozen minimale score gevonden.")
else:
    st.dataframe(
        best[["time", "spot", "score", "wind_kn", "gust_kn", "dir_deg", "wave_m"]],
        column_config={
            "time": st.column_config.DatetimeColumn("Tijd", format="ddd D MMM HH:mm"),
            "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
            "wind_kn": "Wind (kn)",
            "gust_kn": "Vlagen (kn)",
            "dir_deg": "Richting (°)",
            "wave_m": "Golfhoogte (m)",
        },
        hide_index=True,
        use_container_width=True,
    )

st.subheader("Per spot")
tabs = st.tabs([s.name for s in SPOTS])
for tab, spot in zip(tabs, SPOTS):
    with tab:
        spot_df = view[view["spot_id"] == spot.id].sort_values("time")
        if spot_df.empty:
            st.info("Geen uren binnen het geselecteerde filter.")
            continue
        st.line_chart(spot_df.set_index("time")[["score", "wind_kn"]])
        st.dataframe(
            spot_df[["time", "score", "wind_kn", "gust_kn", "dir_deg", "precip_mm", "wave_m"]],
            column_config={"time": st.column_config.DatetimeColumn("Tijd", format="ddd D MMM HH:mm")},
            hide_index=True,
            use_container_width=True,
            height=300,
        )
        statuses = model_status.get(spot.id, {})
        ok = [m for m, up in statuses.items() if up]
        down = [m for m, up in statuses.items() if not up]
        status_line = f"Modellen actief: {', '.join(ok) if ok else 'geen'}"
        if down:
            status_line += f" · uitgevallen: {', '.join(down)}"
        st.caption(status_line)
