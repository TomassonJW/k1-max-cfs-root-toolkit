#!/usr/bin/env python3
"""Verify the durable calibration-before-insertion rule without K1 access."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parent
CONTRACT = PACKAGE / "contract.json"
PREFLIGHT = PACKAGE / "preflight-evidence.json"
R3_CONTRACT = ROOT / "packages/k1-control-v1/start-sequence-owner-camera-purge-r3/contract.json"
R3_CFG = ROOT / "packages/k1-control-v1/start-sequence-owner-camera-purge-r3/k1-control-start-sequence-owner-camera-purge-r3.cfg"
ADR = ROOT / "docs/adr/ADR-034-calibrations-avant-insertion-filament.md"
CYCLE = ROOT / "docs/25-contrat-cycle-impression-nettoyage-cfs-v1.md"
AGENTS = ROOT / "AGENTS.md"


def ordered(items: list[str], before: str, after: str) -> None:
    if items.index(before) >= items.index(after):
        raise ValueError(f"wrong_order:{before}:{after}")


def verify() -> dict[str, object]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    evidence = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    r3 = json.loads(R3_CONTRACT.read_text(encoding="utf-8"))
    r3_cfg = R3_CFG.read_text(encoding="utf-8")
    docs = "\n".join(
        path.read_text(encoding="utf-8") for path in (ADR, CYCLE, AGENTS)
    )

    decision = contract["decision"]
    if not decision["filament_insertion_is_contamination_boundary"]:
        raise ValueError("insertion_boundary_missing")
    if not decision["probing_after_insertion_forbidden"]:
        raise ValueError("post_insertion_probe_not_forbidden")

    order = contract["final_paths"]["fresh_geometry"]["required_order"]
    ordered(order, "prove_no_engaged_route", "complete_all_contact_probing")
    ordered(order, "complete_all_contact_probing", "resolve_and_insert_filament")
    ordered(order, "resolve_and_insert_filament", "purge_and_prove_flow")
    ordered(order, "purge_and_prove_flow", "start_model")

    reuse = contract["final_paths"]["reuse_valid_geometry"]
    if "no_contact_probe_in_job_start" not in reuse["required"]:
        raise ValueError("reuse_path_can_probe")

    if r3["status"] != "SUPERSEDED_NEVER_DEPLOY_OR_RUN_PROBING_AFTER_INSERTION":
        raise ValueError("r3_not_tombstoned")
    if r3["deployment_candidate"] or r3["physical_run_authorized"]:
        raise ValueError("r3_effect_path_reopened")
    if "G1 E20 F360" not in r3_cfg or "ACCURATE_G28" not in r3_cfg:
        raise ValueError("r3_closure_evidence_missing")

    required_doc_fragments = (
        "avant l'insertion",
        "Toute insertion est présumée laisser un résidu",
        "ne repalpe pas",
    )
    for fragment in required_doc_fragments:
        if fragment not in docs:
            raise ValueError(f"durable_documentation_missing:{fragment}")

    if evidence["verdict"] != "CLOSED_KO_R3_SUPERSEDED_AND_ACTIVE_MESH_DRIFT":
        raise ValueError("preflight_verdict_changed")
    if evidence["machine_snapshots"]["active_mesh"] != "default":
        raise ValueError("preflight_mesh_drift_not_recorded")
    if evidence["machine_snapshots"]["active_probed_matrix"] != "6x6":
        raise ValueError("preflight_mesh_shape_not_recorded")
    if not evidence["machine_snapshots"]["T1A_engaged"]:
        raise ValueError("confirmed_route_not_recorded")
    if any(contract["effects"].values()):
        raise ValueError("contract_declares_effect")
    effect_flags = evidence["effects"]
    forbidden_effects = (
        "gcode_sent",
        "heater_action",
        "motion_action",
        "extrusion_action",
        "cfs_action",
        "remote_file_write",
        "service_action",
    )
    if any(effect_flags[key] for key in forbidden_effects):
        raise ValueError("preflight_declares_effect")

    return {
        "status": "CALIBRATION_BEFORE_INSERTION_V1_OFFLINE_OK",
        "r3_tombstoned": True,
        "probing_before_insertion": True,
        "reuse_path_has_no_probe": True,
        "preflight_closed_on_mesh_drift": True,
        "effects": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2, sort_keys=True))
