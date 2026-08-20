"use strict";

let state;
let previousAccepted;

const byId = (id) => document.getElementById(id);
const formatOffset = (value) => `${value >= 0 ? "+" : ""}${value.toFixed(3)}`.replace(".", ",");
const formatTemp = (value) => `${value} °C`;

function addEvent(message) {
  state.events.unshift(message);
  state.events = state.events.slice(0, 6);
}

function setSessionControls(active) {
  document.querySelectorAll("[data-adjust]").forEach((button) => {
    button.disabled = !active;
  });
  byId("save-calibration").disabled = !active;
  byId("cancel-calibration").disabled = !active;
}

function renderReadiness() {
  const card = byId("readiness-card");
  card.classList.toggle("blocked", !state.ready);
  byId("readiness-title").textContent = state.ready ? "Prêt pour un travail qualifié" : "Production bloquée";
  byId("readiness-detail").textContent = state.ready
    ? "Plaque, mesh, correction Z et températures ont un propriétaire connu."
    : state.blockReason;
}

function renderCalibration() {
  const calibration = state.calibration;
  const session = calibration.session;
  const displayedOffset = session ? session.currentOffsetMm : calibration.offsetMm;
  const status = byId("calibration-status");

  byId("offset-value").textContent = displayedOffset == null ? "—" : formatOffset(displayedOffset);
  status.textContent = session ? "Session en cours" : calibration.status === "accepted" ? "Accepté" : "À refaire";
  status.classList.toggle("success", !session && calibration.status === "accepted");
  status.classList.toggle("invalid", calibration.status !== "accepted");
  byId("calibration-context").textContent = session
    ? "Les clics restent provisoires jusqu'au bouton Enregistrer."
    : `${state.plate.label} · ${state.plate.temperatureBandC} °C · ${calibration.nozzle}`;
  byId("seed-offset").value = calibration.provisionalSeedMm;
  setSessionControls(Boolean(session));
  byId("begin-calibration").disabled = Boolean(session);
  byId("restore-calibration").disabled = !previousAccepted;
}

function renderMesh() {
  byId("mesh-mode").textContent = state.mesh.mode === "adaptive" ? "Adaptatif par travail" : "Référence complète";
  byId("plate-label").textContent = state.plate.label;
  byId("bed-target").textContent = formatTemp(state.plate.bedTargetC);
  byId("mesh-profile").textContent = state.mesh.referenceProfile;
  byId("mesh-persistence").textContent = state.mesh.persistAfterJob ? "Profil conservé" : "Adaptation supprimée";
  byId("mesh-quality").textContent = state.mesh.quality;
}

function renderTemperature() {
  byId("temperature-owner").textContent = state.temperature.owner;
  byId("expected-nozzle").textContent = formatTemp(state.temperature.expectedNozzleC);
  byId("actual-nozzle").textContent = formatTemp(state.temperature.actualNozzleC);
  byId("initial-tool").textContent = state.temperature.initialTool;
  byId("active-cfs").textContent = state.temperature.activeCfs;
  byId("next-target").textContent = formatTemp(state.temperature.nextToolTargetC);
}

function renderSequence() {
  byId("sequence-list").replaceChildren(
    ...state.sequence.map((stage) => {
      const item = document.createElement("li");
      item.className = stage.status;
      item.textContent = stage.label;
      return item;
    }),
  );
}

function renderEvents() {
  byId("connection-label").textContent = state.connection;
  byId("event-log").replaceChildren(
    ...state.events.map((message) => {
      const item = document.createElement("li");
      item.textContent = message;
      return item;
    }),
  );
}

function render() {
  renderReadiness();
  renderCalibration();
  renderMesh();
  renderTemperature();
  renderSequence();
  renderEvents();
}

function beginCalibration() {
  const seed = Number.parseFloat(byId("seed-offset").value);
  if (!Number.isFinite(seed)) {
    addEvent("Calibration refusée : la valeur provisoire doit être explicite.");
    renderEvents();
    return;
  }
  state.calibration.session = {seedOffsetMm: seed, currentOffsetMm: seed};
  addEvent(`Session Z ouverte à ${formatOffset(seed)} mm. Rien n'est encore enregistré.`);
  render();
}

function adjustCalibration(delta) {
  if (!state.calibration.session) return;
  state.calibration.session.currentOffsetMm = Number(
    (state.calibration.session.currentOffsetMm + delta).toFixed(4),
  );
  addEvent(`Réglage provisoire : ${formatOffset(state.calibration.session.currentOffsetMm)} mm.`);
  render();
}

function saveCalibration() {
  const session = state.calibration.session;
  if (!session) return;
  previousAccepted = {
    offsetMm: state.calibration.offsetMm,
    status: state.calibration.status,
    acceptedAt: state.calibration.acceptedAt,
  };
  state.calibration.offsetMm = session.currentOffsetMm;
  state.calibration.provisionalSeedMm = session.currentOffsetMm;
  state.calibration.acceptedAt = new Date().toISOString();
  state.calibration.status = "accepted";
  state.calibration.session = null;
  state.ready = true;
  state.blockReason = null;
  addEvent(`Calibration Z enregistrée explicitement à ${formatOffset(state.calibration.offsetMm)} mm.`);
  render();
}

function cancelCalibration() {
  if (!state.calibration.session) return;
  state.calibration.session = null;
  addEvent("Session annulée : la calibration acceptée précédente n'a pas changé.");
  render();
}

function invalidateCalibration() {
  state.calibration.session = null;
  state.calibration.status = "invalid";
  state.ready = false;
  state.blockReason = "Une nouvelle calibration de référence a invalidé le Z accepté. Recalibration requise.";
  addEvent("Nouvelle référence simulée : l'ancienne valeur est conservée dans l'historique mais bloquée.");
  render();
}

function restoreCalibration() {
  if (!previousAccepted) return;
  const current = {
    offsetMm: state.calibration.offsetMm,
    status: state.calibration.status,
    acceptedAt: state.calibration.acceptedAt,
  };
  state.calibration.offsetMm = previousAccepted.offsetMm;
  state.calibration.status = previousAccepted.status;
  state.calibration.acceptedAt = previousAccepted.acceptedAt;
  state.calibration.provisionalSeedMm = previousAccepted.offsetMm;
  previousAccepted = current;
  state.ready = state.calibration.status === "accepted";
  state.blockReason = state.ready ? null : "La calibration restaurée n'est pas qualifiée.";
  addEvent(`Calibration précédente restaurée à ${formatOffset(state.calibration.offsetMm)} mm.`);
  render();
}

function preserveCalibration(eventLabel) {
  addEvent(`${eventLabel} : la calibration acceptée reste ${formatOffset(state.calibration.offsetMm)} mm.`);
  renderEvents();
}

function bindEvents() {
  byId("begin-calibration").addEventListener("click", beginCalibration);
  byId("save-calibration").addEventListener("click", saveCalibration);
  byId("cancel-calibration").addEventListener("click", cancelCalibration);
  byId("restore-calibration").addEventListener("click", restoreCalibration);
  byId("simulate-reference").addEventListener("click", invalidateCalibration);
  byId("simulate-restart").addEventListener("click", () => preserveCalibration("Redémarrage simulé"));
  byId("simulate-print-end").addEventListener("click", () => preserveCalibration("Fin d'impression simulée"));
  byId("expert-button").addEventListener("click", () => {
    addEvent("Mainsail n'est pas connecté dans ce prototype local.");
    renderEvents();
  });
  document.querySelectorAll("[data-adjust]").forEach((button) => {
    button.addEventListener("click", () => adjustCalibration(Number(button.dataset.adjust)));
  });
}

async function start() {
  const response = await fetch("mock-state.json", {cache: "no-store"});
  if (!response.ok) throw new Error(`mock state unavailable: ${response.status}`);
  state = await response.json();
  if (!state.simulation) throw new Error("this prototype accepts simulation state only");
  bindEvents();
  render();
}

start().catch((error) => {
  byId("readiness-title").textContent = "Prototype indisponible";
  byId("readiness-detail").textContent = error.message;
  byId("readiness-card").classList.add("blocked");
});
