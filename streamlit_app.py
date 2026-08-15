"""Phone-facing UI. Run with: streamlit run streamlit_app.py

Deploy for free on Streamlit Community Cloud, then on Android open the URL
in Chrome and use "Add to Home Screen" for an app-like icon.
"""

import asyncio

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from kitesurf.scoring import score_hour
from kitesurf.spots import SPOTS, SPOTS_BY_ID
from kitesurf.weather import CACHE_TTL_SECONDS, get_forecasts
from kitesurf.windows import compute_good_windows

SPOTS_BY_NAME = {s.name: s for s in SPOTS}

st.set_page_config(page_title="NH Kitesurf", page_icon="🪁", layout="wide")

# Reload the tab once the forecast cache would expire anyway, so an open tab
# picks up fresh data without the user having to refresh manually.
components.html(f"<script>setTimeout(() => window.parent.location.reload(), {CACHE_TTL_SECONDS * 1000});</script>", height=0)

COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
WATER_LABEL = {True: "Zee", False: "Binnenwater"}
NL_WEEKDAYS = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"]
NL_MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
GOOD_WINDOW_MIN_HOURS = 3
METRIC_OPTIONS = {"Score": ("score", "Score (0-100)"), "Wind": ("wind_kn", "Wind (kn)"), "Neerslag": ("precip_mm", "Neerslag (mm)")}

# Muted, solid status colors (white text) -- reads consistently in both light and dark mode
# since each chip carries its own fixed background rather than relying on the page theme.
TIER_COLORS = {
    "GO": "#0f766e",
    "KANSRIJK": "#b45309",
    "TWIJFEL": "#9a3412",
    "NIKS": "#475569",
}


def fmt_day(d) -> str:
    return f"{NL_WEEKDAYS[d.weekday()]} {d.day} {NL_MONTHS[d.month - 1]}"


def fmt_range(start, end) -> str:
    if start.date() == end.date():
        return f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"
    return f"{start.strftime('%a %H:%M')}–{end.strftime('%a %H:%M')}"


def compass(deg):
    if deg is None or pd.isna(deg):
        return "–"
    return COMPASS[round(deg / 22.5) % 16]


def score_style(score: float) -> dict:
    if score >= 75:
        tier = "GO"
    elif score >= 50:
        tier = "KANSRIJK"
    elif score >= 25:
        tier = "TWIJFEL"
    else:
        tier = "NIKS"
    return {"tier": tier, "color": TIER_COLORS[tier]}


def score_pill(score: float) -> str:
    s = score_style(score)
    return (
        f'<span style="background:{s["color"]};color:#ffffff;'
        f'border-radius:6px;padding:3px 10px;font-weight:700;font-size:0.85rem;white-space:nowrap;">'
        f"{score:.0f}</span>"
    )


st.markdown(
    """
    <style>
    .kite-hero {
        background: linear-gradient(120deg, #0f172a 0%, #1e293b 55%, #0f2942 100%);
        color: #f1f5f9; border-radius: 12px; padding: 24px 26px; margin-bottom: 14px;
        border: 1px solid rgba(255,255,255,0.06);
    }
    .kite-hero h1 { margin: 0; font-size: 1.5rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.01em; }
    .kite-hero p { margin: 6px 0 0 0; opacity: 0.82; font-size: 0.92rem; color: #cbd5e1; }
    .kite-kpis { display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
    .kite-kpi {
        background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
        border-radius: 6px; padding: 5px 12px; font-size: 0.78rem; color: #e2e8f0;
        text-transform: uppercase; letter-spacing: 0.04em;
    }

    .section-title {
        font-size: 1.2rem; font-weight: 700; margin: 0 0 2px 0;
        border-left: 4px solid #0f766e; padding-left: 10px;
    }

    .day-card {
        border: 1px solid rgba(128,128,128,0.25); border-radius: 10px; padding: 12px 14px;
        background: var(--secondary-background-color); height: 100%;
    }
    .spot-tag {
        font-size: 0.65rem; color: #64748b; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.04em; margin-left: 6px;
    }
    .day-strip { display: flex; gap: 4px; overflow-x: auto; -webkit-overflow-scrolling: touch; padding-bottom: 6px; }
    .day-col { text-align: center; padding: 6px 6px; flex: 0 0 auto; min-width: 84px; }
    .day-label { font-size: 0.68rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; }
    .day-meta { font-size: 0.7rem; color: #64748b; margin-top: 4px; }

    .top-card {
        border-radius: 10px; padding: 14px; text-align: center; height: 100%;
        background: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.25);
        border-top: 4px solid var(--accent-color, #0f766e);
    }
    .top-card .rank { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; color: #94a3b8; text-transform: uppercase; }
    .top-card .spotname { font-weight: 700; font-size: 1rem; margin: 6px 0 2px 0; }
    .top-card .bigscore { font-size: 2.1rem; font-weight: 800; }
    .top-card .tierlabel { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 4px; }
    .top-card .meta { font-size: 0.78rem; color: #64748b; }

    .hero-stat {
        border-radius: 10px; padding: 16px 18px; margin-bottom: 8px;
        background: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.25);
        border-left: 5px solid var(--accent-color, #0f766e);
    }
    .hero-stat .tierlabel { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
    .hero-stat .num { font-size: 2.4rem; font-weight: 800; line-height: 1.1; }
    .hero-stat .sub { font-size: 0.82rem; margin-top: 4px; color: #64748b; }

    .day-card { text-align: center; border-top: 3px solid var(--accent-color, #94a3b8); }
    .day-card .dow { font-size: 0.75rem; font-weight: 600; color: #64748b; }
    .day-card .num { font-size: 1.25rem; font-weight: 800; margin: 4px 0 0 0; }
    .day-card .sub { font-size: 0.66rem; color: #94a3b8; }
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
        <h1>Noord-Holland Kitesurf Forecast</h1>
        <p>Eén overzicht voor de komende week, samengesteld uit vier onafhankelijke weermodellen.</p>
        <div class="kite-kpis">
            <div class="kite-kpi">6 spots</div>
            <div class="kite-kpi">4 modellen &middot; ECMWF / GFS / ICON / KNMI</div>
            <div class="kite-kpi">7 dagen vooruit</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

cap_col, info_col = st.columns([0.85, 0.15])
with cap_col:
    st.caption(
        "Muiderberg · Strand Horst · Schellinkhout · IJmuiden · Wijk aan Zee · Zandvoort — "
        "de score is een planningshulp, geen veiligheidsadvies. Check altijd lokale wind, stroming, getij en spotregels zelf."
    )
with info_col:
    with st.popover("Uitleg", use_container_width=True):
        st.markdown(
            f"""
**Hoe wordt de score (0-100) berekend?**

Elk uur krijgt een gewogen score op basis van vijf factoren:

- **Windsnelheid (~40%)** — piek tussen 15-28 knopen. Onder 9 of boven 38 knopen is het onrijdbaar en wordt de score altijd 0.
- **Windrichting (~30%)** — hoe dicht de wind bij de ideale hoek voor die specifieke spot zit (elke waterplas ligt anders gedraaid).
- **Vlagerigheid (~15%)** — hoe veel de vlagen afwijken van de gemiddelde windsnelheid; grillige wind scoort lager.
- **Neerslag (~10%)** — regen trekt de score omlaag.
- **Golfhoogte (~5%, alleen zeespots)** — ruwer water bij IJmuiden, Wijk aan Zee en Zandvoort scoort lager. Voor de meren telt dit niet mee.

**Waarom telt een losse piekuur niet altijd mee?** Één goed uur tussen twee slechte uren is geen sessie. Deze app kijkt daarom naar **aaneengesloten vensters van minimaal {GOOD_WINDOW_MIN_HOURS} uur** boven de gekozen score — alleen die vensters worden als "goed" geteld, overal in de app.

**Statusniveaus:** GO (75+) · KANSRIJK (50-74) · TWIJFEL (25-49) · NIKS (<25)

**Databron:** vier onafhankelijke weermodellen (ECMWF, GFS, ICON, KNMI HARMONIE-AROME) via Open-Meteo — de score gebruikt de mediaan, zodat één afwijkend model de uitkomst niet domineert. Golfdata komt van Open-Meteo Marine. KNMI HARMONIE-AROME dekt doorgaans maar 2-3 dagen vooruit; daarna vullen de overige modellen aan.

Dit is een **planningshulp, geen veiligheidsadvies**. Check altijd zelf lokale wind, stroming, getij en spotregels.
            """
        )

df, model_status = load_all_forecasts()

if df.empty:
    st.error("Geen data ontvangen van Open-Meteo. Probeer het later opnieuw.")
    st.stop()

st.sidebar.header("Filters")
only_daylight = st.sidebar.checkbox("Alleen overdag (07:00-21:00)", value=True)
min_score = st.sidebar.slider(
    "Minimale score voor een 'goed venster'",
    0,
    100,
    75,
    help=f"Alleen aaneengesloten vensters van minimaal {GOOD_WINDOW_MIN_HOURS} uur boven deze score tellen als 'goed'.",
)
st.sidebar.caption(f"Vereist ≥{GOOD_WINDOW_MIN_HOURS} uur op rij boven deze score. GO 75+ · KANSRIJK 50-74 · TWIJFEL 25-49 · NIKS <25")

view = df.copy()
if only_daylight:
    view = view[(view["time"].dt.hour >= 7) & (view["time"].dt.hour <= 21)]

unique_days = sorted(view["time"].dt.date.unique())

# ---------------------------------------------------------------------------
# Compute good windows (>= GOOD_WINDOW_MIN_HOURS consecutive hours >= min_score) per spot, once.
# ---------------------------------------------------------------------------
windows_by_spot = {}
all_windows = []
for spot in SPOTS:
    spot_df = view[view["spot_id"] == spot.id]
    w = compute_good_windows(spot_df, threshold=min_score, min_hours=GOOD_WINDOW_MIN_HOURS)
    windows_by_spot[spot.id] = w
    if not w.empty:
        w = w.copy()
        w["spot"] = spot.name
        w["spot_id"] = spot.id
        all_windows.append(w)

all_windows_df = pd.concat(all_windows, ignore_index=True) if all_windows else pd.DataFrame()

# ---------------------------------------------------------------------------
# 1. Beste sessies
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">Beste sessies</div>', unsafe_allow_html=True)
st.caption(f"Vensters van minimaal {GOOD_WINDOW_MIN_HOURS} aaneengesloten uren boven score {min_score}, gerangschikt op piekscore.")

if all_windows_df.empty:
    st.info(
        f"Geen vensters van {GOOD_WINDOW_MIN_HOURS}+ uur boven score {min_score} gevonden. "
        "Verlaag de slider in de zijbalk om minder strikte sessies te zien."
    )
else:
    ranked = all_windows_df.sort_values("peak_score", ascending=False).reset_index(drop=True)
    top3 = ranked.head(3)
    ranks = ["#1", "#2", "#3"]
    cols = st.columns(len(top3))
    for col, (_, row), rank in zip(cols, top3.iterrows(), ranks):
        s = score_style(row["peak_score"])
        with col:
            st.markdown(
                f"""
                <div class="top-card" style="--accent-color:{s['color']};">
                    <div class="rank">{rank}</div>
                    <div class="spotname">{row['spot']}</div>
                    <div class="tierlabel" style="color:{s['color']};">{s['tier']}</div>
                    <div class="bigscore">{row['peak_score']:.0f}</div>
                    <div class="meta">{fmt_day(row['start'].date())} &middot; {fmt_range(row['start'], row['end'])}</div>
                    <div class="meta">{row['wind_kn']:.0f} kn &middot; {compass(row['dir_deg'])} &middot; {row['hours']:.0f}u</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.write("")
    with st.expander(f"Alle {len(ranked)} goede vensters (tabel)", expanded=False):
        table = ranked.copy()
        table["dag"] = table["start"].apply(lambda t: fmt_day(t.date()))
        table["venster"] = table.apply(lambda r: fmt_range(r["start"], r["end"]), axis=1)
        table["richting"] = table["dir_deg"].apply(compass)
        st.dataframe(
            table[["dag", "spot", "venster", "hours", "peak_score", "avg_score", "wind_kn", "richting"]],
            column_config={
                "dag": "Dag",
                "spot": "Spot",
                "venster": "Venster",
                "hours": st.column_config.NumberColumn("Duur (u)", format="%d"),
                "peak_score": st.column_config.ProgressColumn("Piekscore", min_value=0, max_value=100, format="%.0f"),
                "avg_score": st.column_config.NumberColumn("Gem. score", format="%.0f"),
                "wind_kn": st.column_config.NumberColumn("Wind (kn)", format="%.0f"),
                "richting": "Richting",
            },
            hide_index=True,
            use_container_width=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# 2. Alle spots, komende dagen (grid overview, exact dates)
# ---------------------------------------------------------------------------
grid_days = unique_days
st.markdown(f'<div class="section-title">Alle spots — komende {len(grid_days)} dagen</div>', unsafe_allow_html=True)
st.caption(
    f"Beste {GOOD_WINDOW_MIN_HOURS}+ uur venster per dag, per spot. 0 betekent: geen aaneengesloten venster van "
    f"{GOOD_WINDOW_MIN_HOURS}+ uur boven score {min_score} die dag. Swipe zijwaarts voor meer dagen, of klik "
    "'Bekijk' voor het volledige overzicht van een spot."
)


def _select_spot(spot_name: str) -> None:
    st.session_state["spot_selector"] = spot_name
    st.session_state["scroll_to_spot"] = True


for spot in SPOTS:
    windows = windows_by_spot[spot.id]
    with st.container(border=True):
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
            f'<span style="font-weight:700;font-size:1rem;">{spot.name}</span>'
            f'<span class="spot-tag">{WATER_LABEL[spot.is_coastal]} &middot; {spot.water_body}</span></div>',
            unsafe_allow_html=True,
        )
        strip_html = '<div class="day-strip">'
        for d in grid_days:
            day_windows = windows[windows["start"].dt.date == d] if not windows.empty else windows
            if windows.empty or day_windows.empty:
                strip_html += (
                    f'<div class="day-col"><div class="day-label">{fmt_day(d)}</div>'
                    f'<div style="margin-top:6px;">{score_pill(0)}</div>'
                    f'<div class="day-meta">geen {GOOD_WINDOW_MIN_HOURS}u+</div></div>'
                )
                continue
            best = day_windows.loc[day_windows["peak_score"].idxmax()]
            strip_html += (
                f'<div class="day-col"><div class="day-label">{fmt_day(d)}</div>'
                f'<div style="margin-top:6px;">{score_pill(best["peak_score"])}</div>'
                f'<div class="day-meta">{fmt_range(best["start"], best["end"])}<br>{best["wind_kn"]:.0f}kn {compass(best["dir_deg"])}</div>'
                f"</div>"
            )
        strip_html += "</div>"
        st.markdown(strip_html, unsafe_allow_html=True)
        st.button(
            f"Bekijk {spot.name} →",
            key=f"open_{spot.id}",
            use_container_width=True,
            on_click=_select_spot,
            args=(spot.name,),
        )

st.divider()

# ---------------------------------------------------------------------------
# 3. Per spot detail
# ---------------------------------------------------------------------------
st.markdown('<div id="per-spot-section"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Per spot</div>', unsafe_allow_html=True)
st.write("")

if st.session_state.get("scroll_to_spot"):
    st.session_state["scroll_to_spot"] = False
    components.html(
        "<script>setTimeout(() => { const el = window.parent.document.getElementById('per-spot-section'); "
        "if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'}); }, 100);</script>",
        height=0,
    )

spot_name_options = [s.name for s in SPOTS]
st.session_state.setdefault("spot_selector", spot_name_options[0])
chosen_name = st.segmented_control("Kies een spot", spot_name_options, key="spot_selector")
spot = SPOTS_BY_NAME.get(chosen_name, SPOTS[0])

spot_df = view[view["spot_id"] == spot.id].sort_values("time")
if spot_df.empty:
    st.info("Geen uren binnen het geselecteerde filter.")
else:
    windows = windows_by_spot[spot.id]

    hero_col, metrics_col = st.columns([0.4, 0.6])
    with hero_col:
        if windows.empty:
            st.markdown(
                f"""
                <div class="hero-stat" style="--accent-color:{TIER_COLORS['NIKS']};">
                    <div class="tierlabel" style="color:{TIER_COLORS['NIKS']};">NIKS</div>
                    <div class="num">–</div>
                    <div class="sub">Geen venster van {GOOD_WINDOW_MIN_HOURS}+ uur boven score {min_score} deze week.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            best = windows.loc[windows["peak_score"].idxmax()]
            s = score_style(best["peak_score"])
            st.markdown(
                f"""
                <div class="hero-stat" style="--accent-color:{s['color']};">
                    <div class="tierlabel" style="color:{s['color']};">{s['tier']}</div>
                    <div class="num">{best['peak_score']:.0f}</div>
                    <div class="sub">{fmt_day(best['start'].date())} &middot; {fmt_range(best['start'], best['end'])}</div>
                    <div class="sub">{best['wind_kn']:.0f} kn &middot; {compass(best['dir_deg'])} &middot; {best['hours']:.0f}u aaneengesloten</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with metrics_col:
        c1, c2 = st.columns(2)
        c1.metric(f"Goede vensters (≥{GOOD_WINDOW_MIN_HOURS}u)", len(windows))
        good_hours = int(windows["hours"].sum()) if not windows.empty else 0
        c2.metric("Totaal goede uren", good_hours, "deze week")

    metric_choice = st.segmented_control("Toon op de grafiek", list(METRIC_OPTIONS.keys()), default="Score", key=f"metric_{spot.id}")
    metric_col, metric_title = METRIC_OPTIONS.get(metric_choice, METRIC_OPTIONS["Score"])

    chart_df = spot_df[["time", metric_col]].rename(columns={metric_col: "value"})
    base = alt.Chart(chart_df).encode(
        x=alt.X("time:T", title=None, axis=alt.Axis(format="%a %d/%m %Hu", labelAngle=-40)),
    )
    area = base.mark_area(opacity=0.18, color="#0f766e").encode(y=alt.Y("value:Q", title=metric_title))
    line = base.mark_line(color="#0f766e", strokeWidth=2).encode(y=alt.Y("value:Q", title=metric_title))
    layers = [area, line]
    if not windows.empty:
        band_df = windows.rename(columns={"start": "start", "end": "end"})
        band = alt.Chart(band_df).mark_rect(color="#0f766e", opacity=0.15).encode(x="start:T", x2="end:T")
        layers = [band] + layers
    st.altair_chart(alt.layer(*layers).properties(height=260), use_container_width=True)
    st.caption("Gemarkeerde band = aaneengesloten goed venster.")

    st.markdown("**Dagoverzicht**")
    day_cols = st.columns(len(unique_days))
    for col, d in zip(day_cols, unique_days):
        day_windows = windows[windows["start"].dt.date == d] if not windows.empty else windows
        with col:
            if windows.empty or day_windows.empty:
                st.markdown(
                    f"""
                    <div class="day-card" style="--accent-color:{TIER_COLORS['NIKS']};">
                        <div class="dow">{fmt_day(d)}</div>
                        <div class="num">0</div>
                        <div class="sub">geen venster</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                best_day = day_windows.loc[day_windows["peak_score"].idxmax()]
                s = score_style(best_day["peak_score"])
                st.markdown(
                    f"""
                    <div class="day-card" style="--accent-color:{s['color']};">
                        <div class="dow">{fmt_day(d)}</div>
                        <div class="num">{best_day['peak_score']:.0f}</div>
                        <div class="sub">{fmt_range(best_day['start'], best_day['end'])}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    if not windows.empty:
        with st.expander("Goede vensters deze week", expanded=False):
            table = windows.copy()
            table["dag"] = table["start"].apply(lambda t: fmt_day(t.date()))
            table["venster"] = table.apply(lambda r: fmt_range(r["start"], r["end"]), axis=1)
            table["richting"] = table["dir_deg"].apply(compass)
            st.dataframe(
                table[["dag", "venster", "hours", "peak_score", "avg_score", "wind_kn", "richting"]],
                column_config={
                    "dag": "Dag",
                    "venster": "Venster",
                    "hours": st.column_config.NumberColumn("Duur (u)", format="%d"),
                    "peak_score": st.column_config.ProgressColumn("Piekscore", min_value=0, max_value=100, format="%.0f"),
                    "avg_score": st.column_config.NumberColumn("Gem. score", format="%.0f"),
                    "wind_kn": st.column_config.NumberColumn("Wind (kn)", format="%.0f"),
                    "richting": "Richting",
                },
                hide_index=True,
                use_container_width=True,
            )

    with st.expander("Volledige uurdata", expanded=False):
        st.dataframe(
            spot_df[["time", "score", "wind_kn", "gust_kn", "dir_deg", "precip_mm", "wave_m"]],
            column_config={
                "time": st.column_config.DatetimeColumn("Tijd", format="ddd D MMM HH:mm"),
                "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.0f"),
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
