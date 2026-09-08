"""The CFS cannot heat the nozzle past what the G-code asked for.

The stock loader never reads the sliced file for its temperature. It reads the
material type of the slot it is about to pull from, looks that identifier up in
creality/userdata/box/material_database.json, and heats to the
nozzle_temperature of that record. The Generic PLA record carries 220 C, so
every PLA load has always heated to 220 C. Measured on the machine on
2026-09-09: the same load logged max_volumetric_speed: 14, the
filament_max_volumetric_speed of that very record, while the sliced file
carried 23,24.

The database is corrected per material and that is the fix. The window pinned
here is the net under it, and a net that silently stopped being armed would be
worse than none: the ordering, the closing on every exit, and the fact that the
wrapper lowers a target instead of refusing it are all asserted by rendering
the macros rather than by reading them.
"""

import os

import jinja2
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START = os.path.join(ROOT, "packages", "k1-control-v1", "owned-start-print-v2",
                     "k1-control-owned-start-print-v2.cfg")
GUARD = os.path.join(ROOT, "packages", "k1-control-v1", "mesh-acquisition-v2",
                     "k1-control-probe-temp-guard-v1.cfg")

# Klipper: jinja2.Environment('{%', '%}', '{', '}')
ENV = jinja2.Environment("{%", "%}", "{", "}", extensions=["jinja2.ext.do"])

OPEN = "_KCTRL_LOAD_GUARD_ON"
CLOSE = "_KCTRL_LOAD_GUARD_OFF"
# Everything the stock loader touches between these two calls can set a
# temperature of its own.
STOCK_LOADER = ("BOX_CHECK_MATERIAL", "BOX_EXTRUDER_EXTRUDE", "BOX_MATERIAL_FLUSH")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def section(text, name):
    """Return the gcode: body of one [gcode_macro NAME] section.

    Anchored on the start of a line: the header comment of the guard file names
    [gcode_macro M104] in prose, and a plain search lands there instead.
    """
    header = "\n[gcode_macro %s]\n" % name
    start = text.index(header) + 1
    end = text.find("\n[", start + 1)
    block = text[start:end if end != -1 else len(text)]
    body = block.split("\ngcode:\n", 1)[1]
    return "\n".join(line[2:] if line.startswith("  ") else line
                     for line in body.splitlines())


def commands(text, name):
    """The section body with comments and blank lines dropped.

    A comment naming a macro is not a call to it.
    """
    kept = [line.strip() for line in section(text, name).splitlines()]
    return [line for line in kept if line and not line.startswith("#")]


def guard_state(active, ceiling):
    return {"active": 1 if active else 0, "ceiling": ceiling}


def render(body, params, probe, load):
    """Render one macro body the way Klipper would, and return its G-code."""
    said = []
    raised = []

    def respond(message):
        said.append(message)
        return ""

    def fail(message):
        raised.append(message)
        return ""

    printer = {
        "gcode_macro _KCTRL_PROBE_GUARD": probe,
        "gcode_macro _KCTRL_LOAD_GUARD": load,
    }
    rawparams = " ".join("%s%s" % (k, v) for k, v in params.items())
    out = ENV.from_string(body).render(
        printer=printer, params=params, rawparams=rawparams,
        action_respond_info=respond, action_raise_error=fail)
    emitted = [line.strip() for line in out.splitlines() if line.strip()]
    return emitted, said, raised


@pytest.fixture(scope="module")
def start_text():
    return read(START)


@pytest.fixture(scope="module")
def guard_text():
    return read(GUARD)


def test_both_files_are_valid_klipper_templates(start_text, guard_text):
    """A template error only shows up at the next restart, and the next restart
    is the middle of a print. It is caught here instead."""
    for text in (start_text, guard_text):
        for name in ("M104", "M109", "START_PRINT", "END_PRINT", "CANCEL_PRINT",
                     OPEN, CLOSE, "_KCTRL_LOAD_GUARD"):
            if "[gcode_macro %s]" % name not in text:
                continue
            ENV.from_string(section(text, name))


def test_the_window_wraps_every_stock_loader_call(start_text):
    lines = commands(start_text, "START_PRINT")
    opens = [i for i, line in enumerate(lines) if line.startswith(OPEN)]
    closes = [i for i, line in enumerate(lines) if line.startswith(CLOSE)]
    assert len(opens) == 1, "the loading window is opened once per start"
    # One close clears a window left over by a previous job, one closes ours.
    assert len(closes) == 2, "cleared on entry, closed after the purge"
    entry, exit_ = min(closes), max(closes)
    assert entry < opens[0] < exit_
    for i, line in enumerate(lines):
        if line.split()[0] in STOCK_LOADER:
            assert opens[0] < i < exit_, "%s runs outside the window" % line


def test_the_ceiling_follows_the_gcode_temperature(start_text):
    """A constant here would be wrong for every filament but one."""
    body = section(start_text, "START_PRINT")
    opening = [line for line in body.splitlines() if OPEN in line and "#" not in line]
    assert opening, "no opening call found"
    assert "CEILING={load_ceiling}" in opening[0]
    assert "set load_ceiling = nozzle +" in body


def test_the_window_is_closed_on_every_exit(start_text):
    for macro in ("END_PRINT", "CANCEL_PRINT"):
        assert CLOSE in commands(start_text, macro), \
            "%s can leave a stale ceiling armed" % macro


@pytest.mark.parametrize("macro,stock", [("M104", "M104.1"), ("M109", "M109.1")])
def test_a_hot_target_is_lowered_not_refused_while_loading(guard_text, macro, stock):
    """This is the whole point: the load asks for 220 C and gets 205 C, and the
    print survives. Refusing killed three prints in a row on 2026-09-05."""
    emitted, said, raised = render(
        section(guard_text, macro), {"S": 220.0},
        probe=guard_state(False, 0.0), load=guard_state(True, 205.0))
    assert not raised, "a print must not die at the load"
    assert emitted == ["%s S205.0" % stock]
    assert said and "205" in said[0]


@pytest.mark.parametrize("macro,stock", [("M104", "M104.1"), ("M109", "M109.1")])
def test_a_target_within_the_ceiling_passes_untouched(guard_text, macro, stock):
    emitted, said, raised = render(
        section(guard_text, macro), {"S": 190.0},
        probe=guard_state(False, 0.0), load=guard_state(True, 205.0))
    assert not raised and not said
    assert emitted == ["%s S190.0" % stock]


@pytest.mark.parametrize("macro", ["M104", "M109"])
def test_the_probing_window_still_refuses(guard_text, macro):
    """Lowering is right during a load and wrong before a contact: a nozzle
    quietly held at the ceiling still oozes onto the plate."""
    _, _, raised = render(
        section(guard_text, macro), {"S": 220.0},
        probe=guard_state(True, 45.0), load=guard_state(False, 0.0))
    assert raised, "the probing ceiling must refuse, not lower"


@pytest.mark.parametrize("macro", ["M104", "M109"])
def test_nothing_is_capped_when_both_windows_are_closed(guard_text, macro):
    emitted, said, raised = render(
        section(guard_text, macro), {"S": 250.0},
        probe=guard_state(False, 0.0), load=guard_state(False, 0.0))
    assert not raised and not said
    assert emitted == ["%s.1 S250.0" % macro]
