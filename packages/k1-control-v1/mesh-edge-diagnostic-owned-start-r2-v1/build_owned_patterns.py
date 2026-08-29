#!/usr/bin/env python3
"""Build edge diagnostic patterns behind the installed owned R2 start."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, Tuple


PACKAGE_DIR = Path(__file__).resolve().parent
LEGACY_PACKAGE = PACKAGE_DIR.parent / "mesh-edge-diagnostic-v1"
MISSION = "G4-K1-CONTROL-MESH-EDGE-DIAGNOSTIC-OWNED-START-R2-V1"
SOURCE_PROFILE = "k1_p001_t055_r001_n11x11"
DERIVED_PROFILE = SOURCE_PROFILE + "_tuned_v001"
INSTALLED_START_OWNER_SHA256 = "678582e808d74f6b720ef3d6b52dc2c443c7a0652a62c484319e2b22fba7b0bc"
LEGACY_PATTERN_SHA256 = {
    "source": "da9796160af5d56ee0155a5daf5a96906dfe8c5eff84de64954fb270732da978",
    "corrected": "0192f4c53d11acde3136cdc8a89cd82eb94a71b9510cb08dc22f7ab12bab65d2",
}
OWNED_PATTERN_SHA256 = {
    "source": "0e1e9f87e99a4c5c0b70be96f1cf6f40825f4ef0012709362fb819c7b9849260",
    "corrected": "09aae82a3b1cfeb93a6c67c220e2d5eea6bf709652f8bda062b9b318a4374ea1",
}
START_CALL = (
    "KCTRL_JOB_BEGIN_KEEP_CORRECT_V1 BED=55 PROBE_NOZZLE=140 FIRST_NOZZLE=190 "
    "PLATE=1 PROBE_REV=1 NOZZLE_ID=1 CONFIG_ID=1 X_COUNT=11 Y_COUNT=11"
)
ASSERT_LINE = "KCTRL_PRODUCTION_ASSERT_ARMED"
LEGACY_TAIL = "\n".join(
    (
        "BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n06x06",
        "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=low_moves_armed VALUE=0",
        "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=armed_mesh_profile VALUE='\"none\"'",
        "TURN_OFF_HEATERS",
        "M84",
        "M73 P100 R0",
    )
) + "\n"
SAFE_TAIL = "\n".join(
    (
        "KCTRL_START_ABORT_V1",
        "BED_MESH_PROFILE LOAD=" + SOURCE_PROFILE,
        "KCTRL_CLEAR_MANUAL_NOZZLE_CLEAN_V1",
        "M107 P1",
        "M107 P2",
        "TURN_OFF_HEATERS",
        "G90",
        "G1 Z50 F600",
        "G1 X203 Y273 F1200",
        "M400",
        "M84",
        "M73 P100 R0",
    )
) + "\n"


class OwnedPatternError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_legacy_module():
    path = LEGACY_PACKAGE / "prepare_diagnostic.py"
    spec = importlib.util.spec_from_file_location("mesh_edge_legacy_prepare", path)
    if spec is None or spec.loader is None:
        raise OwnedPatternError("legacy_generator_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def owned_prefix(variant: str) -> str:
    lines = [START_CALL]
    if variant == "corrected":
        lines.extend(
            (
                "BED_MESH_PROFILE LOAD=" + DERIVED_PROFILE,
                "KCTRL_PRODUCTION_VERIFY PROFILE=" + DERIVED_PROFILE,
            )
        )
    elif variant != "source":
        raise OwnedPatternError("variant_invalid")
    lines.append(ASSERT_LINE)
    return "\n".join(lines)


def build_pattern(variant: str) -> Tuple[bytes, Dict[str, Any]]:
    legacy = load_legacy_module()
    legacy_payload, geometry_sha256, filament_mm = legacy.render_pattern_gcode(variant)
    actual_legacy_sha256 = sha256_bytes(legacy_payload)
    if actual_legacy_sha256 != LEGACY_PATTERN_SHA256[variant]:
        raise OwnedPatternError("legacy_pattern_hash_drift:%s" % actual_legacy_sha256)
    text = legacy_payload.decode("utf-8")
    if text.count(ASSERT_LINE) != 1:
        raise OwnedPatternError("legacy_assert_count_invalid")
    if text.count(LEGACY_TAIL) != 1:
        raise OwnedPatternError("legacy_tail_count_invalid")
    text = text.replace(
        "; MESH-EDGE-DIAGNOSTIC-V1 PATTERN",
        "; MESH-EDGE-DIAGNOSTIC-OWNED-START-R2-V1 PATTERN\n; mission: " + MISSION,
        1,
    )
    text = text.replace(ASSERT_LINE, owned_prefix(variant), 1)
    text = text.replace(LEGACY_TAIL, SAFE_TAIL, 1)
    payload = text.encode("utf-8")
    validate_owned_pattern(payload, variant)
    actual_owned_sha256 = sha256_bytes(payload)
    if actual_owned_sha256 != OWNED_PATTERN_SHA256[variant]:
        raise OwnedPatternError("owned_pattern_hash_drift:%s" % actual_owned_sha256)
    return payload, {
        "variant": variant,
        "legacy_sha256": sha256_bytes(legacy_payload),
        "owned_sha256": actual_owned_sha256,
        "geometry_sha256": geometry_sha256,
        "estimated_filament_mm": round(float(filament_mm), 6),
    }


def executable_lines(payload: bytes):
    for raw in payload.decode("utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith(";"):
            yield line


def validate_owned_pattern(payload: bytes, variant: str) -> None:
    text = payload.decode("utf-8")
    lines = list(executable_lines(payload))
    if lines.count(START_CALL) != 1 or lines.count(ASSERT_LINE) != 1:
        raise OwnedPatternError("owned_start_or_assert_count_invalid")
    if any(line == "START_PRINT" or line.startswith("START_PRINT ") for line in lines):
        raise OwnedPatternError("stock_start_forbidden")
    if any(line == "END_PRINT" or line.startswith("END_PRINT ") for line in lines):
        raise OwnedPatternError("stock_end_forbidden")
    if any(line in ("T0", "T1", "T2", "T3") for line in lines):
        raise OwnedPatternError("physical_tool_selection_forbidden")
    if "k1_p001_t055_r001_n06x06" in text:
        raise OwnedPatternError("obsolete_6x6_fallback_forbidden")
    required_tail = (
        "KCTRL_START_ABORT_V1",
        "BED_MESH_PROFILE LOAD=" + SOURCE_PROFILE,
        "KCTRL_CLEAR_MANUAL_NOZZLE_CLEAN_V1",
        "G1 Z50 F600",
        "G1 X203 Y273 F1200",
        "M400",
        "M84",
    )
    if any(lines.count(line) != 1 for line in required_tail):
        raise OwnedPatternError("safe_tail_invalid")
    if variant == "source":
        if DERIVED_PROFILE in text:
            raise OwnedPatternError("source_uses_derived_profile")
    elif variant == "corrected":
        if lines.count("BED_MESH_PROFILE LOAD=" + DERIVED_PROFILE) != 1:
            raise OwnedPatternError("derived_profile_load_missing")
        if lines.count("KCTRL_PRODUCTION_VERIFY PROFILE=" + DERIVED_PROFILE) != 1:
            raise OwnedPatternError("derived_profile_verification_missing")
    else:
        raise OwnedPatternError("variant_invalid")


def build_all(output_directory: Path) -> Dict[str, Any]:
    if output_directory.exists():
        raise OwnedPatternError("output_directory_already_exists")
    output_directory.mkdir(parents=True)
    manifest: Dict[str, Any] = {
        "schema": 1,
        "mission": MISSION,
        "installed_start_owner_sha256": INSTALLED_START_OWNER_SHA256,
        "source_profile": SOURCE_PROFILE,
        "derived_profile": DERIVED_PROFILE,
        "automatic_retry": False,
        "printer_connection": False,
        "files": {},
    }
    names = {
        "source": "K1-MESH-EDGE-R2-01-SOURCE.gcode",
        "corrected": "K1-MESH-EDGE-R2-02-CORRECTED-X034-Y266.gcode",
    }
    for variant in ("source", "corrected"):
        payload, record = build_pattern(variant)
        path = output_directory / names[variant]
        path.write_bytes(payload)
        manifest["files"][variant] = {"name": path.name, **record}
    if manifest["files"]["source"]["geometry_sha256"] != manifest["files"]["corrected"]["geometry_sha256"]:
        raise OwnedPatternError("variant_geometry_drift")
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    manifest = build_all(args.output_directory)
    print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    print("MESH_EDGE_DIAGNOSTIC_OWNED_START_R2_V1_BUILD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
