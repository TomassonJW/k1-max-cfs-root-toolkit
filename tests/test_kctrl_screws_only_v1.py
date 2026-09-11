"""KCTRL_SCREWS_PROBE: four raw contacts, one over each screw, and the turns.

On 2026-09-11 Thomas asked for a first pass on the screws alone, four contacts
and nothing else, to iterate fast after a lost bed bolt. The 25 point grid of
KCTRL_BED_SCREWS reads the screws out of a stored mesh, which the firmware
tilts by 0.10 mm front to back (doc 73); the plain PROBE path does not go
through that ramp. These tests pin what the command does: it probes exactly
the configured screw positions, in order, lifting between them, reports the
raw contact of each, and turns the spread into the same eighths-of-a-turn
table as the grid report. They also pin its refusals.
"""

import importlib.util
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "packages", "k1-control-v1", "mesh-acquisition-v2")
MODULE = os.path.join(PACKAGE, "kctrl_mesh.py")
CFG = os.path.join(PACKAGE, "k1-control-mesh-reference-v2.cfg")

SCREWS = [
    ("avant-gauche", 18.5, 23.7),
    ("avant-droit", 276.5, 23.7),
    ("arriere-gauche", 48.5, 273.7),
    ("arriere-droit", 246.5, 273.7),
]


def _load():
    spec = importlib.util.spec_from_file_location("kctrl_mesh_screws_only", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Error(Exception):
    pass


class _FakeGcode:
    error = _Error

    def __init__(self):
        self.scripts = []

    def run_script_from_command(self, script):
        self.scripts.append(script)


class _FakeCmd:
    _REQUIRED = object()

    def __init__(self, **kwargs):
        self.params = {key.upper(): value for key, value in kwargs.items()}
        self.lines = []

    def _fetch(self, key, default):
        value = self.params.get(key, default)
        if value is self._REQUIRED:
            raise _Error("missing %s" % key)
        return value

    def get(self, key, default=_REQUIRED):
        return self._fetch(key, default)

    def get_int(self, key, default=_REQUIRED, minval=None, maxval=None):
        value = self._fetch(key, default)
        return None if value is None else int(value)

    def get_float(self, key, default=_REQUIRED, minval=None, maxval=None,
                  above=None):
        value = self._fetch(key, default)
        if value is None:
            return None
        value = float(value)
        if minval is not None and value < minval:
            raise _Error("%s below %s" % (key, minval))
        if above is not None and value <= above:
            raise _Error("%s not above %s" % (key, above))
        return value

    def respond_info(self, msg):
        self.lines.append(msg)


class _Status:
    def __init__(self, **status):
        self.status = status

    def get_status(self, eventtime):
        return dict(self.status)


class _FakeReactor:
    def monotonic(self):
        return 1234.5


class _FakeProbe:
    """Returns the bed height of the point the toolhead was last sent to."""

    def __init__(self, gcode, heights):
        self.gcode = gcode
        self.heights = heights
        self.probed = []

    def run_probe(self, gcmd):
        last = self.gcode.scripts[-1]
        match = re.search(r"G1 X([-\d.]+) Y([-\d.]+)", last)
        assert match, "probe called without a preceding XY move: %r" % last
        x, y = float(match.group(1)), float(match.group(2))
        self.probed.append((x, y))
        return [x, y, self.heights[(x, y)]]


class _FakePrinter:
    def __init__(self, objects):
        self.objects = objects

    def lookup_object(self, name, default=Exception):
        if name in self.objects:
            return self.objects[name]
        if default is Exception:
            raise _Error("unknown object %s" % name)
        return default

    def get_reactor(self):
        return _FakeReactor()


@pytest.fixture(scope="module")
def module():
    return _load()


def machine(module, heights, state="standby", homed="xyz", probe=True):
    instance = object.__new__(module.KctrlMesh)
    gcode = _FakeGcode()
    instance.gcode = gcode
    instance.screws = list(SCREWS)
    instance.screw_pitch = 0.7
    objects = {
        "gcode": gcode,
        "print_stats": _Status(state=state),
        "toolhead": _Status(homed_axes=homed),
    }
    fake_probe = _FakeProbe(gcode, heights) if probe else None
    if probe:
        objects["probe"] = fake_probe
    instance.printer = _FakePrinter(objects)
    return instance, gcode, fake_probe


def level_heights(**offsets):
    heights = {}
    for name, x, y in SCREWS:
        heights[(x, y)] = offsets.get(name.replace("-", "_"), 0.0)
    return heights


def test_it_probes_exactly_the_four_screw_positions_in_order(module):
    instance, gcode, probe = machine(module, level_heights())
    cmd = _FakeCmd()
    instance.cmd_KCTRL_SCREWS_PROBE(cmd)
    assert probe.probed == [(x, y) for _, x, y in SCREWS]
    assert len(probe.probed) == 4


def test_it_lifts_to_the_travel_height_before_every_move_and_after_the_last(module):
    instance, gcode, probe = machine(module, level_heights())
    instance.cmd_KCTRL_SCREWS_PROBE(_FakeCmd(travel_z=7))
    # One script per screw (lift, then XY), then one final lift.
    assert len(gcode.scripts) == 5
    for script in gcode.scripts[:4]:
        lines = script.split("\n")
        assert lines[0] == "G90"
        assert lines[1].startswith("G1 Z7.000 ")
        assert lines[2].startswith("G1 X")
    assert gcode.scripts[4].startswith("G1 Z7.000 ")


def test_the_rear_screws_are_probed_where_they_are_not_at_the_corners(module):
    instance, gcode, probe = machine(module, level_heights())
    instance.cmd_KCTRL_SCREWS_PROBE(_FakeCmd())
    rear = [p for p in probe.probed if p[1] > 200]
    assert rear == [(48.5, 273.7), (246.5, 273.7)]


def test_each_raw_contact_is_reported_and_the_turns_follow_the_spread(module):
    # Front left sits 0.175 mm above the rest: exactly two eighths of an M4
    # turn. The all-tightening block names it, the others are left alone.
    instance, gcode, probe = machine(module, level_heights(avant_gauche=0.175))
    cmd = _FakeCmd()
    instance.cmd_KCTRL_SCREWS_PROBE(cmd)
    text = "\n".join(cmd.lines)
    assert "avant-gauche X18.5 Y23.7 contact at +0.1750 mm" in text
    assert "arriere-droit X246.5 Y273.7 contact at +0.0000 mm" in text
    assert "screw heights span 0.1750 mm" in text
    visser = text.split("VISSER")[1].split("DEVISSER")[0]
    assert "avant-gauche" in visser and "visser 2.0 huitiemes" in visser
    assert visser.count("ne pas toucher") == 3


def test_a_level_bed_asks_for_nothing(module):
    instance, gcode, probe = machine(module, level_heights())
    cmd = _FakeCmd()
    instance.cmd_KCTRL_SCREWS_PROBE(cmd)
    text = "\n".join(cmd.lines)
    assert "screw heights span 0.0000 mm" in text
    assert text.count("ne pas toucher") == 8
    assert "huitiemes" not in text


@pytest.mark.parametrize("state", ["printing", "paused"])
def test_it_refuses_during_a_print_before_moving_anything(module, state):
    instance, gcode, probe = machine(module, level_heights(), state=state)
    with pytest.raises(_Error, match="print is in progress or paused"):
        instance.cmd_KCTRL_SCREWS_PROBE(_FakeCmd())
    assert gcode.scripts == []
    assert probe.probed == []


@pytest.mark.parametrize("state", ["standby", "complete", "cancelled", "error"])
def test_it_runs_in_every_state_that_is_not_a_print(module, state):
    instance, gcode, probe = machine(module, level_heights(), state=state)
    instance.cmd_KCTRL_SCREWS_PROBE(_FakeCmd())
    assert len(probe.probed) == 4


def test_it_refuses_when_the_axes_are_not_homed(module):
    instance, gcode, probe = machine(module, level_heights(), homed="xy")
    with pytest.raises(_Error, match="home all axes"):
        instance.cmd_KCTRL_SCREWS_PROBE(_FakeCmd())
    assert gcode.scripts == []


def test_it_refuses_without_a_probe_or_without_screws(module):
    instance, gcode, probe = machine(module, level_heights(), probe=False)
    with pytest.raises(_Error, match="no probe"):
        instance.cmd_KCTRL_SCREWS_PROBE(_FakeCmd())
    instance, gcode, probe = machine(module, level_heights())
    instance.screws = []
    with pytest.raises(_Error, match="no screw position"):
        instance.cmd_KCTRL_SCREWS_PROBE(_FakeCmd())


def test_the_grid_report_still_uses_the_shared_turns_table(module):
    # The refactor moved the turns table into _report_heights; the grid
    # report must print the same lines as before.
    instance = object.__new__(module.KctrlMesh)
    instance.gcode = _FakeGcode()
    instance.screw_pitch = 0.7
    cmd = _FakeCmd()
    instance._report_heights(cmd, [
        ("avant-gauche", 18.5, 23.7, 0.0875),
        ("avant-droit", 276.5, 23.7, 0.0),
    ])
    text = "\n".join(cmd.lines)
    assert "one eighth of a turn is 0.0875 mm" in text
    assert "visser 1.0 huitiemes" in text
    assert "devisser 1.0 huitiemes" in text


# ----------------------------------------------------------------- the macro
def section(text, name):
    start = text.index("[gcode_macro %s]" % name)
    end = text.find("\n[", start + 1)
    return text[start:end if end != -1 else len(text)]


@pytest.fixture(scope="module")
def macro():
    return section(open(CFG, encoding="utf-8").read(), "KCTRL_SCREWS_ONLY")


def test_the_macro_homes_clears_the_mesh_then_probes_the_screws(macro):
    order = ["CX_ROUGH_G28", "ACCURATE_G28", "_KCTRL_PROBE_GUARD_OFF",
             "BED_MESH_CLEAR", "KCTRL_SCREWS_PROBE", "M104 S0", "G1 Z{park}"]
    positions = [macro.index(step) for step in order]
    assert positions == sorted(positions)
    assert "BED_MESH_CALIBRATE" not in macro
    assert "KCTRL_SCREWS_REPORT" not in macro


def test_the_macro_keeps_the_bed_hot_between_passes(macro):
    assert "TURN_OFF_HEATERS" not in [
        line.strip() for line in macro.splitlines()]
    assert "M104 S0" in macro


def test_the_macro_refuses_prints_and_an_engaged_filament(macro):
    assert '{% if printer.print_stats.state|string in ["printing", "paused"] %}' in macro
    assert 'filament_switch_sensor filament_sensor_2"].filament_detected' in macro


def test_no_hash_inside_a_macro_string(macro):
    # A "#" inside a gcode: string halts Klipper (doc 54); comments must be
    # whole lines.
    for line in macro.splitlines():
        stripped = line.strip()
        if "#" in stripped and not stripped.startswith("#"):
            raise AssertionError(line)
