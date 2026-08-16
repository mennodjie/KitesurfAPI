"""Phone-facing UI. Run with: streamlit run streamlit_app.py

Deploy for free on Streamlit Community Cloud, then on Android open the URL
in Chrome and use "Add to Home Screen" for an app-like icon.
"""

import asyncio
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from kitesurf.accuracy import MIN_SAMPLES_FOR_SUMMARY, load_log, summarize
from kitesurf.observations import get_observations
from kitesurf.scoring import gust_ratio, model_confidence, score_hour
from kitesurf.spots import SPOTS, SPOTS_BY_ID
from kitesurf.tides import TIDE_STATION_NAME, get_tide_events
from kitesurf.weather import CACHE_TTL_SECONDS, get_forecasts
from kitesurf.windows import compute_good_windows

SPOTS_BY_NAME = {s.name: s for s in SPOTS}
ICON_PATH = Path(__file__).parent / "assets" / "icon.png"

st.set_page_config(page_title="KiteScout", page_icon=str(ICON_PATH), layout="wide")

# Reload the tab once the forecast cache would expire anyway, so an open tab
# picks up fresh data without the user having to refresh manually.
st.html(
    f"<script>setTimeout(() => window.location.reload(), {CACHE_TTL_SECONDS * 1000});</script>",
    unsafe_allow_javascript=True,
)

# Best-effort PWA metadata for Android "Add to Home Screen" / TWA packaging tools
# (e.g. PWABuilder). Streamlit doesn't expose its <head>, so this isn't guaranteed
# to be picked up by every tool -- but it's harmless, and the manifest/icons are
# genuinely served (enableStaticServing in .streamlit/config.toml) at these URLs
# regardless, so they can be entered manually wherever a tool needs them pasted in.
st.html(
    """
    <link rel="manifest" href="/app/static/manifest.json">
    <meta name="theme-color" content="#0f172a">
    <link rel="apple-touch-icon" href="/app/static/icon-192.png">
    """,
)

COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
WATER_LABEL = {True: "Sea", False: "Inland water"}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DEFAULT_GOOD_WINDOW_MIN_HOURS = 3
METRIC_OPTIONS = {
    "Score": ("score", "Score (0-100)"),
    "Wind": ("wind_kn", "Wind (kn)"),
    "Gust ratio": ("gust_ratio", "Gust / wind ratio"),
    "Rain": ("precip_mm", "Rain (mm)"),
}

# Muted, solid status colors (white text) -- reads consistently in both light and dark mode
# since each chip carries its own fixed background rather than relying on the page theme.
TIER_COLORS = {
    "GO": "#0f766e",
    "PROMISING": "#b45309",
    "MARGINAL": "#9a3412",
    "SKIP": "#475569",
}


def fmt_day(d) -> str:
    return f"{WEEKDAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"


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
        tier = "PROMISING"
    elif score >= 25:
        tier = "MARGINAL"
    else:
        tier = "SKIP"
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
    .block-container { padding-top: 1.4rem; padding-bottom: 1.5rem; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 0.3rem 0.1rem; }
    hr { margin: 0.35rem 0 !important; }
    div[data-testid="stMarkdownContainer"] p { margin-bottom: 0.2rem; }

    .kite-hero {
        background: linear-gradient(120deg, #0f172a 0%, #1e293b 55%, #0f2942 100%);
        color: #f1f5f9; border-radius: 10px; padding: 10px 16px; margin-bottom: 8px;
        border: 1px solid rgba(255,255,255,0.06);
        display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px;
    }
    .kite-hero h1 { margin: 0; font-size: 1.05rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.01em; }
    .kite-hero .kite-kpis { font-size: 0.72rem; color: #94a3b8; }

    .section-title {
        font-size: 1rem; font-weight: 700; margin: 4px 0 0 0;
        border-left: 3px solid #0f766e; padding-left: 8px;
    }

    .day-card {
        border: 1px solid rgba(128,128,128,0.25); border-radius: 8px; padding: 6px 6px;
        background: var(--secondary-background-color); height: 100%;
        flex: 0 0 92px; min-width: 92px;
    }
    .spot-tag {
        font-size: 0.62rem; color: #64748b; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.04em; margin-left: 6px;
    }
    .day-strip { display: flex; gap: 4px; overflow-x: auto; -webkit-overflow-scrolling: touch; padding-bottom: 3px; }
    .day-col { text-align: center; padding: 3px 5px; flex: 0 0 auto; min-width: 74px; }
    .day-label { font-size: 0.62rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; }
    .day-meta { font-size: 0.64rem; color: #64748b; margin-top: 2px; line-height: 1.25; }

    .top-card {
        border-radius: 8px; padding: 8px 10px; text-align: center; height: 100%;
        background: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.25);
        border-top: 3px solid var(--accent-color, #0f766e);
    }
    .top-card .rank { font-size: 0.62rem; font-weight: 700; letter-spacing: 0.06em; color: #94a3b8; text-transform: uppercase; }
    .top-card .spotname { font-weight: 700; font-size: 0.88rem; margin: 2px 0 1px 0; }
    .top-card .bigscore { font-size: 1.5rem; font-weight: 800; line-height: 1.1; }
    .top-card .tierlabel { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 1px; }
    .top-card .meta { font-size: 0.68rem; color: #64748b; line-height: 1.3; }

    .hero-stat {
        border-radius: 8px; padding: 8px 12px; margin-bottom: 4px;
        background: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.25);
        border-left: 4px solid var(--accent-color, #0f766e);
    }
    .hero-stat .tierlabel { font-size: 0.62rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
    .hero-stat .num { font-size: 1.6rem; font-weight: 800; line-height: 1.1; }
    .hero-stat .sub { font-size: 0.72rem; margin-top: 2px; color: #64748b; }

    .day-card { text-align: center; border-top: 2px solid var(--accent-color, #94a3b8); }
    .day-card .dow { font-size: 0.66rem; font-weight: 600; color: #64748b; }
    .day-card .num { font-size: 0.95rem; font-weight: 800; margin: 2px 0 0 0; }
    .day-card .sub { font-size: 0.6rem; color: #94a3b8; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=900, show_spinner="Fetching weather models...")
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
                    "gust_ratio": gust_ratio(h),
                    "dir_deg": h.wind_direction_deg,
                    "precip_mm": h.precipitation_mm,
                    "wave_m": h.wave_height_m,
                    "model_spread_kn": h.wind_speed_spread_kn,
                    "confidence": model_confidence(h.wind_speed_spread_kn),
                }
            )
    # Captured inside the cached function, so it reflects when the data was actually
    # fetched -- not the current render time, which would just always say "now".
    # Naive Amsterdam wall-clock time, matching the (also naive) Open-Meteo timestamps.
    # Streamlit Cloud runs its containers in UTC, so a plain pd.Timestamp.now() would be
    # 1-2 hours off depending on DST.
    fetched_at = pd.Timestamp.now(tz="Europe/Amsterdam").tz_localize(None)
    return pd.DataFrame(rows), model_status, fetched_at


@st.cache_data(ttl=300, show_spinner=False)
def load_live_observations():
    """Actual (not forecast) station readings -- refreshed more often than the forecast."""
    return asyncio.run(get_observations(SPOTS))


@st.cache_data(ttl=1800, show_spinner=False)
def load_tide_events():
    """Shared North Sea tide reference -- changes slowly, cached longer than the forecast."""
    return asyncio.run(get_tide_events())


@st.cache_data(ttl=900, show_spinner=False)
def load_accuracy_summary():
    log_path = Path(__file__).parent / "data" / "accuracy_log.jsonl"
    return summarize(load_log(log_path))


df, model_status, fetched_at = load_all_forecasts()
updated_label = f"Updated {fetched_at.day} {MONTHS[fetched_at.month - 1]} {fetched_at.strftime('%H:%M')}"

hero_col, info_col = st.columns([0.85, 0.15])
with hero_col:
    st.markdown(
        f"""
        <div class="kite-hero">
            <h1>KiteScout</h1>
            <div class="kite-kpis">{len(SPOTS)} spots &middot; 4 models &middot; 7 days &middot; {updated_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with info_col:
    with st.popover("How it works", width="stretch"):
        st.markdown(
            f"""
**How is the score (0-100) calculated?**

Every hour gets a weighted score based on five factors:

- **Wind speed (~40%)** — peaks between 15-28 knots. Below 9 or above 38 knots it's unridable and the score is always 0.
- **Wind direction (~30%)** — how close the wind is to the ideal angle for that specific spot (every stretch of water faces a different way).
- **Gustiness (~15%)** — how much the gusts deviate from the average wind speed; erratic wind scores lower.
- **Rain (~10%)** — rain drags the score down.
- **Wave height (~5%, sea spots only)** — rougher water at the North Sea spots scores lower. Doesn't count for the lakes.

**Why doesn't a single good hour always count?** One good hour between two bad ones isn't a session. This app looks for **consecutive windows** above the chosen score — how long that window needs to be is up to you in the sidebar (default {DEFAULT_GOOD_WINDOW_MIN_HOURS} hours). Only those windows count as "good," everywhere in the app.

**Status levels:** GO (75+) · PROMISING (50-74) · MARGINAL (25-49) · SKIP (<25)

**Data source:** four independent weather models (ECMWF, GFS, ICON, KNMI HARMONIE-AROME) via Open-Meteo — the score uses the median, so one outlier model doesn't dominate the result. Wave data comes from Open-Meteo Marine. KNMI HARMONIE-AROME usually only covers 2-3 days ahead; the other models fill in beyond that.

This is a **planning aid, not safety advice**. Always check local wind, current, tide, and spot rules yourself.
            """
        )

if df.empty:
    st.error("No data received from Open-Meteo. Please try again later.")
    st.stop()

st.sidebar.header("Filters")
only_daylight = st.sidebar.checkbox("Daytime only (07:00-21:00)", value=True)
good_window_min_hours = st.sidebar.slider(
    "Minimum window length (hours)",
    1,
    6,
    DEFAULT_GOOD_WINDOW_MIN_HOURS,
    help="How long the wind must stay consecutively above the score to count as a 'good window'.",
)
min_score = st.sidebar.slider(
    "Minimum score for a 'good window'",
    0,
    100,
    75,
    help=f"Only windows of at least {good_window_min_hours} consecutive hours above this score count as 'good'.",
)
st.sidebar.caption(f"Requires ≥{good_window_min_hours}h in a row above this score. GO 75+ · PROMISING 50-74 · MARGINAL 25-49 · SKIP <25")

view = df.copy()
if only_daylight:
    view = view[(view["time"].dt.hour >= 7) & (view["time"].dt.hour <= 21)]

all_days = sorted(view["time"].dt.date.unique())
ALL_DAYS_LABEL = "All days"
day_options = [ALL_DAYS_LABEL] + [fmt_day(d) for d in all_days]
day_choice = st.segmented_control("Day", day_options, default=ALL_DAYS_LABEL, key="day_filter")
selected_day = None
if day_choice and day_choice != ALL_DAYS_LABEL:
    selected_day = all_days[day_options.index(day_choice) - 1]
    view = view[view["time"].dt.date == selected_day]

unique_days = sorted(view["time"].dt.date.unique())

# ---------------------------------------------------------------------------
# Compute good windows (>= good_window_min_hours consecutive hours >= min_score) per spot, once.
# ---------------------------------------------------------------------------
windows_by_spot = {}
all_windows = []
for spot in SPOTS:
    spot_df = view[view["spot_id"] == spot.id]
    w = compute_good_windows(spot_df, threshold=min_score, min_hours=good_window_min_hours)
    windows_by_spot[spot.id] = w
    if not w.empty:
        w = w.copy()
        w["spot"] = spot.name
        w["spot_id"] = spot.id
        all_windows.append(w)

all_windows_df = pd.concat(all_windows, ignore_index=True) if all_windows else pd.DataFrame()

# ---------------------------------------------------------------------------
# 1. Best sessions
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">Best sessions</div>', unsafe_allow_html=True)

if all_windows_df.empty:
    st.info(
        f"No windows of {good_window_min_hours}+ hours above score {min_score} found. "
        "Lower the slider in the sidebar to see less strict sessions."
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
                    <div class="meta">{row['wind_kn']:.0f} kn &middot; {compass(row['dir_deg'])} &middot; {row['hours']:.0f}h</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander(f"All {len(ranked)} good windows (table)", expanded=False):
        table = ranked.copy()
        table["day"] = table["start"].apply(lambda t: fmt_day(t.date()))
        table["window"] = table.apply(lambda r: fmt_range(r["start"], r["end"]), axis=1)
        table["direction"] = table["dir_deg"].apply(compass)
        st.dataframe(
            table[["day", "spot", "window", "hours", "peak_score", "avg_score", "wind_kn", "direction", "confidence"]],
            column_config={
                "day": "Day",
                "spot": "Spot",
                "window": "Window",
                "hours": st.column_config.NumberColumn("Duration (h)", format="%d"),
                "peak_score": st.column_config.ProgressColumn("Peak score", min_value=0, max_value=100, format="%.0f"),
                "avg_score": st.column_config.NumberColumn("Avg score", format="%.0f"),
                "wind_kn": st.column_config.NumberColumn("Wind (kn)", format="%.0f"),
                "direction": "Direction",
                "confidence": st.column_config.TextColumn("Model agreement", help="How closely the 4 weather models agree at the peak hour."),
            },
            hide_index=True,
            width="stretch",
        )

st.divider()

# ---------------------------------------------------------------------------
# 2. All spots, upcoming days (grid overview, exact dates)
# ---------------------------------------------------------------------------
grid_days = unique_days
grid_title = f"All spots — {fmt_day(selected_day)}" if selected_day else f"All spots — next {len(grid_days)} days"
st.markdown(f'<div class="section-title">{grid_title}</div>', unsafe_allow_html=True)


def _select_spot(spot_name: str) -> None:
    st.session_state["spot_selector"] = spot_name
    st.session_state["scroll_to_spot"] = True


with st.container(horizontal=True, key="spot_grid", gap="medium"):
    for spot in SPOTS:
        windows = windows_by_spot[spot.id]
        with st.container(border=True, width=380):
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
                        f'<div class="day-meta">no {good_window_min_hours}h+</div></div>'
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
                f"View {spot.name} →",
                key=f"open_{spot.id}",
                width="stretch",
                on_click=_select_spot,
                args=(spot.name,),
            )

st.divider()

# ---------------------------------------------------------------------------
# 3. Per spot detail
# ---------------------------------------------------------------------------
st.markdown('<div id="per-spot-section"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Per spot</div>', unsafe_allow_html=True)

if st.session_state.get("scroll_to_spot"):
    st.session_state["scroll_to_spot"] = False
    st.html(
        "<script>setTimeout(() => { const el = document.getElementById('per-spot-section'); "
        "if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'}); }, 100);</script>",
        unsafe_allow_javascript=True,
    )

spot_name_options = [s.name for s in SPOTS]
if st.session_state.get("spot_selector") not in spot_name_options:
    st.session_state["spot_selector"] = spot_name_options[0]
chosen_name = st.segmented_control("Choose a spot", spot_name_options, key="spot_selector")
spot = SPOTS_BY_NAME.get(chosen_name, SPOTS[0])

spot_df = view[view["spot_id"] == spot.id].sort_values("time")
if spot_df.empty:
    st.info("No hours within the selected filter.")
else:
    windows = windows_by_spot[spot.id]

    live_obs = load_live_observations().get(spot.id)
    live_bits = []
    if live_obs is not None:
        live_bits.append(
            f"Live now: {live_obs.wind_kn:.0f} kn, gust {live_obs.gust_kn:.0f} kn, {compass(live_obs.dir_deg)} "
            f"— {live_obs.station_name} ({live_obs.distance_km:.0f} km away)"
        )
    if spot.is_coastal:
        tide_events = [e for e in load_tide_events() if e.time >= pd.Timestamp.now(tz=e.time.tz)]
        next_high = next((e for e in tide_events if e.kind == "high"), None)
        next_low = next((e for e in tide_events if e.kind == "low"), None)
        tide_bits = []
        if next_high is not None:
            tide_bits.append(f"high {next_high.time.strftime('%a %H:%M')}")
        if next_low is not None:
            tide_bits.append(f"low {next_low.time.strftime('%a %H:%M')}")
        if tide_bits:
            live_bits.append(f"Next tide ({TIDE_STATION_NAME}): {' · '.join(tide_bits)}")
    if live_bits:
        st.caption(" · ".join(live_bits))

    hero_col, metrics_col = st.columns([0.4, 0.6])
    with hero_col:
        if windows.empty:
            st.markdown(
                f"""
                <div class="hero-stat" style="--accent-color:{TIER_COLORS['SKIP']};">
                    <div class="tierlabel" style="color:{TIER_COLORS['SKIP']};">SKIP</div>
                    <div class="num">–</div>
                    <div class="sub">No window of {good_window_min_hours}+ hours above score {min_score} this week.</div>
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
                    <div class="sub">{best['wind_kn']:.0f} kn &middot; {compass(best['dir_deg'])} &middot; {best['hours']:.0f}h in a row</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with metrics_col:
        c1, c2 = st.columns(2)
        c1.metric(f"Good windows (≥{good_window_min_hours}h)", len(windows))
        good_hours = int(windows["hours"].sum()) if not windows.empty else 0
        c2.metric("Total good hours", good_hours, "this week")

    metric_choice = st.segmented_control("Show on the chart", list(METRIC_OPTIONS.keys()), default="Score", key=f"metric_{spot.id}")
    metric_col, metric_title = METRIC_OPTIONS.get(metric_choice, METRIC_OPTIONS["Score"])

    chart_df = spot_df[["time", metric_col]].rename(columns={metric_col: "value"})
    base = alt.Chart(chart_df).encode(
        x=alt.X("time:T", title=None, axis=alt.Axis(format="%a %d/%m %Hh", labelAngle=-40)),
    )
    area = base.mark_area(opacity=0.18, color="#0f766e").encode(y=alt.Y("value:Q", title=metric_title))
    line = base.mark_line(color="#0f766e", strokeWidth=2).encode(y=alt.Y("value:Q", title=metric_title))
    layers = [area, line]
    if not windows.empty:
        band_df = windows.rename(columns={"start": "start", "end": "end"})
        band = alt.Chart(band_df).mark_rect(color="#0f766e", opacity=0.15).encode(x="start:T", x2="end:T")
        layers = [band] + layers
    st.altair_chart(alt.layer(*layers).properties(height=190), width="stretch")
    with st.container(horizontal=True, key=f"day_cards_{spot.id}", gap="small"):
        for d in unique_days:
            day_windows = windows[windows["start"].dt.date == d] if not windows.empty else windows
            if windows.empty or day_windows.empty:
                st.markdown(
                    f"""
                    <div class="day-card" style="--accent-color:{TIER_COLORS['SKIP']};">
                        <div class="dow">{fmt_day(d)}</div>
                        <div class="num">0</div>
                        <div class="sub">no window</div>
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
        with st.expander("Good windows this week", expanded=False):
            table = windows.copy()
            table["day"] = table["start"].apply(lambda t: fmt_day(t.date()))
            table["window"] = table.apply(lambda r: fmt_range(r["start"], r["end"]), axis=1)
            table["direction"] = table["dir_deg"].apply(compass)
            st.dataframe(
                table[["day", "window", "hours", "peak_score", "avg_score", "wind_kn", "direction", "confidence"]],
                column_config={
                    "day": "Day",
                    "window": "Window",
                    "hours": st.column_config.NumberColumn("Duration (h)", format="%d"),
                    "peak_score": st.column_config.ProgressColumn("Peak score", min_value=0, max_value=100, format="%.0f"),
                    "avg_score": st.column_config.NumberColumn("Avg score", format="%.0f"),
                    "wind_kn": st.column_config.NumberColumn("Wind (kn)", format="%.0f"),
                    "direction": "Direction",
                    "confidence": st.column_config.TextColumn("Model agreement", help="How closely the 4 weather models agree at the peak hour."),
                },
                hide_index=True,
                width="stretch",
            )

    with st.expander("Full hourly data", expanded=False):
        st.dataframe(
            spot_df[["time", "score", "wind_kn", "gust_kn", "gust_ratio", "dir_deg", "precip_mm", "wave_m", "model_spread_kn", "confidence"]],
            column_config={
                "time": st.column_config.DatetimeColumn("Time", format="ddd D MMM HH:mm"),
                "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.0f"),
                "gust_ratio": st.column_config.NumberColumn("Gust ratio", format="%.2f"),
                "model_spread_kn": st.column_config.NumberColumn("Model spread (kn)", format="%.1f"),
                "confidence": st.column_config.TextColumn("Model agreement"),
            },
            hide_index=True,
            width="stretch",
            height=300,
        )

    with st.expander("Forecast accuracy", expanded=False):
        accuracy = load_accuracy_summary()
        spot_accuracy = accuracy[accuracy["spot_id"] == spot.id]
        if spot_accuracy.empty:
            st.caption(
                f"Not enough logged samples yet for {spot.name} (needs {MIN_SAMPLES_FOR_SUMMARY}+, checked every 3h). "
                "Come back after this has run for a day or two."
            )
        else:
            row = spot_accuracy.iloc[0]
            st.caption(
                f"Based on {int(row['samples'])} logged hours: forecast wind speed has been off by an average of "
                f"{row['mean_wind_error_kn']:.1f} kn, and direction by {row['mean_dir_error_deg']:.0f}° at {spot.name}."
            )

    statuses = model_status.get(spot.id, {})
    ok = [m for m, up in statuses.items() if up]
    down = [m for m, up in statuses.items() if not up]
    status_line = f"Active models: {', '.join(ok) if ok else 'none'}"
    if down:
        status_line += f" · down: {', '.join(down)}"
    st.caption(status_line)
