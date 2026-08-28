"""Classify a passive T1A to T2C stock-change capture."""

import json
import sys
from pathlib import Path


def compress(values):
    result = []
    for value in values:
        if not result or result[-1] != value:
            result.append(value)
    return result


def analyze(path):
    entries = [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip().startswith("{")]
    snapshots = [entry for entry in entries if entry.get("kind") == "snapshot"]
    route_timeline = compress([tuple(item.get("cfs", {}).get("engaged_routes", [])) for item in snapshots])
    nozzle_targets = [float(item.get("nozzle", {}).get("target", 0.0)) for item in snapshots]
    commands = [item.get("cfs", {}).get("active_command") for item in snapshots]
    t1a_release_index = next((i for i, item in enumerate(snapshots) if item.get("cfs", {}).get("engaged_routes", []) != ["T1A"]), None)
    t2c_index = next((i for i, item in enumerate(snapshots) if item.get("cfs", {}).get("engaged_routes", []) == ["T2C"]), None)
    positive_before_release = bool(t1a_release_index is not None and any(value > 0.0 for value in nozzle_targets[:t1a_release_index + 1]))
    positive_after_t2c = bool(t2c_index is not None and any(value > 0.0 for value in nozzle_targets[t2c_index:]))
    footer = next((entry for entry in reversed(entries) if entry.get("kind") == "footer"), {})
    final = snapshots[-1] if snapshots else {}
    allowed_routes = {("T1A",), (), ("T2C",)}
    result = {
        "status": "WRONG_CHANGE_T1A_TO_T2C_AUTOMATIC_OK",
        "human_visible_purge_verdict_required": True,
        "route_timeline": [list(item) for item in route_timeline],
        "maximum_nozzle_target_c": max(nozzle_targets, default=0.0),
        "positive_target_before_T1A_release": positive_before_release,
        "positive_target_after_T2C_engagement": positive_after_t2c,
        "active_command_observed": any(item not in (None, "") for item in commands),
        "automatic_retry": False,
        "footer_status": footer.get("status"),
    }
    checks = [
        bool(snapshots),
        route_timeline[0] == ("T1A",) if route_timeline else False,
        route_timeline[-1] == ("T2C",) if route_timeline else False,
        all(item in allowed_routes for item in route_timeline),
        sum(item == ("T2C",) for item in route_timeline) == 1,
        positive_before_release,
        positive_after_t2c,
        final.get("cfs", {}).get("active_command") in (None, ""),
        float(final.get("nozzle", {}).get("target", -1.0)) == 0.0,
        float(final.get("bed", {}).get("target", -1.0)) == 0.0,
        final.get("calibration", {}).get("active_profile") == "k1_p001_t055_r001_n11x11",
        final.get("calibration", {}).get("accepted_z_offset") == -0.04,
        footer.get("status") == "WRONG_CHANGE_OBSERVATION_OK",
    ]
    if not all(checks):
        result["status"] = "WRONG_CHANGE_T1A_TO_T2C_AUTOMATIC_KO"
    return result


def main():
    if len(sys.argv) != 2:
        return 2
    result = analyze(sys.argv[1])
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"].endswith("_OK") else 1


if __name__ == "__main__":
    raise SystemExit(main())
