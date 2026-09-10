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

Since 2026-09-10 the material step is the tool change the start issues itself:
cmd_T loads, pulls to the nozzle and purges over the bin, hot, at the flush
temperature of the record aligned on the file. The push this file used to
order after the wait - BOX_EXTRUDER_EXTRUDE, a 120 mm top up, BOX_MATERIAL_FLUSH
- was written when that tool change did not exist and the stock flush ran on a
nozzle at 109 C. On the print of 2026-09-10 11:15 it added 254 mm at 190 C on
top of a full purge at 200 C: two balls in the bin, and the operator asked for
one. The start pushes no filament of its own any more; the wait and the
assertion stay, after the tool change, as the proof that the load reached the
head.
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

# Everything that ever pushed filament from this file. None of it is called by
# the start any more; the tool change does the whole material step.
OUR_PUSHES = ("BOX_EXTRUDER_EXTRUDE", "BOX_MATERIAL_FLUSH", "_KCTRL_PURGE_BALL")
TOOL = "T{position - 1}"
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
def test_the_start_pushes_no_filament_of_its_own():
    # Measured on 2026-09-10 11:15: the tool change had already purged at
    # 200 C when this block pushed 254 mm more at 190 C. Two balls in the bin
    # for one print, and the operator asked for one.
    lines = commands("START_PRINT")
    for command in OUR_PUSHES:
        assert not any(line.startswith(command) for line in lines), command


def test_the_only_purge_is_the_stock_one_inside_the_tool_change():
    # cmd_T loads, pulls to the nozzle and purges over the bin, hot, at the
    # flush temperature of the record aligned on the file. Once.
    lines = commands("START_PRINT")
    assert sum(1 for line in lines if line.startswith(TOOL)) == 1


def test_the_wait_and_the_assertion_come_after_the_tool_change():
    # The wait no longer protects a push of ours - there is none. It proves
    # the stock load reached the head before the start goes near the plate.
    lines = commands("START_PRINT")
    tool = index_of(lines, TOOL)
    wait = index_of(lines, WAIT)
    assertion = index_of(lines, "_KCTRL_ASSERT_FILAMENT_ENGAGED STAGE=after_cfs_load")
    assert tool < wait < assertion


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


def test_the_gcode_temperature_is_restored_and_waited_on_after_the_loader():
    # The stock loader sets targets of its own (flush at 200 for a file at 190
    # on 2026-09-10). The file's temperature is re-established, and waited on,
    # between the loader and the plate.
    lines = commands("START_PRINT")
    tool = index_of(lines, TOOL)
    heats = [n for n, line in enumerate(lines) if line == "M109 S{nozzle}"]
    assert heats and tool < max(heats) < index_of(lines, "_KCTRL_PRIME_LINE")


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


def test_the_standing_default_is_the_length_judged_over_the_bin():
    # Not arithmetic, and bounded on both sides. 200 mm gave the ball that
    # detaches instead of the strand that hangs; 180 mm overflowed the bin;
    # 120 mm is the ceiling the operator set from there. The value is a
    # decision, so it is pinned here rather than left to drift.
    assert variables("_KCTRL_PURGE_BALL")["purge_mm"] == 120.0


def test_the_top_up_is_a_manual_tool_and_not_part_of_the_start():
    # It was written for a stock flush that ran on a nozzle at 109 C. The tool
    # change purges hot now, so a top up only adds a second ball. It stays for
    # the operator: _KCTRL_PURGE_BALL TEMP=200 LEN=100.
    assert "[gcode_macro _KCTRL_PURGE_BALL]" in config_text()
    assert not any(line.startswith("_KCTRL_PURGE_BALL")
                   for line in commands("START_PRINT"))


def test_the_stock_flush_is_not_called_by_the_start():
    # It runs inside cmd_T, sized and heated by the stock loader. Called again
    # from here it is the second ball of 2026-09-10.
    assert not any(line.startswith("BOX_MATERIAL_FLUSH")
                   for line in commands("START_PRINT"))


# ----------------------------------------------------------- the measurement
def test_the_measurement_of_a_push_that_no_longer_exists_is_gone():
    # The mark and the report bracketed our push. There is no push of ours to
    # measure, and the report never measured anyway: -2 mm on 2026-09-02, the
    # box routines issue G92 E0 under it.
    text = config_text()
    assert "[gcode_macro _KCTRL_PURGE_MARK]" not in text
    assert "[gcode_macro _KCTRL_PURGE_REPORT]" not in text
    lines = commands("START_PRINT")
    assert not any(line.startswith("_KCTRL_PURGE_MARK")
                   or line.startswith("_KCTRL_PURGE_REPORT") for line in lines)
