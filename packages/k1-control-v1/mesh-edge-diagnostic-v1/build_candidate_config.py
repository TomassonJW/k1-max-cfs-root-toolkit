#!/usr/bin/env python3
"""Append the reviewed diagnostic profile to Klipper's SAVE_CONFIG block."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
EDITOR_DIR = PACKAGE_DIR.parent / "mesh-editor-offline-v1"
SOURCE_PROFILE = "k1_p001_t055_r001_n11x11"
ROBUST_PROFILE = "k1_p001_t055_r001_n06x06"
DERIVED_PROFILE = SOURCE_PROFILE + "_tuned_v001"
ALLOWED_BASELINE_SHA256 = {
    "f88d6b52477592805384fca2b4d7abd00298deecd82227af2fa580085fe26fa2",
}


class CandidateConfigError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def encode_save_config_block(block: str) -> str:
    """Keep every appended line inside Klipper's generated comment envelope."""
    encoded: list[str] = []
    for line in block.splitlines():
        if line.startswith("#*#"):
            encoded.append(line)
        elif line.startswith("#"):
            encoded.append("#*# " + line)
        elif not line:
            encoded.append("#*#")
        else:
            raise CandidateConfigError(
                "Le profil canonique contient une ligne active hors SAVE_CONFIG."
            )
    return "\n".join(encoded)


def build_candidate(base: bytes, profile_block: bytes, expected_base_sha256: str) -> bytes:
    actual = sha256_bytes(base)
    if expected_base_sha256 not in ALLOWED_BASELINE_SHA256 or actual != expected_base_sha256:
        raise CandidateConfigError("printer.cfg n'a pas l'empreinte de base revue.")
    try:
        text = base.decode("utf-8")
        block = profile_block.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CandidateConfigError("La configuration ou le profil n'est pas en UTF-8.") from exc
    for profile in (ROBUST_PROFILE, SOURCE_PROFILE):
        if text.count("#*# [bed_mesh " + profile + "]") != 1:
            raise CandidateConfigError("Le profil requis est absent ou dupliqué : " + profile)
    if text.count("#*# <---------------------- SAVE_CONFIG ---------------------->") != 1:
        raise CandidateConfigError("Le marqueur SAVE_CONFIG est absent ou dupliqué.")
    if DERIVED_PROFILE in text:
        raise CandidateConfigError("Le profil diagnostic existe déjà.")
    sys.path.insert(0, str(EDITOR_DIR))
    from klipper_profile import canonical_round_trip  # pylint: disable=import-error,import-outside-toplevel

    canonical = encode_save_config_block(canonical_round_trip(block))
    newline = "\r\n" if "\r\n" in text else "\n"
    base_text = text.rstrip("\r\n") + newline + "#*#" + newline
    candidate = (base_text + canonical.replace("\n", newline).rstrip("\r\n") + newline).encode("utf-8")
    if candidate.count(("#*# [bed_mesh " + DERIVED_PROFILE + "]").encode("utf-8")) != 1:
        raise CandidateConfigError("Le profil diagnostic n'est pas unique dans le candidat.")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--expected-base-sha256", required=True)
    args = parser.parse_args()
    candidate = build_candidate(
        args.base.read_bytes(), args.profile.read_bytes(), args.expected_base_sha256
    )
    args.candidate.write_bytes(candidate)
    print("candidate_sha256=" + sha256_bytes(candidate))
    print("BUILD_MESH_EDGE_DIAGNOSTIC_CONFIG_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
