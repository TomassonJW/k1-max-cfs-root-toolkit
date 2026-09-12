"""La page Bobines : ce qui doit être vrai des fichiers servis par la passerelle.

Pas de ressource extérieure (la page tourne sur un réseau privé sans
internet), les commandes et les routes exactes que le module publie, le
bloc nginx qui la sert, et les tests node de sa partie pure quand node est
là (ADR-063, document 78).
"""

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


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


@pytest.mark.parametrize("name", ["index.html", "styles.css", "app.js", "logic.js"])
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
    assert 'id="main"' in text and 'id="toast"' in text and 'id="offline"' in text


def test_app_talks_to_moonraker_with_the_exact_routes_and_commands():
    text = read(PAGE, "app.js")
    assert '"/printer/objects/query?kctrl_print_gate&print_stats"' in text
    assert '"/printer/gcode/script"' in text
    assert '"/printer/print/start"' in text
    assert '"/server/files/list?root=gcodes"' in text
    assert "KCTRL_GATE_CONFIRM MAP=" in text
    assert '"KCTRL_GATE_CANCEL"' in text
    assert 'from "./logic.js"' in text


def test_app_never_connects_a_spool_on_its_own():
    text = read(PAGE, "app.js")
    # A new pending file starts from an empty choice; only a click assigns.
    assert "app.assignments = {};" in text
    assert text.count("assign(app.assignments") == 1
    assert "pickSpool" in text.split("assign(app.assignments")[0].rsplit("function ", 1)[1]


def test_the_launch_button_is_disabled_until_every_used_filament_has_a_spool():
    text = read(PAGE, "app.js")
    assert "disabled: !check.complete || Boolean(app.busy)" in text


def test_the_package_is_an_es_module():
    assert '"type": "module"' in read(PAGE, "package.json")


def test_the_nginx_block_uses_root_and_sits_before_the_catch_all():
    snippet = read(PACKAGE, "nginx-location.conf")
    assert "location /bobines/ {" in snippet
    assert "root /usr/data/k1-control-v1/current/www;" in snippet
    assert not [line for line in snippet.splitlines()
                if "alias" in line and not line.strip().startswith("#")]
    gateway = read(GATEWAY)
    assert snippet.strip() in gateway
    assert gateway.index("location /bobines/") < gateway.index("location / {")


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
