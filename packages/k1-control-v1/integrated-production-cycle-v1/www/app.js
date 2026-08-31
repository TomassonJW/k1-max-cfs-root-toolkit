"use strict";

const API = "/machine/k1_control/cycle";
const $ = (id) => document.getElementById(id);
let state = null;
let pending = false;
let filesLoaded = false;

const ORDER = [
  "idle", "unload_before_clean", "await_manual_clean", "await_geometry",
  "await_t1a_load", "await_purge_proof", "ready_to_print", "printing",
  "ending", "closed_safe"
];

const COPY = {
  idle: ["Prêt", "Le cycle peut vérifier la machine et le travail sélectionné."],
  unload_before_clean: ["Retrait du filament", "K1 Control retire la route engagée à la température déclarée."],
  await_manual_clean: ["Nettoyage attendu", "Le filament est retiré. Nettoie la face de la buse."],
  await_geometry: ["Références en cours", "X/Y puis Z à 140/55 °C, sans nouveau mesh."],
  await_t1a_load: ["Chargement T1A", "Le 11 × 11 est verrouillé avant le chargement contrôlé."],
  await_purge_proof: ["Purge de preuve", "Une seule purge hors modèle doit être confirmée par caméra."],
  ready_to_print: ["Départ prêt", "Le fichier sélectionné va démarrer avec le contexte vérifié."],
  printing: ["Impression en cours", "K1 Control conserve la route, le mesh et les températures du travail."],
  ending: ["Fin en cours", "Parcage, retrait, refroidissement puis libération des moteurs."],
  closed_safe: ["Travail terminé", "Filament retiré, chauffes coupées et moteurs libérés."],
  failed_safe: ["Cycle bloqué", "La machine est arrêtée en sécurité. Aucun effet n’est rejoué."],
};

const LABELS = {
  idle: "Vérification initiale",
  unload_before_clean: "Retrait avant nettoyage",
  await_manual_clean: "Nettoyage manuel",
  await_geometry: "Références X/Y/Z",
  await_t1a_load: "Chargement T1A",
  await_purge_proof: "Purge et caméra",
  ready_to_print: "Lancement du fichier",
  printing: "Impression",
  ending: "Fin et retrait",
  closed_safe: "État sûr final",
};

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {cache: "no-store", ...options});
  const payload = await response.json();
  if (!response.ok || payload.error) throw new Error(payload.error?.message ?? `API indisponible (${response.status}).`);
  return payload.result ?? payload;
}

async function post(path, body = {}) {
  if (pending) return;
  pending = true;
  render();
  try {
    state = await request(path, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    $("error").textContent = "";
  } catch (error) {
    $("error").textContent = error.message;
  } finally {
    pending = false;
    render();
  }
}

async function loadFiles() {
  const payload = await request("/files");
  const select = $("file-select");
  const selected = payload.selected?.filename ?? state?.job?.filename ?? "";
  select.replaceChildren(new Option("Choisir un fichier…", ""));
  for (const file of payload.files ?? []) {
    const details = [file.filament_type, file.first_layer_extr_temp ? `${file.first_layer_extr_temp} °C` : null]
      .filter(Boolean).join(" · ");
    select.append(new Option(`${file.filename}${details ? ` — ${details}` : ""}`, file.filename));
  }
  select.value = selected;
  filesLoaded = true;
}

async function selectFile() {
  const filename = $("file-select").value;
  if (!filename) return;
  await post("/select", {filename});
}

function renderSteps(phase) {
  const current = ORDER.indexOf(phase);
  $("steps").replaceChildren(...ORDER.slice(1).map((item, index) => {
    const li = document.createElement("li");
    li.textContent = LABELS[item];
    if (phase === "closed_safe" || index + 1 < current) li.className = "done";
    else if (index + 1 === current) li.className = "current";
    return li;
  }));
}

function render() {
  const phase = state?.phase ?? "idle";
  const [title, detail] = COPY[phase] ?? [phase, "État inconnu."];
  $("phase-title").textContent = title;
  $("phase-detail").textContent = detail;
  $("phase-badge").textContent = phase === "failed_safe" ? "BLOQUÉ" : (phase === "closed_safe" ? "TERMINÉ" : "ACTIF");
  $("phase-badge").className = `badge ${phase === "failed_safe" ? "blocked" : (phase === "closed_safe" ? "good" : "")}`;
  $("job-name").textContent = state?.job?.filename ?? "Aucun fichier sélectionné";
  $("route").textContent = state?.route ?? "Aucune";
  $("bed-temp").textContent = state?.job ? `${state.job.bed_first_c} °C` : "55 °C";
  $("nozzle-temp").textContent = state?.job ? `${state.job.nozzle_first_c} °C` : "—";
  $("mesh").textContent = state?.mesh_profile?.endsWith("n11x11") ? "11 × 11" : (state?.mesh_profile ?? "11 × 11 attendu");
  const offline = state?.authority_mode === "offline";
  $("mode-warning").classList.toggle("hidden", !offline);
  $("mode-warning").textContent = offline ? "Candidat hors imprimante : les effets physiques restent verrouillés." : "";
  $("clean-card").classList.toggle("hidden", phase !== "await_manual_clean");
  $("file-select").disabled = pending || !["idle", "closed_safe"].includes(phase);
  $("prepare").disabled = pending || offline || !["idle", "closed_safe"].includes(phase) || !state?.job?.filename;
  $("abort").disabled = pending || ["idle", "closed_safe", "failed_safe"].includes(phase);
  $("confirm-clean").disabled = pending || !$("clean-check").checked || phase !== "await_manual_clean";
  $("technical").textContent = JSON.stringify(state ?? {}, null, 2);
  renderSteps(phase);
}

async function refresh() {
  if (pending) return;
  pending = true;
  try {
    state = await request("/status");
    if (!filesLoaded) await loadFiles();
    $("error").textContent = "";
  } catch (error) {
    $("error").textContent = error.message;
  } finally {
    pending = false;
    render();
  }
}

$("refresh").addEventListener("click", refresh);
$("file-select").addEventListener("change", selectFile);
$("prepare").addEventListener("click", () => post("/prepare"));
$("abort").addEventListener("click", () => post("/abort", {automatic_retry: false}));
$("clean-check").addEventListener("change", render);
$("confirm-clean").addEventListener("click", () => post("/clean-confirm", {
  operator_confirmed: true,
  nozzle_visibly_clean: true,
  confirmation_fresh: true,
}));

render();
refresh();
setInterval(refresh, 2000);
