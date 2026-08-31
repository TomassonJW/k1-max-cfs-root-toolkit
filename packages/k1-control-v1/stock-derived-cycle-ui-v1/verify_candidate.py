"""Vérifie le candidat statique sans connexion K1."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXPECTED_ROUTES = ["T1A", "T1B", "T1C", "T1D", "T2A", "T2B", "T2C", "T2D"]
REQUIRED_MATERIAL_FIELDS = {
    "reference_id",
    "material_type",
    "color",
    "diameter_mm",
    "thermal_recipe_id",
    "user_approved",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> list[str]:
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    manifest = json.loads((HERE / "deployment-manifest.json").read_text(encoding="utf-8"))
    index = (HERE / "index.html").read_text(encoding="utf-8")
    app = (HERE / "app.js").read_text(encoding="utf-8")
    styles = (HERE / "styles.css").read_text(encoding="utf-8")
    results: list[str] = []

    assert contract["contract_id"] == "G4-K1-CONTROL-STOCK-DERIVED-CYCLE-UI-V1"
    assert contract["status"] in {
        "offline_review_candidate_not_installed",
        "installed_validated_static_no_physical_trial",
    }
    assert contract["interface"]["routes"] == EXPECTED_ROUTES
    assert set(contract["interface"]["strict_material_identity_fields"]) == REQUIRED_MATERIAL_FIELDS
    assert contract["interface"]["manual_camera_pass_button"] is False
    assert contract["api"]["camera_verdict_called_by_ui"] is False
    assert contract["deployment_effects"] == {
        "service_restart": False,
        "heat": False,
        "motion": False,
        "extrusion": False,
        "filament": False,
        "cfs_frame": False,
        "probe": False,
        "mesh_recalculation": False,
        "starts_cycle": False,
    }
    results.append("contract_static_only")

    assert 'const API = "/machine/k1_control/stock-cycle"' in app
    for path in ("/status", "/files", "/inventory", "/select", "/begin", "/clean-confirm", "/tool-change", "/abort"):
        assert f'"{path}"' in app
    assert "camera-verdict" not in app
    assert "/printer/gcode" not in app
    assert "run_gcode" not in app
    assert "BOX_" not in app
    assert "automatic_retry" not in app
    results.append("backend_only_effect_routes")

    for field in REQUIRED_MATERIAL_FIELDS - {"user_approved"}:
        assert field in app
    assert "material.user_approved = true" in app
    assert "matches.length === 1" in app
    assert "Secours ambigu" in app
    assert "roulement sera refusé" in app
    results.append("strict_unique_spare_ux")

    assert "operator_present: true" in app
    assert "camera_available: true" in app
    assert "machine_clear: true" in app
    assert "operator_confirmed: true" in app
    assert "nozzle_visibly_clean: true" in app
    assert "plate_clean: true" in app
    assert "confirmation_fresh: true" in app
    assert "Aucun bouton ne permet de contourner cette preuve" in index
    results.append("human_and_camera_boundaries")

    assert 'href="calibration/index.html"' in index
    assert contract["preserved_remote_tree"] == "calibration/"
    assert len(manifest["unchanged"]["calibration"]) == 3
    assert ".dashboard-grid" in styles
    assert ".inventory-row" not in styles
    results.append("calibration_preserved")

    assert manifest["contract_id"] == contract["contract_id"]
    assert manifest["status"] == contract["status"]
    expected_sources = ["index.html", "app.js", "styles.css"]
    assert [item["source"] for item in manifest["files"]] == expected_sources
    for item in manifest["files"]:
        assert sha256(HERE / item["source"]) == item["sha256"]
    assert sha256(HERE / "contract.json") == manifest["contract"]["sha256"]
    deployer = ROOT / manifest["deployer"]["source"]
    assert sha256(deployer) == manifest["deployer"]["sha256"]
    results.append("manifest_hashes")

    return results


if __name__ == "__main__":
    checks = verify()
    print(f"VERIFY_STOCK_DERIVED_CYCLE_UI_V1_OK checks={len(checks)}")
    for check in checks:
        print(f"OK {check}")
