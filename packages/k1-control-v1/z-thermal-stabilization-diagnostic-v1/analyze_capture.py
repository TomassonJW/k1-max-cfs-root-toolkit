"""Analyze the bounded live trace and prove the thermal soak occurred."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def analyze_records(records: list[dict]) -> dict:
    snapshots = [item for item in records if item.get("kind") == "snapshot"]
    footer = next((item for item in reversed(records) if item.get("kind") == "footer"), {})
    if not snapshots:
        raise ValueError("snapshots_missing")
    soak_printing = [
        item for item in snapshots
        if item["print"].get("state") == "printing"
        and item["owner"].get("phase") == "idle"
        and item["bed"].get("target") == 55.0
        and item["bed"].get("temperature", 0.0) >= 54.8
        and item["nozzle"].get("target") == 0.0
    ]
    soak_observed = 0.0
    if len(soak_printing) >= 2:
        soak_observed = soak_printing[-1]["elapsed_s"] - soak_printing[0]["elapsed_s"]
    phases = []
    for item in snapshots:
        phase = item["owner"].get("phase")
        if phase not in phases:
            phases.append(phase)
    routes = sorted({tuple(item["cfs"]["engaged_routes"]) for item in snapshots})
    commands = sorted({item["cfs"].get("active_command") or "" for item in snapshots})
    soak_nozzle_targets = sorted({item["nozzle"].get("target") for item in soak_printing})
    checks = [
        footer.get("status") == "Z_THERMAL_STABILIZATION_DIAGNOSTIC_AUTOMATION_OK",
        soak_observed >= 195.0,
        soak_nozzle_targets == [0.0],
        routes == [("T1A",)],
        commands == [""],
        all(phase in phases for phase in ("manual_clean_confirmed", "reference_heating", "visible_purge", "model_ready", "idle")),
    ]
    return {
        "status": "Z_THERMAL_STABILIZATION_DIAGNOSTIC_AUTOMATIC_OK" if all(checks) else "Z_THERMAL_STABILIZATION_DIAGNOSTIC_AUTOMATIC_KO",
        "soak_observed_seconds": round(soak_observed, 3),
        "soak_nozzle_targets_c": soak_nozzle_targets,
        "engaged_route_sets": [list(item) for item in routes],
        "active_commands": commands,
        "phases": phases,
        "human_verdict_required": True,
        "automatic_retry": False,
    }


def analyze(path: Path) -> dict:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip().startswith("{")]
    return analyze_records(records)


def main() -> int:
    result = analyze(Path(sys.argv[1]))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"].endswith("_OK") else 1


if __name__ == "__main__":
    raise SystemExit(main())
