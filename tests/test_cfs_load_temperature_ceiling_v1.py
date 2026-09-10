"""The CFS cannot heat the nozzle past what the G-code asked for.

The stock loader never reads the sliced file for its temperature. It reads the
material type of the slot it is about to pull from, looks that identifier up in
creality/userdata/box/material_database.json, and heats to the
nozzle_temperature of that record. The Generic PLA record carries 220 C, so
every PLA load has always heated to 220 C. Measured on the machine on
2026-09-09: the same load logged max_volumetric_speed: 14, the
filament_max_volumetric_speed of that very record, while the sliced file
carried 23,24.

The database is corrected per material and that is the fix - and the firmware
rewrites the database at boot, which is how the record corrected on 2026-09-09
was back at 220 C on 2026-09-10. That morning the window lowered the loader's
220 C to 205 C, and the loader, which waits for the temperature it asked for,
re-asked every second for five minutes with cancel queued behind it. An
emergency stop ended it.

So two things are pinned here. START_PRINT reads the material record of the
slot it will load and refuses, before anything heats or moves, when that record
is above the ceiling. And the window under it refuses instead of lowering,
because a lowered target is a hang, not a print that survives. The ordering,
the closing on every exit and the refusal are asserted by rendering the macros
rather than by reading them.
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


@pytest.mark.parametrize("macro", ["M104", "M109"])
def test_a_hot_target_is_refused_not_lowered_while_loading(guard_text, macro):
    """Lowering 220 C to 205 C looked kinder than refusing, and it was a hang:
    the loader waits for 220 C and re-asks every second, measured on
    2026-09-10 at 10:06. A refusal ends; nothing is emitted in its place."""
    emitted, said, raised = render(
        section(guard_text, macro), {"S": 220.0},
        probe=guard_state(False, 0.0), load=guard_state(True, 205.0))
    # action_raise_error aborts the macro in Klipper; the stub here returns, so
    # only the refusal and the absence of a rewritten target are asserted.
    assert raised and "220" in raised[0] and "205" in raised[0]
    assert "S205" not in " ".join(emitted), "a refused target must not be rewritten"
    assert not said


def test_the_material_record_is_checked_before_anything_heats(start_text):
    """The check has to run before the bed heats and before the head moves: a
    refusal there costs nothing, a hang at the load costs an emergency stop."""
    lines = commands(start_text, "START_PRINT")
    check = [i for i, line in enumerate(lines) if "material_temp.get(" in line]
    assert len(check) == 1, "the record is read exactly once"
    refusals = [i for i, line in enumerate(lines)
                if line.startswith("{% if load_temp")]
    assert len(refusals) == 2, "unknown record and hot record are both refused"
    for i in refusals:
        assert "action_raise_error" in lines[i + 1], "a bad record is a refusal"
    first_heat = min(i for i, line in enumerate(lines)
                     if line.split()[0] in ("M140", "M190", "M104", "M109"))
    first_move = min(i for i, line in enumerate(lines)
                     if line.split()[0] in ("CX_ROUGH_G28", "ACCURATE_G28", "G28"))
    opening = min(i for i, line in enumerate(lines) if line.startswith(OPEN))
    for i in [check[0]] + refusals:
        assert i < first_heat and i < first_move and i < opening
    ceiling = min(i for i, line in enumerate(lines)
                  if "set load_ceiling = nozzle +" in line)
    assert ceiling < check[0], "the ceiling exists before it is compared to"


def test_the_record_check_reads_the_slot_actually_loaded(start_text):
    """The slot's six character type is turned into the five character id the
    database is keyed on; guessing a record from the file would read the wrong
    spool, which is the failure the whole slot map exists to end."""
    body = section(start_text, "START_PRINT")
    assert 'printer.box["T" ~ tool[1]].material_type[slot_nums[tool[2]]]' in body
    assert 'slot_type[1:] if slot_type|length == 6 and slot_type[0] == "0"' in body
    assert "load_temp|float > load_ceiling" in body


def test_the_refusal_names_the_command_that_fixes_it(start_text):
    body = section(start_text, "START_PRINT")
    assert "corriger-temperatures-chargement-cfs-v1.py --temp %s=%d --appliquer" in body


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
