// The Bobines choice as a window inside Mainsail. Loaded by the one script
// tag that mainsail_overlay_patch.py adds to Mainsail's index.html, it draws
// nothing until Klipper holds a start, then covers Mainsail with the very
// same interface as /bobines/ and gets out of the way once the print left
// or was dropped. "Réduire" (or Escape, or a click beside the window) folds
// it to a pill at the bottom right for this file only; the pill brings it
// back, and a new held file opens it again.
//
// Shadow DOM: Mainsail's styles never reach the window and the window's never
// reach Mainsail. Everything is fetched from /bobines/ on the same origin.
import { mount } from "./bobines.js";

const POLL_MS = 750;

const host = document.createElement("div");
host.id = "kctrl-bobines";
host.dataset.mode = "hidden";
const shadow = host.attachShadow({ mode: "open" });

const stylesheet = document.createElement("link");
stylesheet.rel = "stylesheet";
stylesheet.href = new URL("./styles.css", import.meta.url).href;
shadow.append(stylesheet);

const frame = document.createElement("div");
frame.innerHTML = `
  <div class="overlay-backdrop" id="backdrop" hidden>
    <div class="overlay-panel" id="panel" role="dialog" aria-modal="true"
         aria-labelledby="overlay-title" tabindex="-1">
      <div class="bobines">
        <header class="top">
          <div class="brand">
            <span class="logo" aria-hidden="true"></span>
            <div>
              <h1 id="overlay-title">Bobines</h1>
              <p class="tagline">Le fichier d'un côté, le CFS de l'autre. Raccordez, puis lancez.</p>
            </div>
          </div>
          <div class="top-right">
            <div class="status" id="status" aria-live="polite">
              <span class="dot" id="dot"></span>
              <span id="state-label">Connexion…</span>
            </div>
            <button class="btn is-small is-ghost" id="minimise" type="button"
                    title="Mettre de côté, l'impression reste en attente (Échap)">Réduire</button>
          </div>
        </header>
        <div class="banner" id="offline" hidden>Imprimante injoignable. Nouvelle tentative en cours…</div>
        <main id="main" class="main"></main>
        <div class="toast" id="toast" role="status" hidden></div>
      </div>
    </div>
  </div>
  <button class="pill" id="pill" type="button" hidden>
    <span class="dot" aria-hidden="true"></span>
    Une impression attend son choix de bobines · Ouvrir
  </button>
`;
shadow.append(...frame.childNodes);

const backdrop = shadow.getElementById("backdrop");
const panel = shadow.getElementById("panel");
const pill = shadow.getElementById("pill");

function show(mode) {
  host.dataset.mode = mode;
  const open = mode === "choice" || mode === "launched";
  backdrop.hidden = !open;
  pill.hidden = mode !== "minimised";
  if (mode === "choice") {
    panel.scrollTop = 0;
    panel.focus({ preventScroll: true });
  }
}

const api = mount(shadow, { overlay: true, pollMs: POLL_MS, onMode: show });

shadow.getElementById("minimise").addEventListener("click", () => api.minimise());
pill.addEventListener("click", () => api.restore());
backdrop.addEventListener("click", (event) => {
  if (event.target === backdrop) api.minimise();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && host.dataset.mode === "choice") api.minimise();
});

document.body.append(host);
