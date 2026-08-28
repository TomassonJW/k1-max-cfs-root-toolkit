"""Offline analyzer for a START-SEQUENCE-T1A-ROUTE-V1 JSONL capture."""

from __future__ import print_function

import json
import math
import sys
from pathlib import Path


BEST_PROFILE = "k1_p001_t055_r001_n11x11"
ACCEPTED_Z_OFFSET = -0.04


class AnalysisError(ValueError):
    pass


def finite(value, code):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnalysisError(code)
    result = float(value)
    if not math.isfinite(result):
        raise AnalysisError(code)
    return result


def load_records(path):
    records = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AnalysisError("invalid_json_line_%s" % line_number) from exc
        if not isinstance(record, dict):
            raise AnalysisError("record_not_object_line_%s" % line_number)
        records.append(record)
    return records


def xyz(snapshot):
    position = snapshot.get("motion", {}).get("gcode_position")
    if not isinstance(position, list) or len(position) < 3:
        raise AnalysisError("gcode_position_invalid")
    return tuple(finite(position[index], "gcode_position_invalid") for index in range(3))


def compressed_route_states(snapshots):
    states = []
    for snapshot in snapshots:
        routes = snapshot.get("cfs", {}).get("engaged_routes")
        if routes not in ([], ["T1A"]):
            raise AnalysisError("unexpected_or_ambiguous_route")
        if not states or states[-1] != routes:
            states.append(routes)
    return states


def analyze_records(records):
    headers = [record for record in records if record.get("kind") == "header"]
    footers = [record for record in records if record.get("kind") == "footer"]
    snapshots = [record for record in records if record.get("kind") == "snapshot"]
    if len(headers) != 1 or len(footers) != 1:
        raise AnalysisError("header_or_footer_count_invalid")
    if len(snapshots) < 3:
        raise AnalysisError("snapshot_count_too_small")
    header = headers[0]
    footer = footers[0]
    if header.get("mission") != "G4-K1-CONTROL-START-SEQUENCE-T1A-ROUTE-V1":
        raise AnalysisError("mission_mismatch")
    if header.get("operator_action") != "stock_ui_load_T1A_once":
        raise AnalysisError("operator_action_mismatch")
    if header.get("effects") != {"gcode": False, "remote_write": False, "service_action": False}:
        raise AnalysisError("observer_effect_declared")
    if footer.get("status") != "T1A_ROUTE_OBSERVATION_OK":
        raise AnalysisError("observer_footer_not_ok")
    if footer.get("configuration_unchanged") is not True:
        raise AnalysisError("configuration_changed")
    if footer.get("hashes_after") != header.get("hashes_before"):
        raise AnalysisError("configuration_hashes_changed")

    first_xyz = xyz(snapshots[0])
    first_homed_axes = snapshots[0].get("motion", {}).get("homed_axes")
    maximum_nozzle_target = 0.0
    for snapshot in snapshots:
        if snapshot.get("print_state") != "standby" or snapshot.get("filename_present"):
            raise AnalysisError("print_state_changed")
        cfs = snapshot.get("cfs", {})
        if cfs.get("state") != "connect" or cfs.get("T1_state") != "connect" or cfs.get("T2_state") != "connect":
            raise AnalysisError("cfs_disconnected")
        if xyz(snapshot) != first_xyz:
            raise AnalysisError("xyz_motion_observed")
        if snapshot.get("motion", {}).get("homed_axes") != first_homed_axes:
            raise AnalysisError("homed_axes_changed")
        calibration = snapshot.get("calibration", {})
        if calibration.get("active_profile") != BEST_PROFILE:
            raise AnalysisError("active_profile_drift")
        if calibration.get("accepted_z_valid") != 1:
            raise AnalysisError("accepted_z_invalid")
        if abs(finite(calibration.get("accepted_z_offset"), "accepted_z_invalid") - ACCEPTED_Z_OFFSET) > 0.0005:
            raise AnalysisError("accepted_z_drift")
        owner = snapshot.get("start_owner", {})
        if owner.get("phase") != "idle" or owner.get("watchdog_armed") not in (0, 0.0):
            raise AnalysisError("start_owner_state_changed")
        maximum_nozzle_target = max(
            maximum_nozzle_target,
            finite(snapshot.get("nozzle", {}).get("target_c"), "nozzle_target_invalid"),
        )
        finite(snapshot.get("bed", {}).get("target_c"), "bed_target_invalid")

    route_states = compressed_route_states(snapshots)
    if route_states != [[], ["T1A"]]:
        raise AnalysisError("single_route_transition_not_proved")
    final = snapshots[-1]
    penultimate = snapshots[-2]
    for stable in (penultimate, final):
        if stable.get("cfs", {}).get("engaged_routes") != ["T1A"]:
            raise AnalysisError("final_T1A_not_stable")
        if stable.get("cfs", {}).get("active_command") not in (None, ""):
            raise AnalysisError("final_cfs_command_not_empty")

    final_nozzle_target = finite(final.get("nozzle", {}).get("target_c"), "final_nozzle_target_invalid")
    final_bed_target = finite(final.get("bed", {}).get("target_c"), "final_bed_target_invalid")
    status = "START_SEQUENCE_T1A_ROUTE_V1_TECHNICAL_OK"
    if final_nozzle_target != 0.0 or final_bed_target != 0.0:
        status = "START_SEQUENCE_T1A_ROUTE_V1_SAFE_STOP_REQUIRED_HEATER_TARGET_NONZERO"
    return {
        "status": status,
        "snapshot_count": len(snapshots),
        "route_states": route_states,
        "route_transition_count": 1,
        "final_routes": final.get("cfs", {}).get("engaged_routes"),
        "final_active_command": final.get("cfs", {}).get("active_command"),
        "maximum_nozzle_target_c": maximum_nozzle_target,
        "final_nozzle_target_c": final_nozzle_target,
        "final_bed_target_c": final_bed_target,
        "xyz_unchanged": True,
        "mesh_and_z_unchanged": True,
        "configuration_unchanged": True,
        "observer_effect": False,
    }


def analyze_path(path):
    return analyze_records(load_records(path))


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print(json.dumps({"status": "INVALID_ARGUMENTS"}, sort_keys=True))
        return 2
    try:
        result = analyze_path(arguments[0])
    except Exception as exc:
        print(json.dumps({"status": "START_SEQUENCE_T1A_ROUTE_V1_KO", "error": "%s:%s" % (type(exc).__name__, exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    if result["status"].endswith("SAFE_STOP_REQUIRED_HEATER_TARGET_NONZERO"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
