"""Nothing pushes filament before the head sensor sees it.

The purge over the bin was leaving a thin strand hanging from the nozzle
instead of a ball that drops, and the strand was then dragged into the first
layer. The stock flush is sized for a head that already holds material: started
while the CFS is still feeding, or with the nozzle at 109 C, it is spent on an
empty melt zone and almost nothing comes out. The size was never the problem.

The grace period is a Python command rather than a macro that dwells, because
a macro that dwells does nothing at all once it is called from inside another
macro - and inside START_PRINT is the only place it would ever be used. That
failure is silent, which is why both halves are pinned here: the ordering of
the material step, and the fact that the wait is not a macro.
"""

import importlib.util
import os

import jinja2
import pytest

PACKAGE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "packages", "k1-control-v1", "owned-start-print-v2")
CONFIG = os.path.join(PACKAGE, "k1-control-owned-start-print-v2.cfg")

# Klipper: jinja2.Environment('{%', '%}', '{', '}')
ENV = jinja2.Environment("{%", "%}", "{", "}", extensions=["jinja2.ext.do"])

PUSHES_FILAMENT = ("BOX_EXTRUDER_EXTRUDE", "BOX_MATERIAL_FLUSH")
WAIT = "KCTRL_WAIT_FILAMENT SENSOR=filament_sensor_2"


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


def index_of(lines, needle):
    for position, line in enumerate(lines):
        if line.startswith(needle):
            return position
    raise AssertionError("%s absent de la sequence" % needle)


@pytest.fixture(scope="module")
def waiter():
    spec = importlib.util.spec_from_file_location(
        "kctrl_wait", os.path.join(PACKAGE, "kctrl_wait.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------- the ordering
def test_nothing_pushes_filament_before_the_wait_and_the_assertion():
    # This is the whole fix. Pushing while the CFS is still feeding spends the
    # purge on an empty melt zone, and no amount of extra length repairs that.
    lines = commands("START_PRINT")
    wait = index_of(lines, WAIT)
    assertion = index_of(lines, "_KCTRL_ASSERT_FILAMENT_ENGAGED STAGE=after_cfs_load")
    assert wait < assertion
    for command in PUSHES_FILAMENT:
        assert index_of(lines, command) > assertion, command


def test_the_grace_period_is_fifteen_seconds():
    # Measured against the machine: the CFS needs seven to eight seconds
    # minimum to reach the head, and its own trigger delay before that is not
    # known. Three seconds would have failed on a normal load.
    line = commands("START_PRINT")[index_of(commands("START_PRINT"), WAIT)]
    assert "TIMEOUT=15" in line


def test_the_wait_comes_after_every_cfs_attempt():
    lines = commands("START_PRINT")
    attempts = [n for n, line in enumerate(lines)
                if line.startswith("_KCTRL_CFS_LOAD")]
    assert attempts
    assert index_of(lines, WAIT) > max(attempts)


def test_the_nozzle_is_hot_and_waited_on_before_anything_is_pushed():
    # The stock flush only sets a target. The log of 2026-09-02 00:22 shows it
    # running at 109 C with the CFS target at 220: almost nothing comes out of
    # a nozzle at 109 C, which is the other half of the thin strand.
    lines = commands("START_PRINT")
    heat = index_of(lines, "M109 S{nozzle}")
    for command in PUSHES_FILAMENT:
        assert index_of(lines, command) > heat, command


def test_the_wait_is_not_a_macro():
    # Measured on 2026-09-02: ten dwelling polls flat took 8.14 s, the same ten
    # through one macro took 0.02 s, and a top level M400 straight after showed
    # the dwells had never been queued. A grace period written as a macro is a
    # grace period that does not exist, and it fails silently.
    assert "[gcode_macro _KCTRL_WAIT_HEAD_FILAMENT]" not in config_text()
    assert "[gcode_macro _KCTRL_WAIT_HEAD_5S]" not in config_text()
    assert "[kctrl_wait]" in config_text()


# ------------------------------------------------------------------- the wait
def test_the_pin_is_read_on_every_pass(waiter):
    # A wait that reads the sensor once is an assertion with a sleep in front.
    # The whole point is to see the CFS arrive, which happens while we wait.
    source = open(os.path.join(PACKAGE, "kctrl_wait.py"), encoding="utf-8").read()
    body = source.split("def cmd_KCTRL_WAIT_FILAMENT", 1)[1]
    loop = body.split("while True:", 1)[1]
    assert "get_status" in loop
    assert "reactor.pause" in loop


def test_a_missing_sensor_is_refused(waiter):
    assert "no filament sensor named" in open(
        os.path.join(PACKAGE, "kctrl_wait.py"), encoding="utf-8").read()


def test_a_timeout_fails_the_print_by_default(waiter):
    # Carrying on would purge and then print into an empty head, and the
    # operator would find out on the plate.
    source = open(os.path.join(PACKAGE, "kctrl_wait.py"), encoding="utf-8").read()
    body = source.split("def cmd_KCTRL_WAIT_FILAMENT", 1)[1]
    assert 'gcmd.get_int("REQUIRED", 1' in body
    assert "raise gcmd.error(message)" in body


# ------------------------------------------------------------------ the top up
def variables(name):
    import re
    text = config_text()
    start = text.index("[gcode_macro %s]" % name)
    end = text.find(chr(10) + "gcode:", start)
    found = {}
    for key, value in re.findall(r"^variable_(\w+):\s*(.+)$", text[start:end], re.M):
        found[key] = float(value)
    return found


def render(name, params):
    responses = []
    conf = variables(name)
    rendered = ENV.from_string(section(name)).render(
        params={k: str(v) for k, v in params.items()},
        printer={"gcode_macro %s" % name: type("V", (), conf)()},
        action_respond_info=lambda text: responses.append(text) or "",
    )
    return rendered, responses


def extruded(rendered):
    import re
    return sum(float(v) for v in re.findall(r"^\s*G1 E([\d.]+) F", rendered, re.M))


def test_the_top_up_is_pushed_in_full():
    # If the slicing loses a remainder the purge is short and nothing says so.
    rendered, _ = render("_KCTRL_PURGE_BALL", {"TEMP": 190})
    assert extruded(rendered) == pytest.approx(
        variables("_KCTRL_PURGE_BALL")["purge_mm"], abs=1e-3)


@pytest.mark.parametrize("length", [30, 61, 119, 300, 1000])
def test_any_top_up_is_pushed_in_full(length):
    rendered, _ = render("_KCTRL_PURGE_BALL", {"TEMP": 190, "LEN": length})
    assert extruded(rendered) == pytest.approx(length, abs=1e-3)


def test_the_standing_default_is_the_length_judged_on_the_plate():
    # Not arithmetic: 200 mm was run on 2026-09-02 and gave the ball that
    # detaches instead of the strand that hangs. 180 is what the operator then
    # chose as the standing default, to save a little filament per start.
    # The value is a decision, so it is pinned here rather than left to drift.
    assert variables("_KCTRL_PURGE_BALL")["purge_mm"] == 180.0


def test_the_top_up_comes_after_the_wait_and_the_heat():
    # Pushing before the filament is in the head is the whole defect. A top up
    # placed ahead of the wait would repeat it with more filament.
    lines = commands("START_PRINT")
    top_up = index_of(lines, "_KCTRL_PURGE_BALL")
    assert top_up > index_of(lines, WAIT)
    assert top_up > index_of(lines, "M109 S{nozzle}")
    assert top_up < index_of(lines, "BOX_MATERIAL_FLUSH")


def test_the_stock_flush_size_is_left_alone():
    # box.cfg declares box_need_clean_length_max: 140, so a LEN above it could
    # be clamped without a word - the worst failure a purge can have, since
    # nothing reports it and the defect only shows on the plate.
    lines = commands("START_PRINT")
    flush = [line for line in lines if "BOX_MATERIAL_FLUSH" in line]
    assert flush and all("LEN" not in line for line in flush)


# ----------------------------------------------------------- the measurement
def test_the_material_step_is_measured_end_to_end():
    # The head switch sits after the cutter and before the extruder gears, so
    # seeing filament there is not the same as having primed the nozzle. The
    # measured travel is the only honest answer to "was the purge enough".
    lines = commands("START_PRINT")
    mark = index_of(lines, "_KCTRL_PURGE_MARK")
    report = index_of(lines, "_KCTRL_PURGE_REPORT")
    for command in PUSHES_FILAMENT:
        assert mark < index_of(lines, command) < report, command


@pytest.mark.parametrize("macro", ["_KCTRL_PURGE_MARK", "_KCTRL_PURGE_REPORT"])
def test_each_measurement_reads_after_a_wait_for_moves(macro):
    # A macro renders when its command is processed; M400 blocks the queue
    # until the moves are done. Without it the position read is one that has
    # merely been queued.
    lines = commands("START_PRINT")
    assert lines[index_of(lines, macro) - 1] == "M400"


def test_the_report_refuses_to_print_a_number_it_cannot_measure():
    # It printed -2 mm on 2026-09-02: the box routines issue G92 E0 during
    # the material step, so the extruder axis restarts under the mark. An
    # interface that prints a wrong number is worse than one that says it
    # does not know, so the report guards the reading and falls back on the
    # one length this file actually commands.
    body = section("_KCTRL_PURGE_REPORT")
    assert "travel > 1.0" in body
    assert "non mesurable" in body
    assert "purge_mm" in body
