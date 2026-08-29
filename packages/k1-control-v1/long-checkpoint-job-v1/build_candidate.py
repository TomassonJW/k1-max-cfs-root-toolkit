"""Build an inert private long job candidate from the qualified R2 two-layer job."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
SOURCE = (
    ROOT
    / "inventory"
    / "raw"
    / "20260829-goal3-z-thermal-stabilization-diagnostic-v1"
    / "K1-Z-THERMAL-SOAK-200S-T1A-2LAYER.gcode"
)
OUTPUT = (
    ROOT
    / "inventory"
    / "raw"
    / "20260829-goal3-long-checkpoint-job-v1"
    / "K1-LONG-CHECKPOINT-T1A-8LAYER.gcode"
)
SOURCE_SHA256 = "c4ce0bf765db36322594ed6e3a608a15c9b1f57b6421553c46f4bdcdd4fc574f"
TOTAL_LAYERS = 8
BASE_TEMPLATE_Z = 0.4
LAYER_HEIGHT = 0.2
TOOL_CHANGE_LAYER = 3
RUNOUT_LAYER = 6
START_MACRO = (
    "KCTRL_JOB_BEGIN_KEEP_CORRECT_V1 BED=55 PROBE_NOZZLE=140 FIRST_NOZZLE=190 "
    "PLATE=1 PROBE_REV=1 NOZZLE_ID=1 CONFIG_ID=1 X_COUNT=11 Y_COUNT=11"
)
SAFE_END = [
    "KCTRL_START_ABORT_V1",
    "KCTRL_CLEAR_MANUAL_NOZZLE_CLEAN_V1",
    "TURN_OFF_HEATERS",
    "G1 Z50 F600",
    "G1 X203 Y273 F1200",
    "M400",
    "M84",
]
Z_TOKEN = re.compile(r"(?P<prefix>\bZ)(?P<value>-?(?:\d+(?:\.\d*)?|\.\d+))")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def format_number(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def shift_motion_z(line: str, delta: float) -> str:
    if not line.lstrip().startswith(("G0 ", "G1 ")):
        return line

    def replace(match: re.Match[str]) -> str:
        value = float(match.group("value")) + delta
        return match.group("prefix") + format_number(value)

    return Z_TOKEN.sub(replace, line)


def layer_template(lines: list[str], second_layer: int, insert_at: int) -> list[str]:
    template = list(lines[second_layer:insert_at])
    start_index = next(index for index, line in enumerate(template) if line.startswith("EXCLUDE_OBJECT_START "))
    leading_closes = [
        index
        for index, line in enumerate(template[:start_index])
        if line.startswith("EXCLUDE_OBJECT_END ")
    ]
    if len(leading_closes) != 1:
        raise ValueError("second_layer_leading_object_close_not_unique")
    del template[leading_closes[0]]
    return template


def render_extra_layer(template: list[str], layer_number: int) -> list[str]:
    target_z = layer_number * LAYER_HEIGHT
    delta = target_z - BASE_TEMPLATE_Z
    rendered = []
    marker = None
    if layer_number == TOOL_CHANGE_LAYER:
        marker = ";KCTRL_CHECKPOINT_WINDOW TOOL_CHANGE_T1A_TO_T2C\n"
    elif layer_number == RUNOUT_LAYER:
        marker = ";KCTRL_CHECKPOINT_WINDOW RUNOUT_T2_EQUIVALENT\n"
    for line in template:
        stripped = line.strip()
        if stripped.startswith("M73 "):
            continue
        if stripped == ";LAYER_CHANGE" and marker is not None:
            rendered.append(marker)
        if stripped == ";Z:0.4":
            line = line.replace(";Z:0.4", ";Z:" + format_number(target_z))
        elif stripped == ";0.4":
            line = line.replace(";0.4", ";" + format_number(target_z))
        rendered.append(shift_motion_z(line, delta))
    return rendered


def executable_lines(candidate: bytes) -> list[str]:
    text = candidate.decode("utf-8")
    start = text.index("; EXECUTABLE_BLOCK_START")
    end = text.index("; EXECUTABLE_BLOCK_END")
    return [line.strip() for line in text[start:end].splitlines() if line.strip() and not line.lstrip().startswith(";")]


def validate(candidate: bytes) -> dict:
    text = candidate.decode("utf-8")
    lines = text.splitlines()
    executable = executable_lines(candidate)
    if text.count(";LAYER_CHANGE") != TOTAL_LAYERS:
        raise ValueError("layer_count_mismatch")
    if text.count(";KCTRL_CHECKPOINT_WINDOW TOOL_CHANGE_T1A_TO_T2C") != 1:
        raise ValueError("tool_change_marker_missing_or_duplicate")
    if text.count(";KCTRL_CHECKPOINT_WINDOW RUNOUT_T2_EQUIVALENT") != 1:
        raise ValueError("runout_marker_missing_or_duplicate")
    if executable.count(START_MACRO) != 1:
        raise ValueError("owned_start_not_unique")
    for command in SAFE_END:
        if executable.count(command) != 1:
            raise ValueError("safe_end_command_missing_or_duplicate:%s" % command)
    park_sequence = ["TURN_OFF_HEATERS", "G90", "G1 Z50 F600", "G1 X203 Y273 F1200", "M400", "M84"]
    if sum(
        executable[index : index + len(park_sequence)] == park_sequence
        for index in range(len(executable) - len(park_sequence) + 1)
    ) != 1:
        raise ValueError("safe_end_park_sequence_missing_or_duplicate")
    if any(re.fullmatch(r"T\d+", line) for line in executable):
        raise ValueError("executable_tool_select_forbidden")
    for forbidden in ("START_PRINT", "END_PRINT", "G28", "BOX_"):
        if any(forbidden in line for line in executable):
            raise ValueError("forbidden_executable_command:%s" % forbidden)
    if any(line.startswith("M73 ") for line in executable):
        raise ValueError("stale_progress_command_present")
    if executable.index("G1 Z50 F600") > executable.index("G1 X203 Y273 F1200"):
        raise ValueError("safe_end_park_order_invalid")
    if executable.index("G1 X203 Y273 F1200") > executable.index("M84"):
        raise ValueError("axes_released_before_park")
    expected_z = [format_number(index * LAYER_HEIGHT) for index in range(1, TOTAL_LAYERS + 1)]
    observed_z = [line.split(":", 1)[1] for line in lines if line.startswith(";Z:")]
    if observed_z != expected_z:
        raise ValueError("layer_z_sequence_mismatch")
    return {
        "status": "LONG_CHECKPOINT_JOB_V1_CANDIDATE_OK",
        "sha256": digest(candidate),
        "bytes": len(candidate),
        "layers": TOTAL_LAYERS,
        "tool_change_window_layer": TOOL_CHANGE_LAYER,
        "runout_window_layer": RUNOUT_LAYER,
        "executable_T_commands": 0,
        "connector": False,
        "production_authorized": False,
    }


def derive(source: bytes) -> bytes:
    if digest(source) != SOURCE_SHA256:
        raise ValueError("source_gcode_hash_drift")
    text = source.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    layer_indices = [index for index, line in enumerate(lines) if line.strip() == ";LAYER_CHANGE"]
    if len(layer_indices) != 2:
        raise ValueError("source_layer_count_drift")
    second_layer = layer_indices[1]
    executable_end = next(
        index for index, line in enumerate(lines[second_layer:], start=second_layer)
        if line.strip() == "; EXECUTABLE_BLOCK_END"
    )
    object_ends = [
        index
        for index, line in enumerate(lines[second_layer:executable_end], start=second_layer)
        if line.startswith("EXCLUDE_OBJECT_END ")
    ]
    if len(object_ends) != 2:
        raise ValueError("second_layer_object_end_shape_drift")
    insert_at = object_ends[-1] + 1
    template = layer_template(lines, second_layer, insert_at)
    extras = []
    for layer_number in range(3, TOTAL_LAYERS + 1):
        extras.extend(render_extra_layer(template, layer_number))
    candidate_lines = lines[:insert_at] + extras + lines[insert_at:]
    candidate_lines = [
        line
        for line in candidate_lines
        if not line.strip().startswith("M73 ") and line.strip() != "; MANUAL_TOOL_CHANGE T0"
    ]
    candidate = "".join(candidate_lines)
    candidate = re.sub(r"; total layers count = \d+", "; total layers count = %d" % TOTAL_LAYERS, candidate)
    note = (
        "; LONG_CHECKPOINT_JOB_V1_OFFLINE_CANDIDATE\n"
        "; physical timing and T2 recipe remain human-gated\n"
    ).replace("\n", newline)
    candidate = candidate.replace("; EXECUTABLE_BLOCK_START" + newline, "; EXECUTABLE_BLOCK_START" + newline + note, 1)
    encoded = candidate.encode("utf-8")
    validate(encoded)
    return encoded


def build() -> dict:
    candidate = derive(SOURCE.read_bytes())
    if OUTPUT.is_file():
        if OUTPUT.read_bytes() != candidate:
            raise ValueError("persisted_candidate_drift")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_bytes(candidate)
    result = validate(candidate)
    result.update({"source_sha256": SOURCE_SHA256, "output": str(OUTPUT)})
    return result


def main() -> int:
    print(json.dumps(build(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
