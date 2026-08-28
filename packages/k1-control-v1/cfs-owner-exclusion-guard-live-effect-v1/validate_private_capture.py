#!/usr/bin/env python3
"""Validate the one-shot live effect with the exact offline guard state machine."""

from __future__ import annotations

import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
GUARD_PACKAGE = PACKAGE.parent / "cfs-owner-exclusion-guard-offline-v1"
OBSERVABILITY_PACKAGE = PACKAGE.parent / "cfs-owner-observability-adapter-offline-v2"
CONTRACT = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
GUARD_CONTRACT = json.loads((GUARD_PACKAGE / "contract.json").read_text(encoding="utf-8"))
OBSERVABILITY_CONTRACT = json.loads((OBSERVABILITY_PACKAGE / "contract.json").read_text(encoding="utf-8"))
TERMINAL_MARKER = "CFS_OWNER_EXCLUSION_GUARD_LIVE_EFFECT_V1_CAPTURE_CLOSED"


def _load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("module_import_failed:%s" % name)
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


guard_adapter = _load("adapter", GUARD_PACKAGE / "adapter.py")
guard_module = _load("cfs_owner_exclusion_live_guard", GUARD_PACKAGE / "guard.py")
observability = _load("cfs_owner_exclusion_live_observability_v2", OBSERVABILITY_PACKAGE / "adapter_v2.py")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("%s_invalid" % label)
    return value


def load_capture(path: Path) -> Mapping[str, Any]:
    lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    if len(lines) != 2 or lines[1] != TERMINAL_MARKER:
        raise ValueError("capture_terminal_invalid")
    return _mapping(json.loads(lines[0]), "capture")


def _project_pair(pair: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(pair, list) or len(pair) != 2:
        raise ValueError("%s_pair_invalid" % label)
    try:
        return observability.adapt_observation_pair(
            OBSERVABILITY_CONTRACT, GUARD_CONTRACT, pair
        )
    except observability.ObservationError as exc:
        raise ValueError("%s_projection_rejected:%s:%s" % (label, exc.code, exc.detail))


def verify_payload(raw_capture: Mapping[str, Any]) -> Mapping[str, Any]:
    capture = _mapping(raw_capture, "capture")
    if capture.get("schema") != 1 or capture.get("mission") != CONTRACT["mission"]:
        raise ValueError("capture_identity_invalid")
    if capture.get("status") != "CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED":
        raise ValueError("capture_not_successful")
    expected_commands = [
        CONTRACT["reviewed_commands"]["disable"],
        CONTRACT["reviewed_commands"]["restore"],
    ]
    if capture.get("commands_attempted") != expected_commands:
        raise ValueError("command_sequence_invalid")
    if capture.get("attempts") != {"disable": 1, "restore": 1}:
        raise ValueError("attempt_count_invalid")
    if capture.get("saved_stock_auto_refill") != 1:
        raise ValueError("saved_value_invalid")
    if capture.get("reported_cfs_transition_count") != 0:
        raise ValueError("cfs_transition_observed")
    if capture.get("reported_cfs_transitions") != []:
        raise ValueError("cfs_transition_evidence_invalid")
    acknowledgements = _mapping(capture.get("acknowledgements"), "acknowledgements")
    if set(acknowledgements) != {"disable", "restore"}:
        raise ValueError("acknowledgement_shape_invalid")
    proof = _mapping(capture.get("proof"), "proof")
    if set(proof) != {"before_disable", "after_disable", "before_restore", "after_restore"}:
        raise ValueError("proof_shape_invalid")
    projected = {
        label: _project_pair(proof[label], label)
        for label in ("before_disable", "after_disable", "before_restore", "after_restore")
    }
    epochs = {value["connection_epoch"] for value in projected.values()}
    if len(epochs) != 1:
        raise ValueError("connection_epoch_changed")

    guard = guard_module.Guard(GUARD_CONTRACT)
    acquire = guard.prepare_acquire(projected["before_disable"]["guard_reads"])
    if acquire["phase"] != "disable_pending" or acquire["saved_stock_auto_refill"] != 1:
        raise ValueError("guard_did_not_prepare_disable")
    disabled = guard.observe_disable("accepted", projected["after_disable"]["guard_reads"])
    if disabled["phase"] != "owner_granted" or disabled["owner_granted"] is not True:
        raise ValueError("guard_did_not_prove_exclusion")
    release = guard.prepare_release(projected["before_restore"]["guard_reads"])
    if release["phase"] != "restore_pending" or release["owner_granted"] is not False:
        raise ValueError("guard_did_not_prepare_restore")
    restored = guard.observe_restore("accepted", projected["after_restore"]["guard_reads"])
    if restored["phase"] != "closed_safe" or restored["release_required"] is not False:
        raise ValueError("guard_did_not_prove_restore")
    if restored["attempts"] != {"disable": 1, "restore": 1}:
        raise ValueError("guard_attempt_count_invalid")

    hashes = _mapping(capture.get("configuration_hashes"), "configuration_hashes")
    if set(hashes) != {"before", "pre_disable", "post_disable", "final"}:
        raise ValueError("configuration_checkpoint_invalid")
    values = list(hashes.values())
    if not values or any(item != values[0] for item in values[1:]):
        raise ValueError("configuration_hashes_changed")
    effects = _mapping(capture.get("effects"), "effects")
    expected_effects = {
        "gcode_commands_attempted": 2,
        "stock_auto_refill_policy_changed": True,
        "stock_auto_refill_restored": True,
        "filament_action": False,
        "heater_action": False,
        "motion_action": False,
        "remote_files_written": False,
        "service_action": False,
    }
    if effects != expected_effects:
        raise ValueError("effect_boundary_invalid")
    final = projected["after_restore"]["guard_snapshot"]
    return {
        "status": "OK",
        "verdict": "CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED",
        "saved_stock_auto_refill": 1,
        "disabled_value_proved": projected["after_disable"]["guard_snapshot"]["stock_auto_refill"],
        "restored_value_proved": final["stock_auto_refill"],
        "attempts": restored["attempts"],
        "owner_granted_then_released": True,
        "connection_epoch_stable": True,
        "reported_cfs_transition_count": 0,
        "accepted_z_offset_mm": final["protected"]["effective_z_offset_mm"],
        "active_mesh_profile": final["protected"]["mesh_profile"],
        "connected_units": final["connected_units"],
        "engaged_routes": final["engaged_routes"],
        "configuration_hashes_unchanged": True,
        "filament_action": False,
        "heater_action": False,
        "motion_action": False,
        "remote_write": False,
        "service_action": False,
    }


def verify_capture(path: Path) -> Mapping[str, Any]:
    return verify_payload(load_capture(path))


def verify_evidence(repo_root: Path = ROOT) -> Mapping[str, Any]:
    evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))
    private = evidence["private_source"]
    path = repo_root / private["path"]
    if sha256_file(path) != private["sha256"]:
        raise ValueError("private_capture_hash_mismatch")
    result = verify_capture(path)
    if result != evidence["safe_result"]:
        raise ValueError("safe_result_mismatch")
    return result


def main(arguments: Sequence[str]) -> int:
    result = verify_capture(Path(arguments[0])) if arguments else verify_evidence()
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    print("VALIDATE_CFS_OWNER_EXCLUSION_GUARD_LIVE_EFFECT_V1_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
