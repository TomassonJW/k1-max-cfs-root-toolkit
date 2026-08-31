#!/usr/bin/env python3
"""Calcule sans ecriture les deux configurations apres activation exacte."""

import base64
import hashlib
import json
from pathlib import Path


PRINTER = Path("/usr/data/printer_data/config/printer.cfg")
MOONRAKER = Path(
    "/usr/data/k1-control-v1/current/config/moonraker.conf"
)
BASE_PRINTER = "c3b732ff1b4069da952392eb5eb3d6e2527305164186a723295694ef0d32e941"
BASE_MOONRAKER = "ea817b7275909fa299872f2a23ad2d510470588afd96a738be1dc3277c26d835"


def digest(value):
    return hashlib.sha256(value).hexdigest()


printer = PRINTER.read_bytes()
moon = MOONRAKER.read_bytes()
if digest(printer) != BASE_PRINTER or digest(moon) != BASE_MOONRAKER:
    raise RuntimeError("reviewed_activation_baseline_changed")

replacements = (
    (
        b"[include k1-control-cfs-direct-owner-disabled-v1.cfg]",
        b"[include k1-control-cfs-direct-owner-active-v1.cfg]",
    ),
    (
        b"[include k1-control-stock-derived-cycle-owner-disabled-v1.cfg]",
        b"[include k1-control-stock-cycle-active-v1.cfg]",
    ),
    (
        b"[include k1-control-stock-geometry-handoff-disabled-v1.cfg]",
        b"[include k1-control-stock-geometry-handoff-active-v1.cfg]",
    ),
)
candidate = printer
for old, new in replacements:
    if candidate.count(old) != 1 or candidate.count(new) != 0:
        raise RuntimeError("printer_include_topology_invalid")
    candidate = candidate.replace(old, new, 1)

old_section = base64.b64decode("__OLD_SECTION_B64__").strip()
new_section = base64.b64decode("__NEW_SECTION_B64__").strip()
if moon.count(old_section) != 1 or moon.count(new_section) != 0:
    raise RuntimeError("moonraker_section_topology_invalid")
moon_candidate = moon.replace(old_section, new_section, 1)

print(json.dumps({
    "printer_cfg_before_sha256": digest(printer),
    "printer_cfg_candidate_sha256": digest(candidate),
    "moonraker_conf_before_sha256": digest(moon),
    "moonraker_conf_candidate_sha256": digest(moon_candidate),
}, sort_keys=True, separators=(",", ":")))
