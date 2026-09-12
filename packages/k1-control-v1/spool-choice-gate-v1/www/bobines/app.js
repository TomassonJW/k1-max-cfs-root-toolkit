// The Bobines page: what the printer publishes, drawn; what the operator
// clicks, sent back as one command. Served by the K1 Control gateway next to
// Mainsail, so Moonraker is on the same origin and needs no CORS.
//
// The page never decides anything. It shows the filaments the waiting file
// uses, the spools the CFS holds, and connects them one click at a time; the
// launch button only works once every used filament has a spool. The printer
// checks the same thing again in KCTRL_GATE_CONFIRM before starting.

import {
  NAMES, assign, buildModel, colourName, compatibility, completeness, elapsedLabel,
  isLight, mapParam, nextToConnect, normaliseHex, pendingKey, remainingLabel,
  shortName, summaryLine, usedFilaments,
} from "./logic.js";

const POLL_MS = 1000;
const TIMEOUT_MS = 4000;
const FILES_MS = 15000;

const ui = {
  main: document.getElementById("main"),
  status: document.getElementById("status"),
  stateLabel: document.getElementById("state-label"),
  offline: document.getElementById("offline"),
  toast: document.getElementById("toast"),
};

const app = {
  model: null,
  installed: true,
  online: false,
  key: "",
  seenAt: 0,
  assignments: {},
  active: null,
  busy: "",
  armed: false,
  armedTimer: 0,
  files: [],
  filesAt: 0,
  signature: "",
  toastTimer: 0,
};

// ------------------------------------------------------------------ network
async function call(method, path, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      cache: "no-store",
    });
    let payload = null;
    try { payload = await response.json(); } catch (_) { payload = null; }
    if (!response.ok) {
      const message = payload && payload.error && payload.error.message
        ? String(payload.error.message)
        : "HTTP " + response.status;
      throw new Error(cleanError(message));
    }
    return payload;
  } finally {
    clearTimeout(timer);
  }
}

// Moonraker forwards Klipper's refusal as "{'code': 400, 'message': '...'}"
// or as the raw text; keep only the sentence meant for a person.
function cleanError(text) {
  const found = /'message':\s*'((?:[^'\\]|\\.)*)'/.exec(text) || /"message":\s*"((?:[^"\\]|\\.)*)"/.exec(text);
  let message = found ? found[1] : text;
  message = message.replace(/^Error:\s*/i, "").replace(/\\n/g, " ").trim();
  return message || "erreur inconnue";
}

async function poll() {
  try {
    const payload = await call("GET", "/printer/objects/query?kctrl_print_gate&print_stats");
    const status = (payload && payload.result && payload.result.status) || {};
    app.installed = Object.prototype.hasOwnProperty.call(status, "kctrl_print_gate");
    app.model = buildModel(status);
    app.online = true;
  } catch (_) {
    app.online = false;
  }
  syncChoice();
  if (app.online && app.model && app.model.view === "idle" && Date.now() - app.filesAt > FILES_MS) {
    loadFiles();
  }
  render();
}

async function loadFiles() {
  app.filesAt = Date.now();
  try {
    const payload = await call("GET", "/server/files/list?root=gcodes");
    const list = Array.isArray(payload && payload.result) ? payload.result : [];
    app.files = list
      .filter((entry) => /\.gcode$/i.test(String(entry.path || "")))
      .sort((a, b) => Number(b.modified || 0) - Number(a.modified || 0))
      .slice(0, 8)
      .map((entry) => ({ path: String(entry.path), modified: Number(entry.modified || 0) }));
    render();
  } catch (_) {
    // The list is a convenience; the page stays usable without it.
  }
}

// The choice on screen belongs to one waiting file. A new file, or the same
// file held again, starts from nothing: the operator chooses every time.
function syncChoice() {
  const key = app.model ? pendingKey(app.model) : "";
  if (key === app.key) return;
  app.key = key;
  app.seenAt = Date.now() / 1000;
  app.assignments = {};
  app.active = key ? nextToConnect(app.model.filaments, {}) : null;
  app.busy = "";
  disarm();
  // A toast about the previous file must not hang over the new one.
  ui.toast.hidden = true;
}

// ------------------------------------------------------------------ actions
function pickFilament(logical) {
  app.active = app.active === logical ? null : logical;
  render();
}

function pickSpool(slot) {
  const model = app.model;
  if (!model || model.view !== "choice" || app.busy) return;
  let logical = app.active;
  if (!logical) logical = nextToConnect(model.filaments, app.assignments);
  if (!logical) {
    // Everything is connected: the click means "change the filament that
    // has this spool", so hand that filament back to the operator.
    const owner = Object.keys(app.assignments).find((key) => app.assignments[key] === slot);
    if (owner) app.active = owner;
    render();
    return;
  }
  app.assignments = assign(app.assignments, logical, slot);
  const next = nextToConnect(model.filaments, app.assignments);
  app.active = next || (app.assignments[logical] ? logical : null);
  disarm();
  render();
}

async function launch() {
  const model = app.model;
  if (!model || model.view !== "choice" || app.busy) return;
  const check = completeness(model.filaments, app.assignments);
  if (!check.complete) {
    toast("Il manque une bobine pour : " + check.missing.join(", "), false);
    return;
  }
  const script = 'KCTRL_GATE_CONFIRM MAP=' + mapParam(app.assignments)
    + ' FILE="' + model.name.replace(/"/g, "") + '"';
  app.busy = "launch";
  render();
  try {
    await call("POST", "/printer/gcode/script", { script });
    toast("Impression lancée : " + shortName(model.name), true);
    app.busy = "";
    await poll();
  } catch (error) {
    app.busy = "";
    toast(String(error.message || error), false);
    await poll();
  }
}

function arm() {
  app.armed = true;
  clearTimeout(app.armedTimer);
  app.armedTimer = setTimeout(() => { app.armed = false; render(); }, 5000);
  render();
}

function disarm() {
  app.armed = false;
  clearTimeout(app.armedTimer);
}

async function cancel() {
  const model = app.model;
  if (!model || model.view !== "choice" || app.busy) return;
  if (!app.armed) { arm(); return; }
  disarm();
  app.busy = "cancel";
  render();
  try {
    await call("POST", "/printer/gcode/script", { script: "KCTRL_GATE_CANCEL" });
    toast("Impression abandonnée, rien n'a chauffé.", true);
  } catch (error) {
    toast(String(error.message || error), false);
  }
  app.busy = "";
  await poll();
}

async function startFile(path) {
  if (app.busy) return;
  app.busy = "start:" + path;
  render();
  try {
    await call("POST", "/printer/print/start", { filename: path });
  } catch (error) {
    toast(String(error.message || error), false);
  }
  app.busy = "";
  await poll();
}

// ------------------------------------------------------------------ helpers
function h(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "style") node.style.cssText = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key === "disabled" || key === "hidden") node[key] = Boolean(value);
    else node.setAttribute(key, String(value));
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

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

function toast(message, ok) {
  ui.toast.textContent = message;
  ui.toast.className = "toast" + (ok ? " is-ok" : "");
  ui.toast.hidden = false;
  clearTimeout(app.toastTimer);
  app.toastTimer = setTimeout(() => { ui.toast.hidden = true; }, ok ? 4000 : 8000);
}

function stateWord(model) {
  if (!app.online) return "Hors ligne";
  if (!app.installed) return "Porte absente";
  if (!model) return "Connexion…";
  if (model.state === "printing") return "Impression en cours";
  if (model.state === "paused") return "En pause";
  if (model.pending) return "Choix en attente";
  if (!model.wrapped) return "Porte inactive";
  if (model.state === "complete") return "Impression terminée";
  if (model.state === "cancelled") return "Impression annulée";
  if (model.state === "error") return "Erreur d'impression";
  return "Au repos";
}

function statusClass(model) {
  if (!app.online) return "is-offline";
  if (!model) return "";
  if (model.state === "printing") return "is-printing";
  if (model.state === "paused") return "is-paused";
  if (model.pending) return "is-choice";
  return "is-idle";
}

function dateLabel(seconds) {
  if (!seconds) return "";
  const date = new Date(seconds * 1000);
  return date.toLocaleDateString("fr-FR", { day: "numeric", month: "short" })
    + " " + date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

function elapsed(model) {
  const now = Date.now() / 1000;
  const since = model.since && Math.abs(now - model.since) < 86400 ? model.since : app.seenAt;
  return elapsedLabel(since, now);
}

// ------------------------------------------------------------------- render
function render() {
  const model = app.model;
  ui.status.className = "status " + statusClass(model);
  ui.stateLabel.textContent = stateWord(model);
  ui.offline.hidden = app.online;

  const signature = JSON.stringify([
    model, app.installed, app.online, app.assignments, app.active, app.busy,
    app.armed, app.files,
  ]);
  if (signature === app.signature) {
    const live = document.getElementById("elapsed");
    if (live && model && model.pending) live.textContent = elapsed(model);
    return;
  }
  app.signature = signature;

  const main = ui.main;
  main.replaceChildren();
  if (!model) {
    main.append(hero("Connexion", "Lecture de l'imprimante…", null, "is-quiet"));
    return;
  }
  if (!app.installed) {
    main.append(hero(
      "Porte absente",
      "Klipper ne publie pas la porte de départ",
      "La section [kctrl_print_gate] n'est pas chargée : soit le module n'est pas installé, "
      + "soit le service Klipper n'a pas été relancé depuis. Les impressions partent sans choix.",
      "is-quiet"));
    return;
  }
  if (model.view === "choice") renderChoice(model);
  else if (model.view === "printing") renderPrinting(model);
  else renderIdle(model);
}

function hero(eyebrow, title, hint, extra, meta) {
  return h("section", { class: "hero " + (extra || "") },
    h("p", { class: "eyebrow" }, eyebrow),
    h("h2", null, title),
    hint ? h("p", { class: "hint" }, hint) : null,
    meta ? h("p", { class: "meta" }, meta) : null);
}

function renderChoice(model) {
  const used = usedFilaments(model.filaments);
  const check = completeness(model.filaments, app.assignments);
  const activeEntry = model.filaments.find((entry) => entry.logical === app.active) || null;
  const heroNode = hero(
    check.complete ? "Tout est raccordé" : "À vous de choisir",
    shortName(model.name),
    check.complete
      ? "Chaque filament a sa bobine. Vérifiez d'un coup d'œil, puis lancez : la tête chauffe seulement après."
      : (used.length === 1
        ? "Ce fichier utilise un filament. Touchez la bobine du CFS qui doit l'imprimer. Rien ne chauffe avant que vous lanciez."
        : "Ce fichier utilise " + used.length + " filaments. Touchez un filament, puis la bobine du CFS qui doit l'imprimer. Rien ne chauffe avant que vous lanciez."),
    check.complete ? "is-ok" : "");
  heroNode.append(h("p", { class: "meta" },
    h("span", { id: "elapsed" }, "en attente " + elapsed(model)),
    model.note ? " · " + model.note : ""));
  ui.main.append(heroNode);

  // Filaments of the file.
  const list = h("div", { class: "filament-list" });
  for (const entry of model.filaments) {
    const slotName = app.assignments[entry.logical] || "";
    const slot = slotName ? model.slots.find((item) => item.name === slotName) : null;
    const isActive = entry.logical === app.active && entry.used;
    const classes = ["filament"];
    if (isActive) classes.push("is-active");
    if (slotName) classes.push("is-done");
    if (!entry.used) classes.push("is-unused");
    const colour = normaliseHex(entry.colour);
    let link;
    if (!entry.used) {
      link = h("span", { class: "note is-faint" }, "déclaré dans le fichier, jamais utilisé : pas de bobine à choisir");
    } else if (slot) {
      const fit = compatibility(entry, slot);
      link = [
        h("span", { class: "chip" }, swatch(slot.colour, "is-mini"),
          h("span", { class: "mono" }, slot.name), " ", slot.type || "?"),
        h("span", { class: "note " + (fit.exact ? "is-ok" : fit.level === "type" ? "is-warn" : "") },
          fit.exact ? "identique au fichier" : fit.label),
      ];
    } else if (isActive) {
      link = h("span", { class: "note is-accent" }, "→ touchez une bobine à droite");
    } else {
      link = h("span", { class: "note" }, "pas encore de bobine");
    }
    list.append(h("button", {
      class: classes.join(" "),
      type: "button",
      disabled: !entry.used || Boolean(app.busy),
      "aria-pressed": isActive ? "true" : "false",
      onclick: () => pickFilament(entry.logical),
    },
      swatch(colour, "is-big"),
      h("div", null,
        h("div", { class: "title" }, "Filament " + (entry.index + 1),
          h("span", { class: "tag" }, entry.logical)),
        h("div", { class: "sub" },
          (entry.type || "matière inconnue") + " · "
          + (colour ? colourName(colour) + " #" + colour : "sans couleur")
          + (entry.name ? " · " + entry.name : "")),
        h("div", { class: "link" }, link))));
  }
  ui.main.append(h("section", { class: "pane pane-filaments" },
    h("h3", null, h("span", null, h("span", { class: "step" }, "1"), "Les filaments du fichier"),
      h("span", { class: "count" }, used.length + " utilisé" + (used.length > 1 ? "s" : "")
        + (model.declaredCount > used.length ? ", " + model.declaredCount + " déclarés" : ""))),
    list));

  // Spools of the CFS.
  ui.main.append(h("section", { class: "pane pane-spools" },
    h("h3", null, h("span", null, h("span", { class: "step" }, "2"), "Les bobines du CFS"),
      h("span", { class: "count" }, activeEntry
        ? "pour le filament " + (activeEntry.index + 1)
        : (check.complete ? "touchez une bobine prise pour la changer" : ""))),
    spoolGrid(model, activeEntry, true, app.assignments)));

  // Launch.
  const summary = summaryLine(model.filaments, app.assignments);
  ui.main.append(h("section", { class: "actions" },
    h("div", { class: "summary " + (check.complete ? "is-ready" : "") }, summary),
    h("div", { class: "buttons" },
      h("button", {
        class: "btn is-danger",
        type: "button",
        disabled: Boolean(app.busy),
        onclick: cancel,
      }, app.busy === "cancel" ? [h("span", { class: "spinner" }), "Abandon…"]
        : (app.armed ? "Sûr ? Confirmer l'abandon" : "Abandonner cette impression")),
      h("button", {
        class: "btn is-primary",
        type: "button",
        disabled: !check.complete || Boolean(app.busy),
        onclick: launch,
      }, app.busy === "launch" ? [h("span", { class: "spinner" }), "Lancement…"] : "Lancer l'impression"))));
}

// `owners` maps a filament to the spool it holds: the operator's choice
// while choosing, the confirmed map of a print launched from here, nothing
// otherwise, so a badge never shows a pairing that is not the current one.
// The number a person reads on the filament card: its rank in the file, or
// the rank of its logical slot when the file's list is no longer there.
function filamentNumber(logical, entry) {
  if (entry) return entry.index + 1;
  const rank = NAMES.indexOf(logical);
  return rank >= 0 ? rank + 1 : logical;
}

function spoolGrid(model, activeEntry, clickable, owners) {
  const grid = h("div", { class: "spool-grid" });
  if (model.units.length === 0) {
    grid.append(h("p", { class: "empty" }, "Aucune unité CFS connectée."));
    return grid;
  }
  const taken = {};
  for (const logical of Object.keys(owners || {})) taken[owners[logical]] = logical;
  for (const unit of model.units) {
    grid.append(h("div", { class: "unit-label" }, "CFS " + unit.slice(1)));
    for (const slot of model.slots.filter((item) => item.name.startsWith(unit))) {
      const owner = taken[slot.name];
      const ownerEntry = owner ? model.filaments.find((entry) => entry.logical === owner) : null;
      const fit = activeEntry && slot.loaded ? compatibility(activeEntry, slot) : null;
      const classes = ["spool"];
      if (!slot.loaded) classes.push("is-empty");
      if (!clickable) classes.push("is-static");
      if (owner) classes.push("is-taken");
      if (fit && fit.exact) classes.push("is-exact");
      const colour = normaliseHex(slot.colour);
      grid.append(h("button", {
        class: classes.join(" "),
        type: "button",
        disabled: !clickable || !slot.loaded || Boolean(app.busy),
        onclick: clickable ? () => pickSpool(slot.name) : null,
      },
        owner ? h("span", { class: "badge" }, "filament " + filamentNumber(owner, ownerEntry)) : null,
        fit && fit.exact && !owner ? h("span", { class: "badge is-exact" }, "identique") : null,
        h("span", { class: "slot-name" }, slot.name),
        swatch(colour, "is-big"),
        slot.loaded
          ? [
            h("span", { class: "kind" }, slot.type || "matière ?"),
            h("span", { class: "colour" }, colour ? colourName(colour) : "sans couleur",
              colour ? [h("br"), h("span", { class: "hex" }, "#" + colour)] : null),
            remainingLabel(slot.remain) ? h("span", { class: "remain" }, remainingLabel(slot.remain)) : null,
            fit ? h("span", { class: "fit is-" + fit.level }, fit.label) : null,
          ]
          : h("span", { class: "kind" }, "vide")));
    }
  }
  return grid;
}

function renderPrinting(model) {
  const paused = model.state === "paused";
  const fromPage = model.confirmedName && model.printingName
    && (model.confirmedName === model.printingName
      || shortName(model.confirmedName) === shortName(model.printingName));
  const heroNode = hero(
    paused ? "En pause" : "Impression en cours",
    shortName(model.printingName || model.confirmedName || "impression"),
    fromPage
      ? "Lancée depuis cette page avec les bobines ci-dessous."
      : "Lancée sans passer par cette page (reprise après coupure, ou porte inactive).",
    paused ? "" : "is-ok");
  ui.main.append(heroNode);
  ui.main.append(h("section", { class: "pane pane-spools is-wide" },
    h("h3", null, h("span", null, "Les bobines du CFS")),
    spoolGrid(model, null, false, fromPage ? model.confirmedMap : {})));
}

function renderIdle(model) {
  const heroNode = hero(
    model.wrapped ? "Rien en attente" : "Porte inactive",
    model.wrapped ? "Aucune impression n'attend de choix" : "Klipper n'a pas pris la main sur le départ",
    model.wrapped
      ? "Lancez un fichier depuis Mainsail, l'écran ou Creality Print : il s'arrêtera ici, sans chauffer, jusqu'à ce que vous ayez raccordé ses filaments."
      : "Le module est chargé mais SDCARD_PRINT_FILE n'a pas été repris. Relancez le service Klipper.",
    "is-quiet",
    model.last ? "dernier événement : " + model.last : "");
  ui.main.append(heroNode);
  ui.main.append(h("section", { class: "pane pane-spools is-wide" },
    h("h3", null, h("span", null, "Les bobines du CFS")),
    spoolGrid(model, null, false, {})));
  const list = h("div", { class: "file-list" });
  if (app.files.length === 0) {
    list.append(h("p", { class: "empty" }, "Liste des fichiers en cours de lecture…"));
  }
  for (const file of app.files) {
    const busy = app.busy === "start:" + file.path;
    list.append(h("div", { class: "file-row" },
      h("div", null, h("div", { class: "name" }, file.path),
        h("div", { class: "when" }, dateLabel(file.modified))),
      h("button", {
        class: "btn is-small",
        type: "button",
        disabled: Boolean(app.busy) || !model.wrapped,
        onclick: () => startFile(file.path),
      }, busy ? [h("span", { class: "spinner" }), "Envoi…"] : "Choisir ses bobines")));
  }
  ui.main.append(h("section", { class: "pane pane-files" },
    h("h3", null, h("span", null, "Ou partez d'ici"),
      h("span", { class: "count" }, "les 8 derniers fichiers")),
    list));
}

// --------------------------------------------------------------------- boot
poll();
setInterval(poll, POLL_MS);
