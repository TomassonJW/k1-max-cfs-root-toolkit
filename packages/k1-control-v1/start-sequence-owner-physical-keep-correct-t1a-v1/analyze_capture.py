"""Offline automatic classification of the bounded physical start capture."""

import json
import sys
from pathlib import Path


EXPECTED_PHASES = [
    "manual_clean_confirmed",
    "reference_heating",
    "first_layer_heating",
    "visible_purge",
    "model_ready",
]


def analyze(path):
    entries = [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip().startswith("{")]
    snapshots = [entry for entry in entries if entry.get("kind") == "snapshot"]
    phases = []
    for item in snapshots:
        phase = item.get("owner", {}).get("phase")
        if phase and (not phases or phases[-1] != phase):
            phases.append(phase)
    phase_cursor = 0
    for phase in phases:
        if phase_cursor < len(EXPECTED_PHASES) and phase == EXPECTED_PHASES[phase_cursor]:
            phase_cursor += 1
    nozzle_targets = [float(item.get("nozzle", {}).get("target", 0.0)) for item in snapshots]
    bed_targets = [float(item.get("bed", {}).get("target", 0.0)) for item in snapshots]
    routes = {tuple(item.get("cfs", {}).get("engaged_routes", [])) for item in snapshots}
    commands = {item.get("cfs", {}).get("active_command") for item in snapshots}
    footer = next((entry for entry in reversed(entries) if entry.get("kind") == "footer"), {})
    effects = [entry.get("effect") for entry in entries if entry.get("kind") == "effect"]
    final = snapshots[-1] if snapshots else {}
    result = {
        "status": "KEEP_CORRECT_T1A_PHYSICAL_AUTOMATIC_OK",
        "human_verdict_required": True,
        "expected_phases_observed_in_order": phase_cursor == len(EXPECTED_PHASES),
        "phases": phases,
        "max_nozzle_target_c": max(nozzle_targets, default=0.0),
        "max_bed_target_c": max(bed_targets, default=0.0),
        "engaged_route_sets": [list(item) for item in sorted(routes)],
        "active_commands": sorted("" if item is None else str(item) for item in commands),
        "effects": effects,
        "footer_status": footer.get("status"),
        "automatic_retry": False,
    }
    checks = [
        bool(snapshots),
        result["expected_phases_observed_in_order"],
        result["max_nozzle_target_c"] <= 200.5,
        result["max_bed_target_c"] <= 55.5,
        routes == {("T1A",)},
        commands.issubset({None, ""}),
        effects == ["manual_clean_token_once", "print_start_once"],
        footer.get("status") == "KEEP_CORRECT_T1A_PHYSICAL_AUTOMATION_OK",
        final.get("print", {}).get("state") in ("complete", "standby"),
        float(final.get("nozzle", {}).get("target", -1.0)) == 0.0,
        float(final.get("bed", {}).get("target", -1.0)) == 0.0,
        final.get("calibration", {}).get("active_profile") == "k1_p001_t055_r001_n11x11",
        final.get("calibration", {}).get("low_moves_armed") in (0, 0.0),
        final.get("calibration", {}).get("armed_mesh_profile") in (None, "", "none"),
        final.get("owner", {}).get("phase") == "idle",
        final.get("owner", {}).get("watchdog_armed") in (0, 0.0),
        final.get("owner", {}).get("manual_clean_token") in (0, 0.0),
        final.get("motion", {}).get("homed_axes") in (None, ""),
    ]
    if not all(checks):
        result["status"] = "KEEP_CORRECT_T1A_PHYSICAL_AUTOMATIC_KO"
    return result


def main():
    if len(sys.argv) != 2:
        return 2
    result = analyze(sys.argv[1])
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"].endswith("_OK") else 1


if __name__ == "__main__":
    raise SystemExit(main())
