"use strict";

const API = "/machine/k1_control/stock-cycle";
const ROUTES = ["T1A", "T1B", "T1C", "T1D", "T2A", "T2B", "T2C", "T2D"];
const MATERIAL_FIELDS = ["reference_id", "material_type", "color", "diameter_mm", "thermal_recipe_id"];
const byId = (id) => document.getElementById(id);

let state = null;
let files = [];
let pending = false;
let inventoryHydrated = false;
let inventoryDirty = false;
let jobHydrated = false;

const PHASES = {
  idle: ["Prêt", "Choisis un fichier et une bobine, puis lance la préparation."],
  preclean_unload_ready: ["Retrait nécessaire", "Le filament engagé doit être coupé et retiré avant le nettoyage."],
  preclean_unload_pending: ["Retrait en cours", "K1 Control utilise le cutter puis libère la route engagée."],
  await_manual_clean: ["Nettoyage attendu", "Nettoie maintenant la buse et le plateau."],
  geometry_ready_to_dispatch: ["Géométrie prête", "Les références vont être prises avant toute insertion."],
  geometry_pending: ["Références X/Y/Z", "La buse est propre et aucun filament n’est chargé."],
  initial_load_ready: ["Chargement prêt", "Le mesh 11 × 11 et le Z canonique sont verrouillés."],
  await_release_camera: ["Contrôle de purge", "Le filament a été purgé dans le bac avec quatre allers-retours."],
  initial_prime_ready: ["Ligne d’amorce prête", "La purge est qualifiée ; la ligne hors plateau va être déposée."],
  await_prime_camera: ["Contrôle de la ligne", "La caméra vérifie la ligne d’amorce avant le modèle."],
  ready_to_print: ["Départ prêt", "Le fichier Orca va démarrer avec ses températures."],
  printing: ["Impression en cours", "K1 Control surveille la route, les changements et la fin."],
  tool_change_pending: ["Changement en cours", "Cutter, retrait, chargement et purge sont possédés par K1 Control."],
  await_tool_change_camera: ["Contrôle du changement", "La reprise attend une buse physiquement libre."],
  equivalent_refill_pending: ["Bobine de secours", "La bobine vide est remplacée par l’unique secours strictement identique."],
  await_refill_camera: ["Contrôle du secours", "La reprise attend la preuve caméra de la purge."],
  normal_end_pending: ["Fin en cours", "La tête est parquée, le filament retiré et les chauffes coupées."],
  owner_release_pending: ["Libération du propriétaire", "Le cycle restitue la machine après les preuves finales."],
  closed_safe: ["Cycle terminé", "Filament retiré, chauffes coupées et moteurs libérés."],
  failed_safe: ["Cycle bloqué", "La machine est conservée en sécurité ; aucun effet incertain n’est rejoué."],
  blocked_uncertain: ["Résultat incertain", "Une commande interrompue ne sera jamais relancée automatiquement."],
};

const STAGES = [
  ["clean", "Retrait et nettoyage manuel"],
  ["geometry", "Références X/Y/Z sans filament"],
  ["load", "Chargement et purge dans le bac"],
  ["prime", "Ligne d’amorce hors plateau"],
  ["print", "Impression et roulement éventuel"],
  ["end", "Fin, retrait et refroidissement"],
];

const STAGE_BY_PHASE = {
  preclean_unload_ready: 0, preclean_unload_pending: 0, await_manual_clean: 0,
  geometry_ready_to_dispatch: 1, geometry_pending: 1,
  initial_load_ready: 2, await_release_camera: 2,
  initial_prime_ready: 3, await_prime_camera: 3, ready_to_print: 3,
  printing: 4, tool_change_pending: 4, await_tool_change_camera: 4,
  equivalent_refill_pending: 4, await_refill_camera: 4,
  normal_end_pending: 5, owner_release_pending: 5, closed_safe: 6,
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
  return request(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
}

function setError(message) {
  byId("last-error").textContent = message || "Aucune erreur.";
  byId("cycle-card").classList.toggle("blocked", Boolean(message));
}

function createRouteOptions(select, includeEmpty = false) {
  const current = select.value;
  select.replaceChildren();
  if (includeEmpty) select.append(new Option("Choisir…", ""));
  ROUTES.forEach((route) => select.append(new Option(route, route)));
  if ([...select.options].some((option) => option.value === current)) select.value = current;
}

function createInventoryRows() {
  const container = byId("inventory-rows");
  container.replaceChildren(...ROUTES.map((route) => {
    const row = document.createElement("div");
    row.className = "inventory-row";
    row.dataset.route = route;
    row.innerHTML = `
      <label class="inventory-route"><input type="checkbox" data-field="available">${route}</label>
      <label>Référence<input data-field="reference_id" maxlength="64" placeholder="ex. pla-noir"></label>
      <label>Matière<input data-field="material_type" maxlength="32" placeholder="PLA"></label>
      <label>Couleur<input data-field="color" maxlength="64" placeholder="noir"></label>
      <label>Recette thermique<input data-field="thermal_recipe_id" maxlength="64" placeholder="pla-190"></label>`;
    const diameter = document.createElement("label");
    diameter.textContent = "Diamètre";
    const input = document.createElement("input");
    input.dataset.field = "diameter_mm";
    input.type = "number";
    input.min = "1";
    input.max = "3";
    input.step = "0.01";
    input.value = "1.75";
    diameter.append(input);
    row.append(diameter);
    row.querySelectorAll("input").forEach((field) => field.addEventListener("input", () => {
      inventoryDirty = true;
      renderInventorySummary();
      renderControls();
    }));
    return row;
  }));
}

function inventoryFromForm() {
  const result = [];
  document.querySelectorAll(".inventory-row").forEach((row) => {
    if (!row.querySelector('[data-field="available"]').checked) return;
    const material = {};
    MATERIAL_FIELDS.forEach((field) => {
      const raw = row.querySelector(`[data-field="${field}"]`).value.trim();
      material[field] = field === "diameter_mm" ? Number(raw) : raw;
    });
    material.user_approved = true;
    result.push({route: row.dataset.route, available: true, material});
  });
  return result;
}

function validateInventory(values) {
  if (!values.length) throw new Error("Coche au moins une bobine réellement présente.");
  for (const item of values) {
    for (const field of MATERIAL_FIELDS) {
      const value = item.material[field];
      if (field === "diameter_mm") {
        if (!Number.isFinite(value) || value <= 0) throw new Error(`Diamètre invalide pour ${item.route}.`);
      } else if (!value) {
        throw new Error(`Champ ${field} manquant pour ${item.route}.`);
      }
    }
    if (!/^[A-Za-z0-9._-]+$/.test(item.material.reference_id)
        || !/^[A-Za-z0-9._-]+$/.test(item.material.thermal_recipe_id)) {
      throw new Error(`Référence ou recette invalide pour ${item.route} : utilise lettres, chiffres, point, tiret ou underscore.`);
    }
  }
}

function hydrateInventory() {
  if (inventoryHydrated || inventoryDirty) return;
  const saved = state?.selected?.inventory;
  if (!Array.isArray(saved)) return;
  const byRoute = new Map(saved.map((item) => [item.route, item]));
  document.querySelectorAll(".inventory-row").forEach((row) => {
    const item = byRoute.get(row.dataset.route);
    row.querySelector('[data-field="available"]').checked = Boolean(item?.available);
    MATERIAL_FIELDS.forEach((field) => {
      if (item?.material?.[field] !== undefined) {
        row.querySelector(`[data-field="${field}"]`).value = String(item.material[field]);
      }
    });
  });
  inventoryHydrated = true;
}

function materialKey(material) {
  return JSON.stringify(MATERIAL_FIELDS.map((field) => material?.[field]));
}

function renderInventorySummary() {
  const inventory = inventoryFromForm();
  const initial = byId("initial-route").value;
  const source = inventory.find((item) => item.route === initial);
  const status = byId("inventory-status");
  status.textContent = inventoryDirty ? "Non enregistré" : inventory.length ? `${inventory.length} bobine(s)` : "À configurer";
  status.classList.toggle("success", inventory.length > 0 && !inventoryDirty);
  const summary = byId("spare-summary");
  if (!source) {
    summary.textContent = `${initial || "La bobine de départ"} n’est pas déclarée disponible.`;
    summary.className = "callout warning";
    return;
  }
  const matches = inventory.filter((item) => item.route !== initial && materialKey(item.material) === materialKey(source.material));
  if (matches.length === 1) {
    summary.textContent = `Secours automatique qualifié : ${matches[0].route}.`;
    summary.className = "callout spare-good";
  } else if (matches.length > 1) {
    summary.textContent = `Secours ambigu (${matches.map((item) => item.route).join(", ")}) : le roulement sera refusé.`;
    summary.className = "callout warning";
  } else {
    summary.textContent = "Aucun secours strictement identique : une bobine vide fermera l’impression en sécurité.";
    summary.className = "callout";
  }
}

function selectedFile() {
  return files.find((file) => file.filename === byId("file-select").value);
}

function renderJob() {
  if (!jobHydrated && state?.selected?.job?.initial_route) {
    byId("initial-route").value = state.selected.job.initial_route;
    jobHydrated = true;
  }
  const file = selectedFile();
  byId("job-material").textContent = file?.filament_type || "—";
  byId("job-nozzle").textContent = file?.first_layer_extr_temp ? `${file.first_layer_extr_temp} °C` : "—";
  byId("job-bed").textContent = file?.first_layer_bed_temp ? `${file.first_layer_bed_temp} °C` : "—";
  const selectedJob = state?.selected?.job;
  byId("selection-status").textContent = selectedJob ? "Travail validé" : "Validation au départ";
  byId("selection-status").classList.toggle("success", Boolean(selectedJob));
}

function renderToolChangeRoutes() {
  const select = byId("tool-change-route");
  const current = select.value;
  select.replaceChildren(new Option("Choisir…", ""));
  inventoryFromForm().forEach((item) => select.append(new Option(item.route, item.route)));
  if ([...select.options].some((option) => option.value === current)) select.value = current;
}

function renderSequence() {
  const phase = state?.phase ?? "idle";
  const current = STAGE_BY_PHASE[phase] ?? -1;
  byId("sequence-list").replaceChildren(...STAGES.map(([id, label], index) => {
    const item = document.createElement("li");
    item.dataset.stage = id;
    item.textContent = label;
    if (current > index || current === 6) item.className = "done";
    else if (current === index) item.className = "active";
    else item.className = "locked";
    return item;
  }));
}

function renderCamera() {
  const checkpoint = state?.camera_checkpoint;
  const waiting = Boolean(checkpoint);
  const labels = {
    PURGE_BIN_RELEASE: ["Purge dans le bac", "Vérification du décrochage de la boule et de la buse libre."],
    ORIGIN_PRIME_LINE: ["Ligne d’amorce", "Vérification de la ligne continue hors du plateau."],
    TOOL_CHANGE_PURGE_RELEASE: ["Changement de filament", "Vérification de la purge avant reprise."],
    REFILL_PURGE_RELEASE: ["Bobine de secours", "Vérification de la purge avant reprise automatique."],
  };
  const [title, detail] = labels[checkpoint] ?? ["Aucun contrôle attendu", "Le pilote caméra surveillera les arrêts physiques du cycle."];
  byId("camera-title").textContent = title;
  byId("camera-detail").textContent = detail;
  byId("camera-status").textContent = waiting ? "Image attendue" : state?.last_camera_evidence_id ? "Dernière preuve reçue" : "Au repos";
  byId("camera-status").classList.toggle("invalid", waiting);
  byId("camera-status").classList.toggle("success", !waiting && Boolean(state?.last_camera_evidence_id));
  byId("camera-pending-warning").classList.toggle("is-hidden", !waiting);
}

function renderControls() {
  const phase = state?.phase ?? "idle";
  const startable = ["idle", "closed_safe", "failed_safe"].includes(phase);
  const checks = ["operator-present", "camera-ready", "machine-clear"].every((id) => byId(id).checked);
  const inventory = inventoryFromForm();
  const routeAvailable = inventory.some((item) => item.route === byId("initial-route").value);
  byId("begin-cycle").disabled = pending || !startable || !checks || !byId("file-select").value || !routeAvailable || inventoryDirty;
  byId("save-inventory").disabled = pending || !startable || inventory.length === 0 || !inventoryDirty;
  byId("file-select").disabled = pending || !startable;
  byId("initial-route").disabled = pending || !startable;
  document.querySelectorAll(".inventory-row input").forEach((field) => { field.disabled = pending || !startable; });
  byId("abort-cycle").disabled = pending || ["idle", "closed_safe"].includes(phase);
  byId("clean-panel").classList.toggle("is-hidden", phase !== "await_manual_clean");
  byId("confirm-clean").disabled = pending || phase !== "await_manual_clean" || !byId("nozzle-clean").checked || !byId("plate-clean").checked;
  byId("tool-change-panel").classList.toggle("is-hidden", phase !== "printing");
  renderToolChangeRoutes();
  byId("tool-change").disabled = pending || phase !== "printing" || !byId("tool-change-route").value || byId("tool-change-route").value === state?.active_route;
}

function render() {
  if (!state) return;
  hydrateInventory();
  const phase = state.phase ?? "idle";
  const [title, detail] = PHASES[phase] ?? [phase, "État non documenté."];
  byId("phase-title").textContent = title;
  byId("phase-detail").textContent = state.last_failure || state.last_error || detail;
  byId("connection-status").textContent = state.enabled ? "Propriétaire actif" : "Propriétaire désactivé";
  byId("connection-status").classList.toggle("success", Boolean(state.enabled));
  byId("cycle-card").classList.toggle("blocked", ["failed_safe", "blocked_uncertain"].includes(phase));
  byId("last-error").textContent = state.last_failure || state.last_error || "Aucune erreur.";
  byId("technical-state").textContent = JSON.stringify(state, null, 2);
  renderInventorySummary();
  renderJob();
  renderCamera();
  renderSequence();
  renderControls();
}

async function loadFiles() {
  const payload = await request("/files");
  files = payload.files ?? [];
  const select = byId("file-select");
  const requested = state?.selected?.job?.filename ?? select.value;
  select.replaceChildren(new Option("Choisir un fichier…", ""));
  files.forEach((file) => {
    const details = [file.filament_type, file.first_layer_extr_temp ? `${file.first_layer_extr_temp} °C` : null]
      .filter(Boolean).join(" · ");
    select.append(new Option(`${file.filename}${details ? ` — ${details}` : ""}`, file.filename));
  });
  if ([...select.options].some((option) => option.value === requested)) select.value = requested;
}

async function refresh(loadFileList = false) {
  if (pending) return;
  try {
    state = await request("/status");
    if (loadFileList || files.length === 0) await loadFiles();
    setError("");
  } catch (error) {
    byId("connection-status").textContent = "API indisponible";
    setError(error.message);
  }
  render();
}

async function saveInventory() {
  if (pending) return;
  try {
    const inventory = inventoryFromForm();
    validateInventory(inventory);
    pending = true;
    render();
    state = await post("/inventory", {inventory_json: JSON.stringify(inventory)});
    inventoryDirty = false;
    setError("");
  } catch (error) {
    setError(error.message);
  } finally {
    pending = false;
    render();
  }
}

async function beginCycle() {
  if (pending) return;
  try {
    pending = true;
    render();
    state = await post("/select", {
      filename: byId("file-select").value,
      initial_route: byId("initial-route").value,
    });
    state = await post("/begin", {
      operator_present: true,
      camera_available: true,
      machine_clear: true,
    });
    setError("");
  } catch (error) {
    setError(error.message);
  } finally {
    pending = false;
    render();
  }
}

async function simpleAction(path, body) {
  if (pending) return;
  try {
    pending = true;
    render();
    state = await post(path, body);
    setError("");
  } catch (error) {
    setError(error.message);
  } finally {
    pending = false;
    render();
  }
}

function bind() {
  createRouteOptions(byId("initial-route"));
  createInventoryRows();
  byId("refresh-files").addEventListener("click", () => void refresh(true));
  byId("file-select").addEventListener("change", render);
  byId("initial-route").addEventListener("change", () => { renderInventorySummary(); renderControls(); });
  ["operator-present", "camera-ready", "machine-clear", "nozzle-clean", "plate-clean"].forEach((id) => {
    byId(id).addEventListener("change", renderControls);
  });
  byId("save-inventory").addEventListener("click", () => void saveInventory());
  byId("begin-cycle").addEventListener("click", () => void beginCycle());
  byId("confirm-clean").addEventListener("click", () => void simpleAction("/clean-confirm", {
    operator_confirmed: true,
    nozzle_visibly_clean: true,
    plate_clean: true,
    confirmation_fresh: true,
  }));
  byId("tool-change").addEventListener("click", () => void simpleAction("/tool-change", {
    target_route: byId("tool-change-route").value,
  }));
  byId("abort-cycle").addEventListener("click", () => {
    if (window.confirm("Arrêter le cycle et appliquer la fermeture sûre ?")) {
      void simpleAction("/abort", {operator_confirmed: true});
    }
  });
}

bind();
await refresh(true);
window.setInterval(() => void refresh(false), 2000);
