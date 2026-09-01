/* Live mesh editor.
 *
 * The operator reads a printed square, decides that one point sits two
 * hundredths too close, and types it. Everything here serves that loop: the
 * value is edited in place, the correction is visible on the surface before it
 * is written, and nothing reaches the printer until Enregistrer is pressed.
 *
 * Two invariants are enforced on the page as well as on the printer, because a
 * rule the interface lets you break and the machine refuses afterwards is a
 * rule that wastes an evening: the probing point stays at zero (ADR-046), and a
 * single point never moves by more than MAX_MOVE.
 */

const MAX_MOVE = 0.15;
const REFERENCE = { x: 150, y: 150 };

const el = (id) => document.getElementById(id);
const ui = {
  profile: el("profile"), step: el("step"), grid: el("grid"),
  surface: el("surface"), status: el("status"),
  save: el("save"), revert: el("revert"), reload: el("reload"),
  badgeActive: el("badge-active"), badgeZ: el("badge-z"),
  statMin: el("stat-min"), statMax: el("stat-max"),
  statSpan: el("stat-span"), statEdits: el("stat-edits"),
  legendLow: el("legend-low"), legendHigh: el("legend-high"),
  roWhere: el("ro-where"), roOrigin: el("ro-origin"),
  roValue: el("ro-value"), roDelta: el("ro-delta"),
};

const state = {
  name: null, nx: 0, ny: 0,
  minX: 0, maxX: 0, minY: 0, maxY: 0,
  points: [], origin: [],
  selected: { i: 0, j: 0 },
  editing: false,
  undo: [],
  printerState: null,
  zOffsets: {},
  busy: false,
};

/* ------------------------------------------------------------------ geometry */
const axis = (lo, hi, count) =>
  count < 2 ? [lo] : Array.from({ length: count }, (_, k) => lo + ((hi - lo) / (count - 1)) * k);

const xsOf = () => axis(state.minX, state.maxX, state.nx);
const ysOf = () => axis(state.minY, state.maxY, state.ny);

const isReference = (i, j) =>
  Math.abs(xsOf()[i] - REFERENCE.x) < 1e-6 && Math.abs(ysOf()[j] - REFERENCE.y) < 1e-6;

const flat = () => state.points.flat();
const fmt = (v) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(3);

function editedCells() {
  const out = [];
  for (let j = 0; j < state.ny; j += 1) {
    for (let i = 0; i < state.nx; i += 1) {
      if (Math.abs(state.points[j][i] - state.origin[j][i]) > 1e-9) out.push([i, j]);
    }
  }
  return out;
}

/* -------------------------------------------------------------------- colour */
function ramp(value, low, high) {
  const span = Math.max(high - low, 1e-6);
  const t = Math.min(1, Math.max(0, (value - low) / span));
  // Blue where the bed sits low, warm where it rises, a dark neutral in the
  // middle so the flat majority recedes and the outliers are what you see.
  const stops = [
    [0.0, [58, 110, 168]],
    [0.5, [35, 48, 61]],
    [1.0, [194, 84, 61]],
  ];
  let a = stops[0];
  let b = stops[stops.length - 1];
  for (let k = 0; k < stops.length - 1; k += 1) {
    if (t >= stops[k][0] && t <= stops[k + 1][0]) { a = stops[k]; b = stops[k + 1]; }
  }
  const local = (t - a[0]) / Math.max(b[0] - a[0], 1e-6);
  const mix = a[1].map((channel, k) => Math.round(channel + (b[1][k] - channel) * local));
  return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`;
}

/* ---------------------------------------------------------------------- grid */
function buildGrid() {
  ui.grid.style.gridTemplateColumns = `2.6em repeat(${state.nx}, minmax(0, 1fr))`;
  ui.grid.replaceChildren();
  const xs = xsOf();
  const ys = ysOf();

  const corner = document.createElement("div");
  corner.className = "cell axis";
  corner.textContent = "Y\\X";
  ui.grid.append(corner);
  for (const x of xs) {
    const head = document.createElement("div");
    head.className = "cell axis";
    head.textContent = x.toFixed(0);
    ui.grid.append(head);
  }

  // Back of the bed on top: the grid is read the way the operator stands in
  // front of the machine, not the way the matrix is stored.
  for (let j = state.ny - 1; j >= 0; j -= 1) {
    const label = document.createElement("div");
    label.className = "cell axis";
    label.textContent = ys[j].toFixed(0);
    ui.grid.append(label);
    for (let i = 0; i < state.nx; i += 1) {
      const cell = document.createElement("div");
      cell.className = "cell";
      cell.dataset.i = String(i);
      cell.dataset.j = String(j);
      cell.addEventListener("mousedown", (event) => {
        event.preventDefault();
        select(i, j);
        if (!isReference(i, j)) beginEdit();
      });
      ui.grid.append(cell);
    }
  }
}

function cellAt(i, j) {
  return ui.grid.querySelector(`.cell[data-i="${i}"][data-j="${j}"]`);
}

function paint() {
  const values = flat();
  const low = Math.min(...values);
  const high = Math.max(...values);
  for (let j = 0; j < state.ny; j += 1) {
    for (let i = 0; i < state.nx; i += 1) {
      const cell = cellAt(i, j);
      if (!cell || cell.querySelector("input")) continue;
      const value = state.points[j][i];
      cell.textContent = value.toFixed(3);
      cell.style.background = ramp(value, low, high);
      cell.classList.toggle("edited", Math.abs(value - state.origin[j][i]) > 1e-9);
      cell.classList.toggle("locked", isReference(i, j));
      cell.classList.toggle(
        "selected", i === state.selected.i && j === state.selected.j);
    }
  }
  ui.statMin.textContent = fmt(low);
  ui.statMax.textContent = fmt(high);
  ui.statSpan.textContent = (high - low).toFixed(3);
  ui.legendLow.textContent = fmt(low);
  ui.legendHigh.textContent = fmt(high);

  const edits = editedCells();
  ui.statEdits.textContent = String(edits.length);
  const blocked = state.printerState === "printing";
  ui.save.disabled = state.busy || edits.length === 0 || blocked;
  ui.revert.disabled = state.busy || edits.length === 0;
  ui.save.title = blocked
    ? "Impossible pendant une impression : enregistrer recharge le maillage en cours"
    : "";
  readout();
  drawSurface();
}

function readout() {
  const { i, j } = state.selected;
  if (!state.points.length) return;
  const xs = xsOf();
  const ys = ysOf();
  const value = state.points[j][i];
  const before = state.origin[j][i];
  ui.roWhere.textContent = `X${xs[i].toFixed(0)}  Y${ys[j].toFixed(0)}`;
  ui.roOrigin.textContent = fmt(before);
  ui.roValue.textContent = fmt(value);
  const delta = value - before;
  ui.roDelta.textContent = Math.abs(delta) < 1e-9 ? "—" : fmt(delta);
}

/* ------------------------------------------------------------------ selection */
function select(i, j) {
  state.selected = {
    i: Math.min(state.nx - 1, Math.max(0, i)),
    j: Math.min(state.ny - 1, Math.max(0, j)),
  };
  paint();
  const cell = cellAt(state.selected.i, state.selected.j);
  if (cell) cell.scrollIntoView({ block: "nearest", inline: "nearest" });
}

function move(di, dj) {
  commitEdit();
  select(state.selected.i + di, state.selected.j + dj);
  ui.grid.focus();
}

/* -------------------------------------------------------------------- editing */
function beginEdit(seed = null) {
  const { i, j } = state.selected;
  if (state.editing || isReference(i, j)) return;
  const cell = cellAt(i, j);
  if (!cell) return;
  state.editing = true;
  const input = document.createElement("input");
  input.type = "text";
  input.inputMode = "decimal";
  input.value = seed === null ? state.points[j][i].toFixed(3) : seed;
  cell.textContent = "";
  cell.append(input);
  input.focus();
  if (seed === null) input.select();
  else input.setSelectionRange(input.value.length, input.value.length);

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (commitEdit()) { move(1, 0); beginEdit(); }
    } else if (event.key === "Escape") {
      event.preventDefault();
      cancelEdit();
      ui.grid.focus();
    } else if (event.key === "Tab") {
      event.preventDefault();
      if (commitEdit()) { move(event.shiftKey ? -1 : 1, 0); beginEdit(); }
    }
  });
  input.addEventListener("blur", () => commitEdit());
}

function closeEditor() {
  // paint() skips any cell holding an input so a value cannot be overwritten
  // under the cursor mid-typing. Nothing else removes that input, so closing
  // the editor has to do it explicitly or the cell stays stuck in edit mode
  // forever - which is exactly what happened the first time this was driven.
  const open = ui.grid.querySelector("input");
  if (open) open.remove();
}

function cancelEdit() {
  if (!state.editing) return;
  state.editing = false;
  closeEditor();
  paint();
}

function commitEdit() {
  if (!state.editing) return true;
  const { i, j } = state.selected;
  const cell = cellAt(i, j);
  const input = cell && cell.querySelector("input");
  if (!input) { state.editing = false; return true; }
  const raw = input.value.trim().replace(",", ".");
  state.editing = false;
  closeEditor();
  if (raw === "") { paint(); return true; }
  // The cell shows three decimals while a probed value carries six. Leaving an
  // editor without typing must therefore not rewrite the point to its own
  // rounding: an untouched -0.201691 would silently become -0.202, and moving
  // across a row would repaint the whole bed by a third of a hundredth.
  if (raw === state.points[j][i].toFixed(3)) { paint(); return true; }
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    say(`« ${raw} » n'est pas un nombre, le point n'a pas bougé`, "error");
    paint();
    return false;
  }
  return apply(i, j, value);
}

function apply(i, j, value) {
  const rounded = Math.round(value * 100000) / 100000;
  if (isReference(i, j)) {
    say("X150 Y150 est le zéro de référence du profil, il ne se retouche pas ; "
      + "c'est le décalage Z qui déplace tout le plateau", "error");
    paint();
    return false;
  }
  if (Math.abs(rounded) > 2) {
    say(`${fmt(rounded)} mm sort des limites ±2 mm`, "error");
    paint();
    return false;
  }
  const move = rounded - state.origin[j][i];
  if (Math.abs(move) > MAX_MOVE + 1e-9) {
    say(`${fmt(move)} mm d'écart avec le mesuré : au-delà de ${MAX_MOVE} mm `
      + "l'imprimante refusera l'enregistrement", "error");
    paint();
    return false;
  }
  if (Math.abs(rounded - state.points[j][i]) > 1e-9) {
    state.undo.push({ i, j, value: state.points[j][i] });
    state.points[j][i] = rounded;
  }
  paint();
  return true;
}

function nudge(direction) {
  const step = Number(ui.step.value);
  const { i, j } = state.selected;
  commitEdit();
  apply(i, j, state.points[j][i] + direction * step);
}

function undo() {
  const last = state.undo.pop();
  if (!last) { say("plus rien à défaire", "busy"); return; }
  state.points[last.j][last.i] = last.value;
  select(last.i, last.j);
}

/* -------------------------------------------------------------------- surface */
function project(width, height) {
  const values = flat();
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = Math.max(high - low, 1e-6);
  const halfW = width * 0.40;
  const depth = height * 0.155;
  const lift = height * 0.30;
  const base = height * 0.80;
  const nodes = [];
  for (let j = 0; j < state.ny; j += 1) {
    for (let i = 0; i < state.nx; i += 1) {
      const xr = i / Math.max(state.nx - 1, 1);
      const yr = j / Math.max(state.ny - 1, 1);
      const zr = (state.points[j][i] - low) / span;
      nodes.push({
        i, j,
        x: width * 0.5 + (xr - yr) * halfW,
        y: base - (xr + yr) * depth - zr * lift,
        depthKey: xr + yr,
        value: state.points[j][i],
      });
    }
  }
  return { nodes, low, high };
}

function drawSurface() {
  const canvas = ui.surface;
  const context = canvas.getContext("2d");
  const { width, height } = canvas;
  context.clearRect(0, 0, width, height);
  if (!state.points.length) return;
  const { nodes, low, high } = project(width, height);
  const at = (i, j) => nodes[j * state.nx + i];

  const quads = [];
  for (let j = 0; j < state.ny - 1; j += 1) {
    for (let i = 0; i < state.nx - 1; i += 1) {
      const corners = [at(i, j), at(i + 1, j), at(i + 1, j + 1), at(i, j + 1)];
      const mean = corners.reduce((sum, n) => sum + n.value, 0) / 4;
      quads.push({ corners, mean, key: corners.reduce((s, n) => s + n.depthKey, 0) });
    }
  }
  // Painter's order: the far side of the bed first, so the near side covers it.
  quads.sort((a, b) => b.key - a.key);
  for (const quad of quads) {
    context.beginPath();
    context.moveTo(quad.corners[0].x, quad.corners[0].y);
    for (const node of quad.corners.slice(1)) context.lineTo(node.x, node.y);
    context.closePath();
    context.fillStyle = ramp(quad.mean, low, high);
    context.fill();
    context.strokeStyle = "rgba(230, 237, 243, 0.14)";
    context.lineWidth = 1;
    context.stroke();
  }

  const chosen = at(state.selected.i, state.selected.j);
  for (const node of nodes) {
    const edited = Math.abs(node.value - state.origin[node.j][node.i]) > 1e-9;
    if (!edited) continue;
    context.beginPath();
    context.arc(node.x, node.y, 3.2, 0, Math.PI * 2);
    context.fillStyle = "#ffd24a";
    context.fill();
  }
  if (chosen) {
    context.beginPath();
    context.moveTo(chosen.x, chosen.y);
    context.lineTo(chosen.x, height * 0.93);
    context.strokeStyle = "rgba(255, 255, 255, 0.35)";
    context.setLineDash([3, 3]);
    context.stroke();
    context.setLineDash([]);
    context.beginPath();
    context.arc(chosen.x, chosen.y, 5.5, 0, Math.PI * 2);
    context.fillStyle = "#ffffff";
    context.fill();
    context.font = "600 12px ui-monospace, monospace";
    context.fillStyle = "#e6edf3";
    context.textAlign = "center";
    context.fillText(fmt(chosen.value), chosen.x, chosen.y - 11);
  }
}

ui.surface.addEventListener("mousedown", (event) => {
  if (!state.points.length) return;
  const rect = ui.surface.getBoundingClientRect();
  const scale = ui.surface.width / rect.width;
  const x = (event.clientX - rect.left) * scale;
  const y = (event.clientY - rect.top) * scale;
  const { nodes } = project(ui.surface.width, ui.surface.height);
  let best = null;
  let bestDistance = 26 * 26;
  for (const node of nodes) {
    const distance = (node.x - x) ** 2 + (node.y - y) ** 2;
    if (distance <= bestDistance) { best = node; bestDistance = distance; }
  }
  if (best) { commitEdit(); select(best.i, best.j); ui.grid.focus(); }
});

/* ------------------------------------------------------------------ keyboard */
ui.grid.addEventListener("keydown", (event) => {
  if (state.editing) return;
  const key = event.key;
  const moves = {
    ArrowLeft: [-1, 0], ArrowRight: [1, 0],
    ArrowUp: [0, 1], ArrowDown: [0, -1],
  };
  if (moves[key]) { event.preventDefault(); move(...moves[key]); return; }
  if (key === "Enter") { event.preventDefault(); beginEdit(); return; }
  if (key === "+" || key === "=") { event.preventDefault(); nudge(1); return; }
  if (key === "-" || key === "_") { event.preventDefault(); nudge(-1); return; }
  if (key === "Delete" || key === "Backspace") {
    event.preventDefault();
    const { i, j } = state.selected;
    apply(i, j, state.origin[j][i]);
    return;
  }
  if ((event.ctrlKey || event.metaKey) && key.toLowerCase() === "z") {
    event.preventDefault();
    undo();
    return;
  }
  if (/^[0-9.,+-]$/.test(key) && !event.ctrlKey && !event.metaKey) {
    event.preventDefault();
    beginEdit(key === "," ? "." : key);
  }
});

/* ----------------------------------------------------------------------- data */
function say(message, kind = "") {
  ui.status.textContent = message;
  ui.status.className = "status" + (kind ? " " + kind : "");
}

async function call(path, options) {
  const response = await fetch(path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function adopt(profile) {
  state.name = profile.name;
  state.nx = profile.x_count;
  state.ny = profile.y_count;
  state.minX = profile.min_x; state.maxX = profile.max_x;
  state.minY = profile.min_y; state.maxY = profile.max_y;
  state.points = profile.points.map((row) => row.map(Number));
  state.origin = profile.points.map((row) => row.map(Number));
  state.undo = [];
  state.selected = { i: 0, j: state.ny - 1 };
  ui.badgeActive.hidden = !profile.active;
  const z = state.zOffsets[profile.name.toLowerCase()];
  ui.badgeZ.hidden = z === undefined;
  if (z !== undefined) ui.badgeZ.textContent = `Z ${fmt(Number(z))}`;
  buildGrid();
  paint();
}

async function loadProfile(name) {
  say(`chargement de ${name}…`, "busy");
  const profile = await call(`/api/profile/${encodeURIComponent(name)}`);
  adopt(profile);
  say(`${name} chargé, ${state.nx}×${state.ny} points`
    + (state.printerState === "printing"
      ? " — impression en cours, l'enregistrement est bloqué" : ""),
    state.printerState === "printing" ? "busy" : "good");
}

async function refresh(keep = true) {
  const info = await call("/api/state");
  state.printerState = info.printer_state;
  state.zOffsets = info.z_offsets || {};
  const wanted = keep && state.name && info.profiles.includes(state.name)
    ? state.name
    : (info.profiles.includes(info.active) ? info.active : info.profiles[0]);
  ui.profile.replaceChildren();
  for (const name of info.profiles) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    option.selected = name === wanted;
    ui.profile.append(option);
  }
  if (!wanted) {
    say("aucun profil de maillage sur cette machine", "error");
    return;
  }
  await loadProfile(wanted);
}

async function save() {
  const edits = editedCells();
  if (!edits.length) return;
  commitEdit();
  state.busy = true;
  paint();
  say(`enregistrement de ${edits.length} point(s)…`, "busy");
  try {
    const result = await call("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: state.name, points: state.points }),
    });
    adopt(result.profile);
    say(result.messages.join("\n") || "enregistré", "good");
  } catch (error) {
    say("refusé : " + error.message, "error");
  } finally {
    state.busy = false;
    paint();
  }
}

ui.profile.addEventListener("change", () => {
  loadProfile(ui.profile.value).catch((error) => say(error.message, "error"));
});
ui.reload.addEventListener("click", () => {
  refresh(true).catch((error) => say(error.message, "error"));
});
ui.revert.addEventListener("click", () => {
  state.points = state.origin.map((row) => row.slice());
  state.undo = [];
  paint();
  say("retouches abandonnées, retour aux valeurs enregistrées", "good");
});
ui.save.addEventListener("click", () => save());

window.addEventListener("beforeunload", (event) => {
  if (editedCells().length) event.preventDefault();
});

refresh(false)
  .then(() => ui.grid.focus())
  .catch((error) => say(error.message, "error"));
