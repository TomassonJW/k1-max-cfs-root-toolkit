"""Atomic installer for the already transferred, hash-pinned sacrificial G-code."""

from __future__ import print_function

import hashlib
import json
import os
import sys


ROOT = "/usr/data/printer_data/gcodes"
NAME = "K1-START-OWNER-T1A-2LAYER.gcode"


def digest(path):
    value = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            value.update(block)
    return value.hexdigest()


def main():
    if len(sys.argv) != 3:
        print(json.dumps({"status": "INVALID_ARGUMENTS"}))
        return 2
    stage_name, expected = sys.argv[1:]
    if "/" in stage_name or "\\" in stage_name or not stage_name.startswith(".k1-control-stage-"):
        raise RuntimeError("invalid_stage_name")
    stage = os.path.join(ROOT, stage_name)
    target = os.path.join(ROOT, NAME)
    if not os.path.isfile(stage) or digest(stage) != expected:
        raise RuntimeError("stage_hash_mismatch")
    if os.path.exists(target):
        if not os.path.isfile(target) or digest(target) != expected:
            raise RuntimeError("different_target_already_exists")
        os.unlink(stage)
        print(json.dumps({"status": "GCODE_ALREADY_EXACT", "sha256": expected}, sort_keys=True))
        return 0
    os.replace(stage, target)
    if digest(target) != expected:
        raise RuntimeError("installed_hash_mismatch")
    print(json.dumps({"status": "GCODE_INSTALL_OK", "sha256": expected}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
