"""Contracts of the live mesh editor that failed silently when first driven.

Everything pinned here was found by running the editor against the real
printer, and every one of them failed quietly rather than loudly:

  - the console payload is a dict keyed by the response template, so iterating
    it yields the key name and a save reported the word "response" where the
    backup file name belonged;
  - Klipper stores a profile as a tuple of tuples, so a freshly loaded matrix
    is immutable and no edit can be written into it;
  - the editor serves static files, and a served directory is a path traversal
    away from the rest of the machine.
"""

import importlib.util
import os

import pytest

PACKAGE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "packages", "k1-control-v1", "mesh-editor-live-v1")


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PACKAGE, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def server():
    return _load("kctrl_mesh_editor_server", "server.py")


@pytest.fixture(scope="module")
def mesh_module():
    spec = importlib.util.spec_from_file_location(
        "kctrl_mesh_for_editor",
        os.path.join(os.path.dirname(PACKAGE), "mesh-acquisition-v2",
                     "kctrl_mesh.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------------- console
def test_a_console_notification_carries_its_text_under_response(server):
    message = {"method": "notify_gcode_response",
               "params": {"response": "// K1 Control: 3 points changed"}}
    assert server.console_lines(message) == ["// K1 Control: 3 points changed"]


def test_a_list_payload_is_still_accepted(server):
    message = {"method": "notify_gcode_response",
               "params": ["// une ligne", "  // une autre  "]}
    assert server.console_lines(message) == ["// une ligne", "// une autre"]


@pytest.mark.parametrize("payload", [
    {"response": ""},
    {"response": "   "},
    {"response": "B:55.0 /55.0 T0:190.1 /190.0"},
    {"response": "T0:190.1 /190.0"},
    {},
    None,
    "pas un conteneur",
])
def test_temperature_chatter_and_empty_payloads_are_dropped(server, payload):
    # The temperature report repeats every second during a print and would
    # bury the three lines that matter under hundreds of its own.
    assert server.console_lines(
        {"method": "notify_gcode_response", "params": payload}) == []


def test_the_subscription_declares_a_response_template(server):
    # Klipper accepts a subscription without one and then never sends a single
    # line. The failure is silent, so it is pinned here rather than rediscovered.
    with open(os.path.join(PACKAGE, "server.py"), encoding="utf-8") as handle:
        source = handle.read()
    assert "response_template" in source
    assert '"method": "notify_gcode_response"' in source


# -------------------------------------------------------------- klipper error
def test_a_klipper_error_is_unwrapped_to_its_sentence(server):
    wrapped = {"message": '{"code":"key165", "msg": "K1 Control: refused"}'}
    assert server.Klippy._readable(wrapped) == "K1 Control: refused"


def test_a_plain_error_survives_unwrapping(server):
    assert server.Klippy._readable({"message": "boom"}) == "boom"


# ------------------------------------------------------------- immutable rows
def test_a_profile_stored_as_tuples_becomes_editable(mesh_module):
    # config.getlists parses the stored matrix into a tuple of tuples. Without
    # promotion, every edit would raise or, worse, be dropped.
    instance = object.__new__(mesh_module.KctrlMesh)

    class _Error(Exception):
        pass

    class _Gcode:
        error = _Error

    profile = {
        "points": ((0.0, 0.1), (0.2, 0.3)),
        "mesh_params": {"x_count": 2, "y_count": 2},
    }
    instance.gcode = _Gcode()
    instance._profiles = lambda: {"p": profile}

    prof, points = instance._live_profile("p")
    assert isinstance(points, list) and all(isinstance(r, list) for r in points)
    points[0][0] = 9.9
    # The promotion must land in the stored profile, not in a throwaway copy,
    # or a second edit would start again from the original values.
    assert prof["points"][0][0] == 9.9
    assert instance._live_profile("p")[1][0][0] == 9.9


def test_an_unknown_profile_is_refused(mesh_module):
    instance = object.__new__(mesh_module.KctrlMesh)

    class _Error(Exception):
        pass

    class _Gcode:
        error = _Error

    instance.gcode = _Gcode()
    instance._profiles = lambda: {}
    with pytest.raises(_Error):
        instance._live_profile("absent")


# --------------------------------------------------------------- static files
@pytest.mark.parametrize("name", [
    "../server.py",
    "..\\server.py",
    ".hidden",
    "www/app.mjs",
])
def test_a_traversing_static_path_is_refused(server, name):
    refused = []

    class _Probe(server.Handler):
        def __init__(self):  # bypass the socket plumbing of the base class
            pass

        def _fail(self, code, message):
            refused.append((code, message))

        def _send(self, *args, **kwargs):
            raise AssertionError("un fichier a ete servi: %s" % name)

    _Probe()._static(name)
    assert refused and refused[0][0] in (400, 404)


def test_the_expected_assets_are_served(server):
    for name in ("index.html", "styles.css", "app.mjs"):
        assert os.path.isfile(os.path.join(PACKAGE, "www", name))
    assert server.CONTENT_TYPES[".mjs"].startswith("text/javascript")


# ------------------------------------------------------------ nudge by a step
# There is no JavaScript runner on this project, so the page is pinned the same
# way the subscription template is: by reading the source. These four rules were
# all found by driving the editor by hand, and each one silently made the
# one-click correction impossible rather than failing visibly.
def _www(name):
    with open(os.path.join(PACKAGE, "www", name), encoding="utf-8") as handle:
        return handle.read()


def test_the_offered_steps_are_the_ones_asked_for():
    page = _www("index.html")
    for step in ("0.005", "0.01", "0.02", "0.05"):
        assert 'value="%s"' % step in page, step
    # 0.025 was a guess and it is not one of them; the coarse step is 0.05.
    assert 'value="0.025"' not in page


def test_the_finest_step_is_the_default():
    # Almost every correction read off a printed square is one or two
    # hundredths, so the safe step is the one selected on arrival.
    page = _www("index.html")
    assert 'value="0.005" selected' in page


def test_a_single_click_selects_without_opening_the_text_editor():
    # It used to open an input, which then swallowed the + key and typed a plus
    # sign into the value instead of nudging the point.
    source = _www("app.mjs")
    mousedown = source.split('cell.addEventListener("mousedown"', 1)[1]
    mousedown = mousedown.split("});", 1)[0]
    assert "beginEdit" not in mousedown
    assert "ui.grid.focus()" in mousedown
    assert 'cell.addEventListener("dblclick"' in source


def test_plus_and_minus_are_bound_and_never_seed_the_text_editor():
    source = _www("app.mjs")
    assert 'key === "+"' in source and 'key === "PageUp"' in source
    assert 'key === "-"' in source and 'key === "PageDown"' in source
    # The seed pattern must not claim + or -, or the branch that nudges would
    # be reachable only until someone reordered the handler.
    assert "/^[0-9.,]$/" in source


def test_a_burst_widens_the_step_by_whole_multiples():
    # Held keys repeat every ~30 ms; nudging one step each time would crawl. The
    # factors stay integers so a point keeps landing on the operator's round
    # values instead of drifting onto 0.0175.
    source = _www("app.mjs")
    assert "BURST_STEPS = [[16, 4], [6, 2]]" in source
    assert "BURST_WINDOW" in source
