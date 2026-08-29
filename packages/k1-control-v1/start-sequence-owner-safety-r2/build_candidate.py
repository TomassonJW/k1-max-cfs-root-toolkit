"""Derive the reviewed start-owner purge correction without rewriting V1 history."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
SOURCE = ROOT / "packages" / "k1-control-v1" / "start-sequence-owner-v1" / "k1-control-start-sequence-owner-v1.cfg"
OUTPUT = PACKAGE / "k1-control-start-sequence-owner-safety-r2.cfg"
SOURCE_SHA256 = "25291e1534f0ba100d3171b983796089a24cd49fdfcef76817406d325e6d8e03"
REPLACEMENTS = (
    ("    G1 X15 Y20 F9000", "    G1 X0.1 Y20 F6000"),
    (
        "    G1 Y180 E18 F1200",
        "    G1 Y180 E10 F3000\n"
        "    G1 X0.4 Y180 F3000\n"
        "    G1 Y20 E10 F3000\n"
        "    G1 Y10 F3000",
    ),
    ("    G1 E-0.8 F1800", "    G1 E-1.2 F1800"),
    ("    G1 Z2 F1200", "    G1 Z5 F1200"),
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def derive() -> bytes:
    source = SOURCE.read_bytes()
    if digest(source) != SOURCE_SHA256:
        raise ValueError("start_owner_v1_source_hash_drift")
    text = source.decode("utf-8")
    for old, new in REPLACEMENTS:
        if text.count(old) != 1:
            raise ValueError("purge_source_line_not_unique:%s" % old.strip())
        text = text.replace(old, new)
    return text.encode("utf-8")


def build() -> dict:
    candidate = derive()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(candidate)
    return {
        "status": "START_SEQUENCE_OWNER_SAFETY_R2_BUILD_OK",
        "source_sha256": SOURCE_SHA256,
        "candidate_sha256": digest(candidate),
        "candidate_bytes": len(candidate),
        "output": str(OUTPUT),
    }


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
