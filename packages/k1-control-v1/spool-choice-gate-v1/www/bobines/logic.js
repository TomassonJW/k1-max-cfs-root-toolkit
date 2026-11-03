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

// End status is published by the gate in the SAME query as print_stats.
// null/absent = legacy installation; malformed/present = observation lost.
export function endState(value) {
  const result = (kind, title, hint, blocked = true) => ({ kind, title, hint, blocked });
  if (value == null) return result("legacy", "", "", false);
  if (value.enabled === false && value.phase === "disabled" && value.pending === false) {
    return result("disabled", "", "", false);
  }
  if (value.thermal_failure) return result("failed", "Fin incomplète",
    "L'arrêt des chauffes n'est pas confirmé. Vérifiez immédiatement l'imprimante.");
  if (value.failure || ["failed", "shutdown"].includes(value.phase)) {
    return result("failed", "Fin incomplète",
      "La fin s'est arrêtée. Vérifiez le filament et la buse avant toute nouvelle impression. Aucun nouvel essai automatique.");
  }
  if (value.enabled !== true || typeof value.pending !== "boolean") {
    return result("unknown", "Fin non vérifiée", "L'état de fin est indisponible. Attendez son rétablissement.");
  }
  const phases = {
    waiting: "Le fichier est fini. La machine prépare la fin.",
    heating: "Vérification de la température avant le retrait.",
    cutting: "Coupe du filament en cours.",
    rewinding: "Rembobinage du filament en cours.",
    finalizing: "Rangement de la tête et arrêt des chauffes en cours.",
  };
  if (value.pending || phases[value.phase]) {
    return result("pending", "Fin en cours", phases[value.phase] || "La machine termine encore son cycle.");
  }
  if (value.phase === "complete") return result("complete", "Cycle de fin terminé",
    value.reason === "annulation" ? "L'impression a été annulée ; son cycle de fin est terminé." : "Le cycle de fin est terminé.", false);
  if (value.phase === "idle") return result("idle", "", "", false);
  return result("unknown", "Fin non vérifiée", "L'état de fin est indisponible. Attendez son rétablissement.");
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
  const end = endState(gate.end);
  if (end.blocked) view = "ending";
  return {
    end,
    endKey: String((gate.end || {}).job_epoch || 0) + ":" + end.kind,
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

// How long the window inside Mainsail stays to say the print left.
export const LAUNCHED_MS = 4000;

// The window inside Mainsail decides on its own when to be seen: "choice"
// while a start waits for its spools, "minimised" when the operator put this
// very file aside (a pill stays), "launched" for a moment after the launch
// the window itself sent, "hidden" otherwise so Mainsail keeps its own
// screens for everything else. A cancel, from here or from anywhere, and a
// restart of Klipper both end in "hidden" on the next poll.
export function overlayMode(state, model, now) {
  if (model && model.view === "ending") {
    return state.dismissedEndKey === model.endKey ? "minimised" : "ending";
  }
  if (model && model.view === "choice") {
    const key = pendingKey(model);
    return key && key === state.dismissedKey ? "minimised" : "choice";
  }
  if (state.launchedAt && now - state.launchedAt < LAUNCHED_MS) return "launched";
  return "hidden";
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

// ------------------------------------------------- what is left on a spool
// The spool manager (document 102), when installed, says what each slot
// holds and what is left on it. Without it the cards say nothing about what
// is left: the CFS's own figure is 100 % for every chipless spool, which is
// not a measure.

// A number in French: comma decimal, `decimals` places at most, none when
// the value is whole, rounded half away from zero, never "-0".
export function figure(value, decimals = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  const scale = 10 ** decimals;
  const rounded = Math.sign(number) * Math.round(Math.abs(number) * scale) / scale;
  return String(rounded === 0 ? 0 : rounded).replace(".", ",");
}

// Grams as a person reads them: one decimal under ten, whole above.
export function gramsLabel(value) {
  return figure(value, Math.abs(Number(value)) < 10 ? 1 : 0);
}

// The manager's status, keyed by slot: its verdict, what the CFS shows, the
// spool the library puts there and that spool's fiche. null when the answer
// is not the manager's.
export function spoolSlots(status) {
  if (!status || !Array.isArray(status.slots)) return null;
  const spools = {};
  for (const spool of Array.isArray(status.spools) ? status.spools : []) {
    if (spool && spool.id) spools[spool.id] = spool;
  }
  const fiches = status.filaments && typeof status.filaments === "object" ? status.filaments : {};
  const slots = {};
  for (const view of status.slots) {
    if (!view || typeof view.slot !== "string") continue;
    const spool = (view.spool && spools[view.spool]) || null;
    slots[view.slot] = {
      status: String(view.status || ""),
      observed: view.observed || {},
      spool,
      fiche: (spool && fiches[spool.filament]) || null,
    };
  }
  return {
    slots,
    verified: status.counting_verified === true,
    printing: Boolean(status.klippy && status.klippy.printing),
  };
}

// What the card of a slot says is left, or null to say nothing: the
// library's count when its spool is the one the CFS shows, else the figure a
// chip carries.
export function slotRemaining(known) {
  if (!known) return null;
  if (known.status === "a_verifier") {
    return { text: "à vérifier", level: "warn", kind: "check", counted: false, note: "" };
  }
  const spool = known.spool;
  if (spool && (known.status === "ok" || known.status === "en_attente_cfs")) {
    const remaining = spool.remaining || {};
    const note = known.status === "en_attente_cfs" ? "écriture au CFS en attente" : "";
    if (remaining.exhausted) {
      return { text: "épuisée selon le décompte", level: "low", kind: "spool", counted: true, note };
    }
    const shown = remaining.shown;
    if (shown && Number.isFinite(Number(shown.g))) {
      const parts = ["~" + figure(shown.g, 0) + " g"];
      if (shown.percent != null) parts.push(figure(shown.percent, 0) + " %");
      if (shown.m != null) parts.push(figure(shown.m) + " m");
      return {
        text: parts.join(" · "), level: spool.low ? "low" : "", kind: "spool",
        counted: Number(spool.counted_g) > 0, note,
      };
    }
  }
  const chip = known.observed ? known.observed.chip : null;
  if (typeof chip === "number" && Number.isFinite(chip)) {
    return { text: "puce " + figure(chip, 0) + " %", level: "", kind: "chip", counted: false, note: "" };
  }
  return null;
}

// A chipless spool the CFS holds but could not name: the start window cannot
// give it to a filament, and it is not an empty slot either.
export function unidentified(known) {
  return Boolean(known && known.observed && known.observed.present === true && !known.observed.material);
}

export function unidentifiedSlots(model, info) {
  if (!info) return [];
  return model.slots
    .filter((slot) => Number(slot.loaded) !== 1 && unidentified(info.slots[slot.name]))
    .map((slot) => ({ slot: slot.name, label: info.slots[slot.name].spool ? info.slots[slot.name].spool.label || "" : "" }));
}

// While a start waits, the CFS takes no write: the way to use such a spool
// is to put this start aside.
export function unidentifiedNote(items) {
  if (!items.length) return "";
  const one = items.length === 1;
  return items.map((item) => item.slot + (item.label ? " (" + item.label + ")" : "")).join(", ")
    + (one ? " : bobine sans puce que le CFS n'a pas identifiée, elle ne peut pas servir à ce départ."
      : " : bobines sans puce que le CFS n'a pas identifiées, elles ne peuvent pas servir à ce départ.")
    + " Pour " + (one ? "l'utiliser" : "les utiliser") + " : abandonner, " + (one ? "l'identifier" : "les identifier")
    + " avec le bouton Bobines de Mainsail, puis relancer le fichier.";
}

// The grams a file plans for one filament: the slicer's own figure, or its
// length weighed with the spool's fiche when the slicer gave none.
export function plannedGrams(item, fiche) {
  if (!item) return null;
  const grams = Number(item.g);
  if (Number.isFinite(grams) && grams > 0) return grams;
  const mm = Number(item.mm);
  const density = fiche ? Number(fiche.density) : NaN;
  const diameter = fiche ? Number(fiche.diameter_mm) : NaN;
  if (!(mm > 0) || !(density > 0) || !(diameter > 0)) return null;
  const radius = diameter / 2;
  return mm / 1000 * density * Math.PI * radius * radius;
}

// Under this share above what the file plans, a spool is said to be tight.
export const MARGIN = 0.1;

// Spools that may not hold what the file plans for their filament. The
// count is an estimate and the CFS purges are not in the file: a warning,
// never a block.
export function shortfalls(filaments, assignments, info, planned) {
  const out = [];
  if (!info || !planned || !Array.isArray(planned.items)) return out;
  for (const entry of usedFilaments(filaments)) {
    const slot = assignments[entry.logical];
    const known = slot ? info.slots[slot] : null;
    if (!known || !known.spool || !(known.status === "ok" || known.status === "en_attente_cfs")) continue;
    const left = known.spool.remaining ? known.spool.remaining.net_g : null;
    if (typeof left !== "number" || !Number.isFinite(left)) continue;
    const need = plannedGrams(planned.items[entry.index], known.fiche);
    if (need == null) continue;
    if (left < need) {
      out.push({ slot, level: "short",
        text: slot + " : reste ~" + gramsLabel(left) + " g, le fichier en demande ~" + gramsLabel(need) + " g" });
    } else if (left < need * (1 + MARGIN)) {
      out.push({ slot, level: "tight",
        text: slot + " : reste ~" + gramsLabel(left) + " g pour ~" + gramsLabel(need) + " g demandés, marge faible" });
    }
  }
  return out;
}

// The count adds the file's figures and the CFS's motion; until a weighing
// has checked it once, a remaining that rests on it says so.
export function countingUnverified(info) {
  if (!info || info.verified) return false;
  return Object.values(info.slots).some((known) => known.spool
    && (known.status === "ok" || known.status === "en_attente_cfs")
    && (Number(known.spool.counted_g) > 0 || Boolean(known.spool.remaining && known.spool.remaining.exhausted)));
}

// The notes over the launch button, most pressing first. None blocks.
export function startNotes(model, assignments, info, planned) {
  if (!info) return [];
  const notes = shortfalls(model.filaments, assignments, info, planned);
  const unknown = unidentifiedSlots(model, info);
  if (unknown.length) notes.push({ slot: "", level: "warn", text: unidentifiedNote(unknown) });
  if (countingUnverified(info)) notes.push({ slot: "", level: "faint", text: "décompte non encore vérifié par pesée" });
  return notes;
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
