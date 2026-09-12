"""La page Bobines et la fenêtre qu'elle ouvre dans Mainsail : ce qui doit
être vrai des fichiers servis par la passerelle.

Pas de ressource extérieure (la page tourne sur un réseau privé sans
internet), les commandes et les routes exactes que le module publie, une
seule interface montée deux fois (page et fenêtre), la balise ajoutée à
l'index de Mainsail, les blocs nginx qui servent le tout, et les tests node
de la partie pure quand node est là (ADR-063, document 78).
"""

import importlib.util
import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "packages", "k1-control-v1", "spool-choice-gate-v1")
PAGE = os.path.join(PACKAGE, "www", "bobines")
GATEWAY = os.path.join(ROOT, "packages", "k1-control-v1", "gateway-private-lan-no-auth-v1",
                       "nginx.conf")
PAGE_FILES = ["index.html", "styles.css", "app.js", "bobines.js", "overlay.js", "logic.js"]

# Mainsail's index.html as installed on the machine, trimmed to what matters.
MAINSAIL_INDEX = (
    "<!doctype html>\n<html lang=\"en\">\n    <head>\n        <title>Mainsail</title>\n"
    "      <script type=\"module\" crossorigin src=\"/assets/index-BtmDxkKX.js\"></script>\n"
    "    </head>\n    <body style=\"background-color: #121212\">\n"
    "        <div id=\"app\"></div>\n    </body>\n</html>\n")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


def load_patch():
    spec = importlib.util.spec_from_file_location(
        "mainsail_overlay_patch", os.path.join(PACKAGE, "mainsail_overlay_patch.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", PAGE_FILES)
def test_the_page_loads_nothing_from_outside(name):
    text = read(PAGE, name)
    # The favicon is an inline SVG data URI; its xmlns is a name, not a fetch.
    text = re.sub(r'href="data:[^"]*"', 'href="data:"', text)
    assert "https://" not in text
    assert "http://" not in text
    for found in re.findall(r'(?:src|href)="([^"]+)"', text):
        assert not found.startswith("/") and "//" not in found


def test_index_wires_the_stylesheet_and_the_module():
    text = read(PAGE, "index.html")
    assert '<html lang="fr">' in text
    assert '<link rel="stylesheet" href="styles.css">' in text
    assert '<script type="module" src="app.js"></script>' in text
    assert '<body class="bobines">' in text
    assert 'id="main"' in text and 'id="toast"' in text and 'id="offline"' in text


def test_the_page_and_the_window_mount_the_same_interface():
    app = read(PAGE, "app.js")
    overlay = read(PAGE, "overlay.js")
    shared = read(PAGE, "bobines.js")
    assert 'import { mount } from "./bobines.js";' in app
    assert "mount(document, { overlay: false });" in app
    assert 'import { mount } from "./bobines.js";' in overlay
    assert "overlay: true" in overlay
    assert "export function mount(root, options)" in shared
    # The window carries the same skeleton the page has, plus its own two
    # controls; the stylesheet is the page's, addressed relative to the module.
    for marker in ('id="main"', 'id="toast"', 'id="offline"', 'id="status"',
                   'id="state-label"', 'id="minimise"', 'id="pill"', 'class="bobines"'):
        assert marker in overlay
    assert 'new URL("./styles.css", import.meta.url)' in overlay
    assert "attachShadow" in overlay


def test_the_window_shows_itself_and_never_the_file_list():
    shared = read(PAGE, "bobines.js")
    overlay = read(PAGE, "overlay.js")
    assert "overlayMode(app, model, Date.now())" in shared
    assert "onMode(mode, model)" in shared
    # The idle file list is the page's; the window has nothing to show idle.
    assert "if (!overlay && app.online && app.model && app.model.view === \"idle\"" in shared
    assert 'if (event.key === "Escape"' in overlay
    assert "document.body.append(host)" in overlay


def test_the_stylesheet_serves_the_page_and_the_shadow_root():
    css = read(PAGE, "styles.css")
    assert ":root, :host {" in css
    assert "[hidden] { display: none !important; }" in css
    assert ".overlay-backdrop {" in css and ".overlay-panel {" in css and ".pill {" in css
    # Typography on the wrapper, not on body: body is Mainsail's in the window.
    assert re.search(r"\.bobines \{[^}]*font:", css)
    assert not re.search(r"html, body \{[^}]*font:", css)


def test_app_talks_to_moonraker_with_the_exact_routes_and_commands():
    text = read(PAGE, "bobines.js")
    assert '"/printer/objects/query?kctrl_print_gate&print_stats"' in text
    assert '"/printer/gcode/script"' in text
    assert '"/printer/print/start"' in text
    assert '"/server/files/list?root=gcodes"' in text
    assert "KCTRL_GATE_CONFIRM MAP=" in text
    assert '"KCTRL_GATE_CANCEL"' in text
    assert 'from "./logic.js"' in text


def test_app_never_connects_a_spool_on_its_own():
    text = read(PAGE, "bobines.js")
    # A new pending file starts from an empty choice; only a click assigns.
    assert "app.assignments = {};" in text
    assert text.count("assign(app.assignments") == 1
    assert "pickSpool" in text.split("assign(app.assignments")[0].rsplit("function ", 1)[1]


def test_the_launch_button_is_disabled_until_every_used_filament_has_a_spool():
    text = read(PAGE, "bobines.js")
    assert "disabled: !check.complete || Boolean(app.busy)" in text


def test_the_package_is_an_es_module():
    assert '"type": "module"' in read(PAGE, "package.json")


def test_the_mainsail_patch_adds_one_tag_before_body_end_and_nothing_else(tmp_path):
    patch = load_patch()
    path = tmp_path / "index.html"
    path.write_text(MAINSAIL_INDEX, encoding="utf-8")
    changed, message = patch.apply(str(path))
    assert changed and "balise ajoutee" in message
    after = path.read_text(encoding="utf-8")
    assert after.count(patch.TAG) == 1
    assert after.replace(patch.LINE, "") == MAINSAIL_INDEX
    assert after.index(patch.TAG) < after.index("</body>")
    assert patch.TAG == '<script type="module" src="/bobines/overlay.js"></script>'
    backups = [name for name in os.listdir(str(tmp_path)) if name.startswith("index.html.bak-")]
    assert len(backups) == 1
    assert (tmp_path / backups[0]).read_text(encoding="utf-8") == MAINSAIL_INDEX


def test_the_mainsail_patch_is_idempotent_and_reversible(tmp_path):
    patch = load_patch()
    path = tmp_path / "index.html"
    path.write_text(MAINSAIL_INDEX, encoding="utf-8")
    patch.apply(str(path))
    changed, message = patch.apply(str(path))
    assert not changed and "deja en place" in message
    changed, message = patch.apply(str(path), removing=True)
    assert changed and "balise retiree" in message
    assert path.read_text(encoding="utf-8") == MAINSAIL_INDEX
    changed, _ = patch.apply(str(path), removing=True)
    assert not changed
    assert len([n for n in os.listdir(str(tmp_path)) if n.startswith("index.html.bak-")]) == 2


def test_the_mainsail_patch_refuses_a_file_without_body(tmp_path):
    patch = load_patch()
    path = tmp_path / "index.html"
    path.write_text("<html><head></head></html>", encoding="utf-8")
    changed, message = patch.apply(str(path))
    assert not changed and "pas de </body>" in message
    assert path.read_text(encoding="utf-8") == "<html><head></head></html>"


def test_the_nginx_blocks_use_root_keep_the_headers_and_sit_before_the_catch_all():
    snippet = read(PACKAGE, "nginx-location.conf")
    assert "location = /bobines {" in snippet
    assert "location /bobines/ {" in snippet
    assert "location = /index.html {" in snippet
    assert "root /usr/data/k1-control-v1/current/www;" in snippet
    assert not [line for line in snippet.splitlines()
                if "alias" in line and not line.strip().startswith("#")]
    # A location with its own add_header loses the server's: repeat them.
    for block in snippet.split("location ")[2:]:
        if "add_header" in block:
            for header in ("X-Content-Type-Options nosniff always",
                           "X-Frame-Options SAMEORIGIN always",
                           "Referrer-Policy no-referrer always",
                           'Cache-Control "no-store" always'):
                assert header in block, (header, block)
    gateway = read(GATEWAY)
    assert snippet.strip() in gateway
    assert gateway.index("location /bobines/") < gateway.index("location / {")
    assert gateway.index("location = /index.html") < gateway.index("location / {")


def test_the_gate_module_is_the_one_the_page_reads():
    module = read(PACKAGE, "kctrl_print_gate.py")
    app = read(PAGE, "logic.js")
    for key in ("wrapped", "pending", "filaments", "slots", "units", "used_count",
                "declared_count", "confirmed_name", "confirmed_map", "since", "note"):
        assert '"%s"' % key in module
        assert key in app


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
def test_the_pure_logic_passes_under_node():
    result = subprocess.run(
        ["node", "--test", os.path.join(PACKAGE, "logic.test.mjs")],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "# fail 0" in result.stdout
