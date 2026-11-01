// The spool manager inside Mainsail (document 102, lot I): a « Bobines »
// button over Mainsail's top bar and the window it opens, to keep the spools,
// their fiches and their empty spools, and to see what the CFS holds.
//
// overlay.js loads this module on its own, after the start window: an error
// here leaves the start window intact. It never changes Mainsail's page: the
// button and the window live in their own shadow root, laid over the top bar,
// and fall back to the top-right corner when the bar is not where expected.
//
// Everything comes from /machine/k1_control/spools/ and every change goes
// back as one action the K1 checks again. Nothing is written to the CFS
// during a print, even paused: the K1 keeps the write for the end.

import { colourName, figure, gramsLabel, isLight, normaliseHex, shortName } from "./logic.js";
import {
  DIAMETER, NAME_LIMIT, NOTES_LIMIT, OUTCOME_LABELS, SCOPES, SPOOL_MATERIALS, WRITE_RESULTS,
  candidateSpools, colourKey, emptySpoolLine, emptySpoolName, ficheLine, ficheName, filterStock,
  gramsOfMm, gramsPerMetre, idLabel, impactText, journalText, journalTone, materialRecord,
  materialTypes, materialsOfType, nearlyEmpty, parseNumber, placeableSpools, planText,
  remainingFields, remainingFrom, remainingText, searchTares, slotStatus, stockFacets,
  suggestCrealityId, tareLines, touches, units, usersOf, whereText,
} from "./spools-logic.js";

const API = "/machine/k1_control/spools/";
const TARES = new URL("./tares.json", import.meta.url).href;
const TICK_MS = 1000, OPEN_MS = 5000, CLOSED_MS = 30000, JOURNAL_MS = 30000, JOURNAL_LIMIT = 200, MATERIALS_RETRY_MS = 30000;
const TIMEOUTS = { status: 8000, materials: 8000, journal: 8000, action: 15000, write: 65000, export: 20000, import: 20000, tares: 15000 };
const UNSURE = [0, 502, 504];
const CHANGED = /a changé entre-temps/;
const CHANGED_TEXT = "La bibliothèque a changé entre-temps : vérifie puis refais l'action.";
const EXPORT_FORMAT = "kctrl_spools.export";
const TABS = [["cfs", "CFS"], ["stock", "Stock"], ["vides", "Bobines vides"], ["journal", "Journal"]];
const BARS = ["header.v-app-bar", "header.topbar", ".v-app-bar"];
const CONTROLS = "button, a[href], [role=button], .v-btn";
const TITLES = ".v-toolbar__title, h1, h2";
const START_OPEN = ["choice", "ending", "launched"];
const ARCHIVED = ["terminee", "jetee"];
const LINKED = [["gross", "Poids brut (g)", "pesé avec la bobine"], ["net", "Net (g)", "filament seul"], ["percent", "Pourcentage", "du net neuf"], ["metres", "Longueur (m)", ""]];
const FIELD_LABELS = { initial_net_g: "Net neuf", tare_g: "Tare", nominal_net_g: "Net nominal", diameter_mm: "Diamètre", density: "Densité", low_g: "Seuil bobine basse", cut_loss_mm: "Perte à la coupe" };
const SECTIONS = { slot: ["slot"], spool: ["remaining", "identity", "where", "end"], "new-spool": ["fiche", "spool", "rest", "where", "create"], fiche: ["fiche"], empty: ["empty"], settings: ["settings", "backup"] };
const BOOLEAN_PROPS = ["checked", "selected", "disabled", "hidden", "multiple", "readOnly"];
const ICON = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor">'
  + '<circle cx="12" cy="12" r="9.5" stroke-width="1.6"/><circle cx="12" cy="12" r="6" stroke-width="4" opacity=".45"/>'
  + '<circle cx="12" cy="12" r="2" fill="currentColor" stroke="none"/></svg>';

function failure(message, status) { const error = new Error(message); error.status = status; return error; }
// Moonraker wraps a component's error in its own words: keep the message only.
function cleanError(text) {
  const raw = String(text == null ? "" : text);
  const quoted = raw.match(/'message':\s*'((?:[^'\\]|\\.)*)'/) || raw.match(/"message":\s*"((?:[^"\\]|\\.)*)"/);
  const value = (quoted ? quoted[1] : raw).replace(/^\s*(?:[A-Za-z]*Error:\s*)+/, "").replace(/\\n|\n/g, " ").replace(/\s+/g, " ").trim();
  return value || "erreur inconnue";
}
function metres(mm) { const v = Number(mm); return mm == null || !Number.isFinite(v) ? "? m" : figure(v / 1000) + " m"; }
function grams(value) { const v = Number(value); return value == null || !Number.isFinite(v) ? "? g" : gramsLabel(v) + " g"; }
function capital(text) { const v = String(text == null ? "" : text); return v ? v[0].toUpperCase() + v.slice(1) : v; }
function sentence(text) { const v = capital(String(text == null ? "" : text).trim()); return !v || /[.!?…]$/.test(v) ? v : v + "."; }
function count(number, one, many) { return number + " " + (number < 2 ? one : many); }
function joinFr(items) { const list = items.filter(Boolean).map(String); return list.length < 2 ? list.join("") : list.slice(0, -1).join(", ") + " et " + list[list.length - 1]; }
function usersText(labels) { return labels.length <= 4 ? joinFr(labels) : labels.slice(0, 3).join(", ") + " et " + (labels.length - 3) + " autres"; }
function isoDay(ms) { const d = new Date(ms); const pad = (n) => String(n).padStart(2, "0"); return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
function dateLabel(seconds) {
  const value = Number(seconds);
  if (seconds == null || !Number.isFinite(value) || value <= 0) return "";
  try { return new Date(value * 1000).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); }
  catch (_) { return isoDay(value * 1000); }
}
function dayLabel(seconds) {
  const value = Number(seconds);
  if (seconds == null || !Number.isFinite(value) || value <= 0) return "?";
  try { return new Date(value * 1000).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" }); }
  catch (_) { return isoDay(value * 1000); }
}
function signed(value) { const n = Number(value); return (n > 0 ? "+" : "") + gramsLabel(n) + " g"; }
function entriesByName(records, nameOf) {
  return Object.entries(records || {}).sort(([ka, a], [kb, b]) => nameOf(a).localeCompare(nameOf(b), "fr") || (ka < kb ? -1 : ka > kb ? 1 : 0));
}
function creality(material) { return String(material || "").replace(/^0/, ""); }
function num(value, decimals) { return value == null || value === "" ? "" : figure(value, decimals); }

export function start() {
  if (typeof document === "undefined" || document.getElementById("kctrl-spools")) return null;
  const host = document.createElement("div");
  host.id = "kctrl-spools";
  // Hidden until its styles are in: no unstyled button over Mainsail's bar.
  host.hidden = true;
  const shadow = host.attachShadow({ mode: "open" });
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = new URL("./styles.css", import.meta.url).href;
  let api = null;
  stylesheet.addEventListener("load", () => { host.hidden = false; if (api) api.place(); });
  stylesheet.addEventListener("error", () => console.warn("K1 Control: styles des bobines introuvables"));
  shadow.append(stylesheet);
  document.body.append(host);
  api = mountManager(shadow, { host });
  return api;
}

export function mountManager(root, options) {
  const config = options || {};
  const host = config.host || root.host || null;
  const clock = config.now || (() => Date.now());
  const ask = config.confirm || ((text) => window.confirm(text));
  let sheetSerial = 0, timer = 0, observer = null, observed = null, placing = false, index = {}, indexFor = null;
  const app = {
    status: null, installed: true, seen: false, online: false, error: "", reading: null, statusAt: 0, statusEpoch: 0,
    materials: null, materialsKey: "", materialsError: "", materialsFailed: 0, materialsLoading: false, materialsAt: 0,
    tares: null, taresError: "", taresLoading: false, tareQuery: "",
    journal: null, journalRevision: -1, journalKey: "", journalAt: 0, journalError: "", journalLoading: false,
    open: false, tab: "cfs", sheet: null, busy: "", form: "compact",
    filters: { scope: "rangees", text: "", material: "", colour: "", place: "" }, journalFilter: "", showFiches: false, choices: {},
    signature: "", toastTimer: 0, fullWidth: 0, placed: "", refs: {}, resetScroll: false, liveKey: "",
  };
  function h(tag, attrs, ...children) {
    const node = document.createElement(tag);
    let value = null;
    for (const [key, item] of Object.entries(attrs || {})) {
      if (item == null || item === false) continue;
      if (key === "class") node.className = item;
      else if (key === "style") node.style.cssText = item;
      else if (key === "ref") { app.refs[item] = node; node.dataset.ref = item; }
      else if (key === "dataset") Object.assign(node.dataset, item);
      else if (key === "value") value = item;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), item);
      else if (BOOLEAN_PROPS.includes(key)) node[key] = Boolean(item);
      else node.setAttribute(key, String(item));
    }
    for (const child of children.flat(Infinity)) {
      if (child == null || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    // After the children: a select only takes the value of an option it holds.
    if (value !== null) node.value = String(value);
    return node;
  }
  function fill(node, ...items) { node.replaceChildren(...items.flat(Infinity).filter((i) => i != null && i !== false)); }
  function swatch(hex, extra) {
    const value = normaliseHex(hex);
    const classes = ["swatch"];
    if (extra) classes.push(extra);
    if (!value) classes.push("is-none");
    else if (isLight(value)) classes.push("is-light");
    return h("span", {
      class: classes.join(" "),
      style: value ? "background:#" + value : "",
      title: value ? colourName(value) + " #" + value : "sans couleur",
      "aria-hidden": "true",
    });
  }
  const badge = h("span", { class: "spools-badge", hidden: true });
  const icon = h("span", { class: "spools-icon", "aria-hidden": "true" });
  icon.innerHTML = ICON;
  const launch = h("button", { class: "spools-launch is-compact", type: "button", "aria-haspopup": "dialog",
    "aria-expanded": "false", "aria-controls": "spools-panel", hidden: true,
    onclick: () => (app.open ? close(true) : open()) }, icon, h("span", { class: "spools-label" }, "Bobines"), badge);
  const head = h("header", { class: "spools-head" });
  const banners = h("div", { class: "spools-banners" });
  const tabs = h("nav", { class: "spools-tabs", role: "tablist", "aria-label": "Vues des bobines" });
  const body = h("div", { class: "spools-body" });
  const panel = h("div", { class: "spools spools-panel", id: "spools-panel", role: "dialog",
    "aria-labelledby": "spools-title", tabindex: "-1", hidden: true }, head, banners, tabs, body);
  const toastBox = h("div", { class: "toast is-spools", role: "status", hidden: true });
  root.append(launch, panel, toastBox);
  function onKey(event) {
    if (!app.open || event.key !== "Escape") return;
    // The start window answers Escape first while it is open over Mainsail.
    const start = document.getElementById("kctrl-bobines");
    if (start && START_OPEN.includes(start.dataset && start.dataset.mode)) return;
    close(true);
  }
  function onPointer(event) {
    if (!app.open) return;
    const path = typeof event.composedPath === "function" ? event.composedPath() : [];
    if (host ? path.includes(host) : path.includes(panel) || path.includes(launch)) return;
    close(false);
  }
  function onVisible() { tick(); }
  function onResize() { schedulePlace(); }
  document.addEventListener("keydown", onKey);
  document.addEventListener("pointerdown", onPointer, true);
  document.addEventListener("visibilitychange", onVisible);
  window.addEventListener("resize", onResize);
  function watch(bar) {
    if (bar === observed) return;
    if (observer) observer.disconnect();
    observer = null; observed = bar;
    if (!bar || typeof MutationObserver !== "function") return;
    observer = new MutationObserver(schedulePlace);
    observer.observe(bar, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["style", "class"] });
  }
  function schedulePlace() {
    if (placing) return;
    placing = true;
    const run = () => { placing = false; place(); };
    if (typeof requestAnimationFrame === "function") requestAnimationFrame(run); else setTimeout(run, 0);
  }
  function open() {
    if (app.open || !app.installed) return;
    app.open = true; panel.hidden = false; launch.setAttribute("aria-expanded", "true");
    app.placed = ""; app.signature = "";
    place(); render();
    try { panel.focus({ preventScroll: true }); } catch (_) { /* focus is a comfort */ }
    refresh(); loadMaterials();
    if (app.tab === "journal") loadJournal(true);
  }
  function close(focusLaunch) {
    if (!app.open) return;
    app.open = false; panel.hidden = true; launch.setAttribute("aria-expanded", "false");
    app.signature = ""; renderLaunch();
    if (focusLaunch) { try { launch.focus({ preventScroll: true }); } catch (_) {} }
  }
  function tick() {
    if (document.hidden) return;
    place();
    const now = clock();
    if (!app.reading && now - app.statusAt >= (app.open ? OPEN_MS : CLOSED_MS)) refresh();
    if (app.open && app.tab === "journal" && app.journal && !app.journalLoading && now - app.journalAt >= JOURNAL_MS) loadJournal(false);
  }
  function stop() {
    clearInterval(timer);
    document.removeEventListener("keydown", onKey);
    document.removeEventListener("pointerdown", onPointer, true);
    document.removeEventListener("visibilitychange", onVisible);
    window.removeEventListener("resize", onResize);
    if (observer) observer.disconnect();
    observer = null; observed = null;
    clearTimeout(app.toastTimer);
  }
  function rememberFocus() {
    const active = root.activeElement;
    if (!active || active === launch) return null;
    const state = { ref: (active.dataset && active.dataset.ref) || "", start: null, end: null };
    try { state.start = active.selectionStart; state.end = active.selectionEnd; } catch (_) { /* not a text field */ }
    return state;
  }
  function restoreFocus(state) {
    if (!state || !app.open) return;
    const node = state.ref ? app.refs[state.ref] : null;
    if (node && !node.disabled && !node.hidden) {
      if (root.activeElement === node) return;
      try { node.focus({ preventScroll: true }); } catch (_) {}
      if (state.start != null) { try { node.setSelectionRange(state.start, state.end); } catch (_) {} }
      return;
    }
    const active = root.activeElement;
    if (!active || active.isConnected === false) { try { panel.focus({ preventScroll: true }); } catch (_) {} }
  }
  async function call(method, path, body, timeout) {
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    const limit = timeout || 8000;
    const alarm = setTimeout(() => controller && controller.abort(), limit);
    let response;
    try {
      try {
        response = await fetch(path, { method, headers: body ? { "Content-Type": "application/json" } : undefined,
          body: body ? JSON.stringify(body) : undefined, signal: controller ? controller.signal : undefined, cache: "no-store" });
      } catch (error) {
        throw failure(controller && controller.signal.aborted ? "pas de réponse en " + Math.round(limit / 1000) + " s" : "K1 injoignable", 0);
      }
      let payload = null;
      try { payload = await response.json(); } catch (_) { payload = null; }
      if (!response.ok) {
        const message = payload && payload.error && payload.error.message ? String(payload.error.message) : "HTTP " + response.status;
        throw failure(cleanError(message), response.status);
      }
      // An answer that cannot be read leaves the outcome unknown, like no answer.
      if (payload == null) throw failure("réponse illisible", 0);
      return payload;
    } finally { clearTimeout(alarm); }
  }
  function refresh() { if (!app.reading) app.reading = read().finally(() => { app.reading = null; }); return app.reading; }
  async function reread() { try { await app.reading; } catch (_) {} return refresh(); }
  async function read() {
    const epoch = app.statusEpoch;
    try {
      const payload = await call("GET", API + "status", null, TIMEOUTS.status);
      if (app.statusEpoch === epoch) accept(payload.result, null);
      app.installed = true; app.online = true; app.error = "";
    } catch (error) {
      if (error.status === 404) { app.installed = false; app.status = null; app.seen = false; close(false); }
      else { app.online = false; app.error = error.message; }
    }
    app.statusAt = clock();
    render(); place();
    if (app.open && app.status) {
      loadMaterials();
      if (app.tab === "journal" && app.status.revision !== app.journalRevision && clock() - app.journalAt >= (app.journalError ? JOURNAL_MS : 0)) loadJournal(true);
    }
  }
  function accept(result, ownSheet) {
    if (!result || !Array.isArray(result.slots) || !Array.isArray(result.spools)) throw failure("réponse illisible", 0);
    app.status = result; app.seen = true;
    let sheet = app.sheet;
    if (sheet && sheet !== ownSheet) {
      const before = sheet;
      while (sheet && !merge(sheet)) sheet = sheet.back;
      app.sheet = sheet;
      if (sheet !== before) toast("Ce que tu regardais a été supprimé entre-temps.");
    }
  }
  function merge(sheet) {
    const latest = app.status.revision;
    if (sheet.revision === latest || sheet.merged === latest) return true;
    if (!alive(sheet)) return false;
    sheet.merged = latest;
    if (sheet.creating) { sheet.revision = latest; sheet.version += 1; return true; }
    const fresh = draftOf(sheet.kind, sheet.key);
    let conflict = false;
    for (const [key, value] of Object.entries(fresh)) {
      if (!sheet.touched.has(key)) { sheet.draft[key] = value; sheet.base[key] = value; delete sheet.conflicts[key]; }
      else if (value === sheet.base[key]) delete sheet.conflicts[key];
      else { sheet.conflicts[key] = value; conflict = true; }
    }
    sheet.stale = conflict;
    if (!conflict) sheet.revision = latest;
    sheet.version += 1;
    return true;
  }
  function settle(sheet, keys) {
    const saved = new Set(keys || []);
    if (!sheet.creating) {
      const fresh = draftOf(sheet.kind, sheet.key);
      for (const [key, value] of Object.entries(fresh)) {
        if (saved.has(key) || !sheet.touched.has(key)) { sheet.draft[key] = value; sheet.touched.delete(key); delete sheet.conflicts[key]; }
        else if (value !== sheet.base[key]) sheet.conflicts[key] = value;
        sheet.base[key] = value;
      }
      if (saved.has("remaining")) sheet.typed = null;
    }
    sheet.revision = app.status.revision; sheet.merged = sheet.revision; sheet.stale = false; sheet.error = null; sheet.version += 1;
  }
  function rebase(sheet) {
    if (!sheet.creating) {
      const fresh = draftOf(sheet.kind, sheet.key);
      for (const [key, value] of Object.entries(fresh)) {
        if (!sheet.touched.has(key)) { sheet.draft[key] = value; delete sheet.conflicts[key]; }
        else if (key !== "remaining" && sheet.draft[key] === value) { sheet.touched.delete(key); delete sheet.conflicts[key]; }
        else if (value !== sheet.base[key]) sheet.conflicts[key] = value;
        sheet.base[key] = value;
      }
    }
    sheet.revision = app.status.revision; sheet.merged = sheet.revision; sheet.stale = false; sheet.version += 1;
  }
  function isDirty(sheet) {
    if (sheet.typed && String(sheet.typed.text).trim()) return true;
    if (sheet.creating) return sheet.touched.size > 0;
    for (const key of sheet.touched) if (key !== "remaining" && sheet.draft[key] !== sheet.base[key]) return true;
    return false;
  }
  function setDraft(sheet, key, value) {
    sheet.draft[key] = value;
    if (!sheet.creating && value === sheet.base[key]) sheet.touched.delete(key); else sheet.touched.add(key);
  }
  async function send(path, body, opts) {
    const options = opts || {};
    if (app.busy || !app.status) return null;
    const sheet = app.sheet;
    const section = options.section || "";
    if (sheet && sheet.stale) { rebase(sheet); sheet.error = { section, text: CHANGED_TEXT }; render(); return null; }
    const focus = rememberFocus();
    app.busy = options.busy || path;
    if (sheet) sheet.error = null;
    render();
    const revision = sheet ? sheet.revision : app.status.revision;
    try {
      const reply = await call("POST", API + path, Object.assign({}, body, { revision }), options.timeout || TIMEOUTS.action);
      const answer = reply && reply.result;
      if (!answer || !answer.status) throw failure("réponse illisible", 0);
      app.statusEpoch += 1;
      if (options.leave) { if (app.sheet === sheet) { app.sheet = sheet ? sheet.back : null; app.resetScroll = true; } accept(answer.status, null); }
      else { accept(answer.status, sheet); if (sheet) settle(sheet, options.keys); }
      app.online = true; app.error = ""; app.statusAt = clock();
      return { result: answer.result };
    } catch (error) {
      const message = error.message || "erreur inconnue";
      if (error.status === 409 && CHANGED.test(message)) {
        await reread();
        if (sheet && app.sheet === sheet) { rebase(sheet); sheet.error = { section, text: CHANGED_TEXT }; } else toast(CHANGED_TEXT);
      } else if (UNSURE.includes(error.status)) {
        report(options.unsure || capital(message) + " : la fenêtre se met à jour, vérifie avant de refaire l'action.", section, sheet);
        refresh();
      } else report(sentence(message), section, sheet);
      return null;
    } finally { app.busy = ""; render(); restoreFocus(focus); }
  }
  function report(text, section, sheet) {
    if (sheet && app.sheet === sheet) { sheet.error = { section: section || "", text }; sheet.version += 1; }
    else toast(text);
  }
  function act(action, params, opts) {
    const clean = {};
    for (const [key, value] of Object.entries(params || {})) if (value !== undefined && value !== null) clean[key] = value;
    return send("action", { action, params: clean }, opts);
  }
  function fail(sheet, section, text) { sheet.error = { section, text }; rerender(sheet); return false; }
  function rerender(sheet) { if (sheet) sheet.version += 1; render(); }
  function byId() {
    const status = app.status;
    if (!status) return {};
    if (indexFor !== status) { index = {}; for (const spool of status.spools) if (spool && spool.id) index[spool.id] = spool; indexFor = status; }
    return index;
  }
  function spoolById(id) { return id ? byId()[id] || null : null; }
  function labelOf(id) { if (!id) return "bobine inconnue"; const spool = spoolById(id); return (spool && spool.label) || idLabel(id); }
  function ficheOf(id) { return id && app.status && app.status.filaments ? app.status.filaments[id] || null : null; }
  function emptyOf(id) { return id && app.status && app.status.empty_spools ? app.status.empty_spools[id] || null : null; }
  function slotView(slot) { return slot && app.status ? app.status.slots.find((view) => view && view.slot === slot) || null : null; }
  function ficheGpm(id) {
    const fiche = ficheOf(id);
    const density = fiche ? Number(fiche.density) : 0;
    return density > 0 ? gramsPerMetre(density, Number(fiche.diameter_mm) || DIAMETER) : 0;
  }
  function spoolLabel(spool) { return (spool.label || idLabel(spool.id)) + " · " + ficheName(ficheOf(spool.filament)); }
  function ficheOptionsList() {
    return entriesByName(app.status.filaments, ficheName).map(([id, fiche]) => [id, [ficheName(fiche), ficheLine(fiche)].filter(Boolean).join(" · ")]);
  }
  function emptyOptionsList() {
    return entriesByName(app.status.empty_spools, emptySpoolName).map(([id, record]) => [id, emptySpoolName(record) + " · tare " + gramsLabel(record.tare_g) + " g"]);
  }
  function emptyHint(id) { const record = emptyOf(id); return record ? emptySpoolLine(record) : "sans elle, une pesée ne peut pas retirer la tare"; }
  function alive(sheet) {
    const status = app.status;
    if (!status) return false;
    if (sheet.kind === "spool") return Boolean(spoolById(sheet.key));
    if (sheet.kind === "fiche" && sheet.key) return Boolean(status.filaments && status.filaments[sheet.key]);
    if (sheet.kind === "empty" && sheet.key) return Boolean(status.empty_spools && status.empty_spools[sheet.key]);
    return true;
  }
  function draftOf(kind, key) {
    const status = app.status;
    if (kind === "spool") {
      const spool = spoolById(key);
      if (!spool) return {};
      return { remaining: JSON.stringify(spool.remaining || null), filament: spool.filament || "", empty_spool: spool.empty_spool || "",
        initial_net_g: num(spool.initial_net_g, 2), notes: spool.notes || "", place: spool.place || "" };
    }
    if (kind === "fiche") {
      const fiche = ficheOf(key);
      if (!fiche) return {};
      return { manufacturer: fiche.manufacturer || "", name: fiche.name || "", material: fiche.material || "", colour: colourKey(fiche.colour || ""),
        diameter_mm: num(fiche.diameter_mm, 2), density: num(fiche.density, 3), creality_id: fiche.creality_id == null ? "" : String(fiche.creality_id), notes: fiche.notes || "" };
    }
    if (kind === "empty") {
      const record = emptyOf(key);
      if (!record) return {};
      return { manufacturer: record.manufacturer || "", name: record.name || "", spool_material: record.spool_material || "inconnue",
        tare_g: num(record.tare_g, 2), nominal_net_g: num(record.nominal_net_g, 2), notes: record.notes || "" };
    }
    if (kind === "settings") {
      const settings = (status && status.settings) || {};
      return { low_g: num(settings.low_g, 1), cut_loss_mm: num(settings.cut_loss_mm, 1) };
    }
    return {};
  }
  function makeSheet(kind, key, extra) {
    const more = extra || {};
    const creating = kind === "new-spool" || ((kind === "fiche" || kind === "empty") && !key);
    let draft;
    if (more.draft) draft = more.draft;
    else if (kind === "fiche" && !key) draft = { manufacturer: "", name: "", material: "", colour: "", diameter_mm: figure(DIAMETER, 2), density: "", creality_id: "", notes: "" };
    else if (kind === "empty" && !key) draft = { manufacturer: "", name: "", spool_material: "inconnue", tare_g: "", nominal_net_g: "1000", notes: "", catalogue: "", catalogue_tare: "", weighed: false };
    else draft = draftOf(kind, key);
    const revision = app.status ? app.status.revision : -1;
    return { serial: ++sheetSerial, kind, key: key || "", draft, base: Object.assign({}, draft), touched: new Set(), typed: null,
      revision, merged: revision, stale: false, error: null, conflicts: {}, version: 0, back: null, creating,
      picked: more.picked != null ? more.picked : Boolean(key) };
  }
  function openSheet(sheet) {
    sheet.back = app.sheet; app.sheet = sheet; app.resetScroll = true;
    if (sheet.kind === "empty" && sheet.creating) loadTares();
    render();
  }
  function goBack() {
    const sheet = app.sheet;
    if (!sheet) return;
    if (isDirty(sheet) && !ask("Abandonner la saisie en cours ?")) return;
    let back = sheet.back;
    while (back && !merge(back)) back = back.back;
    app.sheet = back; app.resetScroll = true; render();
  }
  function leaveSheet() {
    for (let sheet = app.sheet; sheet; sheet = sheet.back) if (isDirty(sheet)) return ask("Abandonner la saisie en cours ?");
    return true;
  }
  function chooseTab(key, filter) {
    if (!leaveSheet()) return;
    app.sheet = null; app.tab = key;
    if (filter !== undefined) app.journalFilter = filter;
    app.resetScroll = true; render();
    if (key === "journal") loadJournal(true);
  }
  function openSettings() { if (app.sheet && app.sheet.kind === "settings") return; openSheet(makeSheet("settings", "")); }
  async function loadMaterials() {
    if (!app.open || app.materialsLoading || !app.status) return;
    const info = app.status.materials || {};
    const key = JSON.stringify([info.count, info.error || ""]);
    if (app.materials && app.materialsKey === key) return;
    if (app.materialsFailed && clock() - app.materialsAt < MATERIALS_RETRY_MS) return;
    app.materialsLoading = true;
    try {
      const payload = await call("GET", API + "materials", null, TIMEOUTS.materials);
      const result = payload.result || {};
      if (!Array.isArray(result.materials)) throw failure("réponse illisible", 0);
      app.materials = result.materials; app.materialsKey = key; app.materialsError = result.error || ""; app.materialsFailed = 0;
    } catch (error) {
      app.materialsFailed += 1;
      if (!app.materials) app.materialsError = error.message;
    } finally { app.materialsLoading = false; app.materialsAt = clock(); render(); }
  }
  async function loadJournal(force) {
    if (!app.open || app.journalLoading || !app.status) return;
    if (!force && app.journal && clock() - app.journalAt < JOURNAL_MS) return;
    const revision = app.status.revision;
    app.journalLoading = true; render();
    try {
      const payload = await call("GET", API + "journal?limit=" + JOURNAL_LIMIT, null, TIMEOUTS.journal);
      const entries = payload.result && payload.result.entries;
      if (!Array.isArray(entries)) throw failure("réponse illisible", 0);
      app.journal = entries; app.journalKey = entries.length + ":" + JSON.stringify(entries[0] || null);
      app.journalRevision = revision; app.journalError = "";
    } catch (error) { app.journalError = error.message; }
    finally { app.journalLoading = false; app.journalAt = clock(); render(); }
  }
  async function loadTares() {
    if (app.tares || app.taresLoading) return;
    app.taresLoading = true; app.taresError = ""; render();
    try {
      const payload = await call("GET", TARES, null, TIMEOUTS.tares);
      if (!payload || !Array.isArray(payload.entries)) throw failure("catalogue illisible", 0);
      app.tares = payload.entries;
    } catch (error) { app.taresError = error.message; }
    finally { app.taresLoading = false; render(); }
  }
  function statusKey(status) {
    if (!status) return null;
    const counter = status.counter || {};
    return Object.assign({}, status, { counter: { restored: counter.restored, refused: counter.refused, period: Boolean(counter.live && counter.live.period) } });
  }
  function render() {
    renderLaunch();
    if (!app.open) { app.signature = ""; return; }
    const sheet = app.sheet;
    const signature = JSON.stringify([
      app.tab,
      sheet ? [sheet.serial, sheet.kind, sheet.key, sheet.version, sheet.error, sheet.revision, sheet.stale, sheet.conflicts] : null,
      app.busy, statusKey(app.status), app.installed, app.online, app.error,
      app.materials ? app.materials.length : -1, app.materialsError,
      app.tares ? app.tares.length : -1, app.taresError, app.taresLoading,
      app.journalKey, app.journalError, app.journalRevision, app.journalLoading && !app.journal,
      Object.assign({}, app.filters, { text: "" }), app.journalFilter, app.showFiches, app.choices,
    ]);
    if (signature === app.signature) { renderLive(); return; }
    app.signature = signature;
    const focus = rememberFocus();
    const scroll = app.resetScroll ? 0 : body.scrollTop;
    app.resetScroll = false;
    app.refs = {};
    app.liveKey = "";
    fill(head, headView());
    const notes = bannerViews();
    fill(banners, notes);
    banners.hidden = notes.length === 0;
    fill(tabs, tabViews());
    fill(body, bodyView());
    body.scrollTop = scroll;
    renderStockList();
    renderTareList();
    renderLive();
    renderPreview();
    restoreFocus(focus);
  }
  function renderLaunch() {
    const status = app.status;
    const attention = status && Array.isArray(status.attention) ? status.attention : [];
    const offline = app.seen && !app.online;
    launch.hidden = !(app.installed && app.seen);
    badge.textContent = attention.length ? String(attention.length) : "";
    badge.hidden = attention.length === 0;
    const classes = ["spools-launch"];
    if (app.form === "compact") classes.push("is-compact");
    if (attention.length) classes.push("has-badge");
    if (app.open) classes.push("is-open");
    if (offline) classes.push("is-offline");
    launch.className = classes.join(" ");
    launch.title = offline ? "K1 injoignable" : attention.length ? attention.join("\n") : "Gestion des bobines";
    launch.setAttribute("aria-label", attention.length ? "Bobines, " + count(attention.length, "point à voir", "points à voir") : "Bobines");
  }
  function findBar() {
    for (const selector of BARS) {
      let nodes = [];
      try { nodes = Array.from(document.querySelectorAll(selector)); } catch (_) { nodes = []; }
      for (const node of nodes) {
        const rect = node.getBoundingClientRect();
        if (rect.height >= 32 && rect.height <= 120 && rect.width > 0 && rect.bottom > 0) { watch(node); return { node, rect }; }
      }
    }
    watch(null);
    return null;
  }
  function place() {
    if (launch.hidden) return;
    if (!app.fullWidth) {
      const before = launch.className;
      launch.className = before.replace(" is-compact", "");
      app.fullWidth = Math.ceil(launch.getBoundingClientRect().width) || 0;
      launch.className = before;
    }
    const viewport = document.documentElement.clientWidth || window.innerWidth || 0;
    const found = findBar();
    // A full bar leaves the round button floating at the bottom right, where scrolling clears what it covers.
    let form = "compact", spot = "bottom:16px;right:16px", right = 16, panelTop = found ? found.rect.bottom + 8 : 72;
    const room = found ? widestGap(found.node, found.rect) : null;
    if (room && room[1] - room[0] >= 44) {
      const top = Math.round(found.rect.top + (found.rect.height - 36) / 2);
      if (room[1] - room[0] >= (app.fullWidth || 120)) form = "full";
      right = Math.max(8, Math.round(viewport - room[1]));
      spot = "top:" + top + "px;bottom:auto;right:" + right + "px;z-index:" + aboveBar(found.node);
      panelTop = top + 44;
    } else {
      const pill = startPill();
      const height = document.documentElement.clientHeight || window.innerHeight || 0;
      if (pill && height) spot = "bottom:" + Math.max(16, Math.round(height - pill.top + 8)) + "px;right:16px";
    }
    panelTop = Math.round(panelTop);
    const key = form + ":" + spot + ":" + panelTop + ":" + viewport;
    if (key === app.placed) return;
    app.placed = key;
    if (app.form !== form) { app.form = form; renderLaunch(); }
    launch.style.cssText = spot;
    const width = Math.min(760, viewport - 32);
    const panelRight = Math.max(16, Math.min(right, viewport - 16 - width));
    panel.style.cssText = "--spools-top:" + panelTop + "px;--spools-right:" + panelRight + "px";
  }
  // The widest free stretch of the bar, 8 px clear of what Mainsail shows in it.
  function widestGap(bar, rect) {
    const taken = [];
    for (const selector of [CONTROLS, TITLES]) {
      for (const node of bar.querySelectorAll(selector)) {
        const box = node.getBoundingClientRect();
        if (box.width && box.height) taken.push([box.left - 8, box.right + 8]);
      }
    }
    taken.sort((a, b) => a[0] - b[0]);
    let from = rect.left + 8, best = null;
    const keep = (start, end) => { if (end > start && (!best || end - start >= best[1] - best[0])) best = [start, end]; };
    for (const [start, end] of taken) { keep(from, start); from = Math.max(from, end); }
    keep(from, rect.right - 8);
    return best;
  }
  // The start window folded to its pill holds the bottom right corner: the round button stacks above it.
  function startPill() {
    const start = document.getElementById("kctrl-bobines");
    const pill = start && start.shadowRoot ? start.shadowRoot.getElementById("pill") : null;
    const box = pill && !pill.hidden ? pill.getBoundingClientRect() : null;
    return box && box.height ? box : null;
  }
  // Mainsail lifts its bar onto a layer of its own (8 in v2.18.2): the button goes one higher.
  function aboveBar(bar) {
    let layer = NaN;
    try { layer = parseInt(getComputedStyle(bar).zIndex, 10); } catch (_) { /* no layout to read */ }
    return Number.isFinite(layer) ? Math.max(6, layer + 1) : 6;
  }
  function pane(title, number, ...children) {
    return h("section", { class: "pane spools-pane" },
      title ? h("h3", null, title, number != null ? h("span", { class: "count" }, String(number)) : null) : null, children);
  }
  function box(...children) { return pane("", null, ...children); }
  function note(text, tone) { return h("p", { class: "note" + (tone ? " is-" + tone : "") }, text); }
  function pick(key, placeholder, options, opts) {
    const o = opts || {};
    if (app.choices[key] && !options.some(([value]) => value === app.choices[key])) delete app.choices[key];
    return h("select", { class: "spools-select", ref: o.ref || "pick-" + key, "aria-label": o.label || placeholder, value: app.choices[key] || "",
      onchange: (event) => { const value = event.target.value; if (value) app.choices[key] = value; else delete app.choices[key]; render(); },
    }, h("option", { value: "" }, placeholder), options.map(([value, text]) => h("option", { value }, text)));
  }
  function btn(text, onClick, opts) {
    const o = opts || {};
    const status = app.status;
    const locked = !o.nav && (Boolean(app.busy) || !app.online || Boolean(status && status.read_only && !o.readOnlyOk));
    const busy = Boolean(o.busy) && app.busy === o.busy;
    const classes = ["btn", "is-small"];
    if (o.primary) classes.push("is-primary");
    if (o.danger) classes.push("is-danger");
    if (o.ghost) classes.push("is-ghost");
    return h("button", { class: classes.join(" "), type: "button", ref: o.ref, title: o.title,
      disabled: Boolean(o.disabled) || locked, "aria-busy": busy ? "true" : null,
      onclick: () => {
        try {
          const result = onClick();
          if (result && typeof result.catch === "function") result.catch((error) => console.warn("K1 Control: action des bobines", error));
        } catch (error) { console.warn("K1 Control: action des bobines", error); }
      },
    }, busy ? [h("span", { class: "spinner", "aria-hidden": "true" }), o.busyText || "Envoi…"] : text);
  }
  function field(text, control, opts) {
    const o = opts || {};
    const native = Boolean(control) && ["INPUT", "SELECT", "TEXTAREA"].includes(control.tagName);
    const label = native
      ? h("label", { class: "spools-field-label" }, h("span", { class: "spools-label-text" }, text), control)
      : h("div", { class: "spools-field-label" }, h("span", { class: "spools-label-text" }, text));
    return h("div", { class: "spools-field" + (o.wide ? " is-wide" : "") }, label, native ? null : control,
      o.extra ? h("div", { class: "spools-field-row" }, o.extra) : null,
      o.hint ? h("span", { class: "spools-hint" }, o.hint) : null,
      o.conflict ? h("span", { class: "spools-conflict" }, o.conflict) : null);
  }
  function sheetField(sheet, key, text, control, opts) { return field(text, control, Object.assign({}, opts, { conflict: conflictHint(sheet, key) })); }
  function input(sheet, key, opts) {
    const o = opts || {};
    return h("input", { class: "spools-input", ref: "f-" + key, type: o.type || "text", maxlength: o.maxlength, placeholder: o.placeholder,
      list: o.list, inputmode: o.inputmode, value: sheet.draft[key] == null ? "" : String(sheet.draft[key]),
      oninput: (event) => { setDraft(sheet, key, event.target.value); if (o.oninput) o.oninput(event.target.value); } });
  }
  function numberInput(sheet, key, opts) { return input(sheet, key, Object.assign({ inputmode: "decimal", maxlength: 12 }, opts)); }
  function textArea(sheet, key, opts) {
    const o = opts || {};
    return h("textarea", { class: "spools-input", ref: "f-" + key, rows: 3, maxlength: NOTES_LIMIT, placeholder: o.placeholder,
      value: sheet.draft[key] || "", oninput: (event) => setDraft(sheet, key, event.target.value) });
  }
  function choice(sheet, key, options, opts) {
    const o = opts || {};
    const current = sheet.draft[key] == null ? "" : String(sheet.draft[key]);
    const list = options.slice();
    if (current && !list.some(([value]) => value === current)) list.push([current, current]);
    return h("select", { class: "spools-select", ref: "f-" + key, "aria-label": o.label, value: current,
      onchange: (event) => { setDraft(sheet, key, event.target.value); if (o.after) o.after(event.target.value); rerender(sheet); },
    }, o.placeholder != null ? h("option", { value: "" }, o.placeholder) : null, list.map(([value, text]) => h("option", { value }, text)));
  }
  function segmented(sheet, key, options, label) {
    return h("div", { class: "spools-segmented", role: "group", "aria-label": label }, options.map(([value, text]) => h("button", {
      class: "spools-segment" + (sheet.draft[key] === value ? " is-active" : ""), type: "button",
      "aria-pressed": sheet.draft[key] === value ? "true" : "false", ref: "seg-" + key + "-" + value,
      onclick: () => { if (sheet.draft[key] === value) return; setDraft(sheet, key, value); rerender(sheet); },
    }, text)));
  }
  function placesList() {
    const places = Array.from(new Set(app.status.spools.map((spool) => spool && spool.place).filter(Boolean))).sort((a, b) => a.localeCompare(b, "fr"));
    return h("datalist", { id: "spools-places" }, places.map((place) => h("option", { value: place })));
  }
  function toast(message, ok) {
    clearTimeout(app.toastTimer);
    toastBox.textContent = message;
    toastBox.className = "toast is-spools" + (ok ? " is-ok" : "");
    toastBox.hidden = false;
    app.toastTimer = setTimeout(() => { toastBox.hidden = true; }, ok ? 4000 : 8000);
  }
  function klippy() { return (app.status && app.status.klippy) || { connected: false, cfs_ready: false, printing: false }; }
  function headState() {
    const status = app.status;
    if (!app.online && app.error) return ["offline", "injoignable"];
    if (!status) return ["idle", "lecture…"];
    const k = klippy();
    if (!k.connected) return ["offline", "Klipper déconnecté"];
    if (status.read_only) return ["paused", "lecture seule"];
    if (k.printing) return ["printing", "impression en cours"];
    return ["idle", "à jour"];
  }
  function headView() {
    const status = app.status;
    const spools = status ? status.spools : [];
    const tally = { cfs: 0, stock: 0, a_ranger: 0 };
    for (const spool of spools) if (spool && Object.prototype.hasOwnProperty.call(tally, spool.state)) tally[spool.state] += 1;
    const parts = [];
    if (tally.cfs) parts.push(tally.cfs + " au CFS");
    if (tally.stock) parts.push(tally.stock + " en stock");
    if (tally.a_ranger) parts.push(tally.a_ranger + " à ranger");
    const summary = parts.length ? parts.join(" · ") : spools.length ? "Aucune bobine active" : "Aucune bobine pour l'instant";
    const [tone, text] = headState();
    return [
      h("div", { class: "spools-title" }, h("h2", { id: "spools-title" }, "Bobines"), h("p", { class: "spools-summary" }, status ? summary : "")),
      h("span", { class: "status is-" + tone }, h("span", { class: "dot", "aria-hidden": "true" }), text),
      h("div", { class: "spools-head-actions" },
        btn("Réglages", openSettings, { ghost: true, nav: true, ref: "head-settings", disabled: !status }),
        btn("Fermer", () => close(true), { ghost: true, nav: true, ref: "head-close", title: "Fermer (Échap)" })),
    ];
  }
  function bannerViews() {
    const status = app.status;
    const out = [];
    const add = (tone, text) => out.push(h("p", { class: "spools-banner is-" + tone, role: tone === "danger" ? "alert" : null }, text));
    if (!app.online && app.error && status) add("danger", "K1 injoignable" + (app.error !== "K1 injoignable" ? " : " + app.error : "") + ". Nouvelle tentative dans quelques secondes.");
    if (!status) return out;
    const k = klippy();
    const store = status.store || {};
    if (status.read_only) add("warn", sentence("Lecture seule : " + status.read_only) + (store.locked ? "" : " L'export reste possible, et l'import d'un export valide remplace la bibliothèque."));
    if (k.printing) add("accent", "Impression en cours : tout reste consultable, le stock et les pesées restent modifiables. Les écritures au CFS partiront à la fin de l'impression ; l'import attend.");
    if (!k.connected) add("warn", "Klipper non connecté : le CFS n'est pas lu, ses emplacements peuvent être anciens.");
    if (status.slots_error) add("danger", sentence(status.slots_error));
    const materials = status.materials || {};
    if (materials.error) add("warn", "Base matériau de la K1 illisible (" + materials.error + ") : les nouvelles fiches attendent qu'elle se relise.");
    const unsaved = Array.isArray(status.unsaved_writes) ? status.unsaved_writes : [];
    if (unsaved.length) add("warn", "Résultat d'écriture au CFS pas encore enregistré pour " + joinFr(unsaved) + " : nouvel essai automatique.");
    if (status.reports_waiting > 0) add("warn", count(status.reports_waiting, "rapport d'impression en attente", "rapports d'impression en attente") + " d'enregistrement : nouvel essai automatique.");
    const counter = status.counter || {};
    if (counter.refused) add("warn", "Décompte repris à zéro au démarrage : l'état enregistré n'était pas utilisable.");
    if (store.fallback) add("warn", "Bibliothèque reprise depuis la copie de secours " + (store.source || "") + " : la copie principale était abîmée ou absente.");
    if (store.fresh && Array.isArray(store.damaged) && store.damaged.length) add("danger", "Aucune copie intacte de la bibliothèque : elle repart vide.");
    if (store.quarantined) add("faint", "Copies abîmées mises de côté dans " + store.quarantined + ".");
    return out;
  }
  function tabViews() {
    const attention = app.status && Array.isArray(app.status.attention) ? app.status.attention.length : 0;
    return TABS.map(([key, text]) => h("button", { class: "spools-tab" + (app.tab === key ? " is-active" : ""), type: "button", role: "tab",
      "aria-selected": app.tab === key ? "true" : "false", ref: "tab-" + key, onclick: () => chooseTab(key) },
      text, key === "cfs" && attention ? h("span", { class: "spools-count" }, String(attention)) : null));
  }
  function bodyView() {
    if (!app.installed) return h("p", { class: "empty" }, "Gestion des bobines absente de la K1.");
    if (!app.status) {
      if (app.error) return h("p", { class: "empty" }, app.error === "K1 injoignable" ? "K1 injoignable." : sentence("K1 injoignable : " + app.error));
      return h("p", { class: "empty" }, h("span", { class: "spinner", "aria-hidden": "true" }), "Lecture de la bibliothèque…");
    }
    if (app.sheet) return sheetView(app.sheet);
    if (app.tab === "stock") return stockView();
    if (app.tab === "vides") return emptiesView();
    if (app.tab === "journal") return journalView();
    return cfsView();
  }
  function cfsView() {
    const status = app.status;
    const attention = Array.isArray(status.attention) ? status.attention : [];
    const unassigned = Array.isArray(status.unassigned) ? status.unassigned : [];
    return [
      attention.length ? pane("À voir", attention.length, h("ul", { class: "spools-attention" }, attention.map((text) => h("li", null, text)))) : null,
      unassigned.length ? segmentsPane(unassigned) : null,
      slotsPane(),
      pane("Décompte", null, h("div", { class: "spools-live", ref: "live" }),
        status.counting_verified ? null : note("Décompte pas encore vérifié par une pesée : pèse une bobine après une impression pour le confirmer.", "faint")),
    ];
  }
  function segmentsPane(segments) {
    const options = filterStock(app.status.spools, app.status.filaments, { scope: "actives", text: "", material: "", colour: "", place: "" }).map((spool) => [spool.id, spoolLabel(spool)]);
    return pane("Consommations à attribuer", segments.length,
      note("Filament compté sans bobine connue : choisis la bobine qui l'a fourni."),
      h("div", { class: "spools-list" }, segments.map((segment) => {
        const key = "segment:" + segment.id;
        const select = pick(key, "Choisir la bobine…", options, { label: "Bobine de cette consommation" });
        return h("div", { class: "spools-row is-static" },
          h("span", { class: "spools-row-main" }, h("strong", null, metres(segment.mm) + (segment.slot ? " en " + segment.slot : "")),
            h("span", { class: "spools-sub" }, [segment.reason, dateLabel(segment.on)].filter(Boolean).join(" · "))),
          h("div", { class: "spools-inline" }, select,
            btn("Attribuer", () => assignSegment(segment.id), { primary: true, disabled: !app.choices[key], busy: "assign:" + segment.id }),
            btn("Ignorer", () => dismissSegment(segment.id), { ghost: true, busy: "dismiss:" + segment.id })));
      })));
  }
  async function assignSegment(id) {
    const key = "segment:" + id;
    const spool = app.choices[key];
    if (!spool) return;
    const reply = await act("assign_segment", { segment: id, spool }, { busy: "assign:" + id });
    if (!reply) return;
    delete app.choices[key];
    toast(labelOf(spool) + " : " + grams(reply.result && reply.result.g) + " comptés.", true);
    render();
  }
  async function dismissSegment(id) {
    if (!ask("Ignorer cette consommation ? Elle ne sera comptée sur aucune bobine.")) return;
    const reply = await act("dismiss_segment", { segment: id }, { busy: "dismiss:" + id });
    if (reply) toast("Consommation ignorée.", true);
  }
  function slotsPane() {
    const groups = units(app.status.slots);
    if (!groups.length) return pane("Emplacements", null, note(klippy().connected ? "Aucune unité CFS lue." : "Klipper non connecté : CFS non lu.", "faint"));
    return pane("Emplacements", null, h("div", { class: "spool-grid" }, groups.map((group) => [
      h("p", { class: "unit-label" }, "CFS " + group.unit.slice(1)), group.slots.map((view) => slotCard(view)),
    ])));
  }
  function slotCard(view) {
    const status = slotStatus(view);
    const observed = view.observed || {};
    const spool = spoolById(view.spool);
    const fiche = spool ? ficheOf(spool.filament) : null;
    const own = fiche ? colourKey(fiche.colour || "") : "";
    const seen = colourKey(observed.colour || "");
    const main = own || seen;
    const classes = ["spool"];
    if (view.status === "vide" || view.status === "hors_ligne") classes.push("is-empty");
    else if (view.status === "inconnue") classes.push("is-unknown");
    else if (view.status === "a_verifier" || view.status === "attendue") classes.push("is-check");
    const blank = !spool && (view.status === "vide" || view.status === "hors_ligne");
    const kind = (fiche && fiche.material) || observed.type || (view.status === "hors_ligne" ? "hors ligne" : view.status === "vide" ? "vide" : "matériau inconnu");
    const remaining = spool ? spool.remaining : null;
    return h("button", { class: classes.join(" "), type: "button", ref: "slot-" + view.slot, onclick: () => openSheet(makeSheet("slot", view.slot)) },
      observed.chip != null ? h("span", { class: "badge" }, "puce " + figure(observed.chip, 0) + " %") : null,
      h("span", { class: "slot-name" }, view.slot),
      h("span", { class: "spools-swatches" }, swatch(main, "is-big"), own && seen && own !== seen ? swatch(seen, "is-mini spools-seen") : null),
      h("span", { class: "kind" }, kind),
      blank ? null : h("span", { class: "colour" }, main ? colourName(main) : "couleur inconnue", h("br"), h("span", { class: "hex" }, main ? "#" + main : "")),
      spool ? h("span", { class: "spools-card-id" }, spoolLabel(spool)) : null,
      spool ? h("span", { class: "remain" + (remaining && remaining.exhausted ? " is-warn" : spool.low ? " is-low" : "") }, remainingText(remaining)) : null,
      h("span", { class: "note is-" + status.tone }, capital(status.text)));
  }
  function renderLive() {
    const node = app.refs.live;
    if (!node) return;
    const live = app.status && app.status.counter ? app.status.counter.live : null;
    const key = JSON.stringify(live || null);
    if (key === app.liveKey) return;
    app.liveKey = key;
    fill(node, live ? liveView(live) : note("Décompte non disponible.", "faint"));
  }
  function liveView(live) {
    const period = live.period;
    const lines = [];
    for (const item of Array.isArray(live.spools) ? live.spools : []) {
      const spool = spoolById(item.spool);
      const gpm = spool ? ficheGpm(spool.filament) : 0;
      lines.push(h("li", null, (item.slot ? item.slot + " · " : "") + (item.spool ? labelOf(item.spool) : "bobine inconnue") + " : " + metres(item.mm)
        + (gpm ? " · " + grams(gramsOfMm(item.mm, gpm)) : "")));
    }
    const route = live.route == null ? "Filament engagé : inconnu" : live.route === "" ? "Aucun filament engagé" : "Filament engagé : " + live.route;
    return [
      h("p", { class: "spools-live-head" }, period && period.kind === "job" ? "Impression en cours" + (period.file ? " : " + shortName(period.file) : "") : "Hors impression"),
      lines.length ? h("ul", { class: "spools-live-lines" }, lines) : note("Aucun filament compté pour l'instant.", "faint"),
      live.waiting_mm > 0 ? note(metres(live.waiting_mm) + " pas encore attribués à une bobine.", "warn") : null,
      note(route, "faint"),
      period && Array.isArray(period.notes) ? period.notes.map((text) => note(text, "faint")) : null,
    ];
  }
  function stockView() {
    const status = app.status;
    const filters = app.filters;
    const facets = stockFacets(status.spools, status.filaments, filters.scope);
    if (filters.material && !facets.materials.includes(filters.material)) filters.material = "";
    if (filters.colour && !facets.colours.some((c) => c.key === filters.colour)) filters.colour = "";
    if (filters.place && !facets.places.includes(filters.place)) filters.place = "";
    const facet = (key, placeholder, options) => h("select", { class: "spools-select", ref: "stock-" + key, "aria-label": placeholder, value: filters[key],
      onchange: (event) => { filters[key] = event.target.value; render(); } },
      h("option", { value: "" }, placeholder), options.map(([value, text]) => h("option", { value }, text)));
    const fiches = entriesByName(status.filaments, ficheName);
    return [
      h("div", { class: "spools-filters" },
        h("input", { class: "spools-input spools-search", type: "search", ref: "stock-text", value: filters.text,
          placeholder: "Chercher : marque, couleur, lieu, numéro…", "aria-label": "Chercher une bobine", maxlength: NAME_LIMIT,
          oninput: (event) => { filters.text = event.target.value; renderStockList(); } }),
        h("select", { class: "spools-select", ref: "stock-scope", "aria-label": "Bobines montrées", value: filters.scope,
          onchange: (event) => { app.filters = { scope: event.target.value, text: filters.text, material: "", colour: "", place: "" }; render(); } },
          Object.entries(SCOPES).map(([value, scope]) => h("option", { value }, scope.text))),
        facet("material", "toutes matières", facets.materials.map((m) => [m, m])),
        facet("colour", "toutes couleurs", facets.colours.map((c) => [c.key, c.name])),
        facets.places.length ? facet("place", "tous lieux", facets.places.map((p) => [p, p])) : null,
        btn("Nouvelle bobine", () => openSheet(newSpoolSheet("")), { primary: true, nav: true, ref: "new-spool" })),
      h("div", { class: "spools-list", ref: "stock-list" }),
      h("section", { class: "spools-fiches" },
        h("div", { class: "spools-toggle-row" },
          h("button", { class: "spools-toggle", type: "button", ref: "toggle-fiches", "aria-expanded": app.showFiches ? "true" : "false",
            onclick: () => { app.showFiches = !app.showFiches; render(); } }, (app.showFiches ? "▾ " : "▸ ") + "Fiches filament (" + fiches.length + ")"),
          btn("Nouvelle fiche", () => openSheet(makeSheet("fiche", "")), { ghost: true, nav: true, ref: "new-fiche" })),
        app.showFiches ? (fiches.length ? h("div", { class: "spools-list" }, fiches.map(([id, fiche]) => ficheRow(id, fiche)))
          : note("Aucune fiche : elles se créent avec la première bobine.", "faint")) : null),
    ];
  }
  function renderStockList() {
    const node = app.refs["stock-list"];
    if (!node || !app.status) return;
    const filters = app.filters;
    const list = filterStock(app.status.spools, app.status.filaments, filters);
    if (list.length) { fill(node, list.map((spool) => stockRow(spool))); return; }
    const filtered = String(filters.text || "").trim() || filters.material || filters.colour || filters.place;
    let text = "Aucune bobine en stock : « Nouvelle bobine » en crée une.";
    if (filtered) text = "Aucune bobine ne correspond.";
    else if (filters.scope === "archivees") text = "Aucune bobine terminée ou jetée.";
    else if (filters.scope === "actives") text = "Aucune bobine active : « Nouvelle bobine » en crée une.";
    fill(node, h("p", { class: "empty" }, text));
  }
  function stockRow(spool) {
    const fiche = ficheOf(spool.filament);
    const remaining = spool.remaining;
    return h("button", { class: "spools-row", type: "button", ref: "row-" + spool.id, onclick: () => openSheet(makeSheet("spool", spool.id)) },
      swatch(fiche ? colourKey(fiche.colour || "") : "", "is-mini"),
      h("span", { class: "spools-row-main" }, h("strong", null, spoolLabel(spool)),
        h("span", { class: "spools-sub" }, [ficheLine(fiche), whereText(spool)].filter(Boolean).join(" · "))),
      h("span", { class: "spools-remain" + (remaining && remaining.exhausted ? " is-warn" : spool.low ? " is-low" : "") }, remainingText(remaining)));
  }
  function ficheRow(id, fiche) {
    const users = usersOf(app.status.spools, "filament", id);
    return h("button", { class: "spools-row", type: "button", ref: "fiche-" + id, onclick: () => openSheet(makeSheet("fiche", id)) },
      swatch(colourKey(fiche.colour || ""), "is-mini"),
      h("span", { class: "spools-row-main" }, h("strong", null, ficheName(fiche)),
        h("span", { class: "spools-sub" }, [ficheLine(fiche), users.length ? usersText(users) : "inutilisée"].filter(Boolean).join(" · "))));
  }
  function emptiesView() {
    const entries = entriesByName(app.status.empty_spools, emptySpoolName);
    return pane("Bobines vides", entries.length,
      h("div", { class: "spools-pane-head" },
        note("Le poids à vide de chaque type de bobine : il retire la tare d'une pesée."),
        btn("Nouveau type", () => openSheet(makeSheet("empty", "")), { primary: true, nav: true, ref: "new-empty" })),
      entries.length ? h("div", { class: "spools-list" }, entries.map(([id, record]) => {
        const users = usersOf(app.status.spools, "empty_spool", id);
        return h("button", { class: "spools-row", type: "button", ref: "empty-" + id, onclick: () => openSheet(makeSheet("empty", id)) },
          h("span", { class: "spools-row-main" }, h("strong", null, emptySpoolName(record)),
            h("span", { class: "spools-sub" }, [emptySpoolLine(record), users.length ? usersText(users) : "inutilisée"].filter(Boolean).join(" · "))));
      })) : h("p", { class: "empty" }, "Aucun type de bobine vide : « Nouveau type » en ajoute un, depuis le catalogue SpoolmanDB ou à la main."));
  }
  function journalView() {
    const status = app.status;
    const prints = Array.isArray(status.prints) ? status.prints.slice(-5).reverse() : [];
    if (app.journalFilter && !byId()[app.journalFilter]) app.journalFilter = "";
    const options = status.spools.slice().sort((a, b) => String(a.id).localeCompare(String(b.id)));
    return [
      pane("Dernières impressions", null, prints.length ? prints.map(printView) : note("Aucune impression comptée pour l'instant.", "faint")),
      pane("Journal", null,
        h("div", { class: "spools-filters" },
          h("select", { class: "spools-select", ref: "journal-filter", "aria-label": "Bobine du journal", value: app.journalFilter,
            onchange: (event) => { app.journalFilter = event.target.value; render(); } },
            h("option", { value: "" }, "toutes les bobines"), options.map((spool) => h("option", { value: spool.id }, spoolLabel(spool))))),
        journalBody()),
    ];
  }
  function printView(item) {
    const lines = [];
    for (const part of Array.isArray(item.per_spool) ? item.per_spool : []) lines.push(labelOf(part.spool) + (part.slot ? " en " + part.slot : "") + " : " + metres(part.mm) + (part.g != null ? " · " + grams(part.g) : ""));
    for (const part of Array.isArray(item.assigned) ? item.assigned : []) lines.push(labelOf(part.spool) + " attribuée : " + metres(part.mm) + (part.g != null ? " · " + grams(part.g) : ""));
    const planned = Array.isArray(item.planned) ? item.planned : [];
    if (planned.length) {
      const mm = planned.reduce((sum, part) => sum + (Number(part.mm) || 0), 0);
      const g = planned.reduce((sum, part) => sum + (Number(part.g) || 0), 0);
      lines.push("Prévu par le G-code : " + metres(mm) + (g > 0 ? " · " + grams(g) : ""));
    }
    const open = (Array.isArray(item.unassigned) ? item.unassigned : []).filter((id) => (app.status.unassigned || []).some((segment) => segment.id === id)).length;
    if (open) lines.push(count(open, "consommation à attribuer", "consommations à attribuer"));
    for (const text of Array.isArray(item.notes) ? item.notes : []) lines.push(text);
    return h("article", { class: "spools-print" },
      h("strong", null, [shortName(item.file) || "impression", OUTCOME_LABELS[item.outcome] || item.outcome, dateLabel(item.end || item.start)].filter(Boolean).join(" · ")),
      lines.length ? h("ul", { class: "spools-print-lines" }, lines.map((text) => h("li", null, text))) : null);
  }
  function journalBody() {
    if (!app.journal) {
      if (app.journalError) return note("Journal illisible : " + app.journalError + ".", "warn");
      return h("p", { class: "empty" }, h("span", { class: "spinner", "aria-hidden": "true" }), "Lecture du journal…");
    }
    const status = app.status;
    const names = { spools: byId(), filaments: status.filaments, empty: status.empty_spools };
    const entries = app.journalFilter ? app.journal.filter((entry) => touches(entry, app.journalFilter)) : app.journal;
    return [
      app.journalError ? note("Journal pas relu : " + app.journalError + ".", "warn") : null,
      entries.length ? h("ol", { class: "spools-journal" }, entries.map((entry) => {
        const tone = journalTone(entry);
        return h("li", { class: tone ? "is-" + tone : null }, h("time", { class: "spools-time" }, dateLabel(entry.t)), " " + journalText(entry, names));
      })) : h("p", { class: "empty" }, app.journalFilter ? "Rien au journal pour cette bobine." : "Journal vide."),
    ];
  }
  function sheetView(sheet) {
    const views = { slot: slotSheet, spool: spoolSheet, "new-spool": newSpoolSheetView, fiche: ficheSheet, empty: emptySheet, settings: settingsSheet };
    const view = (views[sheet.kind] || (() => ({ title: "", body: null })))(sheet);
    const sections = SECTIONS[sheet.kind] || [];
    const loose = sheet.error && !sections.includes(sheet.error.section) ? errorLine(sheet.error.text) : null;
    return [
      h("div", { class: "spools-sheet-head" }, btn("‹ Retour", goBack, { ghost: true, nav: true, ref: "sheet-back" }), h("h3", null, view.title)),
      Object.keys(sheet.conflicts).length ? h("p", { class: "spools-banner is-warn" }, "Modifié entre-temps sur la K1 : vérifie les champs signalés avant d'enregistrer.") : null,
      loose, view.body,
    ];
  }
  function errorOf(sheet, section) { return sheet.error && sheet.error.section === section ? errorLine(sheet.error.text) : null; }
  function errorLine(text) { return h("p", { class: "spools-error", role: "alert" }, text); }
  function conflictText(key, value) {
    if (value == null || value === "") return "vide";
    if (key === "remaining") { try { return remainingText(JSON.parse(value)); } catch (_) { return "?"; } }
    if (key === "filament") return ficheName(ficheOf(value));
    if (key === "empty_spool") return emptySpoolName(emptyOf(value));
    if (key === "colour") { const hex = colourKey(value); return hex ? colourName(hex) + " #" + hex : String(value); }
    return String(value);
  }
  function conflictHint(sheet, key) {
    return Object.prototype.hasOwnProperty.call(sheet.conflicts, key) ? "modifié entre-temps sur la K1 : " + conflictText(key, sheet.conflicts[key]) : null;
  }
  function conflictLine(sheet, key) { const text = conflictHint(sheet, key); return text ? h("p", { class: "spools-conflict" }, capital(text)) : null; }
  function slotSheet(sheet) {
    const slot = sheet.key;
    const view = slotView(slot);
    const title = "Emplacement " + slot;
    if (!view) return { title, body: box(note("Emplacement " + slot + " non lu : l'unité CFS ne répond pas.", "warn")) };
    const observed = view.observed || {};
    const spool = spoolById(view.spool);
    const fiche = spool ? ficheOf(spool.filament) : null;
    const seenId = creality(observed.material);
    const record = seenId ? materialRecord(app.materials || [], seenId) : null;
    const seen = colourKey(observed.colour || "");
    const own = fiche ? colourKey(fiche.colour || "") : "";
    const status = slotStatus(view);
    let cfsSide;
    if (observed.connected === false) cfsSide = [note("unité hors ligne", "faint")];
    else if (!observed.present) cfsSide = [note("aucune bobine", "faint")];
    else cfsSide = [
      h("p", null, seenId ? "fiche Creality " + seenId + (record && record.name ? " · " + record.name : "") : "bobine non identifiée"),
      observed.type ? h("p", null, observed.type) : null,
      colourLine(seen, "couleur illisible"),
      observed.chip != null ? h("p", null, "puce : " + figure(observed.chip, 0) + " %") : null,
    ];
    const ownSide = spool ? [
      h("strong", null, spoolLabel(spool)),
      h("p", null, ((fiche && fiche.material) || "matière inconnue") + (fiche && fiche.creality_id != null && fiche.creality_id !== "" ? " · fiche Creality " + fiche.creality_id : "")),
      colourLine(own, "couleur inconnue"),
      h("p", null, remainingText(spool.remaining)),
    ] : [note(view.pending ? "rien (écriture en attente)" : "aucune bobine ici", "faint")];
    const last = view.last_write;
    const lastLine = last && last.result && last.result !== "ok" ? note("Dernière écriture : " + (WRITE_RESULTS[last.result] || last.result)
      + (last.detail ? " · " + last.detail : "") + (last.on ? " · " + dateLabel(last.on) : "") + ".", /^annul/.test(last.result) ? "faint" : "warn") : null;
    return { title, body: [
      box(note(capital(status.text), status.tone),
        h("div", { class: "spools-compare" },
          h("div", { class: "spools-side" }, h("h4", null, "Le CFS montre"), cfsSide),
          h("div", { class: "spools-side" }, h("h4", null, "La bibliothèque"), ownSide)),
        lastLine),
      box(errorOf(sheet, "slot"), slotActions(view, spool)),
    ] };
  }
  function colourLine(hex, missing) { return h("p", { class: "spools-colour-line" }, swatch(hex, "is-mini"), hex ? colourName(hex) + " #" + hex : missing); }
  function slotActions(view, spool) {
    const slot = view.slot;
    const openSpool = spool ? btn("Ouvrir " + labelOf(spool.id), () => openSheet(makeSheet("spool", spool.id)), { nav: true, ghost: true, ref: "slot-open" }) : null;
    const remove = spool ? btn("Retirer du CFS", () => removeFromCfs(spool.id, "slot"), { ghost: true, busy: "remove", ref: "slot-remove" }) : null;
    const actions = (...items) => h("div", { class: "spools-actions" }, items);
    if (view.status === "a_verifier") {
      const plan = planText(view.plan, app.materials || []);
      const impact = impactText(view.plan ? view.plan.impact : null);
      return [
        h("p", null, "Le CFS et la bibliothèque ne disent pas la même chose. Choisis qui a raison :"),
        h("div", { class: "spools-choice" }, h("p", null, "Écrire dans le CFS : " + (plan || "la matière et la couleur de la bibliothèque") + (impact ? " (" + impact + ")" : "") + "."), writeButton(view)),
        h("div", { class: "spools-choice" }, h("p", null, "Garder ce que montre le CFS : la bibliothèque prend la matière et la couleur lues par le CFS."),
          btn("Garder le CFS", () => adoptCfs(slot), { busy: "adopt", ref: "slot-adopt" })),
        h("p", null, "Ou c'est une autre bobine :"), placeRow(view), actions(openSpool, remove),
      ];
    }
    if (view.status === "inconnue") {
      const candidates = candidateSpools(view, app.status.spools);
      return [
        h("p", null, "Le CFS voit une bobine que la bibliothèque ne connaît pas."),
        candidates.length ? h("p", null, candidates.length > 1 ? "C'est peut-être l'une de celles-ci :" : "C'est peut-être celle-ci :") : null,
        candidates.length ? h("div", { class: "spools-list" }, candidates.map((candidate) => {
          const fiche = ficheOf(candidate.filament);
          return h("div", { class: "spools-row is-static" }, swatch(fiche ? colourKey(fiche.colour || "") : "", "is-mini"),
            h("span", { class: "spools-row-main" }, h("strong", null, spoolLabel(candidate)),
              h("span", { class: "spools-sub" }, [ficheLine(fiche), whereText(candidate), remainingText(candidate.remaining)].filter(Boolean).join(" · "))),
            btn("C'est elle", () => putInCfs(candidate.id, slot, "slot"), { primary: true, busy: "put:" + candidate.id }));
        })) : null,
        placeRow(view),
      ];
    }
    if (view.status === "attendue") return [h("p", null, "La bibliothèque attend " + labelOf(view.spool) + " ici, mais le CFS ne voit pas de bobine."), actions(openSpool, remove)];
    if (view.status === "vide") return [h("p", null, "Emplacement vide."), placeRow(view)];
    if (view.status === "en_attente_cfs") {
      const pending = view.pending || {};
      return [
        h("p", null, "Écriture au CFS en attente pour " + labelOf(pending.spool || view.spool) + " : " + (planText(pending, app.materials || []) || "matière et couleur de la bibliothèque") + "."),
        klippy().printing ? note("Elle partira à la fin de l'impression.", "accent") : writeButton(view, "Écrire maintenant"),
        actions(openSpool, remove),
      ];
    }
    if (view.status === "hors_ligne") return [h("p", null, "L'unité CFS " + slot.slice(1, 2) + " n'est pas connectée : rien à faire tant qu'elle ne répond pas."), spool ? actions(openSpool, remove) : null];
    return [h("p", null, "Le CFS et la bibliothèque sont d'accord."), actions(openSpool, remove)];
  }
  async function adoptCfs(slot) {
    const reply = await act("adopt_cfs", { slot }, { busy: "adopt", section: "slot" });
    if (reply) toast(slot + " : la bibliothèque suit maintenant le CFS.", true);
  }
  function writeButton(view, text) {
    const k = klippy();
    return btn(k.printing ? "Programmer l'écriture" : text || "Écrire dans le CFS", () => cfsWrite(view.slot),
      { primary: true, ref: "cfs-write", busy: "cfs-write", busyText: "Écriture au CFS…", disabled: !k.connected });
  }
  async function cfsWrite(slot) {
    const sheet = app.sheet;
    const reply = await send("cfs-write", { slot }, { busy: "cfs-write", timeout: TIMEOUTS.write, section: "slot",
      unsure: slot + " : pas de réponse, l'écriture a peut-être eu lieu ; la fenêtre se met à jour." });
    if (!reply) return;
    const result = reply.result || {};
    if (result.queued) toast(sentence(slot + " : " + (result.detail || "écriture programmée pour la fin de l'impression")), true);
    else if (result.written) toast(slot + " : écrit dans le CFS et relu.", true);
    else { report(sentence(slot + " : " + (WRITE_RESULTS[result.result] || result.result || "échec") + (result.detail ? " · " + result.detail : "")), "slot", sheet); render(); }
  }
  function placeRow(view) {
    const slot = view.slot;
    const key = "slot:" + slot;
    const options = placeableSpools(app.status.spools, app.status.filaments).filter((spool) => spool.id !== view.spool).map((spool) => [spool.id, spoolLabel(spool)]);
    const select = options.length ? pick(key, "Une bobine du stock…", options, { label: "Bobine à mettre en " + slot }) : null;
    return h("div", { class: "spools-inline" },
      select ? [select, btn("Mettre ici", () => putInCfs(app.choices[key], slot, "slot"), { primary: view.status === "vide", disabled: !app.choices[key], busy: "put:" + (app.choices[key] || "") })]
        : note("Aucune bobine en stock à mettre ici.", "faint"),
      btn("Nouvelle bobine ici", () => openSheet(newSpoolSheet(slot)), { ghost: true, nav: true }));
  }
  async function putInCfs(id, slot, section) {
    if (!id || !slot) return;
    const view = slotView(slot);
    if (view && view.spool && view.spool !== id && !ask(slot + " attend déjà " + labelOf(view.spool) + " : elle passera « à ranger ». Continuer ?")) return;
    const reply = await act("put_in_cfs", { id, slot }, { busy: "put:" + id, section });
    if (!reply) return;
    delete app.choices["slot:" + slot]; delete app.choices["put:" + id];
    const after = slotView(slot);
    const here = Boolean(app.sheet && app.sheet.kind === "slot" && app.sheet.key === slot);
    if (after && after.status === "a_verifier") toast(labelOf(id) + " mise en " + slot + " : à vérifier, " + (here ? "voir ci-dessous." : "ouvre l'emplacement pour écrire le CFS."), true);
    else toast(labelOf(id) + " mise en " + slot + ".", true);
    render();
  }
  async function removeFromCfs(id, section) {
    const reply = await act("remove_from_cfs", { id }, { busy: "remove", section });
    if (reply) toast(labelOf(id) + " retirée du CFS : à ranger.", true);
  }
  function slotOptionText(view) {
    if (!view.spool) return view.slot + (view.observed && view.observed.present ? " · bobine non enregistrée" : " · vide");
    return view.slot + " · " + labelOf(view.spool) + " (sera remplacée)";
  }
  function cfsSlotOptions(except) {
    return units(app.status.slots).flatMap((group) => group.slots)
      .filter((view) => (!view.observed || view.observed.connected !== false) && (!except || view.spool !== except))
      .map((view) => [view.slot, slotOptionText(view)]);
  }
  function spoolSheet(sheet) {
    const spool = spoolById(sheet.key);
    if (!spool) return { title: "Bobine", body: box(note("Bobine introuvable.", "warn")) };
    return { title: spoolLabel(spool), body: [heroOf(spool), restPane(sheet, spool), identityPane(sheet, spool), wherePane(sheet, spool), endPane(sheet, spool)] };
  }
  function heroOf(spool) {
    const fiche = ficheOf(spool.filament);
    const remaining = spool.remaining;
    const basis = spool.basis || {};
    const when = dayLabel(basis.on);
    const lines = [];
    if (basis.kind === "pesee") lines.push("pesée à " + grams(basis.value_g) + " brut le " + when + ", puis décompte des impressions");
    else if (basis.kind === "estimation") lines.push("estimée à " + grams(basis.value_g) + " net le " + when + ", puis décompte des impressions");
    else if (basis.kind === "neuve") lines.push("neuve à " + grams(basis.value_g != null ? basis.value_g : spool.initial_net_g) + " net le " + when + ", puis décompte des impressions");
    const gap = spool.last_gap;
    if (gap && gap.g != null) lines.push("dernière pesée : écart de " + signed(gap.g) + " avec le décompte");
    const view = spool.slot ? slotView(spool.slot) : null;
    if (view && view.spool === spool.id && view.observed && view.observed.chip != null) lines.push("puce du CFS : " + figure(view.observed.chip, 0) + " %");
    return h("div", { class: "spools-hero" }, swatch(fiche ? colourKey(fiche.colour || "") : "", "is-big"),
      h("div", { class: "spools-hero-main" },
        h("p", { class: "spools-hero-title" }, spoolLabel(spool)),
        h("p", { class: "spools-sub" }, [ficheLine(fiche), whereText(spool)].filter(Boolean).join(" · ")),
        h("p", { class: "spools-remain" + (remaining && remaining.exhausted ? " is-warn" : spool.low ? " is-low" : "") }, remainingText(remaining)),
        lines.map((text) => h("p", { class: "spools-sub" }, sentence(text)))));
  }
  function restPane(sheet, spool) {
    return pane("Ce qui reste", null,
      note("Remplis un seul champ : les autres suivent. Un poids brut est une pesée, le reste une estimation."),
      linkedInputs(sheet, remainingFields(spool.remaining)),
      h("p", { class: "spools-preview", ref: "rest-preview", "aria-live": "polite" }),
      conflictLine(sheet, "remaining"), errorOf(sheet, "remaining"),
      h("div", { class: "spools-actions" },
        btn("Enregistrer le reste", () => saveRemaining(sheet, spool.id), { primary: true, busy: "rest", ref: "rest-save" }),
        btn("Bobine neuve", () => restartSpool(sheet, spool), { busy: "rest-new" })));
  }
  function linkedInputs(sheet, current) {
    const context = sheetContext(sheet);
    const typed = sheet.typed;
    const computed = typed ? remainingFrom(typed.field, typed.text, context) : null;
    return h("div", { class: "spools-linked" }, LINKED.map(([key, label, hint]) => {
      const noTare = key === "gross" && context.tare == null;
      let value = "";
      if (typed && typed.field === key) value = typed.text;
      else if (computed && !computed.error) value = computed.values[key] || "";
      const control = h("input", { class: "spools-input", ref: "rest-" + key, inputmode: "decimal", maxlength: 12,
        placeholder: current[key] || "", value, disabled: noTare, oninput: (event) => typeRemaining(sheet, key, event.target.value) });
      return field(label, control, { hint: noTare ? "choisir la bobine vide pour peser" : key === "gross" ? "tare : " + grams(context.tare) : hint || null });
    }));
  }
  function typeRemaining(sheet, key, text) {
    if (!String(text).trim()) { sheet.typed = null; sheet.touched.delete("remaining"); }
    else { sheet.typed = { field: key, text }; sheet.touched.add("remaining"); }
    const computed = sheet.typed ? remainingFrom(key, text, sheetContext(sheet)) : null;
    for (const [other] of LINKED) {
      if (other === key) continue;
      const node = app.refs["rest-" + other];
      if (node) node.value = computed && !computed.error ? computed.values[other] || "" : "";
    }
    renderPreview();
  }
  function renderPreview() {
    const node = app.refs["rest-preview"];
    if (!node) return;
    const sheet = app.sheet;
    const typed = sheet && sheet.typed;
    if (!typed || !String(typed.text).trim()) { node.textContent = ""; node.className = "spools-preview"; return; }
    const computed = remainingFrom(typed.field, typed.text, sheetContext(sheet));
    let text = "", tone = "";
    if (computed.error) { text = sentence(computed.error); tone = "warn"; }
    else if (computed.basis && computed.basis.kind === "pesee") { text = "Sera enregistré : pesée, " + grams(computed.basis.value_g) + " brut, soit " + (computed.values.net || "?") + " g net."; tone = "ok"; }
    else if (computed.basis) { text = "Sera enregistré : estimation, " + grams(computed.basis.value_g) + " net."; tone = "ok"; }
    node.textContent = text;
    node.className = "spools-preview" + (tone ? " is-" + tone : "");
  }
  function sheetContext(sheet) { return restContext(sheet, sheet.kind === "spool" ? spoolById(sheet.key) : null); }
  // An existing spool weighs against its saved empty spool: the K1 uses that one.
  function restContext(sheet, spool) {
    const draft = sheet.draft;
    const emptyId = spool ? spool.empty_spool : draft.empty_spool;
    const record = emptyId ? emptyOf(emptyId) : null;
    const tare = record && record.tare_g != null && Number.isFinite(Number(record.tare_g)) ? Number(record.tare_g) : null;
    let initial = 0, density = 0, diameter = DIAMETER;
    if (spool) {
      initial = Number(spool.initial_net_g) || 0;
      const fiche = ficheOf(spool.filament);
      density = fiche ? Number(fiche.density) || 0 : 0;
      diameter = fiche ? Number(fiche.diameter_mm) || DIAMETER : DIAMETER;
    } else {
      const typed = parseNumber(draft.initial_net_g);
      initial = Number.isFinite(typed) && typed > 0 ? typed : record ? Number(record.nominal_net_g) || 0 : 0;
      if (draft.fiche_mode === "existing") {
        const fiche = ficheOf(draft.fiche);
        density = fiche ? Number(fiche.density) || 0 : 0;
        diameter = fiche ? Number(fiche.diameter_mm) || DIAMETER : DIAMETER;
      } else {
        const d = parseNumber(draft.density); density = Number.isFinite(d) && d > 0 ? d : 0;
        const m = parseNumber(draft.diameter_mm); diameter = Number.isFinite(m) && m > 0 ? m : DIAMETER;
      }
    }
    return { tare, initial, gpm: density > 0 ? gramsPerMetre(density, diameter) : 0 };
  }
  async function saveRemaining(sheet, id) {
    const typed = sheet.typed;
    if (!typed || !String(typed.text).trim()) return fail(sheet, "remaining", "Remplis d'abord un des champs.");
    const computed = remainingFrom(typed.field, typed.text, sheetContext(sheet));
    if (computed.error || !computed.basis) return fail(sheet, "remaining", sentence(computed.error || "nombre attendu"));
    const reply = await act("set_remaining", { id, kind: computed.basis.kind, value_g: computed.basis.value_g }, { busy: "rest", section: "remaining", keys: ["remaining"] });
    if (reply) toast(labelOf(id) + " : reste enregistré, " + grams(reply.result && reply.result.net_g) + " net.", true);
  }
  async function restartSpool(sheet, spool) {
    if (!ask("Repartir du net initial de " + grams(spool.initial_net_g) + " ? Le décompte repart de zéro.")) return;
    const reply = await act("set_remaining", { id: spool.id, kind: "neuve" }, { busy: "rest-new", section: "remaining", keys: ["remaining"] });
    if (reply) toast(labelOf(spool.id) + " : repartie neuve, " + grams(reply.result && reply.result.net_g) + " net.", true);
  }
  function identityPane(sheet, spool) {
    const draft = sheet.draft;
    return pane("Fiche et bobine vide", null,
      h("div", { class: "spools-form" },
        sheetField(sheet, "filament", "Fiche filament", choice(sheet, "filament", ficheOptionsList(), { label: "Fiche filament", placeholder: draft.filament ? null : "Choisir une fiche…" }), {
          extra: [
            btn("Modifier la fiche", () => openSheet(makeSheet("fiche", draft.filament)), { nav: true, ghost: true, disabled: !ficheOf(draft.filament), ref: "edit-fiche" }),
            btn("Nouvelle fiche", () => openSheet(makeSheet("fiche", "")), { nav: true, ghost: true, ref: "identity-new-fiche" }),
          ] }),
        sheetField(sheet, "empty_spool", "Bobine vide", choice(sheet, "empty_spool", [["", "aucune (tare inconnue)"]].concat(emptyOptionsList()), { label: "Bobine vide" }), {
          hint: emptyHint(draft.empty_spool),
          extra: btn("Nouveau type", () => openSheet(makeSheet("empty", "")), { nav: true, ghost: true, ref: "identity-new-empty" }) }),
        sheetField(sheet, "initial_net_g", "Net neuf (g)", numberInput(sheet, "initial_net_g"), { hint: "le filament seul, bobine neuve" }),
        sheetField(sheet, "notes", "Notes", textArea(sheet, "notes"), { wide: true })),
      errorOf(sheet, "identity"),
      h("div", { class: "spools-actions" }, btn("Enregistrer", () => saveIdentity(sheet, spool.id), { primary: true, busy: "identity", ref: "identity-save" })));
  }
  async function saveIdentity(sheet, id) {
    const draft = sheet.draft, base = sheet.base;
    const params = { id };
    const keys = [];
    for (const key of ["filament", "empty_spool"]) if (draft[key] !== base[key]) { params[key] = draft[key]; keys.push(key); }
    const notes = String(draft.notes || "").trim();
    if (notes !== String(base.notes || "").trim()) { params.notes = notes; keys.push("notes"); }
    const numbers = readNumbers(sheet, ["initial_net_g"], ["initial_net_g"], "identity");
    if (!numbers) return false;
    Object.assign(params, numbers); keys.push(...Object.keys(numbers));
    if (!keys.length) return fail(sheet, "identity", "Rien n'a changé.");
    if (params.filament === "") return fail(sheet, "identity", "Choisir une fiche filament.");
    const reply = await act("edit_spool", params, { busy: "identity", section: "identity", keys });
    if (reply) toast(labelOf(id) + " : enregistrée.", true);
  }
  function readNumbers(sheet, keys, required, section) {
    const out = {};
    for (const key of keys) {
      const text = String(sheet.draft[key] == null ? "" : sheet.draft[key]).trim();
      if (!sheet.creating && text === String(sheet.base[key] == null ? "" : sheet.base[key]).trim()) continue;
      const value = parseNumber(text);
      if (value === null) { if (required.includes(key)) { fail(sheet, section, (FIELD_LABELS[key] || key) + " : valeur attendue."); return null; } continue; }
      if (!Number.isFinite(value)) { fail(sheet, section, (FIELD_LABELS[key] || key) + " : nombre attendu."); return null; }
      out[key] = value;
    }
    return out;
  }
  function wherePane(sheet, spool) {
    const id = spool.id;
    const parts = [];
    if (spool.state === "cfs") {
      parts.push(h("p", null, "Au CFS en " + spool.slot + "."), h("div", { class: "spools-actions" },
        btn("Retirer du CFS", () => removeFromCfs(id, "where"), { busy: "remove", ref: "where-remove" }),
        btn("Voir l'emplacement", () => openSheet(makeSheet("slot", spool.slot)), { nav: true, ghost: true, ref: "where-slot" })));
    } else if (ARCHIVED.includes(spool.state)) {
      parts.push(h("p", null, (spool.state === "jetee" ? "Jetée" : "Terminée") + " le " + dayLabel(spool.updated) + "."),
        h("div", { class: "spools-actions" }, btn("Remettre en stock", () => restoreSpool(id), { busy: "restore", ref: "where-restore" })));
    } else {
      const place = String(spool.place || "");
      parts.push(h("p", null, spool.state === "a_ranger" ? "À ranger : sortie du CFS, pas encore rangée." : place ? "En stock : " + place + "." : "En stock."),
        h("div", { class: "spools-inline" },
          sheetField(sheet, "place", "Lieu", input(sheet, "place", { maxlength: NAME_LIMIT, placeholder: "étagère, boîte, sac…", list: "spools-places" })),
          placesList(),
          btn(spool.state === "a_ranger" ? "Ranger" : "Déplacer", () => storeSpool(sheet, id, spool.state !== "a_ranger"), { primary: spool.state === "a_ranger", busy: "store", ref: "where-store" })));
    }
    if (!ARCHIVED.includes(spool.state)) {
      const options = cfsSlotOptions(id);
      const key = "put:" + id;
      parts.push(options.length ? h("div", { class: "spools-inline" },
        pick(key, "Choisir un emplacement…", options, { label: "Emplacement du CFS" }),
        btn("Mettre au CFS", () => putInCfs(id, app.choices[key], "where"), { disabled: !app.choices[key], busy: key, ref: "where-put" }))
        : note("Aucun emplacement du CFS lu : Klipper ou les unités ne répondent pas.", "faint"));
    }
    return pane("Où elle est", null, parts, errorOf(sheet, "where"));
  }
  async function storeSpool(sheet, id, moving) {
    const place = String(sheet.draft.place || "").trim();
    const reply = await act("store", { id, place }, { busy: "store", section: "where", keys: ["place"] });
    if (reply) toast(labelOf(id) + (moving ? " déplacée" : " rangée") + (place ? " : " + place : "") + ".", true);
  }
  async function restoreSpool(id) {
    const reply = await act("restore", { id }, { busy: "restore", section: "where" });
    if (reply) toast(labelOf(id) + " remise en stock.", true);
  }
  function endPane(sheet, spool) {
    const id = spool.id;
    const history = btn("Voir son historique", () => chooseTab("journal", id), { nav: true, ghost: true, ref: "end-history" });
    if (ARCHIVED.includes(spool.state)) return pane("Fin de vie", null, note("Archivée : elle reste dans l'historique."), history, errorOf(sheet, "end"));
    return pane("Fin de vie", null,
      h("div", { class: "spools-actions" },
        btn("Terminée", () => archiveSpool(id, "finish"), { primary: nearlyEmpty(spool.remaining), busy: "finish", ref: "end-finish" }),
        btn("Jetée", () => archiveSpool(id, "discard"), { danger: true, busy: "discard", ref: "end-discard" }),
        history),
      errorOf(sheet, "end"));
  }
  async function archiveSpool(id, action) {
    const word = action === "finish" ? "terminée" : "jetée";
    if (!ask("Marquer " + labelOf(id) + " " + word + " ? Elle sort du CFS et du stock ; « Remettre en stock » la fait revenir.")) return;
    const reply = await act(action, { id }, { busy: action, section: "end" });
    if (reply) toast(labelOf(id) + " " + word + ".", true);
  }
  function newSpoolSheet(slot) {
    const view = slot ? slotView(slot) : null;
    const observed = (view && view.observed) || {};
    const seenId = observed.present ? creality(observed.material) : "";
    const colour = observed.present ? colourKey(observed.colour || "") : "";
    const record = seenId ? materialRecord(app.materials || [], seenId) : null;
    const filaments = (app.status && app.status.filaments) || {};
    const match = seenId ? Object.keys(filaments).find((id) => String(filaments[id].creality_id == null ? "" : filaments[id].creality_id) === seenId && colourKey(filaments[id].colour || "") === colour) : "";
    const brand = record && record.brand && !/generic|g[ée]n[ée]rique/i.test(record.brand) ? record.brand : "";
    const draft = { fiche_mode: match ? "existing" : seenId || !Object.keys(filaments).length ? "new" : "existing", fiche: match || "",
      manufacturer: brand, name: "", material: (record && record.type) || observed.type || "", colour, diameter_mm: figure(DIAMETER, 2), density: "",
      creality_id: seenId, empty_spool: "", initial_net_g: "", rest_mode: "neuve", state: slot ? "cfs" : "stock", slot: slot || "", place: "", notes: "" };
    return makeSheet("new-spool", slot, { draft, picked: Boolean(seenId) });
  }
  // A new spool's remaining follows its net, density and diameter while they are typed.
  function relink(sheet) { if (sheet.kind === "new-spool" && sheet.typed) typeRemaining(sheet, sheet.typed.field, sheet.typed.text); }
  function newSpoolSheetView(sheet) {
    const draft = sheet.draft;
    const fiches = ficheOptionsList();
    const record = emptyOf(draft.empty_spool);
    const slots = cfsSlotOptions("");
    const target = draft.state === "cfs" && draft.slot ? slotView(draft.slot) : null;
    return {
      title: "Nouvelle bobine" + (draft.state === "cfs" && draft.slot ? " en " + draft.slot : ""),
      body: [
        pane("Filament", null,
          segmented(sheet, "fiche_mode", [["existing", "Fiche existante"], ["new", "Nouvelle fiche"]], "Fiche du filament"),
          draft.fiche_mode === "existing"
            ? (fiches.length ? h("div", { class: "spools-form" }, field("Fiche filament", choice(sheet, "fiche", fiches, { label: "Fiche filament", placeholder: "Choisir une fiche…" }), { wide: true }))
              : note("Aucune fiche pour l'instant : crée-la ici.", "faint"))
            : ficheFields(sheet),
          errorOf(sheet, "fiche")),
        pane("Bobine vide", null,
          h("div", { class: "spools-form" },
            field("Bobine vide", choice(sheet, "empty_spool", [["", "aucune (tare inconnue)"]].concat(emptyOptionsList()), { label: "Bobine vide" }), {
              hint: emptyHint(draft.empty_spool),
              extra: btn("Nouveau type", () => openSheet(makeSheet("empty", "")), { nav: true, ghost: true, ref: "new-spool-empty" }) }),
            field("Net initial (g)", numberInput(sheet, "initial_net_g", { placeholder: record && record.nominal_net_g != null ? gramsLabel(record.nominal_net_g) : "", oninput: () => relink(sheet) }), {
              hint: record ? "vide : le net nominal de la bobine vide" : "le filament seul, bobine neuve" })),
          errorOf(sheet, "spool")),
        pane("Ce qui reste", null,
          segmented(sheet, "rest_mode", [["neuve", "Neuve"], ["entamee", "Entamée"]], "État de la bobine"),
          draft.rest_mode === "entamee" ? [
            note("Remplis un seul champ : les autres suivent. Un poids brut est une pesée, le reste une estimation."),
            linkedInputs(sheet, remainingFields(null)),
            h("p", { class: "spools-preview", ref: "rest-preview", "aria-live": "polite" }),
          ] : null,
          errorOf(sheet, "rest")),
        pane("Où elle va", null,
          segmented(sheet, "state", [["cfs", "Au CFS"], ["stock", "En stock"], ["a_ranger", "À ranger"]], "Où va la bobine"),
          draft.state === "cfs" ? (slots.length
            ? h("div", { class: "spools-form" }, field("Emplacement", choice(sheet, "slot", slots, { label: "Emplacement", placeholder: "Choisir l'emplacement…" })))
            : note("Aucun emplacement du CFS lu : Klipper ou les unités ne répondent pas.", "faint")) : null,
          target && target.spool ? note(labelOf(target.spool) + " est attendue en " + draft.slot + " : elle passera « à ranger ».", "warn") : null,
          draft.state === "stock" ? h("div", { class: "spools-form" }, field("Lieu", input(sheet, "place", { maxlength: NAME_LIMIT, placeholder: "étagère, boîte, sac…", list: "spools-places" })), placesList()) : null,
          errorOf(sheet, "where")),
        box(h("div", { class: "spools-form" }, field("Notes", textArea(sheet, "notes"), { wide: true })),
          errorOf(sheet, "create"),
          h("div", { class: "spools-actions" }, btn("Créer la bobine", () => createSpool(sheet), { primary: true, busy: "create", ref: "create-spool" }))),
      ],
    };
  }
  async function createSpool(sheet) {
    const draft = sheet.draft;
    let ficheParams = null;
    if (draft.fiche_mode === "existing") { if (!ficheOf(draft.fiche)) return fail(sheet, "fiche", "Choisir une fiche filament."); }
    else { ficheParams = ficheParamsOf(sheet, "fiche"); if (!ficheParams) return false; }
    const initial = parseNumber(String(draft.initial_net_g || "").trim());
    if (initial !== null && !Number.isFinite(initial)) return fail(sheet, "spool", "Net initial : nombre attendu.");
    if (initial === null && !emptyOf(draft.empty_spool)) return fail(sheet, "spool", "Net initial manquant : le donner ou choisir la bobine vide.");
    let basis = { kind: "neuve", value_g: null };
    if (draft.rest_mode === "entamee") {
      const typed = sheet.typed;
      if (!typed || !String(typed.text).trim()) return fail(sheet, "rest", "Bobine entamée : remplis un des champs du reste, ou choisis « Neuve ».");
      const computed = remainingFrom(typed.field, typed.text, sheetContext(sheet));
      if (computed.error || !computed.basis) return fail(sheet, "rest", sentence(computed.error || "nombre attendu"));
      basis = computed.basis;
    }
    if (draft.state === "cfs") {
      if (!draft.slot) return fail(sheet, "where", "Choisir l'emplacement du CFS.");
      const target = slotView(draft.slot);
      if (target && target.spool && !ask(draft.slot + " attend déjà " + labelOf(target.spool) + " : elle passera « à ranger ». Continuer ?")) return false;
    }
    let filament = draft.fiche;
    if (ficheParams) {
      const reply = await act("create_filament", ficheParams, { busy: "create", section: "fiche" });
      if (!reply) return false;
      filament = reply.result && reply.result.id;
      if (!filament) return fail(sheet, "fiche", "Fiche créée sans numéro : relis la liste avant de recommencer.");
      setDraft(sheet, "fiche_mode", "existing"); setDraft(sheet, "fiche", filament); rerender(sheet);
    }
    const params = { filament, basis_kind: basis.kind, state: draft.state };
    if (draft.empty_spool) params.empty_spool = draft.empty_spool;
    if (initial !== null) params.initial_net_g = initial;
    if (basis.kind !== "neuve") params.value_g = basis.value_g;
    if (draft.state === "cfs") params.slot = draft.slot;
    const place = String(draft.place || "").trim();
    if (draft.state === "stock" && place) params.place = place;
    const notes = String(draft.notes || "").trim();
    if (notes) params.notes = notes;
    const reply = await act("create_spool", params, { busy: "create", section: "create", leave: true });
    if (!reply) return false;
    const label = labelOf(reply.result && reply.result.id);
    if (draft.state === "cfs") {
      const view = slotView(draft.slot);
      toast(label + " créée en " + draft.slot + (view && view.status === "a_verifier" ? " : à vérifier, ouvre l'emplacement pour écrire le CFS." : "."), true);
    } else toast(label + (draft.state === "stock" ? " créée, en stock." : " créée, à ranger."), true);
    return true;
  }
  function ficheFields(sheet) {
    const draft = sheet.draft;
    const loaded = Array.isArray(app.materials) && app.materials.length > 0;
    const types = loaded ? materialTypes(app.materials) : [];
    const relinked = { oninput: () => relink(sheet) };
    return h("div", { class: "spools-form" },
      sheetField(sheet, "manufacturer", "Fabricant", input(sheet, "manufacturer", { maxlength: NAME_LIMIT, oninput: () => suggest(sheet) })),
      sheetField(sheet, "name", "Nom", input(sheet, "name", { maxlength: NAME_LIMIT, placeholder: "gamme, finition…", oninput: () => suggest(sheet) })),
      sheetField(sheet, "material", "Matière", types.length
        ? choice(sheet, "material", types.map((type) => [type, type]), { label: "Matière", placeholder: "Choisir…", after: () => materialChanged(sheet) })
        : input(sheet, "material", { maxlength: 20, placeholder: "PLA, PETG…", oninput: () => suggest(sheet) })),
      sheetField(sheet, "colour", "Couleur", colourRow(sheet)),
      sheetField(sheet, "diameter_mm", "Diamètre (mm)", numberInput(sheet, "diameter_mm", relinked)),
      sheetField(sheet, "density", "Densité (g/cm³)", numberInput(sheet, "density", relinked), { hint: sheet.creating ? "vide : celle de la fiche Creality" : null }),
      sheetField(sheet, "creality_id", "Fiche matériau Creality", crealityControl(sheet), { wide: true,
        hint: loaded && draft.material ? "le CFS reconnaît la bobine par cette fiche" : null }),
      sheet.kind === "fiche" ? sheetField(sheet, "notes", "Notes", textArea(sheet, "notes"), { wide: true }) : null);
  }
  function crealityControl(sheet) {
    const draft = sheet.draft;
    if (!app.materials) {
      const prefix = draft.creality_id ? "n° " + draft.creality_id + " · " : "";
      return app.materialsError ? note(prefix + "Base matériau de la K1 illisible : " + app.materialsError + ".", "warn") : note(prefix + "Base matériau de la K1 pas encore lue.", "faint");
    }
    if (!draft.material) return note("choisis d'abord la matière", "faint");
    const options = materialsOfType(app.materials, draft.material).map((record) => [String(record.id), [record.brand, record.name].filter(Boolean).join(" ") + " · n° " + record.id]);
    const first = sheet.creating ? [["", "automatique (la K1 choisit)"]] : draft.creality_id ? [] : [["", "aucune"]];
    return choice(sheet, "creality_id", first.concat(options), { label: "Fiche matériau Creality", after: () => { sheet.picked = true; } });
  }
  function colourRow(sheet) {
    const hex = colourKey(sheet.draft.colour || "");
    const picker = h("input", { class: "spools-picker", type: "color", ref: "f-colour-picker", "aria-label": "Choisir la couleur",
      value: "#" + (hex || "808080").toLowerCase(), oninput: (event) => setColour(sheet, event.target.value, "picker") });
    const text = h("input", { class: "spools-input spools-hex", ref: "f-colour", maxlength: 7, placeholder: "RRGGBB", "aria-label": "Couleur en hexadécimal",
      value: sheet.draft.colour || "", oninput: (event) => setColour(sheet, event.target.value, "text") });
    return h("div", { class: "spools-colour" }, picker, text, h("span", { class: "spools-colour-name", ref: "f-colour-name" }, hex ? colourName(hex) : ""));
  }
  function setColour(sheet, value, from) {
    const hex = colourKey(value);
    setDraft(sheet, "colour", hex || String(value).trim());
    const picker = app.refs["f-colour-picker"], text = app.refs["f-colour"], name = app.refs["f-colour-name"];
    if (from === "picker" && text) text.value = hex;
    if (from === "text" && picker && hex) picker.value = "#" + hex.toLowerCase();
    if (name) name.textContent = hex ? colourName(hex) : "";
  }
  function suggest(sheet) {
    if (sheet.picked || !app.materials || !sheet.draft.material) return;
    const id = suggestCrealityId(sheet.draft.manufacturer, sheet.draft.material, sheet.draft.name, app.materials);
    const value = id ? String(id) : "";
    if (value === sheet.draft.creality_id) return;
    setDraft(sheet, "creality_id", value);
    const node = app.refs["f-creality_id"];
    if (node) node.value = value;
  }
  function materialChanged(sheet) {
    const id = sheet.draft.creality_id;
    if (id && app.materials) { const record = materialRecord(app.materials, id); if (!record || record.type !== sheet.draft.material) setDraft(sheet, "creality_id", ""); }
    sheet.picked = false;
    suggest(sheet);
  }
  function ficheParamsOf(sheet, section) {
    const draft = sheet.draft, base = sheet.base;
    const changed = (key) => sheet.creating || draft[key] !== base[key];
    const manufacturer = String(draft.manufacturer || "").trim();
    const material = String(draft.material || "").trim().toUpperCase();
    const colour = colourKey(draft.colour || "");
    if (!manufacturer) { fail(sheet, section, "Fabricant manquant."); return null; }
    if (!material) { fail(sheet, section, "Matière manquante : choisis-la."); return null; }
    if (!String(draft.colour || "").trim()) { fail(sheet, section, "Couleur manquante : choisis-la."); return null; }
    if (!colour) { fail(sheet, section, "Couleur : six chiffres hexadécimaux attendus."); return null; }
    const numbers = readNumbers(sheet, ["diameter_mm", "density"], ["diameter_mm"], section);
    if (!numbers) return null;
    const params = {};
    if (changed("manufacturer")) params.manufacturer = manufacturer;
    if (changed("name")) params.name = String(draft.name || "").trim();
    if (changed("material")) params.material = material;
    if (changed("colour")) params.colour = colour;
    Object.assign(params, numbers);
    const creality = String(draft.creality_id || "").trim();
    if (creality && changed("creality_id")) params.creality_id = creality;
    if (sheet.kind === "fiche" && changed("notes")) params.notes = String(draft.notes || "").trim();
    return params;
  }
  function ficheSheet(sheet) {
    const fiche = sheet.key ? ficheOf(sheet.key) : null;
    if (sheet.key && !fiche) return { title: "Fiche", body: box(note("Fiche introuvable.", "warn")) };
    const users = sheet.key ? usersOf(app.status.spools, "filament", sheet.key) : [];
    return {
      title: fiche ? "Fiche " + ficheName(fiche) : "Nouvelle fiche filament",
      body: box(
        users.length ? note("Utilisée par " + usersText(users) + " : un changement de matière ou de couleur les met « à vérifier » au CFS.") : null,
        ficheFields(sheet), errorOf(sheet, "fiche"),
        h("div", { class: "spools-actions" },
          btn(sheet.creating ? "Créer la fiche" : "Enregistrer", () => saveFiche(sheet), { primary: true, busy: "fiche", ref: "fiche-save" }),
          !sheet.creating && !users.length ? btn("Supprimer", () => deleteFiche(sheet), { danger: true, busy: "delete-fiche", ref: "fiche-delete" }) : null)),
    };
  }
  async function saveFiche(sheet) {
    const params = ficheParamsOf(sheet, "fiche");
    if (!params) return false;
    if (sheet.creating) {
      const reply = await act("create_filament", params, { busy: "fiche", section: "fiche", leave: true });
      if (!reply) return false;
      const id = reply.result && reply.result.id;
      const below = app.sheet;
      if (id && below && below.kind === "spool") { setDraft(below, "filament", id); rerender(below); toast("Fiche créée : clique « Enregistrer » pour la donner à " + labelOf(below.key) + ".", true); }
      else if (id && below && below.kind === "new-spool") { setDraft(below, "fiche_mode", "existing"); setDraft(below, "fiche", id); rerender(below); toast("Fiche créée.", true); }
      else toast("Fiche créée.", true);
      return true;
    }
    if (!Object.keys(params).length) return fail(sheet, "fiche", "Rien n'a changé.");
    const before = new Set(app.status.slots.filter((view) => view && view.status === "a_verifier").map((view) => view.slot));
    const reply = await act("edit_filament", Object.assign({ id: sheet.key }, params), { busy: "fiche", section: "fiche", keys: Object.keys(params) });
    if (!reply) return false;
    const fresh = app.status.slots.filter((view) => view && view.status === "a_verifier" && !before.has(view.slot)).map((view) => view.slot);
    if (fresh.length) toast(joinFr(fresh) + (fresh.length > 1 ? " sont maintenant à vérifier : ouvre-les pour écrire le CFS." : " est maintenant à vérifier : ouvre-le pour écrire le CFS."), true);
    else toast(Array.isArray(reply.result && reply.result.changed) && !reply.result.changed.length ? "Rien n'a changé." : "Fiche enregistrée.", true);
    return true;
  }
  async function deleteFiche(sheet) {
    if (!ask("Supprimer la fiche " + ficheName(ficheOf(sheet.key)) + " ?")) return;
    const reply = await act("delete_filament", { id: sheet.key }, { busy: "delete-fiche", section: "fiche", leave: true });
    if (reply) toast("Fiche supprimée.", true);
  }
  function emptySheet(sheet) {
    const record = sheet.key ? emptyOf(sheet.key) : null;
    if (sheet.key && !record) return { title: "Bobine vide", body: box(note("Bobine vide introuvable.", "warn")) };
    const draft = sheet.draft;
    const users = sheet.key ? usersOf(app.status.spools, "empty_spool", sheet.key) : [];
    const source = record ? (record.source === "pesee" ? "Source : pesée le " + dayLabel(record.weighed_on) + "." : record.source === "spoolmandb" ? "Source : catalogue SpoolmanDB." : "Source : saisie.") : "";
    const form = h("div", { class: "spools-form" },
      sheetField(sheet, "manufacturer", "Fabricant", input(sheet, "manufacturer", { maxlength: NAME_LIMIT })),
      sheetField(sheet, "name", "Nom", input(sheet, "name", { maxlength: NAME_LIMIT, placeholder: "Bobine 1 kg plastique…" })),
      sheetField(sheet, "spool_material", "Matière de la bobine", choice(sheet, "spool_material", SPOOL_MATERIALS.map((m) => [m, m]), { label: "Matière de la bobine" })),
      sheetField(sheet, "tare_g", "Tare (g)", numberInput(sheet, "tare_g"), { hint: sheet.creating ? "poids de la bobine vide" : "tare pesée sur ta balance : « Enregistrer comme pesée » ; sinon elle devient « saisie »" }),
      sheetField(sheet, "nominal_net_g", "Net nominal (g)", numberInput(sheet, "nominal_net_g"), { hint: "le filament d'une bobine neuve" }),
      sheet.creating ? h("label", { class: "spools-check is-wide" },
        h("input", { type: "checkbox", ref: "weighed", checked: draft.weighed, onchange: (event) => setDraft(sheet, "weighed", event.target.checked) }),
        "Je l'ai pesée moi-même") : null,
      sheetField(sheet, "notes", "Notes", textArea(sheet, "notes"), { wide: true }));
    return {
      title: record ? "Bobine vide " + emptySpoolName(record) : "Nouveau type de bobine vide",
      body: [
        sheet.creating ? pane("Depuis le catalogue SpoolmanDB", null,
          h("input", { class: "spools-input spools-search", type: "search", ref: "tare-query", value: app.tareQuery,
            placeholder: "Chercher une marque ou une matière…", "aria-label": "Chercher dans le catalogue", maxlength: NAME_LIMIT,
            oninput: (event) => { app.tareQuery = event.target.value; renderTareList(); } }),
          h("div", { class: "spools-tares", ref: "tare-list" })) : null,
        pane(sheet.creating ? "Ou à la main" : "Le type", null,
          source ? note(source, "faint") : null,
          users.length ? note("Utilisée par " + usersText(users) + " : changer la tare recalcule leur reste.") : null,
          form, errorOf(sheet, "empty"),
          h("div", { class: "spools-actions" },
            btn(sheet.creating ? "Ajouter ce type" : "Enregistrer", () => saveEmpty(sheet), { primary: true, busy: "empty", ref: "empty-save" }),
            sheet.creating ? null : btn("Enregistrer comme pesée", () => weighEmpty(sheet), { busy: "weigh", ref: "empty-weigh" }),
            !sheet.creating && !users.length ? btn("Supprimer", () => deleteEmpty(sheet), { danger: true, busy: "delete-empty", ref: "empty-delete" }) : null)),
      ],
    };
  }
  function renderTareList() {
    const node = app.refs["tare-list"];
    if (!node) return;
    if (!app.tares) {
      if (app.taresError) fill(node, note("Catalogue illisible : " + app.taresError + ". La saisie à la main reste possible.", "warn"));
      else fill(node, h("p", { class: "empty" }, h("span", { class: "spinner", "aria-hidden": "true" }), "Lecture du catalogue…"));
      return;
    }
    const query = String(app.tareQuery || "").trim();
    if (!query) { fill(node, note(app.tares.length + " types de bobines connus : tape une marque pour chercher.", "faint")); return; }
    const found = searchTares(app.tares, query);
    if (!found.length) { fill(node, note("Rien dans le catalogue : remplis le type à la main ci-dessous.", "faint")); return; }
    const added = {};
    for (const [id, record] of Object.entries((app.status && app.status.empty_spools) || {})) if (record && record.catalogue) added[record.catalogue] = id;
    fill(node, found.map((entry) => h("div", { class: "spools-row is-static" },
      h("span", { class: "spools-row-main" },
        h("strong", null, [entry.manufacturer, gramsLabel(entry.net_g) + " g net", entry.spool_material !== "inconnue" ? entry.spool_material : "", "tare " + gramsLabel(entry.tare_g) + " g"].filter(Boolean).join(" · ")),
        h("span", { class: "spools-sub" }, tareLines(entry))),
      added[entry.key] ? note("déjà ajoutée (" + idLabel(added[entry.key]) + ")", "faint") : btn("Choisir", () => pickTare(entry), { ghost: true, nav: true }))));
  }
  function pickTare(entry) {
    const sheet = app.sheet;
    if (!sheet || sheet.kind !== "empty") return;
    const material = SPOOL_MATERIALS.includes(entry.spool_material) ? entry.spool_material : "inconnue";
    setDraft(sheet, "manufacturer", entry.manufacturer || "");
    setDraft(sheet, "name", "Bobine " + gramsLabel(entry.net_g) + " g" + (material !== "inconnue" ? " " + material : ""));
    setDraft(sheet, "spool_material", material);
    setDraft(sheet, "tare_g", figure(entry.tare_g, 2));
    setDraft(sheet, "nominal_net_g", figure(entry.net_g, 2));
    setDraft(sheet, "catalogue", entry.key);
    setDraft(sheet, "catalogue_tare", figure(entry.tare_g, 2));
    rerender(sheet);
    toast("Type rempli depuis le catalogue : vérifie puis « Ajouter ce type ».", true);
  }
  async function saveEmpty(sheet) {
    const draft = sheet.draft, base = sheet.base;
    const manufacturer = String(draft.manufacturer || "").trim();
    if (!manufacturer) return fail(sheet, "empty", "Fabricant manquant.");
    const numbers = readNumbers(sheet, ["tare_g", "nominal_net_g"], ["tare_g", "nominal_net_g"], "empty");
    if (!numbers) return false;
    if (sheet.creating) {
      const catalogue = String(draft.catalogue || "");
      let source = "manuel";
      if (draft.weighed) source = "pesee";
      else if (catalogue && parseNumber(draft.tare_g) === parseNumber(draft.catalogue_tare)) source = "spoolmandb";
      const params = Object.assign({ manufacturer, name: String(draft.name || "").trim(), spool_material: draft.spool_material || "inconnue" }, numbers, { source });
      if (catalogue) params.catalogue = catalogue;
      const notes = String(draft.notes || "").trim();
      if (notes) params.notes = notes;
      const reply = await act("create_empty_spool", params, { busy: "empty", section: "empty", leave: true });
      if (!reply) return false;
      const id = reply.result && reply.result.id;
      const below = app.sheet;
      if (id && below && (below.kind === "spool" || below.kind === "new-spool")) {
        setDraft(below, "empty_spool", id); rerender(below);
        toast(below.kind === "spool" ? "Type ajouté : clique « Enregistrer » pour le donner à " + labelOf(below.key) + "." : "Type ajouté.", true);
      } else toast("Type ajouté.", true);
      return true;
    }
    const params = { id: sheet.key };
    const keys = [];
    for (const key of ["manufacturer", "name", "spool_material"]) {
      const value = String(draft[key] || "").trim();
      if (value !== String(base[key] || "").trim()) { params[key] = value; keys.push(key); }
    }
    Object.assign(params, numbers); keys.push(...Object.keys(numbers));
    const notes = String(draft.notes || "").trim();
    if (notes !== String(base.notes || "").trim()) { params.notes = notes; keys.push("notes"); }
    if (!keys.length) return fail(sheet, "empty", "Rien n'a changé.");
    const users = usersOf(app.status.spools, "empty_spool", sheet.key);
    const reply = await act("edit_empty_spool", params, { busy: "empty", section: "empty", keys });
    if (!reply) return false;
    toast(keys.includes("tare_g") && users.length ? "Tare changée : le reste de " + usersText(users) + " est recalculé." : "Bobine vide enregistrée.", true);
    return true;
  }
  async function weighEmpty(sheet) {
    const value = parseNumber(String(sheet.draft.tare_g == null ? "" : sheet.draft.tare_g).trim());
    if (value === null) return fail(sheet, "empty", "Tare : valeur attendue.");
    if (!Number.isFinite(value)) return fail(sheet, "empty", "Tare : nombre attendu.");
    const users = usersOf(app.status.spools, "empty_spool", sheet.key);
    const reply = await act("weigh_empty_spool", { id: sheet.key, tare_g: value }, { busy: "weigh", section: "empty", keys: ["tare_g"] });
    if (reply) toast(users.length ? "Tare pesée enregistrée : le reste de " + usersText(users) + " est recalculé." : "Tare pesée enregistrée.", true);
  }
  async function deleteEmpty(sheet) {
    if (!ask("Supprimer la bobine vide " + emptySpoolName(emptyOf(sheet.key)) + " ?")) return;
    const reply = await act("delete_empty_spool", { id: sheet.key }, { busy: "delete-empty", section: "empty", leave: true });
    if (reply) toast("Bobine vide supprimée.", true);
  }
  function settingsSheet(sheet) {
    const status = app.status;
    const store = status.store || {};
    const k = klippy();
    const materials = status.materials || {};
    const counter = status.counter || {};
    const about = [
      ["Version", status.version || "?"],
      ["Révision", String(status.revision)],
      ["Contenu", [count(status.spools.length, "bobine", "bobines"), count(Object.keys(status.filaments || {}).length, "fiche", "fiches"), count(Object.keys(status.empty_spools || {}).length, "bobine vide", "bobines vides")].join(" · ")],
      ["Base matériau", materials.error ? "illisible : " + materials.error : count(materials.count || 0, "matériau", "matériaux")],
      ["Copie lue", store.source || "aucune (bibliothèque neuve)"],
      ["Décompte", counter.restored ? "repris au démarrage" : counter.refused ? "parti de zéro au démarrage" : "démarré à zéro"],
    ];
    return {
      title: "Réglages et sauvegarde",
      body: [
        pane("Réglages", null,
          h("div", { class: "spools-form" },
            sheetField(sheet, "low_g", "Seuil bobine basse (g)", numberInput(sheet, "low_g"), { hint: "sous ce reste net, la bobine est signalée basse" }),
            sheetField(sheet, "cut_loss_mm", "Perte à la coupe (mm)", numberInput(sheet, "cut_loss_mm"), { hint: "longueur coupée à chaque changement de filament, comptée sur la bobine dont elle vient (0 : ignorée)" })),
          errorOf(sheet, "settings"),
          h("div", { class: "spools-actions" }, btn("Enregistrer", () => saveSettings(sheet), { primary: true, busy: "settings", ref: "settings-save" }))),
        pane("Sauvegarde", null,
          note("L'export garde toute la bibliothèque et son journal dans un fichier ; l'import d'un export remplace la bibliothèque."),
          h("div", { class: "spools-actions" },
            btn("Exporter", () => exportLibrary(), { readOnlyOk: true, disabled: Boolean(store.locked), busy: "export", busyText: "Export…", ref: "export" }),
            btn("Importer un export…", () => { const node = app.refs["import-file"]; if (node) node.click(); }, { readOnlyOk: true, disabled: Boolean(store.locked) || k.printing, busy: "import", busyText: "Import…", ref: "import" }),
            h("input", { type: "file", ref: "import-file", accept: "application/json,.json", hidden: true, onchange: (event) => importLibrary(event.target) })),
          k.printing ? note("L'import attend la fin de l'impression.", "faint") : null,
          store.locked ? note("Stockage verrouillé : export et import attendent.", "warn") : null,
          errorOf(sheet, "backup")),
        pane("À propos", null, h("dl", { class: "spools-about" }, about.map(([term, value]) => [h("dt", null, term), h("dd", null, value)]))),
      ],
    };
  }
  async function saveSettings(sheet) {
    const numbers = readNumbers(sheet, ["low_g", "cut_loss_mm"], ["low_g", "cut_loss_mm"], "settings");
    if (!numbers) return false;
    const keys = Object.keys(numbers);
    if (!keys.length) return fail(sheet, "settings", "Rien n'a changé.");
    const reply = await act("settings", numbers, { busy: "settings", section: "settings", keys });
    if (reply) toast(Array.isArray(reply.result && reply.result.changed) && !reply.result.changed.length ? "Rien n'a changé." : "Réglages enregistrés.", true);
    return Boolean(reply);
  }
  async function exportLibrary() {
    if (app.busy) return;
    const sheet = app.sheet;
    app.busy = "export"; render();
    try {
      const payload = await call("GET", API + "export", null, TIMEOUTS.export);
      const exported = payload.result;
      if (!exported || exported.format !== EXPORT_FORMAT) throw failure("export illisible", 0);
      const name = "bobines-" + isoDay(clock()) + ".json";
      const url = URL.createObjectURL(new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.download = name; link.href = url;
      root.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      toast("Export téléchargé : " + name + ".", true);
    } catch (error) { report("Export impossible : " + (error.message || "erreur inconnue") + ".", "backup", sheet); }
    finally { app.busy = ""; render(); }
  }
  async function importLibrary(node) {
    const file = node && node.files && node.files[0];
    if (!file) return;
    const sheet = app.sheet;
    let parsed = null;
    try { parsed = JSON.parse(await file.text()); } catch (_) { parsed = null; } finally { node.value = ""; }
    if (!parsed || parsed.format !== EXPORT_FORMAT || !parsed.library || typeof parsed.library !== "object") {
      report("Ce fichier n'est pas un export des bobines K1 Control.", "backup", sheet); render(); return;
    }
    const size = (value) => Array.isArray(value) ? value.length : value && typeof value === "object" ? Object.keys(value).length : 0;
    const library = parsed.library;
    if (!ask("Remplacer toute la bibliothèque par cet export du " + dayLabel(parsed.exported) + " (" + count(size(library.spools), "bobine", "bobines") + ", "
      + count(size(library.filaments), "fiche", "fiches") + ", " + count(size(library.empty_spools), "bobine vide", "bobines vides") + ") ? Les écritures au CFS en attente ne sont pas reprises.")) return;
    const reply = await send("import", { document: parsed }, { busy: "import", timeout: TIMEOUTS.import, section: "backup" });
    if (reply) toast("Bibliothèque importée.", true);
  }
  refresh();
  timer = setInterval(tick, config.tickMs || TICK_MS);
  return { open, close, refresh, place, render, stop, state: app };
}
