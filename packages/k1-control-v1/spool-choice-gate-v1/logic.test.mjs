// node --test packages/k1-control-v1/spool-choice-gate-v1/logic.test.mjs
// The pure part of the Bobines page, on the spools of the machine as read
// on 10 September (T1B black, T1D white, T2A red, T2B blue, T2C white PETG,
// T2D lilac) and the cube file (black used, #8080FF declared).

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  NAMES, assign, buildModel, colourName, compatibility, completeness,
  elapsedLabel, isLight, mapParam, nextToConnect, normaliseHex, pendingKey,
  remainingLabel, shortName, summaryLine,
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
  assert.equal(remainingLabel(80), "reste 80 %");
  assert.equal(remainingLabel(-1), "");
  assert.equal(remainingLabel("x"), "");
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
