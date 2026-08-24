#!/usr/bin/env python3
"""Validate the one retained 144-contact capture for non-physical recovery."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSER_PATH = (
    ROOT / "packages" / "k1-control-v1" / "composite-mesh-v1" / "compose_mesh.py"
)
EXPECTED_CAMPAIGN = "20260824-151506-337-composite-mesh-v1"
EXPECTED_RAW_MAX = 0.147858
EXPECTED_ALIGNED_MAX = 0.04374502944942382


def _composer():
    spec = importlib.util.spec_from_file_location("composite_mesh_recovery", COMPOSER_PATH)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Composite mesh loader is unavailable")
    spec.loader.exec_module(module)
    return module


def validate(state_path: Path) -> dict:
    state = json.loads(Path(state_path).read_text(encoding="utf-8-sig"))
    if (
        state.get("phase") != "failed"
        or state.get("busy")
        or state.get("campaign_id") != EXPECTED_CAMPAIGN
        or state.get("config_written")
        or not isinstance(state.get("backup"), dict)
    ):
        raise ValueError("Retained composite state is not the reviewed failed capture")
    passes = state.get("passes")
    if not isinstance(passes, list) or len(passes) != 4:
        raise ValueError("Retained composite state does not contain four passes")
    result = _composer().compose_11x11({
        "target": {
            "x_count": 11,
            "y_count": 11,
            "mesh_min": [5, 5],
            "mesh_max": [295, 295],
        },
        "passes": passes,
    })
    if (
        result["physical_contacts"] != 144
        or result["unique_physical_points"] != 121
        or result["duplicate_contacts"] != 23
        or result["overlap_positions"] != 21
    ):
        raise ValueError("Retained composite contact topology differs from review")
    if abs(result["raw_overlap_mm"]["maximum_spread"] - EXPECTED_RAW_MAX) > 1e-9:
        raise ValueError("Retained raw overlap maximum differs from review")
    if abs(result["overlap_mm"]["maximum_spread"] - EXPECTED_ALIGNED_MAX) > 1e-9:
        raise ValueError("Retained aligned overlap maximum differs from review")
    matrix_bytes = json.dumps(
        result["candidate_matrix"], separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    return {
        "result": "VALIDATE_COMPOSITE_MESH_RECOVERY_OK",
        "campaign_id": EXPECTED_CAMPAIGN,
        "physical_contacts": 144,
        "unique_physical_points": 121,
        "raw_maximum_spread_mm": result["raw_overlap_mm"]["maximum_spread"],
        "aligned_maximum_spread_mm": result["overlap_mm"]["maximum_spread"],
        "aligned_mean_spread_mm": result["overlap_mm"]["mean_spread"],
        "pass_offsets_mm": result["pass_offsets_mm"],
        "candidate_matrix_sha256": hashlib.sha256(matrix_bytes).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.state), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
