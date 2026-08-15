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

COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
DAY_LABELS = ["Vandaag", "Morgen", "Overmorgen"]
WATER_ICON = {True: "🌊", False: "🏞️"}


def compass(deg):
    if deg is None or pd.isna(deg):
        return "–"
    return COMPASS[round(deg / 22.5) % 16]


def score_style(score: float) -> dict:
    if score >= 75:
        return {"bg": "#dcfce7", "fg": "#15803d", "border": "#86efac", "label": "GO!"}
    if score >= 50:
        return {"bg": "#fef9c3", "fg": "#854d0e", "border": "#fde68a", "label": "Kansrijk"}
    if score >= 25:
        return {"bg": "#ffedd5", "fg": "#9a3412", "border": "#fed7aa", "label": "Twijfel"}
    return {"bg": "#f1f5f9", "fg": "#64748b", "border": "#e2e8f0", "label": "Blijf droog"}


def score_pill(score: float) -> str:
    s = score_style(score)
    return (
        f'<span style="background:{s["bg"]};color:{s["fg"]};border:1px solid {s["border"]};'
        f'border-radius:999px;padding:2px 10px;font-weight:700;font-size:0.85rem;">'
        f"{score:.0f}</span>"
    )


st.markdown(
    """
    <style>
    .kite-hero {
        background: linear-gradient(120deg, #0ea5e9 0%, #0369a1 55%, #0c4a6e 100%);
        color: white; border-radius: 18px; padding: 28px 32px; margin-bottom: 18px;
    }
    .kite-hero h1 { margin: 0; font-size: 2rem; }
    .kite-hero p { margin: 6px 0 0 0; opacity: 0.92; font-size: 1rem; }
    .kite-kpis { display: flex; gap: 22px; margin-top: 14px; flex-wrap: wrap; }
    .kite-kpi { background: rgba(255,255,255,0.14); border-radius: 10px; padding: 6px 14px; font-size: 0.88rem; }
    .spot-card {
        border: 1px solid #e2e8f0; border-radius: 14px; padding: 14px 16px;
        background: white; height: 100%;
    }
    .spot-card h4 { margin: 0 0 8px 0; font-size: 1.05rem; }
    .day-col { text-align: center; padding: 6px 2px; }
    .day-label { font-size: 0.72rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.04em; }
    .day-meta { font-size: 0.74rem; color: #475569; margin-top: 4px; }
    .top-card {
        border-radius: 14px; padding: 16px; text-align: center; height: 100%;
    }
    .top-card .medal { font-size: 1.6rem; }
    .top-card .spotname { font-weight: 700; font-size: 1.05rem; margin: 4px 0 2px 0; }
    .top-card .bigscore { font-size: 2.2rem; font-weight: 800; }
    .top-card .meta { font-size: 0.82rem; opacity: 0.85; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=900, show_spinner="Weermodellen ophalen...")
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


st.markdown(
    """
    <div class="kite-hero">
        <h1>🪁 Noord-Holland Kitesurf Forecast</h1>
        <p>Jouw eigen wind-scout voor de komende 3 dagen. Wij vergelijken vier weermodellen zodat jij niet steeds vijf apps hoeft te checken.</p>
        <div class="kite-kpis">
            <div class="kite-kpi">📍 6 spots</div>
            <div class="kite-kpi">🛰️ 4 modellen (ECMWF · GFS · ICON · KNMI)</div>
            <div class="kite-kpi">⏱️ 72 uur vooruit</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
cap_col, info_col = st.columns([0.92, 0.08])
with cap_col:
    st.caption(
        "Muiderberg · Strand Horst · Schellinkhout · IJmuiden · Wijk aan Zee · Zandvoort — "
        "de score is een planningshulp, geen veiligheidsadvies. Check altijd lokale wind, stroming, getij en spotregels zelf."
    )
with info_col:
    with st.popover("ℹ️ Uitleg"):
        st.markdown(
            """
**Hoe wordt de score (0-100) berekend?**

Elk uur krijgt een gewogen score op basis van 5 factoren:

- 🌬️ **Windsnelheid (~40%)** — piek tussen 15-28 knopen. Onder 9 of boven 38 knopen is het onrijdbaar en wordt de score altijd 0.
- 🧭 **Windrichting (~30%)** — hoe dicht de wind bij de ideale hoek voor die specifieke spot zit (elke waterplas ligt anders gedraaid).
- 💨 **Vlagerigheid (~15%)** — hoe veel de vlagen afwijken van de gemiddelde windsnelheid; grillige wind scoort lager.
- 🌧️ **Neerslag (~10%)** — regen trekt de score omlaag.
- 🌊 **Golfhoogte (~5%, alleen zeespots)** — ruwer water bij IJmuiden, Wijk aan Zee en Zandvoort scoort lager. Voor de meren telt dit niet mee.

**Kleurcodes:** 🟢 75+ Go! · 🟡 50-74 Kansrijk · 🟠 25-49 Twijfel · ⚪ <25 Blijf droog

**Waar komt de data vandaan?** Vier onafhankelijke weermodellen (ECMWF, GFS, ICON, KNMI HARMONIE-AROME) via Open-Meteo — de score gebruikt de mediaan, zodat één afwijkend model de uitkomst niet domineert. Golfdata komt van Open-Meteo Marine.

Dit is een **planningshulp, geen veiligheidsadvies**. Check altijd zelf lokale wind, stroming, getij en spotregels.
            """
        )

df, model_status = load_all_forecasts()

if df.empty:
    st.error("Geen data ontvangen van Open-Meteo. Probeer het later opnieuw.")
    st.stop()

st.sidebar.header("Filters")
only_daylight = st.sidebar.checkbox("Alleen overdag (07:00-21:00)", value=True)
min_score = st.sidebar.slider("Minimale score", 0, 100, 50)
st.sidebar.caption("🟢 75+ Go! · 🟡 50-74 Kansrijk · 🟠 25-49 Twijfel · ⚪ <25 Blijf droog")

view = df.copy()
if only_daylight:
    view = view[(view["time"].dt.hour >= 7) & (view["time"].dt.hour <= 21)]

unique_days = sorted(view["time"].dt.date.unique())[:3]
day_labels = {d: (DAY_LABELS[i] if i < len(DAY_LABELS) else str(d)) for i, d in enumerate(unique_days)}

# ---------------------------------------------------------------------------
# 1. Beste sessies
# ---------------------------------------------------------------------------
st.header("🏆 Beste sessies")
st.caption("De uren met de hoogste score, over alle spots heen.")

ranked = view.sort_values("score", ascending=False)
top3 = ranked.head(3).reset_index(drop=True)

if top3.empty:
    st.info("Geen sessies gevonden binnen de huidige filters.")
else:
    medals = ["🥇", "🥈", "🥉"]
    cols = st.columns(len(top3))
    for col, (_, row), medal in zip(cols, top3.iterrows(), medals):
        s = score_style(row["score"])
        with col:
            st.markdown(
                f"""
                <div class="top-card" style="background:{s['bg']};border:1px solid {s['border']};">
                    <div class="medal">{medal}</div>
                    <div class="spotname" style="color:{s['fg']};">{row['spot']}</div>
                    <div class="bigscore" style="color:{s['fg']};">{row['score']:.0f}</div>
                    <div class="meta" style="color:{s['fg']};">{row['time'].strftime('%a %d %b · %H:%M')}</div>
                    <div class="meta" style="color:{s['fg']};">{row['wind_kn']:.0f} kn · {compass(row['dir_deg'])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.write("")
best = view[view["score"] >= min_score].sort_values("score", ascending=False).head(15)
if best.empty:
    st.info("Geen sessies boven de gekozen minimale score gevonden — verlaag de slider in de zijbalk.")
else:
    with st.expander(f"📋 Top {len(best)} sessies (tabel)", expanded=False):
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

st.divider()

# ---------------------------------------------------------------------------
# 2. Alle spots, komende 3 dagen (grid overview)
# ---------------------------------------------------------------------------
st.header("📅 Alle spots — komende 3 dagen")
st.caption("Piekscore per dag, per spot. Klik door naar 'Per spot' hieronder voor het uurrooster.")

grid_cols = st.columns(3)
for i, spot in enumerate(SPOTS):
    spot_df = view[view["spot_id"] == spot.id]
    with grid_cols[i % 3]:
        card_html = (
            f'<div class="spot-card"><h4>{WATER_ICON[spot.is_coastal]} {spot.name} '
            f'<span style="font-size:0.72rem;color:#94a3b8;font-weight:400;">· {spot.water_body}</span></h4>'
        )
        card_html += '<div style="display:flex;">'
        for d in unique_days:
            day_df = spot_df[spot_df["time"].dt.date == d]
            if day_df.empty:
                card_html += (
                    '<div class="day-col" style="flex:1;"><div class="day-label">'
                    f'{day_labels[d]}</div><div style="margin-top:6px;">–</div></div>'
                )
                continue
            peak = day_df.loc[day_df["score"].idxmax()]
            card_html += (
                f'<div class="day-col" style="flex:1;">'
                f'<div class="day-label">{day_labels[d]}</div>'
                f'<div style="margin-top:6px;">{score_pill(peak["score"])}</div>'
                f'<div class="day-meta">{peak["time"].strftime("%H:%M")} · {peak["wind_kn"]:.0f}kn {compass(peak["dir_deg"])}</div>'
                f"</div>"
            )
        card_html += "</div></div>"
        st.markdown(card_html, unsafe_allow_html=True)
        st.write("")

st.divider()

# ---------------------------------------------------------------------------
# 3. Per spot detail
# ---------------------------------------------------------------------------
st.header("📍 Per spot")
tabs = st.tabs([f"{WATER_ICON[s.is_coastal]} {s.name}" for s in SPOTS])
for tab, spot in zip(tabs, SPOTS):
    with tab:
        spot_df = view[view["spot_id"] == spot.id].sort_values("time")
        if spot_df.empty:
            st.info("Geen uren binnen het geselecteerde filter.")
            continue

        peak_row = spot_df.loc[spot_df["score"].idxmax()]
        s = score_style(peak_row["score"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Beste moment", peak_row["time"].strftime("%a %H:%M"), f"score {peak_row['score']:.0f}")
        c2.metric("Piekwind", f"{peak_row['wind_kn']:.0f} kn", compass(peak_row["dir_deg"]))
        good_hours = (spot_df["score"] >= min_score).sum()
        c3.metric(f"Uren ≥ {min_score}", f"{good_hours}", "in de gekozen periode")

        st.line_chart(spot_df.set_index("time")[["score", "wind_kn"]])
        st.dataframe(
            spot_df[["time", "score", "wind_kn", "gust_kn", "dir_deg", "precip_mm", "wave_m"]],
            column_config={
                "time": st.column_config.DatetimeColumn("Tijd", format="ddd D MMM HH:mm"),
                "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
            },
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
