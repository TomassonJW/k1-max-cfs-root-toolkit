// node --test packages/k1-control-v1/spool-choice-gate-v1/logic.test.mjs
// The pure part of the Bobines page, on the spools of the machine as read
// on 10 September (T1B black, T1D white, T2A red, T2B blue, T2C white PETG,
// T2D lilac) and the cube file (black used, #8080FF declared).

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  LAUNCHED_MS, MARGIN, NAMES, assign, buildModel, colourName, compatibility, completeness,
  countingUnverified, elapsedLabel, figure, gramsLabel, isLight, mapParam, nextToConnect,
  normaliseHex, overlayMode, pendingKey, plannedGrams, shortName, shortfalls, slotRemaining,
  spoolSlots, startNotes, summaryLine, unidentified, unidentifiedNote, unidentifiedSlots,
} from "./www/bobines/logic.js";

const slot = (type, colour, loaded = 1, remain = 80) => ({ loaded, type, colour, material: "000001", remain });

const GATE = {
  wrapped: 1,
  page: "http://192.168.1.64:4409/bobines/",
  pending: 1,
  file: "/usr/data/printer_data/gcodes/_Cube_PLA_24m21s.gcode",
  name: "_Cube_PLA_24m21s.gcode",
  since: 1000,
  note: "2 filament(s) declare(s), 1 filament(s) utilise(s)",
  filaments: [
    { index: 0, logical: "T1A", type: "PLA", colour: "000000", name: "", declared: 1, used: 1, exact: ["T1B"], same_type: ["T1B", "T1D", "T2A", "T2B", "T2D"] },
    { index: 1, logical: "T1B", type: "PLA", colour: "8080FF", name: "", declared: 1, used: 0, exact: [], same_type: ["T1B", "T1D", "T2A", "T2B", "T2D"] },
  ],
  used_count: 1,
  declared_count: 2,
  slots: {
    T1A: slot("", "", 0, -1), T1B: slot("PLA", "000000"), T1C: slot("", "", 0, -1), T1D: slot("PLA", "FFFFFF"),
    T2A: slot("PLA", "FF1E1E"), T2B: slot("PLA", "00A3FF"), T2C: slot("PETG", "FFFFFF"), T2D: slot("PLA", "B2A1E1"),
  },
  units: ["T1", "T2"],
  table: {},
  confirmed_file: "", confirmed_name: "", confirmed_at: 0, confirmed_map: {},
  last: "en attente du choix pour _Cube_PLA_24m21s.gcode",
};

test("NAMES lists the sixteen slots in box then letter order", () => {
  assert.equal(NAMES.length, 16);
  assert.equal(NAMES[0], "T1A");
  assert.equal(NAMES[3], "T1D");
  assert.equal(NAMES[4], "T2A");
  assert.equal(NAMES[15], "T4D");
});

test("every colour form of the machine reads as six upper hex digits", () => {
  assert.equal(normaliseHex("#8080FF"), "8080FF");
  assert.equal(normaliseHex("0ff1e1e"), "FF1E1E");
  assert.equal(normaliseHex("ffffff"), "FFFFFF");
  assert.equal(normaliseHex("0000000"), "000000");
  assert.equal(normaliseHex("-1"), "");
  assert.equal(normaliseHex(""), "");
  assert.equal(normaliseHex(null), "");
});

test("the spools of the machine get the names a person would give them", () => {
  assert.equal(colourName("000000"), "noir");
  assert.equal(colourName("FFFFFF"), "blanc");
  assert.equal(colourName("FF1E1E"), "rouge");
  assert.equal(colourName("00A3FF"), "bleu");
  assert.equal(colourName("B2A1E1"), "violet clair");
  assert.equal(colourName("8080FF"), "bleu clair");
  assert.equal(colourName("808080"), "gris");
  assert.equal(colourName("FFD700"), "jaune");
  assert.equal(colourName("00FF00"), "vert");
  assert.equal(colourName("FF8800"), "orange");
  assert.equal(colourName("102040"), "bleu marine");
  assert.equal(colourName(""), "couleur inconnue");
});

test("light swatches are flagged so they get a ring on the dark page", () => {
  assert.equal(isLight("FFFFFF"), true);
  assert.equal(isLight("B2A1E1"), true);
  assert.equal(isLight("000000"), false);
  assert.equal(isLight("FF1E1E"), false);
  assert.equal(isLight(""), false);
});

test("buildModel turns the status into the choice view with ordered slots", () => {
  const model = buildModel({ kctrl_print_gate: GATE, print_stats: { state: "standby", filename: "" } });
  assert.equal(model.view, "choice");
  assert.equal(model.pending, true);
  assert.equal(model.wrapped, true);
  assert.deepEqual(model.units, ["T1", "T2"]);
  assert.deepEqual(model.slots.map((s) => s.name), ["T1A", "T1B", "T1C", "T1D", "T2A", "T2B", "T2C", "T2D"]);
  assert.equal(model.slots[1].colour, "000000");
  assert.equal(model.filaments.length, 2);
  assert.equal(model.usedCount, 1);
  assert.equal(model.declaredCount, 2);
  assert.equal(pendingKey(model), GATE.file + "@1000");
  assert.equal(pendingKey(buildModel({ kctrl_print_gate: Object.assign({}, GATE, { since: 1000.7 }) })), GATE.file + "@1000");
});

test("a running or paused print is the printing view whatever the gate says", () => {
  for (const state of ["printing", "paused"]) {
    const model = buildModel({ kctrl_print_gate: GATE, print_stats: { state, filename: "x.gcode" } });
    assert.equal(model.view, "printing");
    assert.equal(model.printingName, "x.gcode");
  }
});

test("nothing pending is the idle view and an empty status is harmless", () => {
  const idle = buildModel({ kctrl_print_gate: Object.assign({}, GATE, { pending: 0, filaments: [] }), print_stats: { state: "standby" } });
  assert.equal(idle.view, "idle");
  assert.equal(pendingKey(idle), "");
  const empty = buildModel({});
  assert.equal(empty.view, "idle");
  assert.deepEqual(empty.slots, []);
  assert.equal(empty.wrapped, false);
});

test("assign gives one spool to one filament and a second click disconnects", () => {
  let table = assign({}, "T1A", "T1B");
  assert.deepEqual(table, { T1A: "T1B" });
  table = assign(table, "T1B", "T1B");
  assert.deepEqual(table, { T1B: "T1B" }, "the spool moves to the filament that took it");
  table = assign(table, "T1A", "T2D");
  assert.deepEqual(table, { T1B: "T1B", T1A: "T2D" });
  table = assign(table, "T1A", "T2D");
  assert.deepEqual(table, { T1B: "T1B" }, "same pair again means disconnect");
});

test("completeness only counts the filaments the file uses", () => {
  const filaments = GATE.filaments;
  assert.deepEqual(completeness(filaments, {}), { complete: false, missing: ["T1A"] });
  assert.deepEqual(completeness(filaments, { T1A: "T1B" }), { complete: true, missing: [] });
  assert.deepEqual(completeness(filaments, { T1B: "T2D" }), { complete: false, missing: ["T1A"] });
  assert.deepEqual(completeness([], {}), { complete: false, missing: [] });
});

test("nextToConnect walks the used filaments in file order", () => {
  const filaments = [
    { logical: "T1A", used: 1 }, { logical: "T1B", used: 1 }, { logical: "T1C", used: 0 },
  ];
  assert.equal(nextToConnect(filaments, {}), "T1A");
  assert.equal(nextToConnect(filaments, { T1A: "T2A" }), "T1B");
  assert.equal(nextToConnect(filaments, { T1A: "T2A", T1B: "T2B" }), null);
});

test("mapParam writes the pairs in slot order, the form KCTRL_GATE_CONFIRM reads", () => {
  assert.equal(mapParam({ T1B: "T1B", T1A: "T2D" }), "T1A:T2D,T1B:T1B");
  assert.equal(mapParam({}), "");
});

test("compatibility says in words what connecting would mean", () => {
  const black = GATE.filaments[0];
  assert.deepEqual(compatibility(black, GATE.slots.T1B), { level: "exact", label: "identique au fichier", exact: true });
  assert.equal(compatibility(black, GATE.slots.T2A).level, "colour");
  assert.equal(compatibility(black, GATE.slots.T2C).level, "type");
  assert.match(compatibility(black, GATE.slots.T2C).label, /PETG au lieu de PLA/);
  assert.equal(compatibility(black, GATE.slots.T1A).level, "empty");
  assert.equal(compatibility(black, undefined).level, "empty");
  assert.equal(compatibility({ type: "", colour: "" }, GATE.slots.T1B).level, "unknown");
});

test("labels for the rest of the page", () => {
  assert.equal(elapsedLabel(100, 130), "depuis 30 s");
  assert.equal(elapsedLabel(100, 100 + 5 * 60), "depuis 5 min");
  assert.equal(elapsedLabel(100, 100 + 3 * 3600 + 7 * 60), "depuis 3 h 07");
  assert.equal(shortName("dossier/sous/fichier.gcode"), "fichier.gcode");
  assert.equal(shortName("fichier.gcode"), "fichier.gcode");
});

test("the summary line counts what is left in plain words", () => {
  const two = [{ logical: "T1A", used: 1 }, { logical: "T1B", used: 1 }, { logical: "T1C", used: 0 }];
  assert.equal(summaryLine(two, {}), "Encore 2 filaments à raccorder.");
  assert.equal(summaryLine(two, { T1A: "T2A" }), "Encore un filament à raccorder.");
  assert.equal(summaryLine(two, { T1A: "T2A", T1B: "T2B" }), "Les 2 filaments sont raccordés, tout est prêt.");
  assert.equal(summaryLine(GATE.filaments, { T1A: "T1B" }), "Le filament est raccordé, tout est prêt.");
  assert.equal(summaryLine([], {}), "Le fichier n'utilise aucun filament.");
});

test("the window inside Mainsail shows itself only while a start waits", () => {
  const choice = buildModel({ kctrl_print_gate: GATE, print_stats: { state: "standby", filename: "" } });
  const idle = buildModel({ kctrl_print_gate: Object.assign({}, GATE, { pending: 0 }), print_stats: { state: "standby" } });
  const printing = buildModel({ kctrl_print_gate: Object.assign({}, GATE, { pending: 0 }), print_stats: { state: "printing", filename: GATE.name } });
  const quiet = { dismissedKey: "", launchedAt: 0 };
  assert.equal(overlayMode(quiet, null, 1000), "hidden");
  assert.equal(overlayMode(quiet, idle, 1000), "hidden");
  assert.equal(overlayMode(quiet, printing, 1000), "hidden");
  assert.equal(overlayMode(quiet, choice, 1000), "choice");
});

test("the window put aside stays a pill for that file only", () => {
  const choice = buildModel({ kctrl_print_gate: GATE, print_stats: { state: "standby" } });
  const again = buildModel({ kctrl_print_gate: Object.assign({}, GATE, { since: 2000 }), print_stats: { state: "standby" } });
  const aside = { dismissedKey: pendingKey(choice), launchedAt: 0 };
  assert.equal(overlayMode(aside, choice, 1000), "minimised");
  assert.equal(overlayMode(aside, again, 1000), "choice");
  assert.equal(overlayMode({ dismissedKey: "", launchedAt: 0 }, choice, 1000), "choice");
});

test("after the launch it sent the window says so for a moment then hides", () => {
  const printing = buildModel({ kctrl_print_gate: Object.assign({}, GATE, { pending: 0 }), print_stats: { state: "printing", filename: GATE.name } });
  const sent = { dismissedKey: "", launchedAt: 50000 };
  assert.equal(overlayMode(sent, printing, 50000 + 1000), "launched");
  assert.equal(overlayMode(sent, printing, 50000 + LAUNCHED_MS - 1), "launched");
  assert.equal(overlayMode(sent, printing, 50000 + LAUNCHED_MS), "hidden");
  // A cancel never shows the launched card: nothing was sent.
  const idle = buildModel({ kctrl_print_gate: Object.assign({}, GATE, { pending: 0 }), print_stats: { state: "standby" } });
  assert.equal(overlayMode({ dismissedKey: "", launchedAt: 0 }, idle, 50000), "hidden");
});


// Deferred end owns the UI even after the SD reader says complete.
for (const phase of ["waiting", "heating", "cutting", "rewinding", "finalizing", "failed", "shutdown"]) {
  test("end " + phase + " overrides SD completion and the launch flash", () => {
    const model = buildModel({ print_stats: { state: "complete" },
      kctrl_print_gate: { ...GATE, end: { enabled: true, pending: true, phase } } });
    assert.equal(model.view, "ending");
    assert.equal(model.end.blocked, true);
    assert.equal(overlayMode({ launchedAt: 999, dismissedKey: pendingKey(model) }, model, 1000), "ending");
  });
}
test("failure remains visible after the callback drained", () => {
  const model = buildModel({ kctrl_print_gate: { end: {
    enabled: true, pending: false, phase: "failed", failure: "cut_refused" } } });
  assert.equal(model.end.title, "Fin incomplète");
  assert.equal(model.view, "ending");
});
test("thermal failure takes priority and does not assert heaters stopped", () => {
  const model = buildModel({ kctrl_print_gate: { end: {
    enabled: true, pending: true, phase: "failed", thermal_failure: "nonzero" } } });
  assert.match(model.end.hint, /Vérifiez immédiatement/);
  assert.match(model.end.hint, /n'est pas confirmé/);
});
for (const end of [{}, { enabled: true }, { enabled: true, pending: false, phase: "new" }]) {
  test("malformed end blocks instead of declaring completion " + JSON.stringify(end), () => {
    assert.equal(buildModel({ kctrl_print_gate: { end } }).view, "ending");
  });
}
test("absent and disabled modules keep legacy choices available", () => {
  for (const end of [undefined, null, { enabled: false, pending: false, phase: "disabled" }]) {
    const model = buildModel({ kctrl_print_gate: { ...GATE, end } });
    assert.equal(model.view, "choice");
    assert.equal(model.end.title, "");
  }
});
test("cancel completion never says the print succeeded", () => {
  const model = buildModel({ print_stats: { state: "cancelled" }, kctrl_print_gate: {
    end: { enabled: true, pending: false, phase: "complete", reason: "annulation" } } });
  assert.equal(model.end.blocked, false);
  assert.match(model.end.hint, /annulée/);
  assert.equal(model.end.title, "Cycle de fin terminé");
});

test("end can be folded to reach Mainsail stop controls; a failure opens it again", () => {
  const status = { kctrl_print_gate: { end: { enabled: true, pending: true, phase: "rewinding", job_epoch: 4 } } };
  const pending = buildModel(status);
  const ui = { dismissedEndKey: pending.endKey };
  assert.equal(overlayMode(ui, pending, 0), "minimised");
  status.kctrl_print_gate.end.phase = "failed";
  assert.equal(overlayMode(ui, buildModel(status), 0), "ending");
});

// Run the real shared view with a small DOM/API double: verifies wiring,
// not just the pure labels. No browser or printer connection is involved.
test("shared view renders end, failure and lost connection without launch controls", async () => {
  const { mount } = await import("./www/bobines/bobines.js");
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this.listeners = {}; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(key, value) { this[key] = value; }
    addEventListener(key, value) { this.listeners[key] = value; }
    querySelector() { return null; }
    text() { return [this.textContent || "", ...this.children.map(n => typeof n === "string" ? n : n.text())].join(" "); }
  }
  const saved = Object.fromEntries(["Node", "document", "fetch", "setInterval", "clearInterval"].map(k => [k, globalThis[k]]));
  const nodes = Object.fromEntries(["main", "status", "state-label", "offline", "toast"].map(k => [k, new Element("div")]));
  let fail = false;
  let status = { print_stats: { state: "complete", filename: "job.gcode" }, kctrl_print_gate: {
    wrapped: 1, end: { enabled: true, pending: true, phase: "rewinding", job_epoch: 1 } } };
  const methods = [];
  try {
    globalThis.Node = Element;
    globalThis.document = { createElement: tag => new Element(tag), createTextNode: text => String(text) };
    globalThis.setInterval = () => 1;
    globalThis.clearInterval = () => {};
    globalThis.fetch = async (path, options) => {
      methods.push(options.method);
      if (fail) throw new Error("offline");
      return { ok: true, json: async () => ({ result: { status } }) };
    };
    const modes = [];
    const app = mount({ getElementById: key => nodes[key] }, { overlay: true, onMode: mode => modes.push(mode) });
    await new Promise(resolve => setImmediate(resolve));
    assert.match(nodes.main.text(), /Fin en cours/);
    assert.equal(nodes["state-label"].textContent, "Fin en cours");
    assert.equal(modes.at(-1), "ending");
    assert.doesNotMatch(nodes.main.text(), /Choisir ses bobines|Impression terminée/);
    status.kctrl_print_gate.end = { enabled: true, pending: false, phase: "failed", failure: "cut_refused" };
    await app.poll();
    assert.match(nodes.main.text(), /Fin incomplète/);
    fail = true;
    await app.poll();
    assert.match(nodes.main.text(), /Imprimante injoignable/);
    assert.equal(nodes["state-label"].textContent, "Hors ligne");
    assert.doesNotMatch(nodes.main.text(), /Choisir ses bobines|Impression terminée/);
    assert.ok(methods.every(method => method === "GET"));
    app.stop();
  } finally {
    for (const [key, value] of Object.entries(saved)) {
      if (value === undefined) delete globalThis[key]; else globalThis[key] = value;
    }
  }
});

// ------------------------------------------------- the spool manager's view
// Its status as the adapter publishes it (document 102), trimmed to what the
// start window reads. Synthetic spools on the same slots as GATE: T1A holds
// a chipless spool the CFS could not name, T1D a chipped spool the library
// does not know, T2A another spool than the library's, T2C one whose CFS
// write waits, T2D one the count says is used up.
const observed = (fields = {}) => Object.assign(
  { connected: true, present: true, material: "000001", colour: "000000", chip: null, type: "PLA" }, fields);
const remaining = (net, percent, m, exhausted = false) => (
  { net_g: net, exhausted, shown: { g: Math.round(net), percent, m }, gross_g: Math.round(net) + 180 });
const spoolView = (id, filament, counted, rest, low = false) => ({
  id, label: "B-" + id.slice(1), filament, empty_spool: "V001", initial_net_g: 1000,
  basis: { kind: "neuve", value_g: 1000 }, counted_g: counted, state: "cfs", slot: "", place: "",
  notes: "", last_gap: null, remaining: rest, low,
});
const fiche = (id, material, colour) => ({ id, manufacturer: "Marque", name: material, material, colour,
  diameter_mm: 1.75, density: 1.24, creality_id: "000001", notes: "" });
const MANAGER = {
  version: 1, revision: 7, read_only: false,
  klippy: { connected: true, cfs_ready: true, printing: false },
  counting_verified: false,
  slots: [
    { slot: "T1A", status: "inconnue", observed: observed({ material: "", colour: "", type: "" }), spool: "" },
    { slot: "T1B", status: "ok", observed: observed(), spool: "B001" },
    { slot: "T1C", status: "vide", observed: observed({ present: false, material: "", colour: "", type: "" }), spool: "" },
    { slot: "T1D", status: "inconnue", observed: observed({ colour: "FFFFFF", chip: 64 }), spool: "" },
    { slot: "T2A", status: "a_verifier", observed: observed({ colour: "FF1E1E" }), spool: "B002" },
    { slot: "T2B", status: "ok", observed: observed({ colour: "00A3FF" }), spool: "B003" },
    { slot: "T2C", status: "en_attente_cfs", observed: observed({ material: "000003", colour: "FFFFFF", type: "PETG" }), spool: "B004" },
    { slot: "T2D", status: "ok", observed: observed({ colour: "B2A1E1" }), spool: "B005" },
  ],
  spools: [
    spoolView("B001", "F001", 662, remaining(338, 34, 113)),
    spoolView("B002", "F002", 0, remaining(1000, 100, 335)),
    spoolView("B003", "F003", 961.6, remaining(38.4, 4, 13), true),
    spoolView("B004", "F004", 0, remaining(4.2, 0, 1.4), true),
    spoolView("B005", "F001", 1012.5, remaining(0, 0, 0, true), true),
  ],
  filaments: {
    F001: fiche("F001", "PLA", "000000"), F002: fiche("F002", "PLA", "00FF00"),
    F003: fiche("F003", "PLA", "00A3FF"), F004: fiche("F004", "PETG", "FFFFFF"),
  },
};
const choiceModel = () => buildModel({ kctrl_print_gate: GATE, print_stats: { state: "standby" } });

test("the manager's status is read by slot, and anything else is not the manager", () => {
  assert.equal(spoolSlots(null), null);
  assert.equal(spoolSlots({ status: { print_stats: {} } }), null);
  assert.equal(spoolSlots({ slots: "T1A" }), null);
  assert.deepEqual(spoolSlots({ slots: [] }), { slots: {}, verified: false, printing: false });
  const info = spoolSlots(MANAGER);
  assert.deepEqual(Object.keys(info.slots), ["T1A", "T1B", "T1C", "T1D", "T2A", "T2B", "T2C", "T2D"]);
  assert.equal(info.slots.T1B.spool.id, "B001");
  assert.equal(info.slots.T1B.fiche.id, "F001");
  assert.equal(info.slots.T1A.spool, null);
  assert.equal(info.slots.T1A.fiche, null);
  assert.equal(info.verified, false);
  assert.equal(info.printing, false);
  const lost = spoolSlots({ slots: [{ slot: "T1B", status: "ok", observed: {}, spool: "B999" }], spools: [] });
  assert.equal(lost.slots.T1B.spool, null);
  const later = spoolSlots(Object.assign({}, MANAGER, { counting_verified: true, klippy: { printing: true } }));
  assert.equal(later.verified, true);
  assert.equal(later.printing, true);
});

test("a card shows the library's count, a chip's figure, a doubt, or nothing", () => {
  const info = spoolSlots(MANAGER);
  assert.deepEqual(slotRemaining(info.slots.T1B),
    { text: "~338 g · 34 % · 113 m", level: "", kind: "spool", counted: true, note: "" });
  assert.deepEqual(slotRemaining(info.slots.T2B),
    { text: "~38 g · 4 % · 13 m", level: "low", kind: "spool", counted: true, note: "" });
  assert.deepEqual(slotRemaining(info.slots.T2C),
    { text: "~4 g · 0 % · 1,4 m", level: "low", kind: "spool", counted: false, note: "écriture au CFS en attente" });
  assert.deepEqual(slotRemaining(info.slots.T2D),
    { text: "épuisée selon le décompte", level: "low", kind: "spool", counted: true, note: "" });
  assert.deepEqual(slotRemaining(info.slots.T2A),
    { text: "à vérifier", level: "warn", kind: "check", counted: false, note: "" });
  assert.deepEqual(slotRemaining(info.slots.T1D),
    { text: "puce 64 %", level: "", kind: "chip", counted: false, note: "" });
  // A chipless spool the library does not know says nothing: never 100 %.
  assert.equal(slotRemaining(info.slots.T1A), null);
  assert.equal(slotRemaining(info.slots.T1C), null);
  assert.equal(slotRemaining(undefined), null);
  assert.equal(slotRemaining({ status: "hors_ligne", observed: { connected: false } }), null);
  // A spool without figures falls back on its chip, or on nothing.
  const bare = { status: "ok", observed: observed({ chip: 12 }), spool: { remaining: { net_g: null, shown: null } } };
  assert.equal(slotRemaining(bare).text, "puce 12 %");
  const noPercent = { status: "ok", observed: observed(),
    spool: { counted_g: 0, low: false, remaining: { net_g: 5, shown: { g: 5, percent: null, m: null } } } };
  assert.equal(slotRemaining(noPercent).text, "~5 g");
});

test("the page no longer reads the CFS's own remaining", async () => {
  const logic = await import("./www/bobines/logic.js");
  assert.equal(logic.remainingLabel, undefined);
});

test("a chipless spool the CFS could not name is told apart from an empty slot", () => {
  const info = spoolSlots(MANAGER);
  assert.equal(unidentified(info.slots.T1A), true);
  assert.equal(unidentified(info.slots.T1C), false);
  assert.equal(unidentified(info.slots.T1B), false);
  assert.equal(unidentified(null), false);
  const model = choiceModel();
  assert.deepEqual(unidentifiedSlots(model, info), [{ slot: "T1A", label: "" }]);
  assert.deepEqual(unidentifiedSlots(model, null), []);
  const linked = spoolSlots(Object.assign({}, MANAGER, { slots: MANAGER.slots.map((view) => view.slot === "T1A"
    ? Object.assign({}, view, { status: "a_verifier", spool: "B002" }) : view) }));
  assert.deepEqual(unidentifiedSlots(model, linked), [{ slot: "T1A", label: "B-002" }]);
  assert.equal(unidentifiedNote([]), "");
  assert.equal(unidentifiedNote([{ slot: "T1A", label: "" }]),
    "T1A : bobine sans puce que le CFS n'a pas identifiée, elle ne peut pas servir à ce départ."
    + " Pour l'utiliser : abandonner, l'identifier avec le bouton Bobines de Mainsail, puis relancer le fichier.");
  assert.equal(unidentifiedNote([{ slot: "T1A", label: "B-002" }, { slot: "T2C", label: "" }]),
    "T1A (B-002), T2C : bobines sans puce que le CFS n'a pas identifiées, elles ne peuvent pas servir à ce départ."
    + " Pour les utiliser : abandonner, les identifier avec le bouton Bobines de Mainsail, puis relancer le fichier.");
});

test("numbers read the French way, grams with one decimal under ten", () => {
  assert.equal(figure(12.6), "12,6");
  assert.equal(figure(13), "13");
  assert.equal(figure(2.25), "2,3");
  assert.equal(figure(-2.25), "-2,3");
  assert.equal(figure(-0.04), "0");
  assert.equal(figure(38, 0), "38");
  assert.equal(figure("x"), "");
  assert.equal(gramsLabel(4.24), "4,2");
  assert.equal(gramsLabel(9.96), "10");
  assert.equal(gramsLabel(52.4), "52");
  assert.equal(gramsLabel(0), "0");
});

test("the planned grams are the slicer's, or its length weighed with the fiche", () => {
  assert.equal(plannedGrams({ mm: 1234.5, g: 3.7 }, null), 3.7);
  const weighed = plannedGrams({ mm: 1000, g: 0 }, { density: 1.24, diameter_mm: 1.75 });
  assert.ok(Math.abs(weighed - 1.24 * Math.PI * 0.875 * 0.875) < 1e-9);
  assert.equal(plannedGrams({ mm: 1000, g: 0 }, null), null);
  assert.equal(plannedGrams({ mm: 1000, g: 0 }, { density: 0, diameter_mm: 1.75 }), null);
  assert.equal(plannedGrams({ mm: 0, g: 0 }, { density: 1.24, diameter_mm: 1.75 }), null);
  assert.equal(plannedGrams(undefined, null), null);
});

test("a spool that may run short is told, without blocking the launch", () => {
  const info = spoolSlots(MANAGER);
  const filaments = [
    { index: 0, logical: "T1A", used: 1 }, { index: 1, logical: "T1B", used: 1 },
    { index: 2, logical: "T1C", used: 0 }, { index: 3, logical: "T1D", used: 1 },
    { index: 4, logical: "T2A", used: 1 }, { index: 5, logical: "T2B", used: 1 },
  ];
  const planned = { items: [
    { mm: 17000, g: 52 }, { mm: 100000, g: 310 }, { mm: 0, g: 0 }, { mm: 2000, g: 0 },
    { mm: 5000, g: 15 }, { mm: 5000, g: 15 },
  ] };
  const assignments = { T1A: "T2B", T1B: "T1B", T1D: "T2D", T2A: "T2A", T2B: "T1D" };
  assert.equal(MARGIN, 0.1);
  assert.deepEqual(shortfalls(filaments, assignments, info, planned), [
    { slot: "T2B", level: "short", text: "T2B : reste ~38 g, le fichier en demande ~52 g" },
    { slot: "T1B", level: "tight", text: "T1B : reste ~338 g pour ~310 g demandés, marge faible" },
    { slot: "T2D", level: "short", text: "T2D : reste ~0 g, le fichier en demande ~6 g" },
  ]);
  // Doubtful or unknown spools say nothing about what they hold, and so
  // does a file whose plan could not be read.
  assert.deepEqual(shortfalls(filaments, { T2A: "T2A", T2B: "T1D" }, info, planned), []);
  assert.deepEqual(shortfalls(filaments, assignments, info, null), []);
  assert.deepEqual(shortfalls(filaments, assignments, null, planned), []);
  assert.deepEqual(shortfalls(filaments, { T1B: "T1B" }, info, { items: [{ mm: 1, g: 1 }, { mm: 1000, g: 300 }] }), []);
});

test("the count is said unverified until a weighing has checked it", () => {
  const info = spoolSlots(MANAGER);
  assert.equal(countingUnverified(info), true);
  assert.equal(countingUnverified(Object.assign({}, info, { verified: true })), false);
  assert.equal(countingUnverified(null), false);
  const fresh = spoolSlots(Object.assign({}, MANAGER, { spools: MANAGER.spools.map((spool) =>
    Object.assign({}, spool, { counted_g: 0, remaining: Object.assign({}, spool.remaining, { exhausted: false }) })) }));
  assert.equal(countingUnverified(fresh), false);
});

test("the notes over the launch button come in order and need the manager", () => {
  const info = spoolSlots(MANAGER);
  const model = choiceModel();
  const planned = { items: [{ mm: 17000, g: 52 }, { mm: 0, g: 0 }] };
  const notes = startNotes(model, { T1A: "T2B" }, info, planned);
  assert.deepEqual(notes.map((note) => note.level), ["short", "warn", "faint"]);
  assert.equal(notes[0].text, "T2B : reste ~38 g, le fichier en demande ~52 g");
  assert.match(notes[1].text, /^T1A : bobine sans puce/);
  assert.equal(notes[2].text, "décompte non encore vérifié par pesée");
  assert.deepEqual(startNotes(model, { T1A: "T2B" }, null, planned), []);
});

// The start window on the page, with the manager answering, then gone: the
// remaining comes from the library, an unnamed chipless spool is shown as
// such, a short spool is told without blocking, and without the manager the
// cards say nothing about what is left. Never the CFS's own 100 %.
test("start window reads the manager, warns without blocking and falls back without it", async () => {
  const { mount } = await import("./www/bobines/bobines.js");
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this.listeners = {}; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(key, value) { this[key] = value; }
    addEventListener(key, value) { this.listeners[key] = value; }
    querySelector() { return null; }
    text() { return [this.textContent || "", ...this.children.map(n => typeof n === "string" ? n : n.text())].join(" "); }
  }
  const all = (node, keep, out = []) => {
    if (typeof node === "string") return out;
    if (keep(node)) out.push(node);
    for (const child of node.children) all(child, keep, out);
    return out;
  };
  const card = (root, name) => all(root, (node) => node.tag === "button" && /\bspool\b/.test(node.className || "")
    && node.text().includes(name))[0];
  const settle = async () => { for (let i = 0; i < 20; i += 1) await new Promise((resolve) => setImmediate(resolve)); };
  const saved = Object.fromEntries(["Node", "document", "fetch", "setInterval", "clearInterval"].map(k => [k, globalThis[k]]));
  const realNow = Date.now;
  let now = 1.9e12;
  const nodes = Object.fromEntries(["main", "status", "state-label", "offline", "toast"].map(k => [k, new Element("div")]));
  // Every loaded spool of the CFS says 100 %, as a chipless spool does.
  const slots = Object.fromEntries(Object.entries(GATE.slots).map(([name, value]) =>
    [name, Object.assign({}, value, { remain: value.loaded ? 100 : -1 })]));
  const status = { print_stats: { state: "standby" }, kctrl_print_gate: Object.assign({}, GATE, { slots }) };
  let manager = MANAGER;
  const calls = [];
  const answer = (body, ok = true) => ({ ok, status: ok ? 200 : 404, json: async () => body });
  try {
    Date.now = () => now;
    globalThis.Node = Element;
    globalThis.document = { createElement: tag => new Element(tag), createTextNode: text => String(text) };
    globalThis.setInterval = () => 1;
    globalThis.clearInterval = () => {};
    globalThis.fetch = async (path, options) => {
      calls.push(options.method + " " + path);
      if (path.startsWith("/printer/objects/query?")) return answer({ result: { status } });
      if (path === "/machine/k1_control/spools/status") {
        return manager ? answer({ result: manager }) : answer({ error: { message: "Not Found" } }, false);
      }
      if (path.startsWith("/machine/k1_control/spools/planned?file=")) {
        return answer({ result: { file: "x", planned: [{ mm: 17000, g: 52 }, { mm: 0, g: 0 }], note: "2 filament(s) prévu(s)" } });
      }
      throw new Error("unexpected " + path);
    };
    const app = mount({ getElementById: key => nodes[key] }, { overlay: false });
    await settle();
    const main = nodes.main;
    assert.match(main.text(), /~338 g · 34 % · 113 m/);
    assert.match(main.text(), /puce 64 %/);
    assert.match(main.text(), /à vérifier/);
    assert.match(main.text(), /écriture au CFS en attente/);
    assert.doesNotMatch(main.text(), /100 %/);
    const unnamed = card(main, "T1A");
    assert.match(unnamed.className, /is-unknown/);
    assert.doesNotMatch(unnamed.className, /is-empty/);
    assert.equal(unnamed.disabled, true);
    assert.match(unnamed.text(), /non identifiée/);
    assert.match(card(main, "T1C").text(), /vide/);
    assert.match(main.text(), /T1A : bobine sans puce que le CFS n'a pas identifiée/);
    assert.match(main.text(), /décompte non encore vérifié par pesée/);
    assert.doesNotMatch(main.text(), /reste ~/);
    // The operator connects the black filament to the nearly empty blue spool.
    card(main, "T2B").listeners.click();
    assert.match(main.text(), /T2B : reste ~38 g, le fichier en demande ~52 g/);
    const launch = all(main, (node) => node.tag === "button" && node.text().includes("Lancer l'impression"))[0];
    assert.ok(launch);
    assert.ok(!launch.disabled);
    assert.deepEqual(calls.filter((call) => call.includes("planned")), [
      "GET /machine/k1_control/spools/planned?file=" + encodeURIComponent(GATE.file)]);
    // The manager stops answering: one failure keeps what it said, the
    // second takes it all away, and the start is the same as before.
    manager = null;
    now += 6000;
    await app.poll();
    await settle();
    assert.match(main.text(), /~338 g/);
    now += 6000;
    await app.poll();
    await settle();
    assert.doesNotMatch(main.text(), /~338 g|puce|à vérifier|non identifiée|reste ~|décompte|100 %/);
    assert.match(card(main, "T1A").className, /is-empty/);
    assert.ok(!all(main, (node) => node.tag === "button" && node.text().includes("Lancer l'impression"))[0].disabled);
    // Read only: nothing but GET, and never more often than every 5 s.
    assert.ok(calls.every((call) => call.startsWith("GET ")));
    assert.equal(calls.filter((call) => call.endsWith("/spools/status")).length, 3);
    app.stop();
  } finally {
    Date.now = realNow;
    for (const [key, value] of Object.entries(saved)) {
      if (value === undefined) delete globalThis[key]; else globalThis[key] = value;
    }
  }
});
