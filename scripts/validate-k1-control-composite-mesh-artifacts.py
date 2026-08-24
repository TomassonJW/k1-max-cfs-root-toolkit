#!/usr/bin/env python3
"""Verify that the persisted config is exactly the rendered composite candidate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = (
    ROOT / "packages" / "k1-control-v1" / "composite-mesh-v1" / "render_profile.py"
)


def _renderer():
    spec = importlib.util.spec_from_file_location("composite_mesh_renderer", RENDERER_PATH)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Renderer loader is unavailable")
    spec.loader.exec_module(module)
    return module


def validate(backup_path: Path, current_path: Path, state_path: Path) -> dict:
    state = json.loads(Path(state_path).read_text(encoding="utf-8-sig"))
    if state.get("phase") != "qualified":
        raise ValueError("Composite state is not qualified")
    matrix = state.get("candidate_matrix")
    backup = Path(backup_path).read_bytes()
    current = Path(current_path).read_bytes()
    expected = _renderer().append_profile(backup, matrix)
    if current != expected:
        raise ValueError("Persisted printer.cfg differs from the exact rendered candidate")
    digest = hashlib.sha256(current).hexdigest()
    if digest != state.get("candidate_printer_cfg_sha256"):
        raise ValueError("Persisted printer.cfg hash differs from the qualified state")
    return {
        "result": "VALIDATE_COMPOSITE_MESH_ARTIFACTS_OK",
        "printer_cfg_sha256": digest,
        "physical_contacts": state.get("physical_contacts"),
        "completed_passes": state.get("completed_passes"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("state", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.backup, args.current, args.state), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
