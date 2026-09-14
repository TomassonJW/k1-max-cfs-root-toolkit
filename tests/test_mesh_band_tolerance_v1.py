"""One mesh profile serves every bed temperature within five degrees of it.

On 14 September 2026 a Benchy sliced for a 50 C bed was refused at 17:40:
START_PRINT wanted k1_p001_t050_r001_n11x11 exactly, and the only profile
was the 55 C one. Thomas chose a tolerance instead of five calibration cubes
per band: the 55 C profile prints 50 to 60 C files, and a new band starts as
a copy of the closest one (KCTRL_MESH_COPY), refined on the printed square.

Two things are pinned here. The resolution itself, rendered with Jinja the
way Klipper renders it, on the cases that matter: exact band, both edges of
the window, the gap between two windows, the tie, and the profiles that look
like the family without belonging to it. And the copy: never over an existing
band, visible at once without a restart, Z carried along.
"""

import collections
import importlib.util
import os

import jinja2
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "packages", "k1-control-v1", "owned-start-print-v2",
                      "k1-control-owned-start-print-v2.cfg")
MODULE = os.path.join(ROOT, "packages", "k1-control-v1", "mesh-acquisition-v2",
                      "kctrl_mesh.py")

# Klipper: jinja2.Environment('{%', '%}', '{', '}')
ENV = jinja2.Environment("{%", "%}", "{", "}", extensions=["jinja2.ext.do"])

CONF = {"plate_id": 1, "probe_rev": 1, "x_count": 11, "y_count": 11,
        "band_tolerance_c": 5}


def name(temp, plate=1, grid="11x11"):
    return "k1_p%03d_t%03d_r001_n%s" % (plate, temp, grid)


def section(macro):
    with open(CONFIG, encoding="utf-8") as handle:
        text = handle.read()
    start = text.index("\n[gcode_macro %s]\n" % macro) + 1
    end = text.find("\n[", start + 1)
    body = text[start:end].split("\ngcode:\n", 1)[1]
    return "\n".join(line[2:] if line.startswith("  ") else line
                     for line in body.splitlines())


def resolution(macro):
    body = section(macro)
    start = body.index("{% set tolerance")
    end = body.index("\n", body.index("{% set measured"))
    return body[start:end]


def resolve(bed, profiles, tolerance=5):
    conf = dict(CONF, band_tolerance_c=tolerance)
    template = ("{% set c = conf %}{% set band = bed %}"
                + resolution("START_PRINT")
                + "{profile}|{found.band}|{found.gap}|{measured}")
    out = ENV.from_string(template).render(
        conf=conf, bed=bed,
        printer={"bed_mesh": {"profiles": dict((p, {}) for p in profiles)}})
    profile, band, gap, measured = out.strip().split("|")
    return profile, int(band), int(gap), measured


def test_start_print_and_profile_name_resolve_with_the_same_block():
    assert resolution("START_PRINT") == resolution("KCTRL_PROFILE_NAME")


def test_the_tolerance_is_five_degrees_in_the_shipped_configuration():
    with open(CONFIG, encoding="utf-8") as handle:
        assert "\nvariable_band_tolerance_c: 5\n" in handle.read()


@pytest.mark.parametrize("bed,expected", [
    (55, 55), (50, 55), (60, 55), (53, 55),
    (65, 70), (70, 70), (75, 70),
])
def test_the_closest_profile_within_five_degrees_is_used(bed, expected):
    profile, band, gap, _ = resolve(bed, [name(55), name(70)])
    assert profile == name(expected)
    assert (band, gap) == (expected, abs(bed - expected))


@pytest.mark.parametrize("bed", [45, 49, 61, 64, 76, 100])
def test_a_bed_outside_every_window_is_refused_with_the_bands_named(bed):
    profile, _, _, measured = resolve(bed, [name(70), name(55)])
    assert profile == ""
    assert measured == "55, 70 C"


def test_the_machine_bands_55_and_65_leave_no_degree_uncovered_from_50_to_70():
    # Thomas, 14 September 2026: the copy sits at 65, not 70, because a
    # five-degree hole without a mesh makes no sense.
    profiles = [name(55), name(65)]
    for bed in range(50, 71):
        assert resolve(bed, profiles)[0] == name(55 if bed <= 60 else 65), bed
    for bed in (49, 71):
        assert resolve(bed, profiles)[0] == "", bed


def test_an_equal_gap_goes_to_the_colder_profile_whatever_the_order():
    for order in ([name(55), name(65)], [name(65), name(55)]):
        assert resolve(60, order)[0] == name(55)


def test_an_exact_band_beats_a_neighbour():
    assert resolve(60, [name(55), name(60), name(65)])[0] == name(60)


def test_profiles_outside_the_family_are_never_picked():
    lookalikes = ["default", name(55) + "_tuned_v001", name(55, grid="06x06"),
                  name(55, plate=2), "K1_SUB_SW", "k1_p001_tabc_r001_n11x11"]
    profile, _, _, measured = resolve(55, lookalikes)
    assert profile == ""
    assert measured == "aucun"


def test_a_zero_tolerance_is_the_old_exact_rule():
    assert resolve(50, [name(55)], tolerance=0)[0] == ""
    assert resolve(55, [name(55)], tolerance=0)[0] == name(55)


def test_start_print_refuses_on_no_profile_and_names_the_way_out():
    body = section("START_PRINT")
    refusal = body[body.index("{% if not profile %}"):]
    refusal = refusal[:refusal.index("{% endif %}")]
    assert "action_raise_error" in refusal
    assert "KCTRL_MESH_COPY BED_TEMP=" in refusal
    assert "profile not in printer.bed_mesh.profiles" not in body


def test_profile_name_says_which_band_and_gap_it_resolved():
    said = []
    body = section("KCTRL_PROFILE_NAME")
    printer = {
        "gcode_macro _KCTRL_START_CONF": CONF,
        "bed_mesh": {"profiles": {name(55): {}, name(70): {}}},
        "save_variables": {"variables": {"z_" + name(55): 0.065}},
    }
    for bed in (50, 62):
        ENV.from_string(body).render(
            printer=printer, params={"BED_TEMP": bed},
            action_respond_info=lambda m: said.append(m) or "")
    assert said[0] == ("plateau 50 C -> %s (maillage 55 C, ecart 5 C) | Z 0.065"
                       % name(55))
    assert said[1].startswith("plateau 62 C -> aucun maillage a +/-5 C "
                              "(maillages: 55, 70 C)")


# ------------------------------------------------------------ KCTRL_MESH_COPY
class _Error(Exception):
    pass


class _Gcode:
    error = _Error

    def __init__(self):
        self.scripts = []

    def run_script_from_command(self, script):
        self.scripts.append(script)


class _Cmd:
    def __init__(self, **params):
        self.params = dict((k.upper(), v) for k, v in params.items())
        self.said = []

    def get(self, key, default=None):
        return self.params.get(key, default)

    def get_int(self, key, default=None, minval=None, maxval=None):
        if key not in self.params and default is None:
            raise _Error("missing %s" % key)
        value = int(self.params.get(key, default))
        if (minval is not None and value < minval) or (
                maxval is not None and value > maxval):
            raise _Error("%s out of range" % key)
        return value

    def respond_info(self, message):
        self.said.append(message)


class _Pmgr:
    def __init__(self, profiles):
        self.profiles = profiles


class _BedMesh:
    def __init__(self, profiles, active):
        self.pmgr = _Pmgr(profiles)
        self.active = active
        self.update_status()

    def update_status(self):
        self.status = {"profile_name": self.active,
                       "profiles": self.pmgr.profiles}

    def get_status(self, eventtime=None):
        return self.status


class _SaveVariables:
    def __init__(self, variables):
        self.variables = variables

    def get_status(self, eventtime):
        return {"variables": self.variables}


class _Printer:
    def __init__(self, objects, config_file):
        self.objects = objects
        self.config_file = config_file

    def lookup_object(self, key, default=None):
        return self.objects.get(key, default)

    def get_start_args(self):
        return {"config_file": self.config_file}


def _params():
    return collections.OrderedDict([
        ("x_count", 11), ("y_count", 11), ("mesh_x_pps", 2), ("mesh_y_pps", 2),
        ("algo", "bicubic"), ("tension", 0.2), ("min_x", 5.0), ("max_x", 295.0),
        ("min_y", 5.0), ("max_y", 295.0)])


@pytest.fixture
def machine(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("kctrl_mesh_copy", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # os.rename replaces the target on the printer (Linux), not on Windows.
    monkeypatch.setattr(module.os, "rename", os.replace)
    points = tuple(tuple(round(0.01 * (i - j), 4) for i in range(11))
                   for j in range(11))
    profiles = {name(55): {"points": points, "mesh_params": _params()}}
    cfg = tmp_path / "printer.cfg"
    cfg.write_text("[printer]\nkinematics: corexy\n\n#*# <---- SAVE_CONFIG ---->\n"
                   "#*# [bed_mesh %s]\n#*# version = 1\n" % name(55))
    bed_mesh = _BedMesh(profiles, name(55))
    gcode = _Gcode()
    saver = _SaveVariables({"z_" + name(55): 0.065})
    instance = object.__new__(module.KctrlMesh)
    instance.gcode = gcode
    instance.printer = _Printer(
        {"bed_mesh": bed_mesh, "save_variables": saver}, str(cfg))
    return instance, bed_mesh, gcode, saver, cfg, points


def test_a_copy_is_written_registered_and_carries_the_z(machine):
    instance, bed_mesh, gcode, _, cfg, points = machine
    cmd = _Cmd(bed_temp=70)
    instance.cmd_KCTRL_MESH_COPY(cmd)
    target = name(70)
    assert bed_mesh.get_status()["profiles"][target]["points"] == \
        [list(row) for row in points]
    assert name(55) in bed_mesh.get_status()["profiles"]
    text = cfg.read_text()
    assert "#*# [bed_mesh %s]" % target in text
    assert "#*# [bed_mesh %s]" % name(55) in text
    assert gcode.scripts == ["SAVE_VARIABLE VARIABLE=z_%s VALUE=0.0650" % target]
    assert any("Z 0.0650 copied" in line for line in cmd.said)


def test_the_copy_is_resolved_by_start_print_at_once(machine):
    instance, bed_mesh, _, _, _, _ = machine
    instance.cmd_KCTRL_MESH_COPY(_Cmd(bed_temp=70))
    assert resolve(68, list(bed_mesh.get_status()["profiles"]))[0] == name(70)


def test_an_existing_band_is_never_overwritten(machine):
    instance, bed_mesh, gcode, _, cfg, _ = machine
    instance.cmd_KCTRL_MESH_COPY(_Cmd(bed_temp=70))
    before = cfg.read_text()
    with pytest.raises(_Error, match="already exists"):
        instance.cmd_KCTRL_MESH_COPY(_Cmd(bed_temp=70))
    assert cfg.read_text() == before
    assert len(gcode.scripts) == 1


@pytest.mark.parametrize("params,message", [
    (dict(bed_temp=55), "already the 55 C profile"),
    (dict(bed_temp=70, source=name(55) + "_tuned_v001"), "must be a"),
    (dict(bed_temp=70, source="default"), "must be a"),
    (dict(bed_temp=70, source=name(60)), "no profile named"),
    (dict(bed_temp=151), "out of range"),
])
def test_a_copy_that_could_not_be_used_is_refused(machine, params, message):
    instance, bed_mesh, gcode, _, cfg, _ = machine
    before = cfg.read_text()
    with pytest.raises(_Error, match=message):
        instance.cmd_KCTRL_MESH_COPY(_Cmd(**params))
    assert cfg.read_text() == before
    assert list(bed_mesh.get_status()["profiles"]) == [name(55)]
    assert gcode.scripts == []


def test_a_source_without_z_says_the_copy_has_none(machine):
    instance, _, gcode, saver, _, _ = machine
    saver.variables.clear()
    cmd = _Cmd(bed_temp=50)
    instance.cmd_KCTRL_MESH_COPY(cmd)
    assert gcode.scripts == []
    assert any("has no saved Z" in line for line in cmd.said)
