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

/* Held keys repeat every ~30 ms once the system autorepeat starts. Nudging by
 * one step each time would crawl, so a sustained burst widens the step - but
 * always by a whole multiple of it, so a point stays on the round values the
 * operator chose and never lands on 0.0175. */
const BURST_WINDOW = 400;
const BURST_STEPS = [[16, 4], [6, 2]];

const el = (id) => document.getElementById(id);
const ui = {
  profile: el("profile"), step: el("step"), grid: el("grid"),
  surface: el("surface"), status: el("status"),
  minus: el("minus"), plus: el("plus"), roStep: el("ro-step"),
  ring: el("ring"), roCount: el("ro-count"),
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
  // selected is the cell under the cursor - the one the readout describes and
  // the one a typed value lands in. anchor is where a rectangle selection
  // started. marks is everything a nudge moves, and it always holds selected.
  selected: { i: 0, j: 0 },
  anchor: { i: 0, j: 0 },
  marks: new Set(["0:0"]),
  editing: false,
  undo: [],
  printerState: null,
  zOffsets: {},
  busy: false,
  burst: { direction: 0, count: 0, at: 0, i: -1, j: -1 },
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
      // A single click selects and nothing more. Opening the text editor here
      // is what made "clique un point puis appuie sur +" impossible: the input
      // swallowed the key and typed a plus sign into the value. Typing is still
      // one gesture away - double click, Entrée, or just start typing digits.
      cell.addEventListener("mousedown", (event) => {
        event.preventDefault();
        commitEdit();
        // Spreadsheet gestures, because those are the ones already in the
        // fingers: Shift stretches a rectangle, Ctrl adds or drops one point.
        if (event.shiftKey) extend(i, j);
        else if (event.ctrlKey || event.metaKey) toggle(i, j);
        else select(i, j);
        ui.grid.focus();
      });
      cell.addEventListener("dblclick", (event) => {
        event.preventDefault();
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
      cell.classList.toggle("in-selection", marked(i, j));
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
  const count = movable().length;
  ui.roCount.textContent = count > 1 ? `${count} points` : "1 point";
  ui.roStep.textContent = count ? Number(ui.step.value).toFixed(3) : "—";
  ui.minus.disabled = count === 0;
  ui.plus.disabled = count === 0;
  ui.ring.disabled = markedCells().length < 2;
}

/* ------------------------------------------------------------------ selection */
const mark = (i, j) => `${i}:${j}`;

function marked(i, j) {
  return state.marks.has(mark(i, j));
}

function markedCells() {
  const out = [];
  for (const key of state.marks) {
    const [i, j] = key.split(":").map(Number);
    if (i >= 0 && i < state.nx && j >= 0 && j < state.ny) out.push({ i, j });
  }
  return out;
}

function movable() {
  // The probing point is the profile's zero (ADR-046). It sits inside any wide
  // rectangle, so a group correction skips it rather than being refused - being
  // unable to correct a whole edge because its middle is locked would be absurd.
  return markedCells().filter(({ i, j }) => !isReference(i, j));
}

function place(i, j) {
  state.selected = {
    i: Math.min(state.nx - 1, Math.max(0, i)),
    j: Math.min(state.ny - 1, Math.max(0, j)),
  };
  const cell = cellAt(state.selected.i, state.selected.j);
  if (cell) cell.scrollIntoView({ block: "nearest", inline: "nearest" });
}

function select(i, j) {
  place(i, j);
  state.anchor = { ...state.selected };
  state.marks = new Set([mark(state.selected.i, state.selected.j)]);
  paint();
}

function extend(i, j) {
  // The rectangle always redraws from the anchor, so walking the cursor around
  // grows and shrinks the same selection instead of accumulating leftovers.
  place(i, j);
  const marks = new Set();
  const [i0, i1] = [state.anchor.i, state.selected.i].sort((a, b) => a - b);
  const [j0, j1] = [state.anchor.j, state.selected.j].sort((a, b) => a - b);
  for (let y = j0; y <= j1; y += 1) {
    for (let x = i0; x <= i1; x += 1) marks.add(mark(x, y));
  }
  state.marks = marks;
  paint();
}

function toggle(i, j) {
  place(i, j);
  state.anchor = { ...state.selected };
  const key = mark(state.selected.i, state.selected.j);
  if (state.marks.has(key) && state.marks.size > 1) state.marks.delete(key);
  else state.marks.add(key);
  // The cursor must stay inside the selection or the readout would describe a
  // point that no + or - is about to move.
  if (!state.marks.has(key)) {
    const first = markedCells()[0];
    if (first) place(first.i, first.j);
  }
  paint();
}

function keepOnlyRing() {
  // A ring is the shape defects actually come in: the outer edge of the plate,
  // then the one just inside it. A rectangle cannot draw one, and clicking
  // eighty interior points out of a full grid is not an option.
  const cells = markedCells();
  if (cells.length < 2) return;
  const is = cells.map((c) => c.i);
  const js = cells.map((c) => c.j);
  const i0 = Math.min(...is); const i1 = Math.max(...is);
  const j0 = Math.min(...js); const j1 = Math.max(...js);
  const marks = new Set();
  for (const { i, j } of cells) {
    if (i === i0 || i === i1 || j === j0 || j === j1) marks.add(mark(i, j));
  }
  if (!marks.size) return;
  state.marks = marks;
  if (!marked(state.selected.i, state.selected.j)) {
    const first = markedCells()[0];
    if (first) place(first.i, first.j);
  }
  paint();
  say(`couronne : ${marks.size} point(s) retenus, l'intérieur est relâché`, "good");
}

function move(di, dj, widen = false) {
  commitEdit();
  if (widen) extend(state.selected.i + di, state.selected.j + dj);
  else select(state.selected.i + di, state.selected.j + dj);
  ui.grid.focus();
}

/* -------------------------------------------------------------------- editing */
function beginEdit(seed = null) {
  const { i, j } = state.selected;
  if (state.editing || isReference(i, j)) return;
  const cell = cellAt(i, j);
  if (!cell) return;
  if (state.marks.size > 1) {
    // A typed value is absolute. Writing the same one into forty points would
    // flatten the relief the probe measured, so typing stays on this one cell
    // and the selection survives for the next nudge.
    say(`saisie sur X${xsOf()[i].toFixed(0)} Y${ysOf()[j].toFixed(0)} `
      + `uniquement ; les ${state.marks.size} points restent sélectionnés `
      + "pour les touches + et −", "busy");
  }
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

function refusal(i, j, value) {
  if (isReference(i, j)) {
    return "X150 Y150 est le zéro de référence du profil, il ne se retouche "
      + "pas ; c'est le décalage Z qui déplace tout le plateau";
  }
  if (Math.abs(value) > 2) return `${fmt(value)} mm sort des limites ±2 mm`;
  const gap = value - state.origin[j][i];
  if (Math.abs(gap) > MAX_MOVE + 1e-9) {
    return `X${xsOf()[i].toFixed(0)} Y${ysOf()[j].toFixed(0)} : ${fmt(gap)} mm `
      + `d'écart avec le mesuré, au-delà de ${MAX_MOVE} mm l'imprimante `
      + "refusera l'enregistrement";
  }
  return null;
}

/* Writes are atomic on purpose. If one point of a group cannot take the
 * correction, none of them do: half a moved edge looks like a corrected edge on
 * the surface, and the point left behind is invisible until it prints. */
function commit(changes) {
  for (const { i, j, value } of changes) {
    const refused = refusal(i, j, value);
    if (refused) { say(refused, "error"); paint(); return false; }
  }
  const undoGroup = [];
  for (const { i, j, value } of changes) {
    if (Math.abs(value - state.points[j][i]) <= 1e-9) continue;
    undoGroup.push({ i, j, value: state.points[j][i] });
  }
  if (undoGroup.length) {
    state.undo.push(undoGroup);
    for (const { i, j, value } of changes) state.points[j][i] = value;
  }
  paint();
  return true;
}

const round5 = (value) => Math.round(value * 100000) / 100000;

function apply(i, j, value) {
  return commit([{ i, j, value: round5(value) }]);
}

function burstFactor(direction, i, j, now) {
  // A burst is consecutive presses in the same direction on the same point.
  // Changing direction or point restarts it, so a correction never runs away
  // because of keys pressed a minute earlier.
  const burst = state.burst;
  const continued = burst.direction === direction && burst.i === i
    && burst.j === j && now - burst.at < BURST_WINDOW;
  burst.count = continued ? burst.count + 1 : 1;
  burst.direction = direction;
  burst.i = i;
  burst.j = j;
  burst.at = now;
  for (const [threshold, factor] of BURST_STEPS) {
    if (burst.count >= threshold) return factor;
  }
  return 1;
}

function nudge(direction) {
  commitEdit();
  const cells = movable();
  if (!cells.length) {
    say("X150 Y150 est le zéro de référence, il ne se déplace pas", "error");
    return;
  }
  const { i, j } = state.selected;
  const step = Number(ui.step.value);
  const now = (typeof performance === "object" ? performance.now() : Date.now());
  const factor = burstFactor(direction, i, j, now);
  const delta = direction * step * factor;
  const before = state.points[j][i];
  if (!commit(cells.map((cell) => ({
    ...cell, value: round5(state.points[cell.j][cell.i] + delta),
  })))) return;
  const suffix = factor > 1 ? ` (rafale : pas ×${factor})` : "";
  const skipped = markedCells().length - cells.length;
  if (cells.length === 1) {
    say(`X${xsOf()[i].toFixed(0)} Y${ysOf()[j].toFixed(0)} : `
      + `${fmt(before)} → ${fmt(state.points[j][i])}${suffix}`, "good");
  } else {
    say(`${cells.length} points déplacés de ${fmt(delta)} mm${suffix}`
      + (skipped ? " (X150 Y150 laissé en place)" : ""), "good");
  }
}

function undo() {
  // One group correction undoes in one keystroke. Undoing forty points one by
  // one would be worse than not offering the group move at all.
  const group = state.undo.pop();
  if (!group) { say("plus rien à défaire", "busy"); return; }
  for (const { i, j, value } of group) state.points[j][i] = value;
  place(group[0].i, group[0].j);
  state.anchor = { ...state.selected };
  state.marks = new Set(group.map(({ i, j }) => mark(i, j)));
  paint();
  say(`${group.length} point(s) remis à leur valeur précédente`, "good");
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
    if (edited) {
      context.beginPath();
      context.arc(node.x, node.y, 3.2, 0, Math.PI * 2);
      context.fillStyle = "#ffd24a";
      context.fill();
    }
    // The selection has to read on the surface too: a whole edge picked in the
    // grid is only obviously the right edge once it is seen in perspective.
    if (marked(node.i, node.j)) {
      context.beginPath();
      context.arc(node.x, node.y, 5, 0, Math.PI * 2);
      context.strokeStyle = "rgba(255, 255, 255, 0.75)";
      context.lineWidth = 1.5;
      context.stroke();
    }
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
  // The canvas is object-fit: contain, so on a short window the drawing is
  // letterboxed inside its box. Scaling by the box alone would offset every
  // pick, and picking the wrong vertex on a bed mesh is not a visible mistake.
  const rect = ui.surface.getBoundingClientRect();
  const fit = Math.min(
    rect.width / ui.surface.width, rect.height / ui.surface.height);
  const x = (event.clientX - rect.left - (rect.width - ui.surface.width * fit) / 2) / fit;
  const y = (event.clientY - rect.top - (rect.height - ui.surface.height * fit) / 2) / fit;
  const { nodes } = project(ui.surface.width, ui.surface.height);
  let best = null;
  let bestDistance = 26 * 26;
  for (const node of nodes) {
    const distance = (node.x - x) ** 2 + (node.y - y) ** 2;
    if (distance <= bestDistance) { best = node; bestDistance = distance; }
  }
  if (!best) return;
  commitEdit();
  if (event.shiftKey) extend(best.i, best.j);
  else if (event.ctrlKey || event.metaKey) toggle(best.i, best.j);
  else select(best.i, best.j);
  ui.grid.focus();
});

/* ------------------------------------------------------------------ keyboard */
ui.grid.addEventListener("keydown", (event) => {
  if (state.editing) return;
  const key = event.key;
  const moves = {
    ArrowLeft: [-1, 0], ArrowRight: [1, 0],
    ArrowUp: [0, 1], ArrowDown: [0, -1],
  };
  if (moves[key]) {
    event.preventDefault();
    move(moves[key][0], moves[key][1], event.shiftKey);
    return;
  }
  if ((event.ctrlKey || event.metaKey) && key.toLowerCase() === "a") {
    event.preventDefault();
    state.anchor = { i: 0, j: 0 };
    extend(state.nx - 1, state.ny - 1);
    say(`plateau entier sélectionné : ${movable().length} points déplaçables`,
      "good");
    return;
  }
  if (key === " ") { event.preventDefault(); toggle(state.selected.i, state.selected.j); return; }
  if (key === "Escape") { event.preventDefault(); select(state.selected.i, state.selected.j); return; }
  if (key === "Enter") { event.preventDefault(); beginEdit(); return; }
  // PageUp/PageDown are there for the French keyboard, where + costs a Shift.
  if (key === "+" || key === "=" || key === "PageUp") {
    event.preventDefault(); nudge(1); return;
  }
  if (key === "-" || key === "_" || key === "PageDown") {
    event.preventDefault(); nudge(-1); return;
  }
  if (key === "Delete" || key === "Backspace") {
    event.preventDefault();
    const cells = movable().filter(
      ({ i, j }) => Math.abs(state.points[j][i] - state.origin[j][i]) > 1e-9);
    if (!cells.length) { say("rien à annuler ici, déjà au mesuré", "busy"); return; }
    if (commit(cells.map(({ i, j }) => ({ i, j, value: state.origin[j][i] })))) {
      say(`${cells.length} point(s) revenus à la valeur mesurée`, "good");
    }
    return;
  }
  if ((event.ctrlKey || event.metaKey) && key.toLowerCase() === "z") {
    event.preventDefault();
    undo();
    return;
  }
  // + and - are consumed above as nudges, so they are not seeds here. A
  // negative value is still typed the usual way: open the editor on Entrée or
  // by double clicking, and the existing value comes up selected.
  if (/^[0-9.,]$/.test(key) && !event.ctrlKey && !event.metaKey) {
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
  state.anchor = { ...state.selected };
  state.marks = new Set([mark(state.selected.i, state.selected.j)]);
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

for (const [button, direction] of [[ui.minus, -1], [ui.plus, 1]]) {
  // mousedown, not click: a held button then repeats through the same burst
  // path as a held key, and the grid keeps the focus so the keyboard stays live.
  button.addEventListener("mousedown", (event) => {
    event.preventDefault();
    nudge(direction);
    ui.grid.focus();
  });
}
ui.step.addEventListener("change", () => { readout(); ui.grid.focus(); });
ui.ring.addEventListener("click", () => { keepOnlyRing(); ui.grid.focus(); });

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
