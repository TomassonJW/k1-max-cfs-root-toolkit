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
import json
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


def test_a_macro_refusal_keeps_its_newline_and_is_still_unwrapped(server):
    # Releve sur la machine : le message porte un vrai saut de ligne, que le
    # parseur strict refuse. L'operateur recevait alors l'enveloppe entiere,
    # code et valeurs compris, au lieu de la phrase qui dit ce qui ne va pas.
    sentence = 'K1 Control: PROFILE is required' + chr(10)
    wrapped = {'message': json.dumps(
        {'code': 'key165', 'msg': sentence, 'values': []}).replace(
            chr(92) + 'n', chr(10))}
    assert server.Klippy._readable(wrapped) == sentence.strip()


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


# ----------------------------------------------------- selecting several points
def test_shift_and_ctrl_build_a_selection():
    # Correcting an edge means correcting eleven points, and doing it one at a
    # time is how a correction ends up uneven.
    source = _www("app.mjs")
    mousedown = source.split('cell.addEventListener("mousedown"', 1)[1]
    mousedown = mousedown.split("});", 1)[0]
    assert "event.shiftKey" in mousedown and "extend(i, j)" in mousedown
    assert "event.ctrlKey || event.metaKey" in mousedown and "toggle(i, j)" in mousedown


def test_a_group_correction_is_all_or_nothing():
    # Half a moved edge looks corrected on the surface and the point left behind
    # is invisible until it prints, so commit() refuses before it writes.
    source = _www("app.mjs")
    body = source.split("function commit(changes)", 1)[1].split("\nfunction ", 1)[0]
    refusal = body.index("refusal(i, j, value)")
    first_write = body.index("state.points[j][i] = value")
    assert refusal < first_write, "la validation doit precéder toute écriture"
    assert "return false" in body[refusal:first_write]


def test_the_reference_point_is_skipped_not_blocking():
    # X150 Y150 is the profile's zero (ADR-046) and sits inside any wide
    # rectangle. Refusing the whole group because of it would make correcting a
    # full plate impossible.
    source = _www("app.mjs")
    body = source.split("function movable()", 1)[1].split("\nfunction ", 1)[0]
    assert "isReference" in body and "filter" in body


def test_one_group_move_undoes_in_one_keystroke():
    # Undoing forty points one by one would be worse than not offering the group
    # move at all, so the undo stack holds groups rather than single points.
    source = _www("app.mjs")
    body = source.split("function undo()", 1)[1].split("\nfunction ", 1)[0]
    assert "const group = state.undo.pop()" in body
    assert "for (const { i, j, value } of group)" in body


def test_a_typed_value_never_lands_on_a_whole_selection():
    # A typed value is absolute. Writing the same one into forty points would
    # flatten the relief the probe measured.
    source = _www("app.mjs")
    body = source.split("function beginEdit(", 1)[1].split("\nfunction ", 1)[0]
    assert "state.marks.size > 1" in body
    assert "uniquement" in body


def test_the_surface_pick_accounts_for_letterboxing():
    # The canvas is object-fit: contain, so scaling by its box alone would
    # offset every pick once the drawing is letterboxed.
    source = _www("app.mjs")
    assert "Math.min(\n    rect.width / ui.surface.width" in source
    assert "object-fit: contain" in _www("styles.css")


def test_the_surface_height_is_not_a_viewport_unit():
    # A vh resolves to zero outside a real window and the surface collapsed to
    # one pixel. A floor in pixels cannot do that.
    import re
    style = _www("styles.css")
    canvas = style.split("\ncanvas {", 1)[1].split("}", 1)[0]
    declarations = re.sub(r"/\*.*?\*/", "", canvas, flags=re.S)
    assert "vh" not in declarations
    assert "min-height" in declarations


# ------------------------------------------------------------------ Z du profil
# The accepted Z is per profile and START_PRINT refuses to start without it. It
# was only writable from a console, so the value found by eye during a first
# layer had to be transcribed by hand or was simply lost. These pin the path the
# editor opens: read what is stored, read what the machine applies right now,
# and write through KCTRL_Z_SAVE - never around it.
class _Probe:
    """Stands in for a handler: the two methods under test only need `klippy`.

    They are called unbound, so none of the socket plumbing of the HTTP base
    class has to exist here.
    """

    def __init__(self, server, status, script=None):
        probe = self

        class _Klippy:
            def query(self, objects):
                probe.queried = objects
                return status

            def script(self, command, timeout=120.0):
                probe.commands.append(command)
                return list(script or [])

        self.commands = []
        self.queried = None
        self.klippy = _Klippy()
        # _zsave re-reads the state to answer with it; the real method does it.
        self._state = lambda: server.Handler._state(self)


def _status(z_saved=-0.04, live=0.0, profiles=("k1_p001_t055_r001_n11x11",)):
    return {
        "bed_mesh": {"profiles": {name: {} for name in profiles},
                     "profile_name": profiles[0] if profiles else None},
        "print_stats": {"state": "standby"},
        "webhooks": {"state": "ready"},
        "save_variables": {"variables": {
            "z_k1_p001_t055_r001_n11x11": z_saved, "autre": 1}},
        "gcode_move": {"homing_origin": [0.0, 0.0, live, 0.0]},
    }


def test_the_state_carries_the_stored_z_and_the_one_in_force(server):
    handler = _Probe(server, _status(z_saved=-0.04, live=0.06))
    state = server.Handler._state(handler)
    assert state["z_offsets"] == {"k1_p001_t055_r001_n11x11": -0.04}
    # What the operator dialled in from Fluidd during the first layer. Without
    # it, that number dies with the print.
    assert state["live_z"] == 0.06
    assert "gcode_move" in handler.queried


def test_saving_a_z_goes_through_the_macro_and_nothing_else(server):
    handler = _Probe(server, _status(), script=["// K1 Control: Z 0.0000 saved"])
    result = server.Handler._zsave(
        handler, {"profile": "k1_p001_t055_r001_n11x11", "z": 0})
    assert handler.commands == ["KCTRL_Z_SAVE PROFILE=k1_p001_t055_r001_n11x11 Z=0.0000"]
    assert result["saved"] == 0
    assert result["messages"] == ["// K1 Control: Z 0.0000 saved"]
    # SAVE_VARIABLE is the macro's business. The editor never writes the file.
    assert "SAVE_VARIABLE" not in "".join(handler.commands)


@pytest.mark.parametrize("body", [
    {"profile": "", "z": 0},
    {"profile": None, "z": 0},
    {"z": 0},
    {"profile": "default", "z": 0},                     # pas un profil connu
    {"profile": "k1_p001_t055_r001_n11x11 ; M112", "z": 0},  # injection G-code
    {"profile": "k1_p001_t055_r001_n11x11"},            # pas de Z
    {"profile": "k1_p001_t055_r001_n11x11", "z": "haut"},
    {"profile": "k1_p001_t055_r001_n11x11", "z": None},
    {"profile": "k1_p001_t055_r001_n11x11", "z": 40},   # 0,40 mal tape
    {"profile": "k1_p001_t055_r001_n11x11", "z": -2.5},
    {"profile": "k1_p001_t055_r001_n11x11", "z": float("nan")},
    {"profile": "k1_p001_t055_r001_n11x11", "z": float("inf")},
])
def test_a_z_that_would_wreck_a_plate_never_leaves_the_page(server, body):
    handler = _Probe(server, _status())
    with pytest.raises(ValueError):
        server.Handler._zsave(handler, body)
    assert handler.commands == []


def test_a_refusal_is_not_dressed_up_as_an_unreadable_body(server):
    # "corps illisible: Z 40 hors de la plage" names the wrong failure and
    # sends the operator looking at their browser instead of at their value.
    handler = _Probe(server, _status())
    with pytest.raises(server.Refused) as refusal:
        server.Handler._zsave(
            handler, {"profile": "k1_p001_t055_r001_n11x11", "z": 40})
    assert str(refusal.value).startswith("Z 40.0000 hors de la plage")
    assert issubclass(server.Refused, ValueError)
    with open(os.path.join(PACKAGE, "server.py"), encoding="utf-8") as handle:
        source = handle.read()
    # The order of the handlers is the whole point: ValueError first would
    # swallow every refusal into the generic message.
    assert source.index("except Refused as exc") < source.index(
        "except ValueError as exc")


def test_the_route_is_declared(server):
    with open(os.path.join(PACKAGE, "server.py"), encoding="utf-8") as handle:
        source = handle.read()
    assert 'if path == "/api/z"' in source
    assert "_zsave(body)" in source


def test_the_page_offers_a_typed_z_and_the_one_in_force():
    page = _www("index.html")
    assert 'id="z-value"' in page and 'type="number"' in page
    assert 'id="z-save"' in page and 'id="z-live"' in page
    source = _www("app.mjs")
    assert '"/api/z"' in source
    # Copying the machine's current offset must not write anything by itself.
    body = source.split('ui.zLive.addEventListener("click"', 1)[1].split("});", 1)[0]
    assert "saveZ" not in body


def test_the_page_refuses_the_same_range_as_the_printer():
    # A page that accepts what the macro refuses sends the operator to a red
    # console line instead of telling them on the spot.
    assert "const Z_LIMIT = 2;" in _www("app.mjs")
    assert "Z_LIMIT = 2.0" in open(
        os.path.join(PACKAGE, "server.py"), encoding="utf-8").read()
