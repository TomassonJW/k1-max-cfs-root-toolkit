"""Classify a passive T2C to T1A stock-return capture."""

from __future__ import annotations

import json
from pathlib import Path
import sys


START_ROUTE = "T2C"
TARGET_ROUTE = "T1A"


def compress(values):
    result = []
    for value in values:
        if not result or result[-1] != value:
            result.append(value)
    return result


def analyze(path):
    entries = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines()
        if line.strip().startswith("{")
    ]
    snapshots = [entry for entry in entries if entry.get("kind") == "snapshot"]
    route_timeline = compress([tuple(item.get("cfs", {}).get("engaged_routes", [])) for item in snapshots])
    nozzle_targets = [float(item.get("nozzle", {}).get("target", 0.0)) for item in snapshots]
    commands = [item.get("cfs", {}).get("active_command") for item in snapshots]
    release_index = next(
        (i for i, item in enumerate(snapshots) if item.get("cfs", {}).get("engaged_routes", []) != [START_ROUTE]),
        None,
    )
    target_index = next(
        (i for i, item in enumerate(snapshots) if item.get("cfs", {}).get("engaged_routes", []) == [TARGET_ROUTE]),
        None,
    )
    positive_before_release = bool(
        release_index is not None and any(value > 0.0 for value in nozzle_targets[: release_index + 1])
    )
    positive_after_target = bool(
        target_index is not None and any(value > 0.0 for value in nozzle_targets[target_index:])
    )
    footer = next((entry for entry in reversed(entries) if entry.get("kind") == "footer"), {})
    final = snapshots[-1] if snapshots else {}
    allowed_routes = {(START_ROUTE,), (), (TARGET_ROUTE,)}
    checks = {
        "snapshots_present": bool(snapshots),
        "starts_T2C": route_timeline[0] == (START_ROUTE,) if route_timeline else False,
        "ends_T1A": route_timeline[-1] == (TARGET_ROUTE,) if route_timeline else False,
        "only_reviewed_routes": all(item in allowed_routes for item in route_timeline),
        "exact_release_then_engage_sequence": route_timeline == [(START_ROUTE,), (), (TARGET_ROUTE,)],
        "T1A_engaged_once": sum(item == (TARGET_ROUTE,) for item in route_timeline) == 1,
        "positive_target_before_T2C_release": positive_before_release,
        "positive_target_after_T1A_engagement": positive_after_target,
        "final_command_empty": final.get("cfs", {}).get("active_command") in (None, ""),
        "final_nozzle_target_zero": float(final.get("nozzle", {}).get("target", -1.0)) == 0.0,
        "final_bed_target_zero": float(final.get("bed", {}).get("target", -1.0)) == 0.0,
        "best_mesh_retained": final.get("calibration", {}).get("active_profile") == "k1_p001_t055_r001_n11x11",
        "accepted_z_retained": final.get("calibration", {}).get("accepted_z_offset") == -0.04,
        "owner_idle": final.get("owner", {}).get("phase") == "idle",
        "low_moves_disarmed": final.get("calibration", {}).get("low_moves_armed") in (0, 0.0),
        "configuration_unchanged": footer.get("status") == "RETURN_T2C_TO_T1A_OBSERVATION_OK",
        "stable_terminal_target": footer.get("stable_terminal_target_reads", 0) >= 4,
    }
    return {
        "status": "RETURN_T2C_TO_T1A_AUTOMATIC_OK" if all(checks.values()) else "RETURN_T2C_TO_T1A_AUTOMATIC_KO",
        "checks": checks,
        "human_visible_purge_verdict_required": True,
        "route_timeline": [list(item) for item in route_timeline],
        "maximum_nozzle_target_c": max(nozzle_targets, default=0.0),
        "active_command_observed": any(item not in (None, "") for item in commands),
        "automatic_retry": False,
        "footer_status": footer.get("status"),
    }


def main():
    if len(sys.argv) != 2:
        return 2
    result = analyze(sys.argv[1])
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"].endswith("_OK") else 1


if __name__ == "__main__":
    raise SystemExit(main())
