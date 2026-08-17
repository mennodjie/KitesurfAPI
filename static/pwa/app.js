const topSessionsEl = document.getElementById("topSessions");
const spotsGridEl = document.getElementById("spotsGrid");
const statusTextEl = document.getElementById("statusText");
const minScoreEl = document.getElementById("minScore");
const minScoreValueEl = document.getElementById("minScoreValue");
const riderWeightEl = document.getElementById("riderWeight");
const dayFilterEl = document.getElementById("dayFilter");
const sessionTemplate = document.getElementById("sessionTemplate");
const installBtn = document.getElementById("installBtn");

let deferredPrompt = null;
let spotsMeta = [];
let spotDetails = {};
let accuracyBySpot = {};
let selectedDay = null; // "YYYY-MM-DD", or null for "All"

// Mirrors kitesurf's compass()/wind_arrow()/dir_label() -- degrees are
// meteorological "from", the arrow points where the wind blows TOWARD
// (the intuitive way to read it at a glance).
const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
const WIND_ARROWS = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"];
const CONFIDENCE_DOTS = { High: "●●●", Medium: "●●○", Low: "●○○", Unknown: "—" };

function compass(deg) {
  if (deg === null || deg === undefined) return "–";
  return COMPASS[Math.round(deg / 22.5) % 16];
}

function windArrow(deg) {
  if (deg === null || deg === undefined) return "";
  return WIND_ARROWS[Math.round(((deg + 180) % 360) / 45) % 8];
}

function dirLabel(deg) {
  if (deg === null || deg === undefined) return "–";
  return `${windArrow(deg)} ${compass(deg)}`;
}

function confidenceLabel(confidence) {
  return `${CONFIDENCE_DOTS[confidence] || "—"} ${confidence || "Unknown"}`;
}

function scoreTier(score) {
  if (score >= 75) return "GO";
  if (score >= 50) return "PROMISING";
  if (score >= 25) return "MARGINAL";
  return "SKIP";
}

function formatTime(iso) {
  return new Date(iso).toLocaleString([], {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRange(startIso, endIso) {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const dateOpts = { weekday: "short", day: "numeric", month: "short" };
  const timeOpts = { hour: "2-digit", minute: "2-digit" };
  if (start.toDateString() === end.toDateString()) {
    return `${start.toLocaleDateString([], dateOpts)} ${start.toLocaleTimeString([], timeOpts)}–${end.toLocaleTimeString([], timeOpts)}`;
  }
  return `${start.toLocaleDateString([], dateOpts)} ${start.toLocaleTimeString([], timeOpts)} – ${end.toLocaleDateString([], dateOpts)} ${end.toLocaleTimeString([], timeOpts)}`;
}

function formatDayLabel(dayIso) {
  const d = new Date(`${dayIso}T00:00:00`);
  return d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
}

function debounce(fn, waitMs) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), waitMs);
  };
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json();
}

async function loadAccuracy() {
  try {
    const rows = await fetchJson("/accuracy");
    accuracyBySpot = {};
    rows.forEach((r) => {
      accuracyBySpot[r.spot_id] = r;
    });
  } catch (err) {
    accuracyBySpot = {};
  }
}

async function refreshDetails() {
  const riderWeightKg = Number(riderWeightEl.value) || 73;
  const minScore = Number(minScoreEl.value);
  const results = await Promise.all(
    spotsMeta.map((spot) => {
      const params = new URLSearchParams({
        rider_weight_kg: riderWeightKg,
        min_score: minScore,
        min_hours: 3,
      });
      return fetchJson(`/spot-detail/${spot.id}?${params}`);
    })
  );
  spotDetails = {};
  results.forEach((detail) => {
    spotDetails[detail.spot_id] = detail;
  });
}

function renderDayFilter() {
  const days = new Set();
  Object.values(spotDetails).forEach((detail) => {
    detail.hours.forEach((h) => days.add(h.time.slice(0, 10)));
  });
  const sortedDays = Array.from(days).sort();

  dayFilterEl.replaceChildren();
  dayFilterEl.appendChild(makeDayPill("All days", null));
  sortedDays.forEach((iso) => dayFilterEl.appendChild(makeDayPill(formatDayLabel(iso), iso)));
}

function makeDayPill(label, value) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "day-pill" + (selectedDay === value ? " active" : "");
  btn.textContent = label;
  btn.addEventListener("click", () => {
    selectedDay = value;
    renderDayFilter();
    renderAll();
  });
  return btn;
}

function renderTopSessions() {
  minScoreValueEl.textContent = minScoreEl.value;

  const allWindows = [];
  Object.values(spotDetails).forEach((detail) => {
    detail.windows.forEach((w) => allWindows.push({ ...w, name: detail.name }));
  });

  const ranked = allWindows
    .filter((w) => !selectedDay || w.start.slice(0, 10) === selectedDay)
    .sort((a, b) => b.peak_score - a.peak_score)
    .slice(0, 6);

  topSessionsEl.replaceChildren();

  if (!ranked.length) {
    const empty = document.createElement("p");
    empty.textContent = "No matching sessions at this threshold yet.";
    topSessionsEl.appendChild(empty);
    return;
  }

  ranked.forEach((w, i) => {
    const node = sessionTemplate.content.firstElementChild.cloneNode(true);
    node.querySelector(".session-rank").textContent = `#${i + 1} ${scoreTier(w.peak_score)}`;
    node.querySelector(".session-spot").textContent = w.name;
    node.querySelector(".session-meta").textContent =
      `${formatRange(w.start, w.end)} · ${Math.round(w.wind_kn)} kn ${dirLabel(w.dir_deg)} · ${w.hours}h`;
    node.querySelector(".session-score").textContent = `Score ${Math.round(w.peak_score)}`;
    node.querySelector(".session-extra").textContent =
      `${confidenceLabel(w.confidence)}${w.kite_m ? ` · Kite ${w.kite_m}m` : ""}`;
    topSessionsEl.appendChild(node);
  });
}

function renderSpots() {
  spotsGridEl.replaceChildren();

  spotsMeta.forEach((spot) => {
    const detail = spotDetails[spot.id];
    if (!detail) return;

    const dayHours = detail.hours.filter((h) => !selectedDay || h.time.slice(0, 10) === selectedDay);
    const best = dayHours.slice().sort((a, b) => b.score - a.score)[0];

    const modelStatus = Object.entries(detail.model_status)
      .map(([model, up]) => `${up ? "✓" : "✕"} ${model}`)
      .join("  ");

    let obsHtml = "";
    if (detail.observation) {
      const obs = detail.observation;
      obsHtml = `<p class="spot-obs">Live: ${obs.wind_kn ?? "–"} kn ${dirLabel(obs.dir_deg)} · ${obs.station_name} (${obs.distance_km} km away)</p>`;
    }

    let tideHtml = "";
    if (detail.tide_events && detail.tide_events.length) {
      const next = detail.tide_events[0];
      const trend = next.kind === "high" ? "↑" : "↓";
      tideHtml = `<p class="spot-tide">${trend} Next ${next.kind} tide ${formatTime(next.time)}</p>`;
    }

    let accuracyHtml = "";
    const acc = accuracyBySpot[spot.id];
    if (acc) {
      accuracyHtml = `<p class="spot-accuracy">Nowcast avg error: ${acc.mean_wind_error_kn} kn (${acc.samples} samples)</p>`;
    }

    const card = document.createElement("article");
    card.className = "spot-card";
    card.innerHTML = `
      <h3>${spot.name}</h3>
      <p>${spot.water_body}</p>
      <p class="spot-models">${modelStatus}</p>
      <p>${
        best
          ? `Best score ${Math.round(best.score)} · ${dirLabel(best.wind_direction_deg)} at ${formatTime(best.time)}${
              best.kite_m ? ` · Kite ${best.kite_m}m` : ""
            }`
          : "No forecast data for this day"
      }</p>
      ${obsHtml}
      ${tideHtml}
      ${accuracyHtml}
    `;
    spotsGridEl.appendChild(card);
  });
}

function renderAll() {
  renderTopSessions();
  renderSpots();
}

async function loadAll() {
  statusTextEl.textContent = "Loading spots...";
  spotsMeta = await fetchJson("/spots");

  statusTextEl.textContent = "Loading forecasts...";
  await Promise.all([refreshDetails(), loadAccuracy()]);

  renderDayFilter();
  renderAll();
  statusTextEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

const triggerRefresh = debounce(async () => {
  statusTextEl.textContent = "Updating...";
  await refreshDetails();
  renderDayFilter();
  renderAll();
  statusTextEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
}, 400);

minScoreEl.addEventListener("input", () => {
  minScoreValueEl.textContent = minScoreEl.value;
  triggerRefresh();
});
riderWeightEl.addEventListener("input", triggerRefresh);

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredPrompt = event;
  installBtn.hidden = false;
});

installBtn.addEventListener("click", async () => {
  if (!deferredPrompt) {
    return;
  }
  deferredPrompt.prompt();
  await deferredPrompt.userChoice;
  deferredPrompt = null;
  installBtn.hidden = true;
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}

loadAll().catch((err) => {
  console.error(err);
  statusTextEl.textContent = "Could not load forecast data.";
});
