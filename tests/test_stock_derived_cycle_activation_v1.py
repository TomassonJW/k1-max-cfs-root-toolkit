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
    assert result["passed"] == result["total"] == 22
    assert result["printer_transport"] is False
    assert result["physical_action"] is False
    assert result["automatic_retry"] is False


def test_manifest_freezes_every_payload_and_support_file():
    assert MANIFEST["gate"] == (
        "G4-K1-CONTROL-STOCK-DERIVED-CYCLE-ACTIVATION-IDLE-V1"
    )
    assert MANIFEST["status"] == "installed_validated_active_idle_no_physical_trial"
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


def test_deployer_restarts_the_klipper_process_to_reload_python_modules():
    deployer = (
        ROOT / "scripts/deploy-k1-control-stock-derived-cycle-activation-v1.ps1"
    ).read_text(encoding="utf-8")
    assert "$KlipperService = '/etc/init.d/S55klipper_service'" in deployer
    assert deployer.count("[void](Invoke-Remote \"'$KlipperService' restart\")") == 2
    assert "Invoke-Admin 'restart'" not in deployer
    assert MANIFEST["planned_effects"]["klipper_restart_kind"] == (
        "full_S55klipper_service_process_restart"
    )
    assert MANIFEST["rollback"]["klipper_restart_kind"] == (
        "full_S55klipper_service_process_restart"
    )


def test_host_restart_restores_effective_accepted_z_without_motion():
    restorer = (PACKAGE / "remote_restore_accepted_z.py").read_text(encoding="utf-8")
    deployer = (
        ROOT / "scripts/deploy-k1-control-stock-derived-cycle-activation-v1.ps1"
    ).read_text(encoding="utf-8")
    assert '"SET_GCODE_OFFSET Z=-0.04 MOVE=0"' in restorer
    assert "BED_MESH_CALIBRATE" not in restorer
    assert "G28" not in restorer
    assert "Restore-AcceptedZNoMove 'deploy-restore-accepted-z.json'" in deployer
    assert "Restore-AcceptedZNoMove 'rollback-restore-accepted-z.json'" in deployer
    assert MANIFEST["planned_effects"]["restore_accepted_z_no_move_once_mm"] == -0.04
    assert MANIFEST["rollback"]["restore_accepted_z_no_move_once_mm"] == -0.04


def test_runout_contract_separates_empty_spool_from_tool_change():
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    assert contract["runout"]["sensor_state_alone_is_sufficient"] is False
    assert contract["runout"]["empty_spool_uses_cutter"] is False
    assert contract["runout"]["unique_strict_spare_required"] is True
    assert contract["runout"]["resume_temperature"] == "saved_gcode_target"
    assert contract["intentional_tool_change"]["cutter_required"] is True
    assert contract["geometry"]["post_filament_probe_count"] == 0


def test_runout_owner_checks_the_identity_published_by_the_real_direct_owner():
    direct_owner = (
        ROOT
        / "packages/k1-control-v1/cfs-direct-owner-install-disabled-v1"
        / "k1_control_cfs_direct_owner.py"
    ).read_text(encoding="utf-8")
    runout_owner = (PACKAGE / "k1_control_cfs_runout_owner.py").read_text(
        encoding="utf-8"
    )
    assert 'OWNER_NAME = "k1_control_direct"' in direct_owner
    assert 'status.get("owner") != "k1_control_direct"' in runout_owner


def test_real_installation_and_independent_idle_validation_are_recorded():
    result = (PACKAGE / "RESULT.md").read_text(encoding="utf-8")
    assert "ACTIVÉE ET CORRIGÉE" in result
    assert "20260831-205322-g4-k1-control-stock-derived-cycle-activation-v1" in result
    installation = MANIFEST["installation"]
    assert installation["independent_validation_marker"] == (
        "VALIDATE_STOCK_DERIVED_CYCLE_ACTIVATION_V1_OK"
    )
    assert installation["effective_z_offset_mm"] == -0.04
    assert installation["mesh_profile"] == "k1_p001_t055_r001_n11x11"
    assert installation["effect_dispatch_count"] == 0
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
    test_deployer_restarts_the_klipper_process_to_reload_python_modules = staticmethod(
        test_deployer_restarts_the_klipper_process_to_reload_python_modules
    )
    test_host_restart_restores_effective_accepted_z_without_motion = staticmethod(
        test_host_restart_restores_effective_accepted_z_without_motion
    )
    test_runout_contract_separates_empty_spool_from_tool_change = staticmethod(
        test_runout_contract_separates_empty_spool_from_tool_change
    )
    test_runout_owner_checks_the_identity_published_by_the_real_direct_owner = staticmethod(
        test_runout_owner_checks_the_identity_published_by_the_real_direct_owner
    )
    test_real_installation_and_independent_idle_validation_are_recorded = staticmethod(
        test_real_installation_and_independent_idle_validation_are_recorded
    )


if __name__ == "__main__":
    unittest.main()
