#!/usr/bin/env python3
"""Sonde en lecture seule les bases exactes de la pose combinée désactivée."""

from hashlib import sha256
import json
from pathlib import Path


PRINTER = Path("/usr/data/printer_data/config/printer.cfg")
MOONRAKER = Path("/usr/data/k1-control-v1/current/config/moonraker.conf")
PRINTER_NEEDLE = b"[include k1-control-cfs-direct-owner-disabled-v1.cfg]\n"
PRINTER_LINES = (
    b"[include k1-control-stock-derived-cycle-owner-disabled-v1.cfg]\n"
    b"[include k1-control-stock-geometry-handoff-disabled-v1.cfg]\n"
)
MOONRAKER_BLOCK = (
    b"[k1_control_stock_cycle]\n"
    b"enabled: false\n"
    b"state_path: /usr/data/k1-control-v1/state/stock-derived-cycle-state.json\n"
)
REQUIRED = {
    "direct_owner_config": "/usr/data/printer_data/config/k1-control-cfs-direct-owner-disabled-v1.cfg",
    "direct_owner_component": "/usr/share/klipper/klippy/extras/k1_control_cfs_direct_owner.py",
    "R4_config": "/usr/data/printer_data/config/k1-control-start-sequence-owner-v1.cfg",
    "integrated_cycle_config": "/usr/data/printer_data/config/k1-control-integrated-production-cycle-v1.cfg",
    "moonraker_existing_cycle": "/usr/data/k1-control-v1/current/moonraker/moonraker/moonraker/components/k1_control_cycle.py",
}
NEW = {
    "stock_cycle_config": "/usr/data/printer_data/config/k1-control-stock-derived-cycle-owner-disabled-v1.cfg",
    "stock_cycle_component": "/usr/share/klipper/klippy/extras/k1_control_stock_cycle_owner.py",
    "geometry_config": "/usr/data/printer_data/config/k1-control-stock-geometry-handoff-disabled-v1.cfg",
    "geometry_component": "/usr/share/klipper/klippy/extras/k1_control_stock_geometry_handoff.py",
    "moonraker_core": "/usr/data/k1-control-v1/current/moonraker/moonraker/moonraker/components/k1_control_stock_cycle_core.py",
    "moonraker_component": "/usr/data/k1-control-v1/current/moonraker/moonraker/moonraker/components/k1_control_stock_cycle.py",
}


def digest(data):
    return sha256(data).hexdigest()


printer = PRINTER.read_bytes()
moonraker = MOONRAKER.read_bytes()
if printer.count(PRINTER_NEEDLE) != 1 or any(line in printer for line in PRINTER_LINES.splitlines(True)):
    raise RuntimeError("printer_cfg_insertion_boundary_invalid")
if b"[k1_control_stock_cycle]" in moonraker:
    raise RuntimeError("moonraker_section_already_present")
printer_candidate = printer.replace(PRINTER_NEEDLE, PRINTER_NEEDLE + PRINTER_LINES, 1)
moonraker_candidate = moonraker
if not moonraker_candidate.endswith(b"\n"):
    moonraker_candidate += b"\n"
if not moonraker_candidate.endswith(b"\n\n"):
    moonraker_candidate += b"\n"
moonraker_candidate += MOONRAKER_BLOCK

result = {
    "schema": 1,
    "printer_cfg": {
        "baseline_sha256": digest(printer),
        "prospective_sha256": digest(printer_candidate),
        "bytes_before": len(printer),
        "bytes_after": len(printer_candidate),
    },
    "moonraker_conf": {
        "baseline_sha256": digest(moonraker),
        "prospective_sha256": digest(moonraker_candidate),
        "bytes_before": len(moonraker),
        "bytes_after": len(moonraker_candidate),
    },
    "required": {},
    "new_paths_absent": {},
    "remote_write": False,
    "gcode": False,
    "service_action": False,
    "heat": False,
    "motion": False,
    "extrusion": False,
    "cfs_frame": False,
}
for name, raw_path in REQUIRED.items():
    path = Path(raw_path)
    if not path.is_file():
        raise RuntimeError("required_file_missing:%s" % name)
    result["required"][name] = digest(path.read_bytes())
for name, raw_path in NEW.items():
    result["new_paths_absent"][name] = not Path(raw_path).exists()
if not all(result["new_paths_absent"].values()):
    raise RuntimeError("new_path_already_present")
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
print("REMOTE_STOCK_DERIVED_HANDOFF_MOONRAKER_BASELINE_READ_ONLY_OK")
