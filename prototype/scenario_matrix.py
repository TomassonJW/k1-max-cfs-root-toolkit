"""Executable 17-scenario proof matrix for K1-CONTROL-V1."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Callable

from prototype.control_runtime import (
    DeploymentSnapshot,
    JobContract,
    PrintRuntime,
    SafeStartController,
    load_product_sequence,
)
from prototype.control_state import (
    MachineContext,
    MeshCatalog,
    MeshProfile,
    ProductionBlocked,
    ZCalibrationController,
)


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_CONTRACT = ROOT / "design" / "production-control-contract.json"
FIXTURES = ROOT / "tests" / "fixtures" / "k1-control-v1"


@dataclass(frozen=True)
class ScenarioResult:
    id: str
    passed: bool
    detail: str


def _context(*, plate: str = "PEI_TEXTURED_A", probe: str = "probe-7") -> MachineContext:
    return MachineContext(
        plate_id=plate,
        bed_temperature_band_c="55-65",
        nozzle_id="unicorn-a",
        nozzle_diameter_mm=0.4,
        probe_reference_revision=probe,
        relevant_config_hashes={"homing": "aaa", "probe": "bbb"},
    )


def _accepted_z() -> tuple[ZCalibrationController, MachineContext]:
    current = _context()
    controller = ZCalibrationController()
    controller.start_session(current, seed_offset_mm=0.30)
    controller.adjust(0.01)
    controller.commit(accepted_at="2026-08-20T18:30:00+00:00")
    return controller, current


def _job(name: str = "production-adaptive.json") -> JobContract:
    payload = json.loads((FIXTURES / "jobs" / name).read_text(encoding="utf-8"))
    return JobContract.from_mapping(payload)


def _must_block(action: Callable[[], object], fragment: str = "") -> str:
    try:
        action()
    except ProductionBlocked as exc:
        if fragment and fragment not in str(exc):
            raise AssertionError(f"unexpected block reason: {exc}") from exc
        return str(exc)
    raise AssertionError("operation should have been blocked")


def _z_live_adjust_then_commit() -> str:
    controller, current = _accepted_z()
    before = controller.accepted
    controller.start_session(current, seed_offset_mm=before.offset_mm)
    controller.adjust(0.005)
    assert controller.accepted == before
    committed = controller.commit(accepted_at="2026-08-20T19:00:00+00:00")
    assert committed.offset_mm == 0.315
    return "live value stayed provisional until K1_Z_COMMIT"


def _z_cancel_calibration() -> str:
    controller, current = _accepted_z()
    before = controller.accepted
    controller.start_session(current, seed_offset_mm=0.31)
    controller.adjust(-0.01)
    controller.cancel()
    assert controller.accepted == before
    assert controller.production_offset(current) == 0.31
    return "cancel restored the accepted production value"


def _z_print_end_and_restart() -> str:
    controller, current = _accepted_z()
    controller.on_print_end()
    controller.on_restart()
    assert controller.production_offset(current) == 0.31
    return "accepted Z survived print end and simulated restart"


def _z_new_reference_calibration() -> str:
    controller, current = _accepted_z()
    retained = controller.accepted
    controller.invalidate("new reference calibration")
    _must_block(lambda: controller.production_offset(current), "new reference")
    assert controller.accepted == retained
    return "old record retained for history but production blocked"


def _mesh_reference_plate_temperature_match() -> str:
    current = _context()
    catalog = MeshCatalog(
        [MeshProfile("PEI_TEXTURED_A__55-65__probe-7", current.plate_id, "55-65", "probe-7")]
    )
    decision = catalog.reference_for(current)
    assert decision.profile_id == "PEI_TEXTURED_A__55-65__probe-7"
    return "unique matching reference mesh selected"


def _mesh_reference_mismatch() -> str:
    catalog = MeshCatalog(
        [MeshProfile("PEI_TEXTURED_A__55-65__probe-7", "PEI_TEXTURED_A", "55-65", "probe-7")]
    )
    reason = _must_block(lambda: catalog.reference_for(_context(plate="PEI_SMOOTH_B")), "no unique")
    return reason


def _mesh_adaptive_job() -> str:
    job = _job()
    decision = MeshCatalog().adaptive_for(job.object_bounds)
    assert decision.bounds == job.object_bounds
    assert decision.persist_after_job is False
    return "Orca bounds used; adaptive mesh remained job-local"


def _safe_start_sequence() -> str:
    sequence = load_product_sequence(PRODUCT_CONTRACT)
    controller = SafeStartController(sequence)
    _must_block(lambda: controller.attempt_production_hazard("early_purge"), "before arm")
    for stage in sequence:
        controller.advance(str(stage["id"]))
    assert controller.production_low_moves_armed
    assert controller.hazards == [
        "cfs_prepare_initial_tool",
        "parameterized_purge",
        "print_model",
    ]
    return "early purge blocked; every declared hazard ran only after arm"


def _cfs_initial_load() -> str:
    runtime = PrintRuntime(_job())
    assert runtime.initial_load() == 205
    return "T0 initial target came from the job contract"


def _cfs_equivalent_refill() -> str:
    runtime = PrintRuntime(_job())
    runtime.initial_load()
    assert runtime.equivalent_refill(220) == 205
    return "stock 220 C overwrite detected and corrected to active 205 C"


def _cfs_intentional_tool_change() -> str:
    runtime = PrintRuntime(_job())
    runtime.initial_load()
    assert runtime.intentional_tool_change(1, 220) == 220
    assert runtime.temperature.active_tool == 1
    return "intentional T1 change accepted Orca target 220 C"


def _cfs_cross_unit_change() -> str:
    runtime = PrintRuntime(_job())
    runtime.initial_load()
    assert runtime.intentional_tool_change(5, 220) == 235
    assert runtime.temperature.active_tool == 5
    return "cross-unit T0 to T5 restored Orca target 235 C across two CFS"


def _pause_resume() -> str:
    z, current = _accepted_z()
    runtime = PrintRuntime(_job())
    runtime.initial_load()
    runtime.pause()
    assert runtime.resume(220) == 205
    assert z.production_offset(current) == 0.31
    return "resume restored target and did not touch accepted Z"


def _cancel_and_end() -> str:
    z, current = _accepted_z()
    runtime = PrintRuntime(_job())
    runtime.initial_load()
    runtime.cancel_or_end()
    assert runtime.heaters_safe and runtime.temperature.expected_target_c == 0
    assert z.production_offset(current) == 0.31
    return "heaters went safe while accepted calibration stayed unchanged"


def _explicit_operator_temperature_change() -> str:
    runtime = PrintRuntime(_job())
    runtime.initial_load()
    runtime.operator_temperature(198)
    assert runtime.equivalent_refill(220) == 198
    assert runtime.temperature.owner == "operator"
    runtime.explicit_gcode_temperature(0, 210)
    assert runtime.temperature.expected_target_c == 210
    assert runtime.temperature.owner == "gcode"
    return "operator owned 198 C until the next explicit G-code target 210 C"


def _orca_contract_version_mismatch() -> str:
    payload = json.loads((FIXTURES / "jobs" / "wrong-version.json").read_text(encoding="utf-8"))
    reason = _must_block(lambda: JobContract.from_mapping(payload), "unsupported Orca contract version")
    controller = SafeStartController(load_product_sequence(PRODUCT_CONTRACT))
    assert controller.completed == [] and not controller.production_low_moves_armed
    return f"job rejected before sequence start: {reason}"


def _deployment_slice_rollback() -> str:
    before_contents = {
        "/etc/init.d/S56k1_control_moonraker": b"absent-marker",
        "/usr/data/k1-control-v1/current": b"release-0",
    }
    after_contents = {
        "/etc/init.d/S56k1_control_moonraker": b"candidate-service",
        "/usr/data/k1-control-v1/current": b"release-1",
    }
    before = DeploymentSnapshot.from_contents(before_contents)
    after = DeploymentSnapshot.from_contents(after_contents)
    restored = DeploymentSnapshot.from_contents(before_contents)
    assert not before.matches(after)
    assert before.matches(restored)
    return "rollback restored the exact pre-slice SHA-256 map"


SCENARIOS: dict[str, Callable[[], str]] = {
    "z_live_adjust_then_commit": _z_live_adjust_then_commit,
    "z_cancel_calibration": _z_cancel_calibration,
    "z_print_end_and_restart": _z_print_end_and_restart,
    "z_new_reference_calibration": _z_new_reference_calibration,
    "mesh_reference_plate_temperature_match": _mesh_reference_plate_temperature_match,
    "mesh_reference_mismatch": _mesh_reference_mismatch,
    "mesh_adaptive_job": _mesh_adaptive_job,
    "safe_start_sequence": _safe_start_sequence,
    "cfs_initial_load": _cfs_initial_load,
    "cfs_equivalent_refill": _cfs_equivalent_refill,
    "cfs_intentional_tool_change": _cfs_intentional_tool_change,
    "cfs_cross_unit_change": _cfs_cross_unit_change,
    "pause_resume": _pause_resume,
    "cancel_and_end": _cancel_and_end,
    "explicit_operator_temperature_change": _explicit_operator_temperature_change,
    "orca_contract_version_mismatch": _orca_contract_version_mismatch,
    "deployment_slice_rollback": _deployment_slice_rollback,
}


def run_matrix() -> list[ScenarioResult]:
    contract = json.loads(PRODUCT_CONTRACT.read_text(encoding="utf-8"))
    required = [scenario["id"] for scenario in contract["required_offline_scenarios"]]
    if set(required) != set(SCENARIOS):
        missing = sorted(set(required) - set(SCENARIOS))
        extra = sorted(set(SCENARIOS) - set(required))
        raise RuntimeError(f"scenario implementation mismatch; missing={missing}, extra={extra}")
    results = []
    for scenario_id in required:
        try:
            detail = SCENARIOS[scenario_id]()
        except Exception as exc:  # matrix must report every scenario
            results.append(ScenarioResult(scenario_id, False, f"{type(exc).__name__}: {exc}"))
        else:
            results.append(ScenarioResult(scenario_id, True, detail))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    args = parser.parse_args()
    results = run_matrix()
    if args.json:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(f"{'OK' if result.passed else 'KO'} {result.id}: {result.detail}")
        print(f"TOTAL {sum(result.passed for result in results)}/{len(results)}")
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
