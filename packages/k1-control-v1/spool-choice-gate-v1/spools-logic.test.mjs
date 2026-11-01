// node --test packages/k1-control-v1/spool-choice-gate-v1/spools-logic.test.mjs
//
// The Bobines window inside Mainsail. The calculator is checked against the
// cases the Python model wrote in calculator-vectors.json, the refusals against
// the model's own words; then the linked fields, the labels, the stock, the
// journal, and the window itself on a small fake DOM.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as logic from "./www/bobines/spools-logic.js";
import { colourName } from "./www/bobines/logic.js";

const VECTORS = JSON.parse(readFileSync(new URL("../spool-manager-v1/calculator-vectors.json", import.meta.url), "utf8"));
// The model's string literals, joined where Python splits them over two lines.
const MODEL = readFileSync(new URL("../spool-manager-v1/kctrl_spools_model.py", import.meta.url), "utf8")
  .replace(/"\s*\n\s*"/g, "");
const PLA = logic.gramsPerMetre(1.24, 1.75);
const CONTEXT = { tare: 180, initial: 1000, gpm: PLA };

// ---------------------------------------------------------------- calculator
test("the vectors are the ones the Python model writes", () => {
  assert.equal(VECTORS.format, "kctrl_spools.vectors");
  for (const key of ["round_half_away", "grams_per_metre", "grams_of_mm", "net_of_length", "net_of_gross",
    "net_of_percent", "shown", "colour_key", "suggest_creality_id"]) {
    assert.ok(Array.isArray(VECTORS[key]) && VECTORS[key].length > 0, key);
  }
});

test("rounding is half away from zero and never -0, as in Python", () => {
  for (const [value, digits, expected] of VECTORS.round_half_away) {
    const result = logic.roundHalfAway(value, digits);
    assert.equal(result, expected, value + " at " + digits);
    assert.ok(!Object.is(result, -0), value + " gives -0");
  }
});

test("grams per metre, of a length and of a net, are the K1's very doubles", () => {
  for (const [density, diameter, expected] of VECTORS.grams_per_metre) {
    assert.equal(logic.gramsPerMetre(density, diameter), expected);
  }
  for (const [mm, density, diameter, expected] of VECTORS.grams_of_mm) {
    assert.equal(logic.gramsOfMm(mm, logic.gramsPerMetre(density, diameter)), expected);
  }
  for (const [metres, density, diameter, expected] of VECTORS.net_of_length) {
    assert.equal(logic.netOfLength(metres, logic.gramsPerMetre(density, diameter)), expected);
  }
});

test("a net from a weighing or from a percentage", () => {
  for (const [gross, tare, expected] of VECTORS.net_of_gross) assert.equal(logic.netOfGross(gross, tare), expected);
  for (const [percent, initial, expected] of VECTORS.net_of_percent) {
    assert.equal(logic.netOfPercent(percent, initial), expected);
  }
  assert.throws(() => logic.netOfGross(100, 180.5), {
    message: "poids brut 100 g inférieur à la tare 180,5 g de la bobine vide : vérifier la pesée ou le type de bobine vide",
  });
});

test("what a spool view shows: grams, percent and metres", () => {
  for (const vector of VECTORS.shown) {
    const gpm = logic.gramsPerMetre(vector.density, vector.diameter);
    assert.deepEqual(logic.shown(vector.net_g, vector.initial_g, gpm), vector.expected, JSON.stringify(vector));
  }
});

test("colours and Creality records are read as the K1 reads them", () => {
  for (const [text, expected] of VECTORS.colour_key) assert.equal(logic.colourKey(text), expected, JSON.stringify(text));
  for (const [maker, material, name, expected] of VECTORS.suggest_creality_id) {
    const label = [maker, material, name].join(" / ");
    assert.equal(logic.suggestCrealityId(maker, material, name, VECTORS.materials), expected, label);
    assert.equal(logic.suggestCrealityId(maker, material, name, Object.values(VECTORS.materials)), expected, label);
  }
  assert.equal(logic.fold("Straße 3D"), "strasse3d");
});

test("the refusals typed here are the model's own words", () => {
  assert.ok(MODEL.includes('"poids brut %s g inférieur à la tare %s g de la bobine vide : '
    + 'vérifier la pesée ou le type de bobine vide"'));
  assert.ok(MODEL.includes('"' + logic.GROSS_WITHOUT_TARE + '"'));
  assert.ok(MODEL.includes('"estimation de %s g au-delà du net initial de %s g"'));
  assert.ok(MODEL.includes("_number(params, \"value_g\", 0, " + logic.VALUE_MAX_G + ")"));
  assert.ok(MODEL.includes('SPOOL_MATERIALS = (' + logic.SPOOL_MATERIALS.map((name) => '"' + name + '"').join(", ") + ")"));
  assert.ok(MODEL.includes('STATES = (' + ["cfs", "a_ranger", "stock", "terminee", "jetee"].map((name) => '"' + name + '"').join(", ") + ")"));
  for (const state of logic.STATE_ORDER) assert.ok(logic.STATE_LABELS[state], state);
});

test("a number typed by a person", () => {
  assert.equal(logic.parseNumber("1 234,5"), 1234.5);
  assert.equal(logic.parseNumber("1 234,5"), 1234.5);
  assert.equal(logic.parseNumber("1 234"), 1234);
  assert.equal(logic.parseNumber(" 470 "), 470);
  assert.equal(logic.parseNumber(",5"), 0.5);
  assert.equal(logic.parseNumber(""), null);
  assert.equal(logic.parseNumber("   "), null);
  assert.equal(logic.parseNumber(null), null);
  assert.ok(Number.isNaN(logic.parseNumber("abc")));
  assert.ok(Number.isNaN(logic.parseNumber("1,2,3")));
  assert.ok(Number.isNaN(logic.parseNumber("12 g")));
  assert.equal(logic.parseNumber(12.5), 12.5);
});

// ------------------------------------------------------- what is left, typed
test("a gross weight is a weighing and fills the three other fields", () => {
  const result = logic.remainingFrom("gross", "650", CONTEXT);
  assert.equal(result.error, "");
  assert.deepEqual(result.values, { gross: "650", net: "470", percent: "47", metres: "158" });
  assert.deepEqual(result.basis, { kind: "pesee", value_g: 650 });
  // A weighing may find a few grams more than the spool held new.
  const heavy = logic.remainingFrom("gross", "1190", CONTEXT);
  assert.equal(heavy.error, "");
  assert.equal(heavy.values.percent, "101");
  assert.deepEqual(heavy.basis, { kind: "pesee", value_g: 1190 });
});

test("a net, a percentage or a length is an estimate", () => {
  const net = logic.remainingFrom("net", "8,25", CONTEXT);
  assert.deepEqual(net.basis, { kind: "estimation", value_g: 8.25 });
  assert.deepEqual(net.values, { gross: "188", net: "8,3", percent: "1", metres: "2,8" });
  const percent = logic.remainingFrom("percent", "47", CONTEXT);
  assert.deepEqual(percent.basis, { kind: "estimation", value_g: 470 });
  assert.deepEqual(percent.values, { gross: "650", net: "470", percent: "47", metres: "158" });
  const metres = logic.remainingFrom("metres", "158", CONTEXT);
  assert.deepEqual(metres.basis, { kind: "estimation", value_g: logic.roundHalfAway(158 * PLA, 2) });
  assert.equal(metres.values.net, "471");
  // Without a known empty spool the gross field stays empty.
  const bare = logic.remainingFrom("net", "470", { tare: null, initial: 1000, gpm: PLA });
  assert.equal(bare.values.gross, "");
  assert.equal(bare.values.percent, "47");
});

test("what cannot be computed says why, and sends nothing", () => {
  const cases = [
    ["gross", "650", { tare: null, initial: 1000, gpm: PLA }, logic.GROSS_WITHOUT_TARE],
    ["gross", "100", CONTEXT, logic.grossBelowTare(100, 180)],
    ["percent", "47", { tare: 180, initial: 0, gpm: PLA }, "net initial inconnu : pourcentage impossible"],
    ["metres", "158", { tare: 180, initial: 1000, gpm: 0 }, "densité inconnue : longueur impossible"],
    ["net", "1200", CONTEXT, "estimation de 1200 g au-delà du net initial de 1000 g"],
    ["percent", "120", CONTEXT, "estimation de 1200 g au-delà du net initial de 1000 g"],
    ["gross", "16000", CONTEXT, "au-delà de 15000 g"],
    ["net", "abc", CONTEXT, "nombre attendu"],
    ["net", "-5", CONTEXT, "nombre positif attendu"],
    ["poids", "5", CONTEXT, "champ inconnu"],
  ];
  for (const [field, text, context, message] of cases) {
    const result = logic.remainingFrom(field, text, context);
    assert.equal(result.error, message, field + " " + text);
    assert.equal(result.basis, null, field + " " + text);
  }
  const empty = logic.remainingFrom("net", "", CONTEXT);
  assert.deepEqual(empty, { values: { gross: "", net: "", percent: "", metres: "" }, basis: null, error: "" });
});

test("the four fields open on what the K1 says is left", () => {
  assert.deepEqual(logic.remainingFields({ net_g: 470, gross_g: 650, shown: { g: 470, percent: 47, m: 158 } }),
    { gross: "650", net: "470", percent: "47", metres: "158" });
  assert.deepEqual(logic.remainingFields({ net_g: 4.5, gross_g: null, shown: { g: 5, percent: null, m: 1.5 } }),
    { gross: "", net: "4,5", percent: "", metres: "1,5" });
  assert.deepEqual(logic.remainingFields(null), { gross: "", net: "", percent: "", metres: "" });
  assert.deepEqual(logic.remainingFields({ net_g: null }), { gross: "", net: "", percent: "", metres: "" });
});

// ------------------------------------------------------------------ labels
test("slots, spools and what is left, in plain words", () => {
  assert.deepEqual(logic.slotStatus({ status: "a_verifier" }), { text: "à vérifier", tone: "warn" });
  assert.deepEqual(logic.slotStatus({ status: "ok" }), { text: "à jour", tone: "ok" });
  assert.deepEqual(logic.slotStatus({ status: "nouveau" }), { text: "nouveau", tone: "faint" });
  assert.deepEqual(logic.slotStatus(null), { text: "état inconnu", tone: "faint" });
  for (const status of ["ok", "a_verifier", "inconnue", "attendue", "en_attente_cfs", "vide", "hors_ligne"]) {
    assert.ok(logic.SLOT_STATUS[status], status);
  }
  assert.equal(logic.idLabel("B001"), "B-001");
  assert.equal(logic.idLabel(""), "");
  assert.equal(logic.remainingText({ net_g: 470, shown: { g: 470, percent: 47, m: 158 } }), "~470 g · 47 % · 158 m");
  assert.equal(logic.remainingText({ net_g: 50, shown: { g: 50, percent: null, m: 16.8 } }), "~50 g · 16,8 m");
  assert.equal(logic.remainingText({ net_g: 0, exhausted: true, shown: { g: 0 } }), "épuisée selon le décompte");
  assert.equal(logic.remainingText(null), "reste inconnu");
  assert.equal(logic.nearlyEmpty({ net_g: 20 }), true);
  assert.equal(logic.nearlyEmpty({ net_g: 21 }), false);
  assert.equal(logic.nearlyEmpty({ net_g: 300, exhausted: true }), true);
  assert.equal(logic.nearlyEmpty({ net_g: null }), false);
  assert.equal(logic.whereText({ state: "cfs", slot: "T1B" }), "au CFS en T1B");
  assert.equal(logic.whereText({ state: "stock", place: "Étagère 2" }), "en stock · Étagère 2");
  assert.equal(logic.whereText({ state: "stock", place: "" }), "en stock");
  assert.equal(logic.whereText({ state: "jetee" }), "jetée");
});

test("fiches and empty spools, named the way Thomas names them", () => {
  const fiche = { manufacturer: "Geeetech", name: "PLA Silk", material: "PLA", colour: "FF1E1E" };
  assert.equal(logic.ficheName(fiche), "Geeetech PLA Silk");
  assert.equal(logic.ficheName({ manufacturer: " ", name: "" }), "sans nom");
  assert.equal(logic.ficheName(null), "fiche inconnue");
  assert.equal(logic.ficheLine(fiche), "PLA · " + colourName("FF1E1E"));
  assert.equal(logic.ficheLine({ material: "PETG", colour: "" }), "PETG");
  const empty = { manufacturer: "Geeetech", name: "plastique fine", spool_material: "plastique", tare_g: 182,
    nominal_net_g: 1000, source: "pesee" };
  assert.equal(logic.emptySpoolName(empty), "Geeetech plastique fine");
  assert.equal(logic.emptySpoolLine(empty), "plastique · tare 182 g · 1000 g net · pesée");
  assert.equal(logic.emptySpoolName(null), "aucune");
});

test("a write to the CFS says what it changes and which refills it makes or breaks", () => {
  assert.equal(logic.impactText({ gained: ["T1B"], lost: [] }), "relais automatique gagné avec T1B");
  assert.equal(logic.impactText({ gained: ["T2A"], lost: ["T1C", "T1D"] }),
    "relais automatique gagné avec T2A ; relais automatique perdu avec T1C, T1D");
  assert.equal(logic.impactText({ gained: [], lost: [] }), "aucun relais automatique changé");
  assert.equal(logic.impactText(null), "");
  assert.equal(logic.planText({ material: "001001", colour: "0ff1e1e" }, VECTORS.materials),
    "matière Hyper PLA et couleur " + colourName("FF1E1E") + " #FF1E1E");
  assert.equal(logic.planText({ material: null, colour: "000ff00" }, VECTORS.materials),
    "couleur " + colourName("00FF00") + " #00FF00");
  assert.equal(logic.planText({ material: "099999", colour: null }, VECTORS.materials), "matière 99999");
  assert.equal(logic.planText(null, VECTORS.materials), "");
});

test("the K1 material records, by type, the way a select lists them", () => {
  assert.deepEqual(logic.materialTypes(VECTORS.materials), ["ABS", "PA", "PETG", "PLA", "PLA-SILK", "TPU"]);
  assert.deepEqual(logic.materialsOfType(VECTORS.materials, "pla").map((record) => record.id),
    ["02001", "01002", "01001", "00001"]);
  assert.equal(logic.materialRecord(VECTORS.materials, "01003").name, "Hyper PETG");
  assert.equal(logic.materialRecord(VECTORS.materials, "nope"), null);
});

test("slots grouped by unit, A to D", () => {
  const views = ["T2A", "T1B", "T5A", "T1A"].map((slot) => ({ slot }));
  assert.deepEqual(logic.units(views).map((unit) => [unit.unit, unit.slots.map((view) => view.slot)]),
    [["T1", ["T1A", "T1B"]], ["T2", ["T2A"]]]);
  assert.deepEqual(logic.units(null), []);
  assert.equal(logic.SLOT_NAMES.length, 16);
});

// ------------------------------------------------------------------- stock
const FICHES = {
  F001: { id: "F001", manufacturer: "Geeetech", name: "PLA Silk", material: "PLA", colour: "FF1E1E" },
  F002: { id: "F002", manufacturer: "Creality", name: "Hyper PLA", material: "PLA", colour: "00FF00" },
  F003: { id: "F003", manufacturer: "Sunlu", name: "PETG", material: "PETG", colour: "0000FF" },
};
const SPOOLS = [
  { id: "B001", label: "B-001", filament: "F001", state: "stock", place: "Étagère 2", notes: "" },
  { id: "B002", label: "B-002", filament: "F002", state: "cfs", slot: "T1A", place: "" },
  { id: "B003", label: "B-003", filament: "F003", state: "a_ranger", place: "" },
  { id: "B004", label: "B-004", filament: "F001", state: "terminee", place: "" },
  { id: "B005", label: "B-005", filament: "F002", state: "stock", place: "Boîte sèche", notes: "ouverte en mars" },
  { id: "B006", label: "B-006", filament: "F003", state: "jetee", place: "" },
];
const ids = (spools) => spools.map((spool) => spool.id);

test("the stock lists what is put away first, then by maker", () => {
  assert.deepEqual(ids(logic.filterStock(SPOOLS, FICHES, {})), ["B003", "B005", "B001"]);
  assert.deepEqual(ids(logic.filterStock(SPOOLS, FICHES, { scope: "actives" })), ["B003", "B005", "B001", "B002"]);
  assert.deepEqual(ids(logic.filterStock(SPOOLS, FICHES, { scope: "archivees" })), ["B004", "B006"]);
  assert.deepEqual(ids(logic.placeableSpools(SPOOLS, FICHES)), ["B003", "B005", "B001"]);
});

test("a search finds a spool by any word, accents and case aside", () => {
  const find = (text, scope) => ids(logic.filterStock(SPOOLS, FICHES, { text, scope }));
  assert.deepEqual(find("etagere"), ["B001"]);
  assert.deepEqual(find("ÉTAGÈRE 2"), ["B001"]);
  assert.deepEqual(find("b-005"), ["B005"]);
  assert.deepEqual(find("creality seche"), ["B005"]);
  assert.deepEqual(find("mars"), ["B005"]);
  assert.deepEqual(find(colourName("FF1E1E")), ["B001"]);
  assert.deepEqual(find("t1a", "actives"), ["B002"]);
  assert.deepEqual(find("pla", "archivees"), ["B004"]);
  assert.deepEqual(find("introuvable"), []);
  assert.deepEqual(ids(logic.filterStock(SPOOLS, FICHES, { material: "PETG" })), ["B003"]);
  assert.deepEqual(ids(logic.filterStock(SPOOLS, FICHES, { colour: "00FF00" })), ["B005"]);
  assert.deepEqual(ids(logic.filterStock(SPOOLS, FICHES, { place: "Boîte sèche" })), ["B005"]);
});

test("the stock filters offer only what the chosen spools hold", () => {
  const facets = logic.stockFacets(SPOOLS, FICHES, "rangees");
  assert.deepEqual(facets.materials, ["PETG", "PLA"]);
  assert.deepEqual(facets.colours.map((colour) => colour.key).sort(), ["0000FF", "00FF00", "FF1E1E"]);
  assert.deepEqual(facets.places, ["Boîte sèche", "Étagère 2"]);
  assert.deepEqual(logic.stockFacets(SPOOLS, FICHES, "archivees").places, []);
});

test("candidates, and who uses a fiche", () => {
  assert.deepEqual(ids(logic.candidateSpools({ candidates: ["B005", "B999", "B001"] }, SPOOLS)), ["B005", "B001"]);
  assert.deepEqual(logic.candidateSpools({}, SPOOLS), []);
  assert.deepEqual(logic.usersOf(SPOOLS, "filament", "F001"), ["B-001", "B-004"]);
  assert.deepEqual(logic.usersOf(SPOOLS, "filament", "F999"), []);
});

// --------------------------------------------------------------- catalogue
test("the SpoolmanDB catalogue is searched word by word", () => {
  const entries = [
    { key: "Sunlu|1000|117|plastique", manufacturer: "Sunlu", spool_material: "plastique", net_g: 1000, tare_g: 117,
      lines: [{ material: "PLA", name: "PLA+" }, { material: "PETG", name: "PETG" }] },
    { key: "Geeetech|1000|150|carton", manufacturer: "Geeetech", spool_material: "carton", net_g: 1000, tare_g: 150,
      lines: [{ material: "PLA", name: "Silk PLA" }] },
  ];
  assert.deepEqual(logic.searchTares(entries, "sunlu").map((entry) => entry.manufacturer), ["Sunlu"]);
  assert.deepEqual(logic.searchTares(entries, "pla carton").map((entry) => entry.manufacturer), ["Geeetech"]);
  assert.deepEqual(logic.searchTares(entries, "117").map((entry) => entry.manufacturer), ["Sunlu"]);
  assert.equal(logic.searchTares(entries, "").length, 2);
  assert.equal(logic.searchTares(entries, "", 1).length, 1);
  assert.equal(logic.tareLines(entries[0]), "PLA, PETG");
  const shipped = JSON.parse(readFileSync(new URL("./www/bobines/tares.json", import.meta.url), "utf8"));
  assert.equal(shipped.format, "kctrl_spools.tares");
  assert.ok(logic.searchTares(shipped.entries, "").length === 30);
});

// ----------------------------------------------------------------- journal
test("each journal line reads as a sentence", () => {
  const names = {
    spools: {},
    filaments: { F001: FICHES.F001 },
    empty: { V001: { manufacturer: "Geeetech", name: "plastique fine" } },
  };
  const cases = [
    [{ kind: "bobine_vide", empty_spool: "V001", change: "pesée", tare_g: 182 }, "Bobine vide Geeetech plastique fine pesée · tare 182 g"],
    [{ kind: "bobine_vide", empty_spool: "V009", change: "supprimée" }, "Bobine vide V-009 supprimée"],
    [{ kind: "fiche", filament: "F001", change: "créée depuis le CFS", slot: "T1A" }, "Fiche Geeetech PLA Silk créée depuis le CFS en T1A"],
    [{ kind: "fiche", filament: "F001", change: "modifiée", fields: ["colour", "name"] }, "Fiche Geeetech PLA Silk modifiée (colour, name)"],
    [{ kind: "bobine", spool: "B001", change: "créée", net_g: 1000 }, "B-001 créée · 1000 g"],
    [{ kind: "bobine", spool: "B001", change: "identité du CFS adoptée", slot: "T1A", fields: ["filament"] }, "B-001 identité du CFS adoptée en T1A (filament)"],
    [{ kind: "etat", spool: "B001", state: "cfs", slot: "T1B" }, "B-001 mise au CFS en T1B"],
    [{ kind: "etat", spool: "B001", state: "stock", place: "Étagère 2", detail: "rangée" }, "B-001 en stock : Étagère 2 · rangée"],
    [{ kind: "etat", spool: "B001", state: "a_ranger", slot: "T1B", detail: "retirée" }, "B-001 à ranger (sortie de T1B) · retirée"],
    [{ kind: "etat", spool: "B001", state: "terminee", slot: "" }, "B-001 terminée"],
    [{ kind: "reste", spool: "B001", basis: "pesee", net_g: 470, gap_g: -12.5 }, "B-001 : reste pesé 470 g · écart -13 g au décompte"],
    [{ kind: "reste", spool: "B001", basis: "estimation", net_g: 300, gap_g: 4.25 }, "B-001 : reste estimé 300 g · écart +4,3 g au décompte"],
    [{ kind: "consommation", spool: "B001", slot: "T1A", mm: 1500, g: 4.47, m: 1.5 }, "B-001 : 4,5 g · 1,5 m en T1A"],
    [{ kind: "consommation", slot: "T2B", mm: 2000, detail: "segment S001 ignoré" }, "Consommation : 2 m en T2B · segment S001 ignoré"],
    [{ kind: "impression", file: "gcodes/sub/cube.gcode", outcome: "complete", spools: ["B001", "B002"], unassigned: 1 },
      "Impression cube.gcode terminée · B-001, B-002 · 1 à attribuer"],
    [{ kind: "impression", file: "vase.gcode", outcome: "cancelled", spools: [], unassigned: 0 }, "Impression vase.gcode annulée"],
    [{ kind: "ecriture_cfs", slot: "T1A", spool: "B002", result: "ecart", detail: "couleur relue 0000000" },
      "Écriture au CFS T1A (B-002) : écart à la relecture · couleur relue 0000000"],
    [{ kind: "ecriture_cfs", slot: "T1A", spool: "B002", result: "en attente" }, "Écriture au CFS T1A (B-002) : en attente"],
    [{ kind: "ecriture_cfs", slot: "T1A", spool: "B002", result: "annulée", detail: "bobine retirée" },
      "Écriture au CFS T1A (B-002) : annulée · bobine retirée"],
    [{ kind: "ecriture_cfs", slot: "T1A", spool: "B002", result: "annulee" }, "Écriture au CFS T1A (B-002) : annulée"],
    [{ kind: "cfs", slot: "T1C", detail: "bobine arrivée" }, "CFS T1C : bobine arrivée"],
    [{ kind: "reglages", fields: ["low_g", "cut_loss_mm"], low_g: 50, cut_loss_mm: 12.5 },
      "Réglages : seuil bobine basse (g) 50, perte à la coupe (mm) 12,5"],
    [{ kind: "route", slot: "T1B", spool: "B003", from: "T1A" }, "Filament engagé en T1B (B-003) après T1A"],
    [{ kind: "erreur", detail: "fin d'impression illisible" }, "Erreur : fin d'impression illisible"],
    [{ kind: "import" }, "Bibliothèque importée"],
    [{ kind: "autre", detail: "x" }, "autre · x"],
  ];
  for (const [entry, expected] of cases) assert.equal(logic.journalText(entry, names), expected, entry.kind);
  assert.equal(logic.journalText(null, names), "");
});

test("journal tones and the entries that touch a spool", () => {
  assert.equal(logic.journalTone({ kind: "erreur" }), "warn");
  assert.equal(logic.journalTone({ kind: "ecriture_cfs", result: "ok" }), "ok");
  assert.equal(logic.journalTone({ kind: "ecriture_cfs", result: "en attente" }), "accent");
  assert.equal(logic.journalTone({ kind: "ecriture_cfs", result: "erreur" }), "warn");
  assert.equal(logic.journalTone({ kind: "ecriture_cfs", result: "annulée" }), "");
  assert.equal(logic.journalTone({ kind: "ecriture_cfs", result: "annulee" }), "");
  assert.equal(logic.journalTone({ kind: "bobine" }), "");
  assert.equal(logic.touches({ spool: "B001" }, "B001"), true);
  assert.equal(logic.touches({ kind: "impression", spools: ["B002", "B001"] }, "B001"), true);
  assert.equal(logic.touches({ kind: "import" }, "B001"), false);
  assert.equal(logic.touches({ spool: "B001" }, ""), false);
});
