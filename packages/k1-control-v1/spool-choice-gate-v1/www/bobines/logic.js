// Pure functions behind the Bobines page. No DOM, no network: everything
// here is exercised by logic.test.mjs under node, and the page only wires
// these results to the screen.

export const NAMES = (() => {
  const out = [];
  for (const box of ["1", "2", "3", "4"]) {
    for (const slot of ["A", "B", "C", "D"]) out.push("T" + box + slot);
  }
  return out;
})();

// Six upper-case hex digits or "". Accepts "#8080FF" (the sliced file),
// "0ff1e1e" (the CFS, seven characters with a leading zero) and "ffffff".
export function normaliseHex(text) {
  let value = String(text == null ? "" : text).trim().replace(/^#/, "").toUpperCase();
  if (value.length === 7 && value[0] === "0") value = value.slice(1);
  return /^[0-9A-F]{6}$/.test(value) ? value : "";
}

export function hexToRgb(hex) {
  const value = normaliseHex(hex);
  if (!value) return null;
  return {
    r: parseInt(value.slice(0, 2), 16),
    g: parseInt(value.slice(2, 4), 16),
    b: parseInt(value.slice(4, 6), 16),
  };
}

export function rgbToHsl({ r, g, b }) {
  const rr = r / 255, gg = g / 255, bb = b / 255;
  const max = Math.max(rr, gg, bb), min = Math.min(rr, gg, bb);
  const l = (max + min) / 2;
  if (max === min) return { h: 0, s: 0, l };
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h;
  if (max === rr) h = ((gg - bb) / d + (gg < bb ? 6 : 0)) * 60;
  else if (max === gg) h = ((bb - rr) / d + 2) * 60;
  else h = ((rr - gg) / d + 4) * 60;
  return { h, s, l };
}

// A French name a person would give the colour, so that "bleu clair" and
// "bleu marine" read differently even before the swatch is looked at.
export function colourName(hex) {
  const rgb = hexToRgb(hex);
  if (!rgb) return "couleur inconnue";
  const { h, s, l } = rgbToHsl(rgb);
  if (l <= 0.11) return "noir";
  if (l >= 0.93 && s <= 0.25) return "blanc";
  if (s <= 0.12) {
    if (l >= 0.8) return "gris clair";
    if (l <= 0.3) return "gris foncé";
    return "gris";
  }
  let base;
  if (h < 12 || h >= 345) base = "rouge";
  else if (h < 40) base = (l < 0.4 && s < 0.7) ? "marron" : "orange";
  else if (h < 68) base = "jaune";
  else if (h < 160) base = "vert";
  else if (h < 195) base = "turquoise";
  else if (h < 255) base = "bleu";
  else if (h < 290) base = "violet";
  else base = "rose";
  if (base === "orange" && l >= 0.75) return "beige";
  if (base === "rouge" && l >= 0.8) return "rose pâle";
  if (base === "bleu" && l <= 0.3) return "bleu marine";
  if (l >= 0.7) return base + " clair";
  if (l <= 0.28) return base + " foncé";
  return base;
}

// Whether a swatch needs a visible ring to be seen on a dark page.
export function isLight(hex) {
  const rgb = hexToRgb(hex);
  if (!rgb) return false;
  return (0.2126 * rgb.r + 0.7152 * rgb.g + 0.0722 * rgb.b) / 255 > 0.6;
}

export function textOn(hex) {
  return isLight(hex) ? "#111" : "#fff";
}

// The page's view of the printer, from one status query.
export function buildModel(status) {
  const gate = (status && status.kctrl_print_gate) || {};
  const stats = (status && status.print_stats) || {};
  const state = String(stats.state || "");
  const slots = NAMES.filter((name) => gate.slots && gate.slots[name])
    .map((name) => Object.assign({ name }, gate.slots[name]));
  const filaments = (gate.filaments || []).map((entry) => Object.assign({}, entry));
  let view = "idle";
  if (state === "printing" || state === "paused") view = "printing";
  else if (Number(gate.pending) === 1) view = "choice";
  return {
    view,
    state,
    wrapped: Number(gate.wrapped) === 1,
    page: gate.page || "",
    pending: Number(gate.pending) === 1,
    file: gate.file || "",
    name: gate.name || "",
    since: Number(gate.since) || 0,
    note: gate.note || "",
    filaments,
    usedCount: Number(gate.used_count) || 0,
    declaredCount: Number(gate.declared_count) || 0,
    slots,
    units: gate.units || [],
    table: gate.table || {},
    confirmedName: gate.confirmed_name || "",
    confirmedMap: gate.confirmed_map || {},
    printingName: stats.filename || "",
    last: gate.last || "",
  };
}

// A key that changes whenever the choice on screen must be rebuilt: another
// file, or the same file held again. Whole seconds, so a float printed two
// ways never throws a choice away.
export function pendingKey(model) {
  return model.pending ? model.file + "@" + Math.floor(model.since) : "";
}

// Give `slot` to `logical`; a spool belongs to one filament at a time, so
// it is taken away from whoever had it. Choosing the same pair again
// disconnects it.
export function assign(assignments, logical, slot) {
  const next = {};
  for (const key of Object.keys(assignments)) {
    if (key === logical) continue;
    if (assignments[key] === slot) continue;
    next[key] = assignments[key];
  }
  if (assignments[logical] !== slot) next[logical] = slot;
  return next;
}

export function usedFilaments(filaments) {
  return filaments.filter((entry) => Number(entry.used) === 1);
}

export function completeness(filaments, assignments) {
  const missing = usedFilaments(filaments)
    .filter((entry) => !assignments[entry.logical])
    .map((entry) => entry.logical);
  return { complete: missing.length === 0 && usedFilaments(filaments).length > 0, missing };
}

// The filament to work on after `current` was just connected: the first
// used one without a spool, or nothing when the choice is complete.
export function nextToConnect(filaments, assignments) {
  const open = usedFilaments(filaments).find((entry) => !assignments[entry.logical]);
  return open ? open.logical : null;
}

export function mapParam(assignments) {
  return NAMES.filter((name) => assignments[name])
    .map((name) => name + ":" + assignments[name]).join(",");
}

// What connecting `filament` to `slot` means: same spool, same material with
// another colour, another material, or an empty slot.
export function compatibility(filament, slot) {
  if (!slot || Number(slot.loaded) !== 1) {
    return { level: "empty", label: "vide", exact: false };
  }
  const wantType = String(filament.type || "").toUpperCase();
  const haveType = String(slot.type || "").toUpperCase();
  const wantColour = normaliseHex(filament.colour);
  const haveColour = normaliseHex(slot.colour);
  if (!wantType) {
    return { level: "unknown", label: "matière du fichier inconnue", exact: false };
  }
  if (wantType !== haveType) {
    return {
      level: "type",
      label: "autre matière : " + (haveType || "?") + " au lieu de " + wantType,
      exact: false,
    };
  }
  if (wantColour && haveColour === wantColour) {
    return { level: "exact", label: "identique au fichier", exact: true };
  }
  return { level: "colour", label: "même matière, autre couleur", exact: false };
}

export function remainingLabel(remain) {
  const value = Number(remain);
  if (!Number.isFinite(value) || value < 0) return "";
  return "reste " + Math.round(value) + " %";
}

export function elapsedLabel(sinceSeconds, nowSeconds) {
  const delta = Math.max(0, Math.floor(nowSeconds - sinceSeconds));
  if (delta < 60) return "depuis " + delta + " s";
  const minutes = Math.floor(delta / 60);
  if (minutes < 60) return "depuis " + minutes + " min";
  return "depuis " + Math.floor(minutes / 60) + " h " + String(minutes % 60).padStart(2, "0");
}

export function shortName(path) {
  const text = String(path || "");
  const cut = text.lastIndexOf("/");
  return cut >= 0 ? text.slice(cut + 1) : text;
}

// The summary line under the launch button, in plain words.
export function summaryLine(filaments, assignments) {
  const used = usedFilaments(filaments);
  const done = used.filter((entry) => assignments[entry.logical]).length;
  if (used.length === 0) return "Le fichier n'utilise aucun filament.";
  if (done === used.length) {
    return used.length === 1
      ? "Le filament est raccordé, tout est prêt."
      : "Les " + used.length + " filaments sont raccordés, tout est prêt.";
  }
  const left = used.length - done;
  return left === 1
    ? "Encore un filament à raccorder."
    : "Encore " + left + " filaments à raccorder.";
}
