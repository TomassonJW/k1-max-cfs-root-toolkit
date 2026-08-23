"use strict";

const API = "/machine/k1_control";
const Z_LADDER = [5, 2, 1, 0.5, 0.3, 0.2, 0.15, 0.1];
const byId = (id) => document.getElementById(id);
let state = null;
let requestPending = false;
let hydratedFormKey = null;

const PHASES = {
  idle: ["Prêt à configurer", "Choisis le contexte puis confirme que le plateau est libre."],
  preflight: ["Préflight en cours", "L’identité, l’état au repos et les gardes sont vérifiés."],
  preparing: ["Préparation en cours", "Backup, chauffe, stabilisation, nettoyage et homing."],
  measuring: ["Maillage en cours", "Un passage complet de 36 points physiques."],
  qualifying: ["Contrôle en cours", "La matrice 6 × 6 est relue avant enregistrement."],
  committing_mesh: ["Enregistrement du mesh", "Le mesh complet est relu avant sa persistance."],
  mesh_ready: ["Mesh prêt", "Le premier Z peut maintenant être qualifié."],
  mesh_rejected: ["Mesh refusé", "La reproductibilité reste hors limites. Aucun candidat n’a été enregistré."],
  cancelling: ["Annulation demandée", "L’opération physique déjà engagée se termine, puis les chauffes seront coupées."],
  starting_z: ["Préparation du Z", "Chauffe, homing et chargement du mesh qualifié."],
  z_testing: ["Descente Z en cours", "Un seul palier peut être franchi à la fois."],
  z_confirmed: ["Jeu confirmé", "La tête est remontée ; le Z peut être enregistré."],
  accepted: ["Calibration acceptée", "Mesh robuste et Z accepté sont persistants."],
  restored: ["Z précédent restauré", "La valeur de récupération a été réappliquée explicitement."],
  rolled_back: ["Campagne restaurée", "printer.cfg et l’état Z correspondent au backup créé avant chauffe."],
  cancelled: ["Calibration annulée", "Les chauffes sont coupées et la session provisoire est fermée."],
  failed: ["Calibration bloquée", "Le système s’est arrêté en sécurité."],
};

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {cache: "no-store", ...options});
  const payload = await response.json();
  if (!response.ok || payload.error) {
    throw new Error(payload.error?.message ?? `API indisponible (${response.status}).`);
  }
  return payload.result ?? payload;
}

async function post(path, body = {}) {
  if (requestPending) return;
  requestPending = true;
  render();
  try {
    state = await request(path, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
  } catch (error) {
    showError(error.message);
  } finally {
    requestPending = false;
    render();
  }
}

function showError(message) {
  byId("last-error").textContent = message;
  byId("readiness-card").classList.add("blocked");
}

function configFromForm() {
  const matrix = Number(byId("matrix-size").value);
  return {
    plate_id: Number(byId("plate").value),
    plate_label: byId("plate").selectedOptions[0].textContent,
    bed_temp_c: Number(byId("bed-temp").value),
    nozzle_temp_c: Number(byId("nozzle-temp").value),
    soak_seconds: Number(byId("soak-seconds").value),
    probe_revision: 1,
    nozzle_id: 1,
    config_id: 1,
    x_count: matrix,
    y_count: matrix,
    algorithm: byId("algorithm").value,
    seed_offset_mm: Number(byId("seed-offset").value),
    replace_existing: byId("replace-existing").checked,
    plate_clear: byId("plate-clear").checked,
  };
}

function formatMm(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(3).replace(".", ",")} mm` : "—";
}

function syncMatrixAlgorithm() {
  byId("matrix-size").value = "6";
  byId("algorithm").value = "lagrange";
}

function isIncompleteRetry(value) {
  return ["cancelled", "failed", "mesh_rejected", "rolled_back"].includes(value?.phase);
}

function hydrateForm() {
  const acceptedOffset = Number(state?.accepted_z_offset_mm);
  const phase = state?.phase ?? "idle";
  const key = state?.campaign_id
    ? `${state.campaign_id}:${phase}`
    : `accepted:${state?.accepted_z_valid}:${state?.accepted_z_offset_mm}`;
  if (hydratedFormKey === key) return;
  const config = state?.config;
  if (config) {
    byId("plate").value = String(config.plate_id);
    byId("bed-temp").value = String(config.bed_temp_c);
    byId("nozzle-temp").value = String(config.nozzle_temp_c);
    byId("soak-seconds").value = String(config.soak_seconds);
    byId("matrix-size").value = "6";
    byId("algorithm").value = "lagrange";
    byId("seed-offset").value = String(config.seed_offset_mm);
    byId("replace-existing").checked = isIncompleteRetry(state)
      ? false
      : Boolean(config.replace_existing);
  } else if (state?.accepted_z_valid && Number.isFinite(acceptedOffset)) {
    byId("seed-offset").value = String(acceptedOffset);
  }
  if (isIncompleteRetry(state)) {
    byId("plate-clear").checked = false;
  }
  syncMatrixAlgorithm();
  hydratedFormKey = key;
}

function renderSequence() {
  const phase = state?.phase ?? "idle";
  const stages = [
    ["preflight", "Contexte et backup"],
    ["measuring", "Mesh 6 × 6"],
    ["qualifying", "Contrôle de la matrice"],
    ["mesh_ready", "Mesh enregistré"],
    ["z_testing", "Paliers Z"],
    ["z_confirmed", "Jeu observé et remontée"],
    ["accepted", "Z enregistré"],
  ];
  const order = stages.map(([id]) => id);
  const currentIndex = order.indexOf(phase);
  const accepted = ["accepted", "restored", "rolled_back"].includes(phase);
  byId("sequence-list").replaceChildren(...stages.map(([id, label], index) => {
    const item = document.createElement("li");
    item.textContent = label;
    item.className = accepted || index < currentIndex ? "done" : index === currentIndex ? "active" : "locked";
    return item;
  }));
}

function renderMesh() {
  const qualification = state?.qualification;
  const meshIndex = Number(state?.mesh_index ?? 0);
  const targetCount = Number(state?.mesh_target_count ?? 1);
  byId("mesh-index").textContent = `${meshIndex} / ${targetCount}`;
  byId("mesh-progress").style.width = `${Math.min(100, meshIndex / targetCount * 100)}%`;
  byId("mesh-status").textContent = qualification
    ? qualification.accepted ? "Qualifié" : "Refusé"
    : meshIndex ? "Mesure" : "En attente";
  byId("mesh-status").classList.toggle("success", Boolean(qualification?.accepted));
  byId("mesh-status").classList.toggle("invalid", qualification?.accepted === false);
  byId("mesh-mean").textContent = "6 × 6";
  byId("mesh-rms").textContent = "36";
  byId("mesh-maximum").textContent = "PRTouch";
  if (qualification) {
    byId("mesh-explanation").textContent = qualification.accepted
      ? "Le mesh 6 × 6 complet a été relu et enregistré."
      : "Le mesh est incomplet ou invalide. Aucun enregistrement automatique.";
  }
}

function renderZ() {
  const phase = state?.phase;
  const index = state?.z_ladder_index;
  const testing = phase === "z_testing";
  const atLastStep = testing && index === Z_LADDER.length - 1;
  byId("start-z").disabled = requestPending || phase !== "mesh_ready"
    || !byId("plate-clear").checked || !byId("nozzle-clean").checked;
  byId("next-z").disabled = requestPending || !testing || atLastStep;
  byId("confirm-gap").disabled = requestPending || !atLastStep || !byId("gap-observed").checked;
  byId("accept-z").disabled = requestPending || phase !== "z_confirmed";
  document.querySelectorAll("[data-adjust]").forEach((button) => {
    button.disabled = requestPending || !atLastStep;
  });
  byId("z-height").textContent = Number.isInteger(index) ? String(Z_LADDER[index]).replace(".", ",") : "—";
  byId("z-status").textContent = phase === "accepted" ? "Accepté" : phase === "z_confirmed" ? "Confirmé" : testing ? "En cours" : "Verrouillé";
  byId("z-status").classList.toggle("success", phase === "accepted" || phase === "z_confirmed");
  byId("z-instruction").textContent = atLastStep
    ? "Observe réellement le jeu. Ajuste si nécessaire, puis confirme : la tête remontera avant l’enregistrement."
    : testing
      ? `Palier actuel ${Z_LADDER[index]} mm. Vérifie l’espace puis passe au palier suivant.`
      : phase === "mesh_ready"
        ? "Confirme la propreté de la buse puis commence la descente à 5 mm."
        : "Qualifie d’abord le mesh robuste.";
}

function render() {
  if (!state) return;
  hydrateForm();
  const [title, detail] = PHASES[state.phase] ?? [state.phase, "État non documenté."];
  byId("phase-title").textContent = title;
  byId("phase-detail").textContent = state.last_error || detail;
  byId("connection-status").textContent = "API connectée";
  byId("connection-status").classList.add("success");
  byId("readiness-card").classList.toggle("blocked", ["failed", "mesh_rejected"].includes(state.phase));
  byId("last-error").textContent = state.last_error || "Aucune erreur.";
  const startable = ["idle", "cancelled", "failed", "mesh_rejected", "accepted", "restored", "rolled_back"].includes(state.phase);
  byId("start-mesh").disabled = requestPending || state.busy || !startable;
  document.querySelectorAll("#calibration-form input:not(#plate-clear), #calibration-form select").forEach((field) => {
    field.disabled = requestPending || state.busy || !startable;
  });
  byId("plate-clear").disabled = requestPending || state.busy;
  byId("cancel-workflow").disabled = requestPending || ["idle", "cancelled", "accepted", "restored", "rolled_back", "cancelling"].includes(state.phase);
  byId("restore-z").disabled = requestPending || !state.previous_z_restorable;
  byId("rollback-campaign").disabled = requestPending || state.busy || !state.backup_available || state.phase === "rolled_back";
  renderMesh();
  renderZ();
  renderSequence();
}

function bind() {
  byId("calibration-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    void post("/calibration/start", configFromForm());
  });
  byId("matrix-size").addEventListener("change", syncMatrixAlgorithm);
  byId("algorithm").addEventListener("change", syncMatrixAlgorithm);
  byId("start-z").addEventListener("click", () => void post("/z/start", {
    plate_clear: byId("plate-clear").checked,
    nozzle_clean: byId("nozzle-clean").checked,
  }));
  byId("next-z").addEventListener("click", () => void post("/z/step"));
  document.querySelectorAll("[data-adjust]").forEach((button) => {
    button.addEventListener("click", () => void post("/z/adjust", {delta: Number(button.dataset.adjust)}));
  });
  byId("gap-observed").addEventListener("change", render);
  byId("plate-clear").addEventListener("change", render);
  byId("nozzle-clean").addEventListener("change", render);
  byId("confirm-gap").addEventListener("click", () => void post("/z/confirm", {
    observed: byId("gap-observed").checked,
  }));
  byId("accept-z").addEventListener("click", () => void post("/z/accept"));
  byId("cancel-workflow").addEventListener("click", () => void post("/calibration/cancel"));
  byId("restore-z").addEventListener("click", () => void post("/z/restore"));
  byId("rollback-campaign").addEventListener("click", () => {
    if (window.confirm("Restaurer exactement printer.cfg et l’état Z sauvegardés avant cette calibration ?")) {
      void post("/calibration/rollback");
    }
  });
}

async function refresh() {
  try {
    state = await request("/status");
    render();
  } catch (error) {
    byId("connection-status").textContent = "API indisponible";
    showError(error.message);
  }
}

bind();
await refresh();
window.setInterval(refresh, 2000);
