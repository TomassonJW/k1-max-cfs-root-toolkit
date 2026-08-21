"use strict";

const byId = (id) => document.getElementById(id);
const formatOffset = (value) => `${value >= 0 ? "+" : ""}${value.toFixed(3)}`.replace(".", ",");
const formatTemp = (value) => `${value} °C`;

export function createK1ControlUi(adapter) {
  let state;

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
    byId("begin-calibration").disabled = Boolean(session) || !state.commandsAvailable;
    byId("restore-calibration").disabled = !calibration.canRestore || !state.commandsAvailable;
  }

  function renderMesh() {
    byId("mesh-mode").textContent = state.mesh.mode === "adaptive" ? "Adaptatif par travail" : "Référence complète";
    byId("plate-label").textContent = state.plate.label;
    byId("bed-target").textContent = formatTemp(state.plate.bedTargetC);
    byId("mesh-profile").textContent = state.mesh.referenceProfile;
    byId("mesh-persistence").textContent = state.mesh.persistAfterJob ? "Profil conservé" : "Profil non qualifié";
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

  async function send(script) {
    try {
      state = await adapter.command(script);
      render();
    } catch (error) {
      byId("readiness-title").textContent = "Commande refusée";
      byId("readiness-detail").textContent = error.message;
      byId("readiness-card").classList.add("blocked");
    }
  }

  function bindEvents() {
    byId("begin-calibration").addEventListener("click", () => {
      const seed = Number.parseFloat(byId("seed-offset").value);
      if (!Number.isFinite(seed)) {
        byId("readiness-detail").textContent = "Calibration refusée : la valeur provisoire doit être explicite.";
        return;
      }
      void send(`K1_Z_SESSION_START SEED=${seed}`);
    });
    byId("save-calibration").addEventListener("click", () => void send("K1_Z_COMMIT"));
    byId("cancel-calibration").addEventListener("click", () => void send("K1_Z_CANCEL"));
    byId("restore-calibration").addEventListener("click", () => void send("K1_Z_RESTORE_PREVIOUS"));
    byId("simulate-reference").addEventListener("click", () => void send("K1_SIM_REFERENCE_CALIBRATION"));
    byId("simulate-restart").addEventListener("click", () => void send("K1_SIM_RESTART"));
    byId("simulate-print-end").addEventListener("click", () => void send("K1_SIM_PRINT_END"));
    byId("expert-button").addEventListener("click", () => void send("K1_SIM_EXPERT_NOTICE"));
    document.querySelectorAll("[data-adjust]").forEach((button) => {
      button.addEventListener("click", () => void send(`K1_Z_ADJUST DELTA=${button.dataset.adjust}`));
    });
  }

  async function start() {
    state = await adapter.connect();
    bindEvents();
    render();
  }

  return {start};
}
