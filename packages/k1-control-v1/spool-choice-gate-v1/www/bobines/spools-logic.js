// The Bobines window inside Mainsail, pure part: the calculator, the labels,
// the stock filters and the journal lines that spools.js draws. No DOM, no
// network, so spools-logic.test.mjs runs it in node.
//
// The calculator mirrors kctrl_spools_model.py operation for operation: the
// same order of multiplications and divisions gives the very doubles the K1
// keeps, and calculator-vectors.json, written by the Python model, holds the
// cases both sides must agree on. The K1 checks every value again: what is
// computed here only fills the fields while Thomas types.
import { colourName, figure, gramsLabel } from "./logic.js";

export const DIAMETER = 1.75;
export const SLOT_NAMES = ["1", "2", "3", "4"].flatMap((unit) => ["A", "B", "C", "D"].map((letter) => "T" + unit + letter));
export const NAME_LIMIT = 80;
export const NOTES_LIMIT = 500;
export const VALUE_MAX_G = 15000;
export const NEARLY_EMPTY_G = 20;

// ---------------------------------------------------------------- calculator
// Python's round_half_away: 2.5 gives 3, -2.5 gives -3, and never -0.
export function roundHalfAway(value, digits = 0) {
  const scale = 10 ** digits;
  const result = Math.floor(Math.abs(value) * scale + 0.5) / scale;
  if (result === 0) return 0;
  return value < 0 ? -result : result;
}

export function gramsPerMetre(density, diameter) {
  const radius = diameter / 2.0;
  return density * Math.PI * radius * radius;
}

export function grossBelowTare(grossG, tareG) {
  return "poids brut " + figure(grossG) + " g inférieur à la tare " + figure(tareG)
    + " g de la bobine vide : vérifier la pesée ou le type de bobine vide";
}

export function netOfGross(grossG, tareG) {
  if (grossG < tareG) throw new Error(grossBelowTare(grossG, tareG));
  return grossG - tareG;
}

export function percentOf(netG, initialG) {
  return netG / initialG * 100.0;
}

export function netOfPercent(percent, initialG) {
  return percent * initialG / 100.0;
}

export function lengthOf(netG, gpm) {
  return netG / gpm;
}

export function netOfLength(metres, gpm) {
  return metres * gpm;
}

export function gramsOfMm(mm, gpm) {
  return mm / 1000.0 * gpm;
}

// What a spool view shows: whole grams, a whole percentage of the net it held
// new, metres with one decimal under ten. null where Python says None.
export function shown(netG, initialG, gpm) {
  const percent = initialG > 0 ? roundHalfAway(percentOf(netG, initialG), 0) : null;
  let metres = null;
  if (gpm > 0) {
    const length = lengthOf(netG, gpm);
    metres = roundHalfAway(length, length < 10 ? 1 : 0);
  }
  return { g: roundHalfAway(netG, 0), percent, m: metres };
}

// The CFS writes its colours "0RRGGBB"; a fiche keeps "RRGGBB".
export function colourKey(text) {
  let value = String(text == null ? "" : text).trim().replace(/^#+/, "").toUpperCase();
  if (value.length === 7 && value[0] === "0") value = value.slice(1);
  return /^[0-9A-F]{6}$/.test(value) ? value : "";
}

// Python's casefold, for the names compared here: "ß" folds to "ss".
export function fold(text) {
  return String(text == null ? "" : text).toLowerCase().replace(/ß/g, "ss").replace(/[^0-9a-z]/g, "");
}

// What a search compares: accents dropped, "Étagère 2" reads "etagere 2".
export function searchKey(text) {
  return String(text == null ? "" : text).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/ß/g, "ss").replace(/[^0-9a-z]+/g, " ").trim();
}

function words(query) {
  return searchKey(query).split(" ").filter(Boolean);
}

// The K1 material record a fiche most likely is: the maker's only record of
// that type, or the one its name names, else the Generic record of the type.
export function suggestCrealityId(manufacturer, material, name, materials) {
  const kind = String(material || "").trim().toUpperCase();
  if (!kind) return "";
  const records = Array.isArray(materials) ? materials : Object.values(materials || {});
  const same = records
    .filter((record) => record && record.type === kind)
    .sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  const brand = fold(manufacturer);
  const mine = same.filter((record) => brand && fold(record.brand) === brand);
  if (mine.length === 1) return mine[0].id;
  if (mine.length) {
    const label = fold(name);
    const named = mine.filter((record) => fold(record.name) && label.includes(fold(record.name)));
    if (named.length === 1) return named[0].id;
  }
  const generic = same.filter((record) => fold(record.brand) === "generic");
  return generic.length ? generic[0].id : "";
}

// A number typed by a person: "1 234,5" is 1234.5. null for an empty field,
// NaN for anything that is not a number.
export function parseNumber(text) {
  if (text == null) return null;
  if (typeof text === "number") return Number.isFinite(text) ? text : NaN;
  const value = String(text).replace(/[\s\u00a0\u202f]/g, "").replace(",", ".");
  if (!value) return null;
  if (!/^[-+]?(\d+\.?\d*|\.\d+)$/.test(value)) return NaN;
  return Number(value);
}

// ------------------------------------------------------- what is left, typed
// The four ways to say what is left on a spool, kept in step: typing one
// fills the three others. A gross weight is a weighing ("pesé"); a net, a
// percentage or a length is an estimate ("estimé"). `context` is the tare of
// the spool's empty spool (null when unknown), the net it held new and the
// grams per metre of its fiche.
export const REMAINING_FIELDS = ["gross", "net", "percent", "metres"];
export const GROSS_WITHOUT_TARE = "poids brut sans bobine vide : choisir le type de bobine vide pour "
  + "retirer sa tare, ou donner une estimation";

export function remainingFrom(field, text, context) {
  const tare = context && typeof context.tare === "number" && Number.isFinite(context.tare) ? context.tare : null;
  const initial = Number(context && context.initial) || 0;
  const gpm = Number(context && context.gpm) || 0;
  const result = { values: { gross: "", net: "", percent: "", metres: "" }, basis: null, error: "" };
  const value = parseNumber(text);
  if (value === null) return result;
  if (Number.isNaN(value)) {
    result.error = "nombre attendu";
    return result;
  }
  if (value < 0) {
    result.error = "nombre positif attendu";
    return result;
  }
  let net;
  let kind = "estimation";
  if (field === "gross") {
    if (tare === null) {
      result.error = GROSS_WITHOUT_TARE;
      return result;
    }
    if (value < tare) {
      result.error = grossBelowTare(value, tare);
      return result;
    }
    net = netOfGross(value, tare);
    kind = "pesee";
  } else if (field === "net") {
    net = value;
  } else if (field === "percent") {
    if (!(initial > 0)) {
      result.error = "net initial inconnu : pourcentage impossible";
      return result;
    }
    net = netOfPercent(value, initial);
  } else if (field === "metres") {
    if (!(gpm > 0)) {
      result.error = "densité inconnue : longueur impossible";
      return result;
    }
    net = netOfLength(value, gpm);
  } else {
    result.error = "champ inconnu";
    return result;
  }
  const basisValue = kind === "pesee" ? value : net;
  if (basisValue > VALUE_MAX_G) {
    result.error = "au-delà de " + figure(VALUE_MAX_G) + " g";
    return result;
  }
  if (kind === "estimation" && net > initial) {
    result.error = "estimation de " + figure(net) + " g au-delà du net initial de " + figure(initial) + " g";
    return result;
  }
  const view = shown(net, initial, gpm);
  result.values = {
    gross: tare === null ? "" : gramsLabel(roundHalfAway(net + tare, 1)),
    net: gramsLabel(roundHalfAway(net, 1)),
    percent: view.percent === null ? "" : figure(view.percent, 0),
    metres: view.m === null ? "" : figure(view.m),
  };
  result.basis = { kind, value_g: roundHalfAway(basisValue, 2) };
  return result;
}

// The four fields as a sheet opens, from the spool view the K1 sent.
export function remainingFields(remaining) {
  const values = { gross: "", net: "", percent: "", metres: "" };
  if (!remaining || remaining.net_g == null) return values;
  values.net = gramsLabel(remaining.net_g);
  if (remaining.gross_g != null) values.gross = gramsLabel(remaining.gross_g);
  const view = remaining.shown || {};
  if (view.percent != null) values.percent = figure(view.percent, 0);
  if (view.m != null) values.metres = figure(view.m);
  return values;
}

// ------------------------------------------------------------------ labels
export const STATE_LABELS = {
  cfs: "au CFS", a_ranger: "à ranger", stock: "en stock", terminee: "terminée", jetee: "jetée",
};
export const STATE_ORDER = ["a_ranger", "stock", "cfs", "terminee", "jetee"];
export const BASIS_LABELS = { neuve: "neuve", estimation: "estimé", pesee: "pesé" };
export const TARE_SOURCE_LABELS = { spoolmandb: "SpoolmanDB", pesee: "pesée", manuel: "saisie" };
export const SPOOL_MATERIALS = ["plastique", "carton", "métal", "inconnue"];
export const OUTCOME_LABELS = {
  complete: "terminée", cancelled: "annulée", error: "en erreur", interrupted: "interrompue",
};
// The journal says "annulée" and "en attente"; a slot's last write keeps "annulee".
export const WRITE_RESULTS = {
  ok: "confirmée", erreur: "échec", ecart: "écart à la relecture", "en attente": "en attente", "annulée": "annulée",
  annulee: "annulée",
};
const CANCELLED = ["annulée", "annulee"];
export const SETTING_LABELS = { cut_loss_mm: "perte à la coupe (mm)", low_g: "seuil bobine basse (g)" };

// What the window says of a slot, and the colour it says it in.
export const SLOT_STATUS = {
  ok: { text: "à jour", tone: "ok" },
  a_verifier: { text: "à vérifier", tone: "warn" },
  inconnue: { text: "bobine inconnue", tone: "warn" },
  attendue: { text: "bobine attendue", tone: "warn" },
  en_attente_cfs: { text: "écriture au CFS en attente", tone: "accent" },
  vide: { text: "vide", tone: "faint" },
  hors_ligne: { text: "unité hors ligne", tone: "faint" },
};

export function slotStatus(view) {
  return SLOT_STATUS[view && view.status] || { text: String((view && view.status) || "état inconnu"), tone: "faint" };
}

// "B001" is shown "B-001", as the K1 labels it.
export function idLabel(ident) {
  const text = String(ident || "");
  return text ? text.slice(0, 1) + "-" + text.slice(1) : "";
}

export function ficheName(fiche) {
  if (!fiche) return "fiche inconnue";
  return [fiche.manufacturer, fiche.name].filter((part) => part && String(part).trim()).join(" ") || "sans nom";
}

export function ficheLine(fiche) {
  if (!fiche) return "";
  const colour = colourKey(fiche.colour);
  return [fiche.material, colour ? colourName(colour) : ""].filter(Boolean).join(" · ");
}

export function emptySpoolName(record) {
  if (!record) return "aucune";
  return [record.manufacturer, record.name].filter((part) => part && String(part).trim()).join(" ") || "sans nom";
}

export function emptySpoolLine(record) {
  if (!record) return "";
  return [
    record.spool_material,
    "tare " + gramsLabel(record.tare_g) + " g",
    gramsLabel(record.nominal_net_g) + " g net",
    TARE_SOURCE_LABELS[record.source] || record.source,
  ].filter(Boolean).join(" · ");
}

// What is left, in the start window's words: "~470 g · 47 % · 158 m".
export function remainingText(remaining) {
  if (!remaining || remaining.net_g == null) return "reste inconnu";
  if (remaining.exhausted) return "épuisée selon le décompte";
  const view = remaining.shown || {};
  const parts = ["~" + figure(view.g, 0) + " g"];
  if (view.percent != null) parts.push(figure(view.percent, 0) + " %");
  if (view.m != null) parts.push(figure(view.m) + " m");
  return parts.join(" · ");
}

// A spool at its end: "Terminée" comes first among its actions.
export function nearlyEmpty(remaining) {
  if (!remaining || remaining.net_g == null) return false;
  return Boolean(remaining.exhausted) || remaining.net_g <= NEARLY_EMPTY_G;
}

// Where a spool is, in a few words.
export function whereText(spool) {
  if (!spool) return "";
  if (spool.state === "cfs") return "au CFS en " + (spool.slot || "?");
  if (spool.state === "stock") return spool.place ? "en stock · " + spool.place : "en stock";
  return STATE_LABELS[spool.state] || String(spool.state || "");
}

// Which automatic refills a write to the CFS makes or breaks: the firmware
// pairs slots that show the same material and colour.
export function impactText(impact) {
  if (!impact) return "";
  const parts = [];
  if (impact.gained && impact.gained.length) parts.push("relais automatique gagné avec " + impact.gained.join(", "));
  if (impact.lost && impact.lost.length) parts.push("relais automatique perdu avec " + impact.lost.join(", "));
  return parts.length ? parts.join(" ; ") : "aucun relais automatique changé";
}

// What the write would change on the slot, read from its plan.
export function planText(plan, materials) {
  if (!plan) return "";
  const parts = [];
  if (plan.material) {
    const record = materialRecord(materials, plan.material.slice(1));
    parts.push("matière " + (record ? record.name || record.type : plan.material.slice(1)));
  }
  if (plan.colour) {
    const colour = colourKey(plan.colour);
    parts.push("couleur " + (colour ? colourName(colour) + " #" + colour : plan.colour));
  }
  return parts.join(" et ");
}

export function materialRecord(materials, ident) {
  const records = Array.isArray(materials) ? materials : Object.values(materials || {});
  return records.find((record) => record && record.id === ident) || null;
}

// The K1 material records of one type, the way a select lists them.
export function materialsOfType(materials, type) {
  const kind = String(type || "").trim().toUpperCase();
  const records = Array.isArray(materials) ? materials : Object.values(materials || {});
  return records
    .filter((record) => record && (!kind || record.type === kind))
    .sort((a, b) => searchKey(a.brand).localeCompare(searchKey(b.brand)) || String(a.name).localeCompare(String(b.name))
      || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
}

export function materialTypes(materials) {
  const records = Array.isArray(materials) ? materials : Object.values(materials || {});
  return [...new Set(records.map((record) => record && record.type).filter(Boolean))].sort();
}

// The slots grouped by unit, A to D, the way the CFS holds them.
export function units(views) {
  const found = {};
  for (const view of Array.isArray(views) ? views : []) {
    if (!view || !SLOT_NAMES.includes(view.slot)) continue;
    const unit = view.slot.slice(0, 2);
    (found[unit] = found[unit] || []).push(view);
  }
  return Object.keys(found).sort().map((unit) => ({
    unit,
    slots: found[unit].sort((a, b) => (a.slot < b.slot ? -1 : 1)),
  }));
}

// ------------------------------------------------------------------- stock
export const SCOPES = {
  rangees: { text: "rangées et à ranger", states: ["a_ranger", "stock"] },
  actives: { text: "toutes, CFS compris", states: ["a_ranger", "stock", "cfs"] },
  archivees: { text: "terminées et jetées", states: ["terminee", "jetee"] },
};

function haystack(spool, fiche) {
  const colour = fiche ? colourKey(fiche.colour) : "";
  return searchKey([
    spool.label, spool.id, fiche && fiche.manufacturer, fiche && fiche.name, fiche && fiche.material,
    colour, colour ? colourName(colour) : "", spool.place, spool.notes, spool.slot, STATE_LABELS[spool.state],
  ].filter(Boolean).join(" "));
}

export function filterStock(spools, fiches, filter) {
  const options = filter || {};
  const scope = SCOPES[options.scope] || SCOPES.rangees;
  const wanted = words(options.text);
  const records = fiches || {};
  return (Array.isArray(spools) ? spools : [])
    .filter((spool) => spool && scope.states.includes(spool.state))
    .filter((spool) => {
      const fiche = records[spool.filament];
      if (options.material && (!fiche || fiche.material !== options.material)) return false;
      if (options.colour && (!fiche || colourKey(fiche.colour) !== options.colour)) return false;
      if (options.place && spool.place !== options.place) return false;
      if (!wanted.length) return true;
      const text = haystack(spool, fiche);
      return wanted.every((word) => text.includes(word));
    })
    .sort((a, b) => {
      const fa = records[a.filament];
      const fb = records[b.filament];
      return STATE_ORDER.indexOf(a.state) - STATE_ORDER.indexOf(b.state)
        || searchKey(fa && fa.manufacturer).localeCompare(searchKey(fb && fb.manufacturer))
        || searchKey(fa && fa.name).localeCompare(searchKey(fb && fb.name))
        || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
    });
}

// The choices of the stock filters, from the spools of the chosen scope.
export function stockFacets(spools, fiches, scope) {
  const states = (SCOPES[scope] || SCOPES.rangees).states;
  const records = fiches || {};
  const materials = new Set();
  const colours = new Map();
  const places = new Set();
  for (const spool of Array.isArray(spools) ? spools : []) {
    if (!spool || !states.includes(spool.state)) continue;
    const fiche = records[spool.filament];
    if (fiche && fiche.material) materials.add(fiche.material);
    const colour = fiche ? colourKey(fiche.colour) : "";
    if (colour) colours.set(colour, colourName(colour));
    if (spool.place) places.add(spool.place);
  }
  // Two shades can share a name: the hex then tells them apart in the list.
  const named = [...colours.values()];
  const shared = new Set(named.filter((name, index) => named.indexOf(name) !== index));
  return {
    materials: [...materials].sort(),
    colours: [...colours].map(([key, name]) => ({ key, name: shared.has(name) ? name + " #" + key : name }))
      .sort((a, b) => a.name.localeCompare(b.name) || (a.key < b.key ? -1 : 1)),
    places: [...places].sort((a, b) => a.localeCompare(b)),
  };
}

// Spools that could be the one in a slot the CFS cannot name, best first:
// the K1 ranks them, this only keeps those still known.
export function candidateSpools(view, spools) {
  const known = {};
  for (const spool of Array.isArray(spools) ? spools : []) if (spool && spool.id) known[spool.id] = spool;
  return (view && Array.isArray(view.candidates) ? view.candidates : []).map((ident) => known[ident]).filter(Boolean);
}

// Spools Thomas may put in a slot: anything out of the CFS and not archived.
export function placeableSpools(spools, fiches) {
  return filterStock(spools, fiches, { scope: "rangees" });
}

export function usersOf(spools, key, value) {
  return (Array.isArray(spools) ? spools : []).filter((spool) => spool && spool[key] === value).map((spool) => spool.label || idLabel(spool.id));
}

// --------------------------------------------------------------- catalogue
// The SpoolmanDB empty spools shipped as tares.json, searched word by word.
export function searchTares(entries, query, limit = 30) {
  const wanted = words(query);
  const found = [];
  for (const entry of Array.isArray(entries) ? entries : []) {
    if (!entry) continue;
    const text = searchKey([
      entry.manufacturer, entry.spool_material, entry.net_g, entry.tare_g,
      ...(Array.isArray(entry.lines) ? entry.lines.flatMap((line) => [line.material, line.name]) : []),
    ].filter((part) => part != null).join(" "));
    if (wanted.every((word) => text.includes(word))) found.push(entry);
    if (found.length >= limit) break;
  }
  return found;
}

export function tareLines(entry) {
  const lines = entry && Array.isArray(entry.lines) ? entry.lines : [];
  const names = [...new Set(lines.map((line) => line.material).filter(Boolean))];
  return names.slice(0, 6).join(", ") + (names.length > 6 ? "…" : "");
}

// ----------------------------------------------------------------- journal
function signedGrams(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  return (number > 0 ? "+" : "") + gramsLabel(number);
}

function metresOf(entry) {
  if (entry.m != null) return figure(entry.m) + " m";
  if (entry.mm != null) return figure(Number(entry.mm) / 1000) + " m";
  return "";
}

function shortFile(path) {
  const text = String(path || "");
  return text.split("/").pop() || text;
}

// One journal line in plain French. `names` resolves ids to what Thomas
// calls them: {spools: {id: view}, filaments: {id: fiche}, empty: {id: record}}.
export function journalText(entry, names) {
  if (!entry || typeof entry !== "object") return "";
  const known = names || {};
  const spool = entry.spool ? idLabel(entry.spool) : "";
  const detail = entry.detail ? " · " + entry.detail : "";
  switch (entry.kind) {
    case "bobine_vide": {
      const record = (known.empty || {})[entry.empty_spool];
      return "Bobine vide " + (record ? emptySpoolName(record) : idLabel(entry.empty_spool)) + " " + (entry.change || "")
        + (entry.tare_g != null ? " · tare " + gramsLabel(entry.tare_g) + " g" : "");
    }
    case "fiche": {
      const fiche = (known.filaments || {})[entry.filament];
      return "Fiche " + (fiche ? ficheName(fiche) : idLabel(entry.filament)) + " " + (entry.change || "")
        + (entry.slot ? " en " + entry.slot : "")
        + (Array.isArray(entry.fields) && entry.fields.length ? " (" + entry.fields.join(", ") + ")" : "");
    }
    case "bobine":
      return spool + " " + (entry.change || "")
        + (entry.slot ? " en " + entry.slot : "")
        + (entry.net_g != null ? " · " + gramsLabel(entry.net_g) + " g" : "")
        + (Array.isArray(entry.fields) && entry.fields.length ? " (" + entry.fields.join(", ") + ")" : "");
    case "etat": {
      if (entry.state === "cfs") return spool + " mise au CFS en " + (entry.slot || "?") + detail;
      if (entry.state === "stock") return spool + " en stock" + (entry.place ? " : " + entry.place : "") + detail;
      if (entry.state === "a_ranger") return spool + " à ranger" + (entry.slot ? " (sortie de " + entry.slot + ")" : "") + detail;
      return spool + " " + (STATE_LABELS[entry.state] || entry.state || "") + detail;
    }
    case "reste":
      return spool + " : reste " + (BASIS_LABELS[entry.basis] || entry.basis || "")
        + (entry.net_g != null ? " " + gramsLabel(entry.net_g) + " g" : "")
        + (entry.gap_g != null ? " · écart " + signedGrams(entry.gap_g) + " g au décompte" : "");
    case "consommation": {
      const amount = [entry.g != null ? gramsLabel(entry.g) + " g" : "", metresOf(entry)].filter(Boolean).join(" · ");
      return (spool ? spool + " : " : "Consommation : ") + (amount || "rien")
        + (entry.slot ? " en " + entry.slot : "") + detail;
    }
    case "impression": {
      const used = Array.isArray(entry.spools) && entry.spools.length ? " · " + entry.spools.map(idLabel).join(", ") : "";
      const left = Number(entry.unassigned) > 0 ? " · " + entry.unassigned + " à attribuer" : "";
      return "Impression " + shortFile(entry.file) + " " + (OUTCOME_LABELS[entry.outcome] || entry.outcome || "") + used + left;
    }
    case "ecriture_cfs":
      return "Écriture au CFS " + (entry.slot || "") + (spool ? " (" + spool + ")" : "") + " : "
        + (WRITE_RESULTS[entry.result] || entry.result || "") + detail;
    case "cfs":
      return "CFS " + (entry.slot || "") + " : " + (entry.detail || "changement");
    case "reglages":
      return "Réglages : " + (Array.isArray(entry.fields) ? entry.fields : [])
        .map((key) => (SETTING_LABELS[key] || key) + " " + figure(entry[key])).join(", ");
    case "route":
      return "Filament engagé en " + (entry.slot || "?") + (spool ? " (" + spool + ")" : "")
        + (entry.from ? " après " + entry.from : "");
    case "erreur":
      return "Erreur : " + (entry.detail || "inconnue");
    case "import":
      return "Bibliothèque importée";
    default:
      return String(entry.kind || "événement") + detail;
  }
}

export function journalTone(entry) {
  if (!entry) return "";
  if (entry.kind === "erreur") return "warn";
  if (entry.kind === "ecriture_cfs") {
    if (entry.result === "ok") return "ok";
    if (entry.result === "en attente") return "accent";
    // A write dropped because the spool left the slot is no failure.
    return CANCELLED.includes(entry.result) ? "" : "warn";
  }
  return "";
}

export function touches(entry, ident) {
  if (!entry || !ident) return false;
  return entry.spool === ident || (Array.isArray(entry.spools) && entry.spools.includes(ident));
}
