"""Pure start-state decision from one sanitized passive CFS capture.

This module has no printer transport and cannot perform any effect. It turns
the last safe snapshot into KEEP, LOAD, CHANGE or BLOCK. Material identity is
never inferred from a route token.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any, Dict


ROUTE = re.compile(r"^T[12][ABCD]$")


class DecisionError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise DecisionError(code)


def classify(snapshot: Dict[str, Any], intended_route: str, material_identity_confirmed: bool) -> Dict[str, Any]:
    require(bool(ROUTE.fullmatch(intended_route)), "intended_route_invalid")
    cfs = snapshot.get("cfs")
    sensors = snapshot.get("sensors")
    require(isinstance(cfs, dict) and isinstance(sensors, dict), "snapshot_shape_invalid")
    require(cfs.get("state") == "connect", "cfs_root_disconnected")
    require(cfs.get("T1_state") == "connect" and cfs.get("T2_state") == "connect", "cfs_unit_disconnected")
    require(cfs.get("active_command") in (None, ""), "cfs_command_active")
    routes = cfs.get("engaged_routes")
    require(isinstance(routes, list), "engaged_routes_invalid")
    require(all(isinstance(route, str) and ROUTE.fullmatch(route) for route in routes), "engaged_routes_invalid")

    if len(routes) > 1:
        decision = "BLOCK"
        reason = "MULTIPLE_ENGAGED_ROUTES"
    elif not routes:
        if sensors.get("head") is True or sensors.get("after_cutter") is True:
            decision = "BLOCK"
            reason = "SEGMENT_PRESENT_WITHOUT_UNIQUE_ROUTE"
        else:
            decision = "LOAD"
            reason = "PATH_CONFIRMED_EMPTY"
    elif not material_identity_confirmed:
        decision = "BLOCK"
        reason = "MATERIAL_IDENTITY_UNPROVEN"
    elif routes[0] == intended_route:
        decision = "KEEP"
        reason = "CONFIRMED_ROUTE_AND_MATERIAL_MATCH"
    else:
        decision = "CHANGE"
        reason = "CONFIRMED_ENGAGED_ROUTE_DIFFERS"

    return {
        "schema": 1,
        "decision": decision,
        "reason": reason,
        "intended_route": intended_route,
        "observed_routes": routes,
        "material_identity_confirmed": material_identity_confirmed,
        "effects": {
            "gcode": False,
            "heating": False,
            "motion": False,
            "cfs_action": False,
            "remote_write": False,
        },
        "human_physical_verdict_required": True,
    }


def classify_capture(path: Path, intended_route: str, material_identity_confirmed: bool) -> Dict[str, Any]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    require(len(records) >= 3, "capture_shape_invalid")
    require(records[0].get("kind") == "header" and records[-1].get("kind") == "footer", "capture_shape_invalid")
    require(records[0].get("effects") == {"gcode": False, "remote_write": False, "service_action": False}, "capture_effect_contract_invalid")
    require(records[-1].get("configuration_unchanged") is True, "configuration_changed")
    snapshots = [record for record in records[1:-1] if record.get("kind") == "snapshot"]
    require(bool(snapshots), "snapshots_missing")
    result = classify(snapshots[-1], intended_route, material_identity_confirmed)
    result["capture_path"] = str(path)
    result["snapshot_count"] = len(snapshots)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--intended-route", required=True)
    parser.add_argument("--material-identity-confirmed", action="store_true")
    args = parser.parse_args()
    try:
        result = classify_capture(args.capture, args.intended_route, args.material_identity_confirmed)
    except Exception as exc:
        print(json.dumps({"status": "CFS_START_DECISION_KO", "error": f"{type(exc).__name__}:{exc}"}, sort_keys=True))
        return 1
    result["status"] = "CFS_START_DECISION_OK"
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
