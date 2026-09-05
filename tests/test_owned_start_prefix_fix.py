"""Regression for the real G28/T0/START_PRINT order; no printer connection."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prefix_fix", ROOT / "scripts/fix_owned_start_prefix.py")
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)

START = b"START_PRINT EXTRUDER_TEMP=190 BED_TEMP=55\n"
REMAINDER = START + (
    b"M104 S190\nM109 S190\nT0\nG1 X5 Y5 E1\n"
    b"; flush_volumes_matrix = 0,140,260,0\nT1\nG1 E120\n"
    b"T0\nKCTRL_PRODUCTION_ARM PLATE=1 TEMP_BAND=55\nEND_PRINT\n")


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_only_the_two_premature_commands_are_removed(newline):
    before = (b"; thumbnail\nM73 P0 R817\nM106 S0\nG28\nT0\n" + REMAINDER).replace(b"\n", newline)
    after, removed = fix.repair_prefix(before)
    assert removed == [4, 5]
    assert after == (b"; thumbnail\nM73 P0 R817\nM106 S0\n" + REMAINDER).replace(b"\n", newline)
    assert fix.repair_prefix(after) == (after, [])


@pytest.mark.parametrize("prefix", [b"G28\nT1\n", b"G28 X Y\nT0\n", b"M104 S220\nG28\nT0\n", b"T0\n", b"ACCURATE_G28\n", b"G1 E50\n"])
def test_another_geometry_tool_or_heat_sequence_is_refused(prefix):
    with pytest.raises(ValueError):
        fix.repair_prefix(prefix + REMAINDER)


def test_streamed_copy_preserves_the_whole_print_and_original(tmp_path):
    source, output = tmp_path / "part.gcode", tmp_path / "part-fixed.gcode"
    tail = REMAINDER + b"G1 X10 Y10 E1\n" * 100000
    original = b"G28\nT0\n" + tail
    source.write_bytes(original)
    result = fix.write_gcode_copy(source, output)
    assert output.read_bytes() == tail
    assert source.read_bytes() == original
    assert result["removed_bytes"] == 7
    import hashlib
    assert result["unchanged_from_start_print_sha256"] == hashlib.sha256(tail).hexdigest()


def test_existing_destination_is_never_overwritten(tmp_path):
    source, output = tmp_path / "part.gcode", tmp_path / "fixed.gcode"
    source.write_bytes(b"G28\nT0\n" + REMAINDER)
    output.write_bytes(b"user file")
    with pytest.raises(ValueError):
        fix.write_gcode_copy(source, output)
    assert output.read_bytes() == b"user file"


def test_printer_became_busy_does_not_publish_a_printable_file(tmp_path):
    source, output = tmp_path / "part.gcode", tmp_path / "fixed.gcode"
    source.write_bytes(b"G28\nT0\n" + REMAINDER)
    def busy():
        raise ValueError("Printer is now busy")
    with pytest.raises(ValueError, match="busy"):
        fix.write_gcode_copy(source, output, before_publish=busy)
    assert not output.exists()
    assert source.read_bytes() == b"G28\nT0\n" + REMAINDER


def test_orca_template_starts_with_the_existing_owner():
    template = (ROOT / "packages/k1-control-v1/owned-start-print-v2/orca-machine-start.gcode").read_text()
    lines = template.splitlines()
    assert lines[0] == "START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single]"
    assert lines[1:] == ["M104 S[nozzle_temperature_initial_layer]", "M109 S[nozzle_temperature_initial_layer]", "M204 S2000", "G1 Z3 F600", "M83", "G92 E0", "G1 Z1 F600"]


@pytest.mark.parametrize("repaired", [False, True])
def test_recorded_220_degree_failure_against_the_actual_probe_guard(repaired):
    # Replay only the recorded command/temperature boundary, not physical CFS
    # behaviour: on 2026-09-05 T0 left a 220 C setpoint before START_PRINT.
    import jinja2
    from types import SimpleNamespace
    prefix = b"G28\nT0\n" + START
    if repaired:
        prefix, _ = fix.repair_prefix(prefix)
    setpoint = 220 if b"T0" in prefix.splitlines() else 0
    path = ROOT / "packages/k1-control-v1/mesh-acquisition-v2/k1-control-probe-temp-guard-v1.cfg"
    block = path.read_text().split("[gcode_macro _KCTRL_PROBE_GUARD_ON]", 1)[1].split("\n[", 1)[0]
    body = block.split("\ngcode:\n", 1)[1]
    template = jinja2.Environment("{%", "%}", "{", "}").from_string(body)
    def refuse(message):
        raise ValueError(message)
    def render():
        return template.render(params={"CEILING": "105"},
                               printer={"extruder": SimpleNamespace(target=setpoint, temperature=33)},
                               action_raise_error=refuse, action_respond_info=lambda _: "")
    if repaired:
        result = render()
        assert "TEMPERATURE_WAIT SENSOR=extruder MAXIMUM=105.0" in result
    else:
        with pytest.raises(ValueError, match="already targeting 220 C.*105 C"):
            render()
