const topSessionsEl = document.getElementById("topSessions");
const spotsGridEl = document.getElementById("spotsGrid");
const statusTextEl = document.getElementById("statusText");
const minScoreEl = document.getElementById("minScore");
const minScoreValueEl = document.getElementById("minScoreValue");
const riderWeightEl = document.getElementById("riderWeight");
const minHoursEl = document.getElementById("minHours");
const minHoursValueEl = document.getElementById("minHoursValue");
const dayFilterEl = document.getElementById("dayFilter");
const sessionTemplate = document.getElementById("sessionTemplate");
const installBtn = document.getElementById("installBtn");

const overviewViewEl = document.getElementById("overviewView");
const spotDetailViewEl = document.getElementById("spotDetailView");
const backBtn = document.getElementById("backBtn");
const detailNameEl = document.getElementById("detailName");
const detailWaterBodyEl = document.getElementById("detailWaterBody");
const detailModelStatusEl = document.getElementById("detailModelStatus");
const detailWindowsEl = document.getElementById("detailWindows");
const detailHoursTableBody = document.querySelector("#detailHoursTable tbody");
const detailObservationEl = document.getElementById("detailObservation");
const detailTidesEl = document.getElementById("detailTides");
const detailAccuracyEl = document.getElementById("detailAccuracy");

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
  const minHours = Number(minHoursEl.value) || 3;
  const results = await Promise.all(
    spotsMeta.map((spot) => {
      const params = new URLSearchParams({
        rider_weight_kg: riderWeightKg,
        min_score: minScore,
        min_hours: minHours,
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
    renderCurrentView();
  });
  return btn;
}

function renderTopSessions() {
  minScoreValueEl.textContent = minScoreEl.value;

  const allWindows = [];
  Object.values(spotDetails).forEach((detail) => {
    detail.windows.forEach((w) => allWindows.push({ ...w, spot_id: detail.spot_id, name: detail.name }));
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
    node.classList.add("clickable");
    node.addEventListener("click", () => {
      location.hash = `#/spot/${w.spot_id}`;
    });
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
    card.className = "spot-card clickable";
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
    card.addEventListener("click", () => {
      location.hash = `#/spot/${spot.id}`;
    });
    spotsGridEl.appendChild(card);
  });
}

function renderSpotDetail(spotId) {
  const detail = spotDetails[spotId];
  if (!detail) {
    location.hash = "";
    return;
  }

  detailNameEl.textContent = detail.name;
  detailWaterBodyEl.textContent = detail.water_body;
  detailModelStatusEl.textContent = Object.entries(detail.model_status)
    .map(([model, up]) => `${up ? "✓" : "✕"} ${model}`)
    .join("  ");

  const windows = detail.windows
    .filter((w) => !selectedDay || w.start.slice(0, 10) === selectedDay)
    .sort((a, b) => new Date(a.start) - new Date(b.start));

  detailWindowsEl.replaceChildren();
  if (!windows.length) {
    const empty = document.createElement("p");
    empty.className = "controls-hint";
    empty.textContent = "No good windows at this threshold yet.";
    detailWindowsEl.appendChild(empty);
  } else {
    windows.forEach((w) => {
      const row = document.createElement("article");
      row.className = "session-card";
      row.innerHTML = `
        <p class="session-rank">${scoreTier(w.peak_score)}</p>
        <p class="session-meta">${formatRange(w.start, w.end)} · ${Math.round(w.wind_kn)} kn ${dirLabel(w.dir_deg)} · ${w.hours}h</p>
        <p class="session-score">Peak ${Math.round(w.peak_score)} · Avg ${Math.round(w.avg_score)}</p>
        <p class="session-extra">${confidenceLabel(w.confidence)}${w.kite_m ? ` · Kite ${w.kite_m}m` : ""}</p>
      `;
      detailWindowsEl.appendChild(row);
    });
  }

  const dayHours = detail.hours.filter((h) => !selectedDay || h.time.slice(0, 10) === selectedDay);
  detailHoursTableBody.replaceChildren();
  dayHours.forEach((h) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatTime(h.time)}</td>
      <td>${Math.round(h.score)}</td>
      <td>${h.wind_speed_kn ?? "–"} kn ${dirLabel(h.wind_direction_deg)}</td>
      <td>${h.wind_gust_kn ?? "–"} kn</td>
      <td>${confidenceLabel(h.confidence)}</td>
      <td>${h.kite_m ? `${h.kite_m}m` : "–"}</td>
    `;
    detailHoursTableBody.appendChild(tr);
  });

  if (detail.observation) {
    const obs = detail.observation;
    detailObservationEl.textContent =
      `${obs.wind_kn ?? "–"} kn ${dirLabel(obs.dir_deg)}, gusts ${obs.gust_kn ?? "–"} kn · ${obs.station_name} (${obs.distance_km} km away)`;
  } else {
    detailObservationEl.textContent = "No nearby live station.";
  }

  detailTidesEl.replaceChildren();
  if (detail.tide_events && detail.tide_events.length) {
    detail.tide_events.forEach((e) => {
      const li = document.createElement("li");
      const trend = e.kind === "high" ? "↑" : "↓";
      li.textContent = `${trend} ${e.kind === "high" ? "High" : "Low"} tide ${formatTime(e.time)} (${Math.round(e.height_cm)} cm)`;
      detailTidesEl.appendChild(li);
    });
  } else {
    const li = document.createElement("li");
    li.textContent = detail.is_coastal ? "No tide data available." : "Not tidal water.";
    detailTidesEl.appendChild(li);
  }

  const acc = accuracyBySpot[spotId];
  detailAccuracyEl.textContent = acc
    ? `Mean wind error ${acc.mean_wind_error_kn} kn, mean direction error ${acc.mean_dir_error_deg}° (${acc.samples} samples)`
    : "Not enough samples yet.";
}

function renderCurrentView() {
  const spotId = currentSpotIdFromHash();
  if (spotId) {
    overviewViewEl.hidden = true;
    spotDetailViewEl.hidden = false;
    renderSpotDetail(spotId);
  } else {
    overviewViewEl.hidden = false;
    spotDetailViewEl.hidden = true;
    renderTopSessions();
    renderSpots();
  }
}

function currentSpotIdFromHash() {
  const match = location.hash.match(/^#\/spot\/(.+)$/);
  return match ? match[1] : null;
}

async function loadAll() {
  statusTextEl.textContent = "Loading spots...";
  spotsMeta = await fetchJson("/spots");

  statusTextEl.textContent = "Loading forecasts...";
  await Promise.all([refreshDetails(), loadAccuracy()]);

  renderDayFilter();
  renderCurrentView();
  statusTextEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

const triggerRefresh = debounce(async () => {
  statusTextEl.textContent = "Updating...";
  await refreshDetails();
  renderDayFilter();
  renderCurrentView();
  statusTextEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
}, 400);

minScoreEl.addEventListener("input", () => {
  minScoreValueEl.textContent = minScoreEl.value;
  triggerRefresh();
});
riderWeightEl.addEventListener("input", triggerRefresh);
minHoursEl.addEventListener("input", () => {
  minHoursValueEl.textContent = `${minHoursEl.value}h`;
  triggerRefresh();
});

backBtn.addEventListener("click", () => {
  location.hash = "";
});
window.addEventListener("hashchange", renderCurrentView);

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
