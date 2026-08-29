"""Analyze a sanitized passive print-lifecycle observation."""

from __future__ import annotations

import json
from pathlib import Path
import sys


MISSION = "G4-K1-CONTROL-JOB-LIFECYCLE-OBSERVER-V1"
ALLOWED_CHECKPOINTS = {"FULL_CYCLE", "TOOL_CHANGE", "RUNOUT_RECOVERY", "PAUSE_RESUME", "CANCEL", "NORMAL_END", "DISENGAGE"}
FORBIDDEN_IDENTITY_KEYS = {"sn", "uuid", "rfid", "serial", "serial_number", "filename", "file_path"}


class AnalysisError(ValueError):
    pass


def compressed(values):
    result = []
    for value in values:
        if not result or result[-1] != value:
            result.append(value)
    return result


def contains_forbidden_identity(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_IDENTITY_KEYS or contains_forbidden_identity(child):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_identity(child) for child in value)
    return False


def numeric(value, code):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnalysisError(code)
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise AnalysisError(code)
    return result


def has_false_after_true(values):
    seen_true = False
    for value in values:
        if value is True:
            seen_true = True
        elif seen_true and value is False:
            return True
    return False


def checkpoint_checks(checkpoint, snapshots, summary):
    first = snapshots[0]
    final = snapshots[-1]
    print_states = summary["print_state_sequence"]
    pause_states = summary["pause_state_sequence"]
    route_states = summary["route_states"]
    common = {
        "mesh_and_z_stable": summary["mesh_and_z_stable"],
        "no_ambiguous_route": not summary["ambiguous_route_observed"],
        "watchdog_never_armed": summary["start_watchdog_states"] in ([0], [0.0]),
        "manual_clean_token_never_active": summary["manual_clean_token_states"] in ([0], [0.0]),
    }
    terminal_owner_safe = (
        final.get("start_owner", {}).get("phase") == "idle"
        and final.get("start_owner", {}).get("watchdog_armed") in (0, 0.0)
        and final.get("start_owner", {}).get("manual_clean_token") in (0, 0.0)
        and final.get("calibration", {}).get("low_moves_armed") in (0, 0.0)
        and final.get("calibration", {}).get("armed_mesh_profile") in (None, "", "none")
    )
    active_owner_safe = (
        summary["start_owner_phase_states"] == ["model_ready"]
        and summary["low_moves_armed_states"] in ([1], [1.0])
        and summary["armed_mesh_profile_states"] == ["k1_p001_t055_r001_n11x11"]
    )
    if checkpoint == "PAUSE_RESUME":
        specific = {
            "pause_observed": True in pause_states,
            "resume_observed_after_pause": has_false_after_true(pause_states),
            "route_unchanged": len(route_states) == 1,
            "active_owner_and_geometry_remain_armed": active_owner_safe,
        }
    elif checkpoint == "TOOL_CHANGE":
        specific = {
            "single_route_change_observed": len(route_states) == 2 and route_states[0] != route_states[-1],
            "cfs_command_observed": any(value not in (None, "") for value in summary["active_command_states"]),
            "active_owner_and_geometry_remain_armed": active_owner_safe,
        }
    elif checkpoint == "RUNOUT_RECOVERY":
        specific = {
            "pause_observed": True in pause_states,
            "resume_observed_after_pause": has_false_after_true(pause_states),
            "route_change_observed": len(route_states) >= 2,
            "active_owner_and_geometry_remain_armed": active_owner_safe,
        }
    elif checkpoint == "CANCEL":
        specific = {
            "active_state_observed": any(value in ("printing", "paused") for value in print_states),
            "terminal_state_observed": print_states[-1] not in ("printing", "paused"),
            "terminal_heaters_zero": summary["terminal_heater_targets_zero"],
            "terminal_owner_and_geometry_disarmed": terminal_owner_safe,
        }
    elif checkpoint == "NORMAL_END":
        specific = {
            "printing_observed": "printing" in print_states,
            "normal_terminal_state_observed": print_states[-1] in ("complete", "standby"),
            "route_unchanged": len(route_states) == 1,
            "terminal_heaters_zero": summary["terminal_heater_targets_zero"],
            "terminal_owner_and_geometry_disarmed": terminal_owner_safe,
        }
    elif checkpoint == "DISENGAGE":
        specific = {
            "one_starting_route_observed": len(first.get("cfs", {}).get("engaged_routes", [])) == 1,
            "final_route_empty": final.get("cfs", {}).get("engaged_routes") == [],
            "final_cfs_command_empty": final.get("cfs", {}).get("active_command") in (None, ""),
            "terminal_heaters_zero": summary["terminal_heater_targets_zero"],
            "terminal_owner_and_geometry_disarmed": terminal_owner_safe,
        }
    else:
        specific = {
            "printing_observed": "printing" in print_states,
            "terminal_state_observed": print_states[-1] in ("complete", "standby"),
            "terminal_heaters_zero": summary["terminal_heater_targets_zero"],
            "terminal_owner_and_geometry_disarmed": terminal_owner_safe,
        }
    result = dict(common)
    result.update(specific)
    return result


def analyze(path):
    records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(records) < 3 or records[0].get("kind") != "header" or records[-1].get("kind") != "footer":
        raise AnalysisError("capture_shape_invalid")
    header = records[0]
    footer = records[-1]
    snapshots = [record for record in records[1:-1] if record.get("kind") == "snapshot"]
    if header.get("schema") != 1 or header.get("mission") != MISSION:
        raise AnalysisError("capture_contract_invalid")
    if header.get("checkpoint") not in ALLOWED_CHECKPOINTS:
        raise AnalysisError("checkpoint_invalid")
    if header.get("effects") != {"gcode": False, "remote_write": False, "service_action": False}:
        raise AnalysisError("observer_effect_contract_invalid")
    if contains_forbidden_identity(records):
        raise AnalysisError("identity_field_exported")
    if not snapshots or footer.get("snapshot_count") != len(snapshots):
        raise AnalysisError("snapshot_count_mismatch")
    if footer.get("status") != "JOB_LIFECYCLE_OBSERVATION_OK":
        raise AnalysisError("terminal_status_invalid")
    if header.get("hashes_before") != footer.get("hashes_after") or footer.get("configuration_unchanged") is not True:
        raise AnalysisError("configuration_changed")
    elapsed = [numeric(snapshot.get("elapsed_s"), "elapsed_invalid") for snapshot in snapshots]
    if elapsed != sorted(elapsed):
        raise AnalysisError("elapsed_not_monotonic")
    for snapshot in snapshots:
        routes = snapshot.get("cfs", {}).get("engaged_routes")
        if not isinstance(routes, list) or any(route not in {"T1A", "T1B", "T1C", "T1D", "T2A", "T2B", "T2C", "T2D"} for route in routes):
            raise AnalysisError("engaged_routes_invalid")
    route_states = compressed([snapshot["cfs"]["engaged_routes"] for snapshot in snapshots])
    nozzle_targets = [numeric(snapshot["heaters"]["nozzle_target_c"], "nozzle_target_invalid") for snapshot in snapshots]
    bed_targets = [numeric(snapshot["heaters"]["bed_target_c"], "bed_target_invalid") for snapshot in snapshots]
    profile_states = compressed([snapshot["calibration"]["active_profile"] for snapshot in snapshots])
    accepted_z_states = compressed([snapshot["calibration"]["accepted_z_offset"] for snapshot in snapshots])
    homed_states = compressed([snapshot["motion"]["homed_axes"] for snapshot in snapshots])
    summary = {
        "schema": 1,
        "status": "JOB_LIFECYCLE_ANALYSIS_OK",
        "checkpoint": header["checkpoint"],
        "snapshot_count": len(snapshots),
        "configuration_unchanged": True,
        "print_state_sequence": compressed([snapshot["job"]["print_state"] for snapshot in snapshots]),
        "pause_state_sequence": compressed([snapshot["job"]["is_paused"] for snapshot in snapshots]),
        "virtual_sd_active_sequence": compressed([snapshot["job"]["virtual_sd_active"] for snapshot in snapshots]),
        "idle_state_sequence": compressed([snapshot["job"]["idle_state"] for snapshot in snapshots]),
        "route_states": route_states,
        "route_transition_count": max(0, len(route_states) - 1),
        "active_command_states": compressed([snapshot["cfs"]["active_command"] for snapshot in snapshots]),
        "head_sensor_states": compressed([snapshot["sensors"]["head"] for snapshot in snapshots]),
        "after_cutter_sensor_states": compressed([snapshot["sensors"]["after_cutter"] for snapshot in snapshots]),
        "maximum_nozzle_target_c": max(nozzle_targets),
        "maximum_bed_target_c": max(bed_targets),
        "terminal_heater_targets_zero": nozzle_targets[-1] == 0.0 and bed_targets[-1] == 0.0,
        "active_profile_states": profile_states,
        "accepted_z_states": accepted_z_states,
        "homed_axes_states": homed_states,
        "mesh_and_z_stable": profile_states == ["k1_p001_t055_r001_n11x11"] and accepted_z_states == [-0.04],
        "ambiguous_route_observed": any(len(routes) > 1 for routes in route_states),
        "low_moves_armed_states": compressed([snapshot["calibration"].get("low_moves_armed") for snapshot in snapshots]),
        "armed_mesh_profile_states": compressed([snapshot["calibration"].get("armed_mesh_profile") for snapshot in snapshots]),
        "start_owner_phase_states": compressed([snapshot.get("start_owner", {}).get("phase") for snapshot in snapshots]),
        "start_watchdog_states": compressed([snapshot.get("start_owner", {}).get("watchdog_armed") for snapshot in snapshots]),
        "manual_clean_token_states": compressed([snapshot.get("start_owner", {}).get("manual_clean_token") for snapshot in snapshots]),
        "human_physical_verdict_required": True,
        "observer_effect": False,
        "identity_fields_exported": False
    }
    checks = checkpoint_checks(header["checkpoint"], snapshots, summary)
    summary["automatic_checkpoint_checks"] = checks
    summary["automatic_checkpoint_evidence_status"] = (
        "COMPLETE" if all(checks.values()) else "INCOMPLETE"
    )
    return summary


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print("usage: analyze_observation.py <safe-jsonl>", file=sys.stderr)
        return 2
    try:
        result = analyze(arguments[0])
    except Exception as exc:
        print(json.dumps({"status": "JOB_LIFECYCLE_ANALYSIS_KO", "error": "%s:%s" % (type(exc).__name__, exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
