"""Nothing pushes filament before the head sensor sees it.

The purge over the bin was leaving a thin strand hanging from the nozzle
instead of a ball that drops, and the strand was then dragged into the first
layer. The stock flush is sized for a head that already holds material: started
while the CFS is still feeding, or with the nozzle at 109 C, it is spent on an
empty melt zone and almost nothing comes out. The size was never the problem.

So the ordering of the material step is what is pinned here, and it is pinned
by rendering the macros with Klipper's own Jinja environment rather than by
reading the file: a slip in a print start macro only ever surfaces at the
moment a print starts, with the plate hot.
"""

import os
import re

import jinja2
import pytest

CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "packages", "k1-control-v1", "owned-start-print-v2",
    "k1-control-owned-start-print-v2.cfg")

# Klipper: jinja2.Environment('{%', '%}', '{', '}')
ENV = jinja2.Environment("{%", "%}", "{", "}", extensions=["jinja2.ext.do"])

PUSHES_FILAMENT = ("BOX_EXTRUDER_EXTRUDE", "BOX_MATERIAL_FLUSH")


def config_text():
    with open(CONFIG, encoding="utf-8") as handle:
        return handle.read()


def section(name):
    """Return the gcode: body of one [gcode_macro NAME] section."""
    text = config_text()
    start = text.index("[gcode_macro %s]" % name)
    end = text.find("\n[", start + 1)
    block = text[start:end if end != -1 else len(text)]
    body = block.split("\ngcode:\n", 1)[1]
    return "\n".join(line[2:] if line.startswith("  ") else line
                     for line in body.splitlines())


def commands(name):
    """The section body with comments and blank lines dropped.

    A comment naming a macro is not a call to it, and an ordering assertion
    that cannot tell them apart proves nothing - the first version of this file
    passed on a comment.
    """
    kept = [line.strip() for line in section(name).splitlines()]
    return [line for line in kept if line and not line.startswith("#")]


def render(name, params=None, detected=True):
    sensor = type("S", (), {"filament_detected": detected})()
    responses = []
    rendered = ENV.from_string(section(name)).render(
        params={k: str(v) for k, v in (params or {}).items()},
        printer={"filament_switch_sensor filament_sensor_2": sensor},
        action_respond_info=lambda text: responses.append(text) or "",
    )
    return rendered, responses


def index_of(lines, needle):
    for position, line in enumerate(lines):
        if line.startswith(needle):
            return position
    raise AssertionError("%s absent de la sequence" % needle)


# ------------------------------------------------------- wait, do not assume
def test_the_wait_polls_only_while_the_head_is_empty():
    empty, _ = render("_KCTRL_WAIT_HEAD_FILAMENT", detected=False)
    assert "G4 P250" in empty
    loaded, _ = render("_KCTRL_WAIT_HEAD_FILAMENT", detected=True)
    assert "G4" not in loaded


def test_the_wait_is_unrolled_because_one_call_reads_once():
    # A macro reads the sensor once, when its template renders. A Jinja loop
    # inside a single macro would re-emit the same stale reading, and Klipper
    # refuses a macro that calls itself, so repeated calls are the only shape
    # that actually re-reads the pin.
    body = section("_KCTRL_WAIT_HEAD_FILAMENT")
    assert "{% for" not in body
    assert "_KCTRL_WAIT_HEAD_FILAMENT" not in body
    calls = [line for line in commands("START_PRINT")
             if line == "_KCTRL_WAIT_HEAD_FILAMENT"]
    assert len(calls) >= 8, "trop peu de sondages pour laisser le CFS arriver"


def test_nothing_pushes_filament_before_the_wait_and_the_assertion():
    # This is the whole fix. Pushing while the CFS is still feeding spends the
    # purge on an empty melt zone, and no amount of extra length repairs that.
    lines = commands("START_PRINT")
    wait = index_of(lines, "_KCTRL_WAIT_HEAD_FILAMENT")
    assertion = index_of(lines, "_KCTRL_ASSERT_FILAMENT_ENGAGED STAGE=after_cfs_load")
    assert wait < assertion
    for command in PUSHES_FILAMENT:
        assert index_of(lines, command) > assertion, command


def test_the_nozzle_is_hot_and_waited_on_before_anything_is_pushed():
    # The stock flush only sets a target. The log of 2026-09-02 00:22 shows it
    # running at 109 C with the CFS target at 220: almost nothing comes out of
    # a nozzle at 109 C, which is the other half of the thin strand.
    lines = commands("START_PRINT")
    heat = index_of(lines, "M109 S{nozzle}")
    for command in PUSHES_FILAMENT:
        assert index_of(lines, command) > heat, command


def test_the_wait_comes_after_every_cfs_attempt():
    lines = commands("START_PRINT")
    attempts = [n for n, line in enumerate(lines)
                if line.startswith("_KCTRL_CFS_LOAD")]
    assert attempts
    assert index_of(lines, "_KCTRL_WAIT_HEAD_FILAMENT") > max(attempts)


# ------------------------------------------------------------- no extra purge
def test_the_stock_flush_size_is_left_alone():
    # 140 mm was never the problem and 440 mm is a lot of filament to burn at
    # every print start. box.cfg also declares box_need_clean_length_max: 140,
    # so a LEN above it could be clamped without a word.
    lines = commands("START_PRINT")
    flush = [line for line in lines if "BOX_MATERIAL_FLUSH" in line]
    assert flush and all("LEN" not in line for line in flush)
    assert "_KCTRL_PURGE_BALL" not in config_text()


# ----------------------------------------------------------- the measurement
def test_the_material_step_is_measured_end_to_end():
    # The head switch sits after the cutter and before the extruder gears, so
    # seeing filament there is not the same as having primed the nozzle. The
    # measured travel is the only honest answer to "was the purge enough".
    lines = commands("START_PRINT")
    mark = index_of(lines, "_KCTRL_PURGE_MARK")
    report = index_of(lines, "_KCTRL_PURGE_REPORT")
    for command in PUSHES_FILAMENT:
        position = index_of(lines, command)
        assert mark < position < report, command


@pytest.mark.parametrize("macro", ["_KCTRL_PURGE_MARK", "_KCTRL_PURGE_REPORT"])
def test_each_measurement_reads_after_a_wait_for_moves(macro):
    # A macro renders when its command is processed; M400 blocks the queue
    # until the moves are done. Without it the position read is one that has
    # merely been queued.
    lines = commands("START_PRINT")
    assert lines[index_of(lines, macro) - 1] == "M400"


def test_the_config_has_no_leftover_purge_variables():
    assert "purge_mm" not in config_text()
    assert "purge_speed" not in config_text()
