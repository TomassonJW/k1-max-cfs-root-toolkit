#!/usr/bin/env python3
"""Valide la cohérence documentaire et les scénarios du paquet hors K1."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import run_scenarios  # type: ignore


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_json(name: str):
    with (HERE / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    required = [
        "README.md",
        "RESULT.md",
        "contract.json",
        "evidence-map.json",
        "owner.py",
        "protocol.py",
        "runtime_adapter.py",
        "run_scenarios.py",
    ]
    for name in required:
        require((HERE / name).is_file(), "required_file_missing_%s" % name)

    for path in HERE.glob("*.py"):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
            feature_version=(3, 8),
        )

    contract = load_json("contract.json")
    evidence = load_json("evidence-map.json")
    require(contract["status"] == "CLOSED_OK_OFFLINE_24_OF_24", "contract_status")
    require(contract["decision"] == "ADR-036", "contract_decision")
    require(contract["scope"]["printer_transport"] is False, "printer_transport")
    require(contract["scope"]["physical_action"] is False, "physical_action")
    require(contract["scope"]["deployment_candidate"] is False, "deployment")
    require(contract["transport"]["automatic_retry"] is False, "retry_contract")
    require(
        contract["failure_policy"]["effect_id_once_only"] is True,
        "effect_id_contract",
    )
    require(len(contract["routes"]["allowed"]) == 8, "route_count")
    require(
        evidence["precedence"][0] == "exact_local_K1_log",
        "evidence_precedence",
    )
    require(len(evidence["public_cross_checks"]) == 3, "public_cross_checks")

    owner_text = (HERE / "owner.py").read_text(encoding="utf-8")
    forbidden_runtime_tokens = [
        "START_PRINT",
        "END_PRINT",
        "BOX_EXTRUDE_MATERIAL",
        "BOX_RETRUDE_MATERIAL",
        "BED_MESH_CLEAR",
        "G28",
        "M104",
        "M109",
    ]
    for token in forbidden_runtime_tokens:
        require(token not in owner_text, "forbidden_owner_token_%s" % token)
    require("retry=False" in owner_text, "explicit_retry_false_missing")

    report = run_scenarios.run_all()
    require(report["status"] == "OK", "scenario_status")
    require(report["scenario_count"] == 24, "scenario_count")
    require(report["ok_count"] == 24, "scenario_ok_count")
    require(report["ko_count"] == 0, "scenario_ko_count")
    require(report["printer_transport"] is False, "scenario_printer_transport")
    require(report["physical_action"] is False, "scenario_physical_action")

    test_path = ROOT / "tests" / "test_cfs_direct_owner_offline_v1.py"
    require(test_path.is_file(), "repository_test_missing")
    ast.parse(
        test_path.read_text(encoding="utf-8"),
        filename=str(test_path),
        feature_version=(3, 8),
    )

    adr_path = ROOT / "docs" / "adr" / (
        "ADR-036-proprietaire-cfs-direct-sur-transport-serie-borne.md"
    )
    require(adr_path.is_file(), "adr_036_missing")
    print("VERIFY_CFS_DIRECT_OWNER_OFFLINE_V1_OK 24/24")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
