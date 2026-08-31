import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/k1-control-v1/stock-derived-cycle-activation-v1"
MANIFEST = json.loads((PACKAGE / "deployment-manifest.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_scenarios():
    spec = importlib.util.spec_from_file_location(
        "pytest_activation_scenarios", PACKAGE / "run_scenarios.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_activation_scenarios_are_all_green_without_transport():
    result = load_scenarios().run()
    assert result["status"] == "OK"
    assert result["passed"] == result["total"] == 18
    assert result["printer_transport"] is False
    assert result["physical_action"] is False
    assert result["automatic_retry"] is False


def test_manifest_freezes_every_payload_and_support_file():
    assert MANIFEST["gate"] == (
        "G4-K1-CONTROL-STOCK-DERIVED-CYCLE-ACTIVATION-IDLE-V1"
    )
    assert MANIFEST["status"] == "offline_review_candidate_not_installed"
    assert len(MANIFEST["files"]) == 8
    for entry in (
        MANIFEST["files"]
        + MANIFEST["support_files"]
        + MANIFEST["preparation_evidence"]
        + [MANIFEST["deployer"]]
    ):
        path = ROOT / entry["source"]
        assert path.is_file(), entry["source"]
        assert sha256(path) == entry["sha256"], entry["source"]


def test_deployment_is_idle_only_and_has_exact_rollback():
    effects = MANIFEST["planned_effects"]
    for field in (
        "heat", "axis_motion", "extrusion", "filament", "cfs_frame",
        "probe", "mesh_recalculation",
    ):
        assert effects[field] is False
    assert MANIFEST["physical_trial_included"] is False
    assert MANIFEST["rollback"]["restore_exact"] == [
        "printer.cfg",
        "moonraker.conf",
        "k1_control_stock_cycle.py",
    ]
    assert MANIFEST["rollback"]["remove_new_files"] == 7


def test_runout_contract_separates_empty_spool_from_tool_change():
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    assert contract["runout"]["sensor_state_alone_is_sufficient"] is False
    assert contract["runout"]["empty_spool_uses_cutter"] is False
    assert contract["runout"]["unique_strict_spare_required"] is True
    assert contract["runout"]["resume_temperature"] == "saved_gcode_target"
    assert contract["intentional_tool_change"]["cutter_required"] is True
    assert contract["geometry"]["post_filament_probe_count"] == 0


def test_real_preflight_evidence_is_present_but_install_is_not_claimed():
    result = (PACKAGE / "RESULT.md").read_text(encoding="utf-8")
    assert "PRÉFLIGHT RÉEL OK — POSE NON EXÉCUTÉE" in result
    assert "20260831-191518-g4-k1-control-stock-derived-cycle-activation-v1" in result
    baseline = json.loads((PACKAGE / "baseline-read-only.json").read_text(encoding="utf-8"))
    assert baseline["status"] == "CURRENT_DISABLED_INSTALLATION_VALIDATED_READ_ONLY"
    assert baseline["physical_effect"] is False


class StockDerivedCycleActivationV1Tests(unittest.TestCase):
    test_activation_scenarios_are_all_green_without_transport = staticmethod(
        test_activation_scenarios_are_all_green_without_transport
    )
    test_manifest_freezes_every_payload_and_support_file = staticmethod(
        test_manifest_freezes_every_payload_and_support_file
    )
    test_deployment_is_idle_only_and_has_exact_rollback = staticmethod(
        test_deployment_is_idle_only_and_has_exact_rollback
    )
    test_runout_contract_separates_empty_spool_from_tool_change = staticmethod(
        test_runout_contract_separates_empty_spool_from_tool_change
    )
    test_real_preflight_evidence_is_present_but_install_is_not_claimed = staticmethod(
        test_real_preflight_evidence_is_present_but_install_is_not_claimed
    )


if __name__ == "__main__":
    unittest.main()
