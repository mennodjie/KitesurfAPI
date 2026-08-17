const topSessionsEl = document.getElementById("topSessions");
const spotsGridEl = document.getElementById("spotsGrid");
const statusTextEl = document.getElementById("statusText");
const minScoreEl = document.getElementById("minScore");
const minScoreValueEl = document.getElementById("minScoreValue");
const sessionTemplate = document.getElementById("sessionTemplate");
const installBtn = document.getElementById("installBtn");

let deferredPrompt = null;
let allHours = [];

function formatDate(iso) {
  return new Date(iso).toLocaleString([], {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    day: "numeric",
  });
}

function scoreTier(score) {
  if (score >= 75) {
    return "GO";
  }
  if (score >= 50) {
    return "PROMISING";
  }
  if (score >= 25) {
    return "MARGINAL";
  }
  return "SKIP";
}

function renderTopSessions() {
  const minScore = Number(minScoreEl.value);
  minScoreValueEl.textContent = String(minScore);

  const ranked = allHours
    .filter((h) => h.score >= minScore)
    .sort((a, b) => b.score - a.score)
    .slice(0, 6);

  topSessionsEl.replaceChildren();

  if (!ranked.length) {
    const empty = document.createElement("p");
    empty.textContent = "No matching sessions at this threshold yet.";
    topSessionsEl.appendChild(empty);
    return;
  }

  ranked.forEach((row, i) => {
    const node = sessionTemplate.content.firstElementChild.cloneNode(true);
    node.querySelector(".session-rank").textContent = `#${i + 1} ${scoreTier(row.score)}`;
    node.querySelector(".session-spot").textContent = row.name;
    node.querySelector(".session-meta").textContent = `${formatDate(row.time)} | ${Math.round(
      row.wind_speed_kn
    )} kn`;
    node.querySelector(".session-score").textContent = `Score ${Math.round(row.score)}`;
    topSessionsEl.appendChild(node);
  });
}

function renderSpots(spots) {
  spotsGridEl.replaceChildren();

  spots.forEach((spot) => {
    const spotHours = allHours.filter((h) => h.spot_id === spot.id);
    const best = spotHours.sort((a, b) => b.score - a.score)[0];

    const card = document.createElement("article");
    card.className = "spot-card";
    card.innerHTML = `
      <h3>${spot.name}</h3>
      <p>${spot.water_body}</p>
      <p>${best ? `Best score ${Math.round(best.score)} at ${formatDate(best.time)}` : "No forecast data"}</p>
    `;
    spotsGridEl.appendChild(card);
  });
}

async function loadForecast() {
  statusTextEl.textContent = "Loading spots...";
  const spotsRes = await fetch("/spots");
  const spots = await spotsRes.json();

  statusTextEl.textContent = "Loading forecasts...";
  const forecasts = await Promise.all(
    spots.map(async (spot) => {
      const res = await fetch(`/forecast/${spot.id}`);
      return res.json();
    })
  );

  allHours = forecasts.flatMap((fc) =>
    fc.hours.map((h) => ({
      ...h,
      spot_id: fc.spot_id,
      name: fc.name,
    }))
  );

  renderTopSessions();
  renderSpots(spots);
  statusTextEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

minScoreEl.addEventListener("input", renderTopSessions);

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
    navigator.serviceWorker.register("/service-worker.js").catch(() => undefined);
  });
}

loadForecast().catch((err) => {
  console.error(err);
  statusTextEl.textContent = "Could not load forecast data.";
});
