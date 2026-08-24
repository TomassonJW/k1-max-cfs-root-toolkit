import {
  allCellsForMode,
  displayRowOrder,
  indexToMillimeters,
  nearestProjectedPoint,
  projectSurface,
  selectionPayload,
} from "./ui-geometry.mjs";

const SOURCE_ID = "k1_p001_t055_r001_n11x11";

const elements = {
  create: document.querySelector("#create-profile"),
  empty: document.querySelector("#empty-state"),
  editor: document.querySelector("#editor"),
  grid: document.querySelector("#mesh-grid"),
  surface: document.querySelector("#surface"),
  selectionMode: document.querySelector("#selection-mode"),
  selectionSummary: document.querySelector("#selection-summary"),
  step: document.querySelector("#step-mm"),
  closer: document.querySelector("#closer"),
  farther: document.querySelector("#farther"),
  undo: document.querySelector("#undo"),
  redo: document.querySelector("#redo"),
  compare: document.querySelector("#compare"),
  restore: document.querySelector("#restore"),
  history: document.querySelector("#history-list"),
  historyCount: document.querySelector("#history-count"),
  mean: document.querySelector("#mean-value"),
  maximum: document.querySelector("#max-value"),
  warnings: document.querySelector("#warnings"),
  exportJson: document.querySelector("#export-json"),
  exportKlipper: document.querySelector("#export-klipper"),
  connectionState: document.querySelector("#connection-state"),
  profileState: document.querySelector("#profile-state"),
  message: document.querySelector("#message"),
};

const ui = {
  status: null,
  view: "final",
  comparison: false,
  selectedCells: [],
  regionAnchor: null,
  projectedPoints: [],
  messageTimer: null,
};

function profilePath(suffix) {
  return "/api/mesh-editor/v1/profiles/" + encodeURIComponent(ui.status.profile.profile_id) + "/" + suffix;
}

async function api(path, options = {}, raw = false) {
  const response = await fetch(path, {
    cache: "no-store",
    headers: options.body ? { "Content-Type": "application/json" } : {},
    ...options,
  });
  if (raw) {
    const body = await response.text();
    if (!response.ok) {
      throw new Error(body || "Erreur locale " + response.status);
    }
    return body;
  }
  const value = await response.json();
  if (!response.ok) {
    throw new Error(value.message || value.error || "Erreur locale " + response.status);
  }
  return value;
}

function showMessage(message, isError = false) {
  window.clearTimeout(ui.messageTimer);
  elements.message.textContent = message;
  elements.message.classList.toggle("error", isError);
  elements.message.classList.add("visible");
  ui.messageTimer = window.setTimeout(() => {
    elements.message.classList.remove("visible");
  }, 4500);
}

function numberText(value, places = 6, signed = false) {
  const number = Number(value);
  const prefix = signed && number > 0 ? "+" : "";
  return prefix + number.toFixed(places).replace(".", ",");
}

function selectedKey(row, column) {
  return row + ":" + column;
}

function selectedSet() {
  return new Set(ui.selectedCells.map(([row, column]) => selectedKey(row, column)));
}

function matrixForView(profile) {
  if (ui.view === "source") return profile.source_matrix;
  if (ui.view === "delta") return profile.normalized_delta;
  return profile.final_matrix;
}

function cellColor(value, values, deltaView) {
  const numeric = Number(value);
  if (deltaView) {
    const limit = Math.max(...values.map((item) => Math.abs(item)), 0.005);
    const normalized = Math.max(0, Math.min(1, (numeric / limit + 1) / 2));
    const hue = 210 - normalized * 175;
    return "hsl(" + hue + " 48% " + (29 + Math.abs(normalized - 0.5) * 12) + "%)";
  }
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const normalized = (numeric - minimum) / Math.max(maximum - minimum, 0.000001);
  const hue = 210 - normalized * 180;
  return "hsl(" + hue + " 45% " + (27 + normalized * 6) + "%)";
}

function focusCell(row, column) {
  const selector = "[data-row=\"" + row + "\"][data-column=\"" + column + "\"]";
  const target = elements.grid.querySelector(selector);
  if (target) target.focus();
}

function onCellKeydown(event) {
  const row = Number(event.currentTarget.dataset.row);
  const column = Number(event.currentTarget.dataset.column);
  const movements = {
    ArrowUp: [Math.min(10, row + 1), column],
    ArrowDown: [Math.max(0, row - 1), column],
    ArrowLeft: [row, Math.max(0, column - 1)],
    ArrowRight: [row, Math.min(10, column + 1)],
  };
  if (movements[event.key]) {
    event.preventDefault();
    focusCell(...movements[event.key]);
  } else if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    selectCell(row, column);
  }
}

function selectCell(row, column) {
  const mode = elements.selectionMode.value;
  try {
    if (mode === "region") {
      if (ui.regionAnchor === null) {
        ui.regionAnchor = [row, column];
        ui.selectedCells = [[row, column]];
        showMessage("Premier coin choisi. Sélectionne le coin opposé, dans une zone 3 × 3.");
      } else {
        ui.selectedCells = allCellsForMode(mode, row, column, ui.regionAnchor);
        ui.regionAnchor = null;
      }
    } else {
      ui.regionAnchor = null;
      ui.selectedCells = allCellsForMode(mode, row, column);
    }
    renderEditor();
  } catch (error) {
    ui.regionAnchor = null;
    ui.selectedCells = [];
    renderEditor();
    showMessage(error.message, true);
  }
}

function selectionSummary() {
  if (ui.selectedCells.length === 0) return "Aucun point sélectionné";
  const rows = ui.selectedCells.map(([row]) => row);
  const columns = ui.selectedCells.map(([, column]) => column);
  const minY = indexToMillimeters(Math.min(...rows));
  const maxY = indexToMillimeters(Math.max(...rows));
  const minX = indexToMillimeters(Math.min(...columns));
  const maxX = indexToMillimeters(Math.max(...columns));
  const extentX = minX === maxX ? "X " + minX : "X " + minX + " à " + maxX;
  const extentY = minY === maxY ? "Y " + minY : "Y " + minY + " à " + maxY;
  const pending = ui.regionAnchor !== null ? " · choisis le second coin" : "";
  const plural = ui.selectedCells.length > 1 ? "s" : "";
  return ui.selectedCells.length + " point" + plural + " · " + extentX + " · " + extentY + pending;
}

function renderGrid(profile) {
  const matrix = matrixForView(profile);
  const values = matrix.flat().map(Number);
  const selected = selectedSet();
  const fragment = document.createDocumentFragment();
  let firstFocusableAssigned = false;
  for (const row of displayRowOrder()) {
    for (let column = 0; column < 11; column += 1) {
      const button = document.createElement("button");
      const value = matrix[row][column];
      const isSelected = selected.has(selectedKey(row, column));
      button.type = "button";
      button.className = "mesh-cell" + (isSelected ? " selected" : "") + (ui.comparison ? " comparison" : "");
      button.dataset.row = String(row);
      button.dataset.column = String(column);
      button.style.background = cellColor(value, values, ui.view === "delta");
      button.setAttribute("role", "gridcell");
      button.setAttribute("aria-selected", String(isSelected));
      const x = indexToMillimeters(column);
      const y = indexToMillimeters(row);
      button.setAttribute(
        "aria-label",
        "X " + x + " millimètres, Y " + y + " millimètres, " + numberText(value, 6, ui.view === "delta") + " millimètre",
      );
      button.title = "X " + x + " · Y " + y + " · " + numberText(value, 6, ui.view === "delta") + " mm";
      const label = document.createElement("span");
      if (ui.comparison) {
        label.textContent = numberText(profile.source_matrix[row][column], 3) + " → " + numberText(profile.final_matrix[row][column], 3);
      } else {
        label.textContent = numberText(value, 3, ui.view === "delta");
      }
      button.append(label);
      const shouldBeFocusable = !firstFocusableAssigned && (isSelected || selected.size === 0);
      button.tabIndex = shouldBeFocusable ? 0 : -1;
      if (button.tabIndex === 0) firstFocusableAssigned = true;
      button.addEventListener("click", () => selectCell(row, column));
      button.addEventListener("keydown", onCellKeydown);
      fragment.append(button);
    }
  }
  elements.grid.replaceChildren(fragment);
}

function pointMap(points) {
  const map = new Map();
  for (const point of points) map.set(selectedKey(point.row, point.column), point);
  return map;
}

function renderSurface(profile) {
  const canvas = elements.surface;
  const context = canvas.getContext("2d");
  const matrix = profile.final_matrix.map((row) => row.map(Number));
  const points = projectSurface(matrix, canvas.width, canvas.height);
  ui.projectedPoints = points;
  const byCell = pointMap(points);
  const selected = selectedSet();
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.lineWidth = 2;
  for (let row = 0; row < 11; row += 1) {
    context.beginPath();
    for (let column = 0; column < 11; column += 1) {
      const point = byCell.get(selectedKey(row, column));
      if (column === 0) context.moveTo(point.x, point.y);
      else context.lineTo(point.x, point.y);
    }
    context.strokeStyle = "rgba(121, 226, 181, 0.42)";
    context.stroke();
  }
  for (let column = 0; column < 11; column += 1) {
    context.beginPath();
    for (let row = 0; row < 11; row += 1) {
      const point = byCell.get(selectedKey(row, column));
      if (row === 0) context.moveTo(point.x, point.y);
      else context.lineTo(point.x, point.y);
    }
    context.strokeStyle = "rgba(100, 197, 212, 0.38)";
    context.stroke();
  }
  for (const point of points) {
    context.beginPath();
    context.arc(point.x, point.y, selected.has(selectedKey(point.row, point.column)) ? 7 : 3.5, 0, Math.PI * 2);
    context.fillStyle = selected.has(selectedKey(point.row, point.column))
      ? "#ffffff"
      : "hsl(" + (205 - point.zRatio * 170) + " 62% 58%)";
    context.fill();
  }
  context.fillStyle = "#91a4a6";
  context.font = "700 18px Segoe UI";
  context.fillText("APERÇU UNIQUEMENT · PAS DE TRAÎNÉE VERTICALE", 28, 38);
}

function renderHistory(profile) {
  elements.history.replaceChildren();
  for (const event of [...profile.history].reverse()) {
    const item = document.createElement("li");
    item.classList.toggle("redo-available", event.state === "redo_available");
    if (event.kind === "restore_source") {
      item.textContent = "#" + event.sequence + " · source restaurée";
    } else {
      const label = event.direction === "closer" ? "rapprocher" : "éloigner";
      item.textContent = "#" + event.sequence + " · " + label + " " + event.step_mm + " mm · " + event.selection.cells.length + " point(s)";
    }
    elements.history.append(item);
  }
  elements.historyCount.textContent = String(profile.history.length);
}

function renderEditor() {
  const profile = ui.status?.profile;
  const hasProfile = Boolean(profile);
  elements.empty.hidden = hasProfile;
  elements.editor.hidden = !hasProfile;
  elements.create.disabled = hasProfile || Boolean(ui.status?.busy);
  elements.create.textContent = hasProfile ? "Dérivation v001 créée" : "Créer la dérivation v001";
  elements.profileState.textContent = hasProfile ? profile.profile_id : "Aucun profil dérivé";
  elements.connectionState.textContent = ui.status?.busy ? "Chargement simulé" : "API simulée locale";
  if (!hasProfile) {
    elements.undo.disabled = true;
    elements.redo.disabled = true;
    elements.closer.disabled = true;
    elements.farther.disabled = true;
    elements.restore.disabled = true;
    elements.exportJson.disabled = true;
    elements.exportKlipper.disabled = true;
    return;
  }

  const surfaceMode = ui.view === "surface";
  elements.grid.hidden = surfaceMode;
  elements.surface.hidden = !surfaceMode;
  if (surfaceMode) renderSurface(profile);
  else renderGrid(profile);

  elements.selectionSummary.textContent = selectionSummary();
  elements.mean.textContent = numberText(profile.statistics.weighted_surface_mean_mm, 12) + " mm";
  elements.maximum.textContent = numberText(profile.statistics.max_absolute_normalized_delta_mm, 6) + " mm";
  elements.undo.disabled = !profile.can_undo || ui.status.busy;
  elements.redo.disabled = !profile.can_redo || ui.status.busy;
  elements.closer.disabled = ui.status.busy;
  elements.farther.disabled = ui.status.busy;
  elements.restore.disabled = ui.status.busy;
  elements.exportJson.disabled = ui.status.busy;
  elements.exportKlipper.disabled = ui.status.busy;
  renderHistory(profile);

  if (profile.warnings.length === 0) {
    elements.warnings.className = "notice success";
    elements.warnings.textContent = "Aucun avertissement.";
  } else {
    elements.warnings.className = "notice warning";
    elements.warnings.textContent = profile.warnings.join(" ");
  }
}

function render() {
  document.querySelectorAll("[data-view]").forEach((button) => {
    const active = button.dataset.view === ui.view;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  elements.compare.classList.toggle("active", ui.comparison);
  elements.compare.setAttribute("aria-pressed", String(ui.comparison));
  renderEditor();
}

async function refresh() {
  ui.status = await api("/api/mesh-editor/v1/status");
  render();
}

async function createProfile() {
  ui.status = await api("/api/mesh-editor/v1/profiles", {
    method: "POST",
    body: JSON.stringify({ source_id: SOURCE_ID, version: 1 }),
  });
  ui.selectedCells = [];
  ui.regionAnchor = null;
  render();
  showMessage("Profil dérivé v001 créé en mémoire locale.");
}

async function correct(direction) {
  if (ui.selectedCells.length === 0) {
    showMessage("Sélectionne au moins un point.", true);
    return;
  }
  const payload = {
    direction,
    step_mm: elements.step.value,
    selection: selectionPayload(elements.selectionMode.value, ui.selectedCells),
  };
  const result = await api(profilePath("corrections"), {
    method: "POST",
    body: JSON.stringify(payload),
  });
  ui.status.profile = result.state;
  ui.status.scenario = "ready";
  render();
  showMessage(direction === "closer" ? "Correction Rapprocher appliquée." : "Correction Éloigner appliquée.");
}

async function historyAction(action) {
  const result = await api(profilePath("actions"), {
    method: "POST",
    body: JSON.stringify({ action }),
  });
  ui.status.profile = result.state;
  if (action === "restore_source") ui.status.scenario = "restored";
  render();
  const message = action === "undo"
    ? "Dernière correction annulée."
    : action === "redo"
      ? "Correction rétablie."
      : "Source restaurée.";
  showMessage(message);
}

function download(name, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function exportProfile(format) {
  const content = await api(profilePath("export/" + format), {}, true);
  if (format === "json") {
    download(ui.status.profile.profile_id + ".json", content, "application/json");
  } else {
    download(ui.status.profile.profile_id + ".cfg", content, "text/plain");
  }
  showMessage("Export hors ligne préparé. Rien n’a été installé.");
}

async function setScenario(scenario) {
  ui.status = await api("/api/mesh-editor/v1/simulation", {
    method: "POST",
    body: JSON.stringify({ scenario }),
  });
  render();
  if (scenario === "validation_error") {
    showMessage("Le prochain changement sera refusé par la simulation.", true);
  } else if (scenario === "loading") {
    showMessage("État de chargement simulé.");
  } else if (scenario === "restored") {
    showMessage("État restauré simulé : la source est intacte.");
  } else {
    showMessage("Simulation revenue à l’état prêt.");
  }
}

elements.create.addEventListener("click", () => createProfile().catch((error) => showMessage(error.message, true)));
elements.closer.addEventListener("click", () => correct("closer").catch((error) => showMessage(error.message, true)));
elements.farther.addEventListener("click", () => correct("farther").catch((error) => showMessage(error.message, true)));
elements.undo.addEventListener("click", () => historyAction("undo").catch((error) => showMessage(error.message, true)));
elements.redo.addEventListener("click", () => historyAction("redo").catch((error) => showMessage(error.message, true)));
elements.restore.addEventListener("click", () => {
  if (window.confirm("Restaurer exactement la source et conserver cette action dans l’historique ?")) {
    historyAction("restore_source").catch((error) => showMessage(error.message, true));
  }
});
elements.compare.addEventListener("click", () => {
  ui.comparison = !ui.comparison;
  if (ui.comparison && ui.view === "surface") ui.view = "final";
  render();
});
elements.exportJson.addEventListener("click", () => exportProfile("json").catch((error) => showMessage(error.message, true)));
elements.exportKlipper.addEventListener("click", () => exportProfile("klipper").catch((error) => showMessage(error.message, true)));
elements.selectionMode.addEventListener("change", () => {
  ui.selectedCells = [];
  ui.regionAnchor = null;
  render();
});
document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    ui.view = button.dataset.view;
    render();
  });
});
document.querySelectorAll("[data-scenario]").forEach((button) => {
  button.addEventListener("click", () => setScenario(button.dataset.scenario).catch((error) => showMessage(error.message, true)));
});
elements.surface.addEventListener("click", (event) => {
  const rectangle = elements.surface.getBoundingClientRect();
  const x = (event.clientX - rectangle.left) * (elements.surface.width / rectangle.width);
  const y = (event.clientY - rectangle.top) * (elements.surface.height / rectangle.height);
  const point = nearestProjectedPoint(ui.projectedPoints, x, y, 28);
  if (point) selectCell(point.row, point.column);
});

refresh().catch((error) => {
  elements.connectionState.textContent = "API simulée indisponible";
  showMessage("Impossible d’ouvrir la simulation locale : " + error.message, true);
});
