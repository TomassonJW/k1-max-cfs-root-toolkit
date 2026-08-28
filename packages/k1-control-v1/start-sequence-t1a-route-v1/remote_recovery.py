"""Bounded recovery after a stock filament check drifted mesh and homing state."""

from __future__ import print_function

import hashlib
import json
import os
import socket
import sys
import time
from urllib.request import Request, urlopen


MISSION = "G4-K1-CONTROL-START-SEQUENCE-T1A-ROUTE-V1"
BEST_PROFILE = "k1_p001_t055_r001_n11x11"
BASE_URL = "http://127.0.0.1:7125"
QUERY_PATH = (
    "/printer/objects/query?"
    "print_stats=state,filename"
    "&extruder=target"
    "&heater_bed=target"
    "&toolhead=homed_axes"
    "&bed_mesh=profile_name"
    "&box=state,t_command,T1,T2"
    "&gcode_macro+KCTRL_STATE=accepted_z_valid,accepted_z_offset"
    "&gcode_macro+KCTRL_START_OWNER_STATE=phase,watchdog_armed"
)
EXPECTED_HASHES = {
    "/usr/data/printer_data/config/printer.cfg": "a79c8c917d8eee2575939ade4907640c2b2cf7ff59283d28def895b020e127af",
    "/usr/data/printer_data/config/box.cfg": "e7a6b26df58a9fa8e49d3af6845f5a0937a790c8ef494b96ec72fd7392abc7a7",
    "/usr/data/printer_data/config/gcode_macro.cfg": "864fedde88fbb345c220ae5658f7b04779b3981bd78d68eda6fa63c59c79a04f",
    "/usr/data/printer_data/config/k1-control-z-mesh.cfg": "dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113",
    "/usr/data/printer_data/config/k1-control-calibration-path.cfg": "825aadac8679e0d0e9be140cc5ba4e7656b2bff0d197d1683a73d2b5be4e364e",
    "/usr/data/printer_data/config/k1-control-start-sequence-owner-v1.cfg": "25291e1534f0ba100d3171b983796089a24cd49fdfcef76817406d325e6d8e03",
}
ALLOWED_COMMANDS = (
    "BED_MESH_PROFILE LOAD=%s" % BEST_PROFILE,
    "M84",
)


class RecoveryError(RuntimeError):
    pass


def child(mapping, key):
    value = mapping.get(key)
    return value if isinstance(value, dict) else {}


def hash_file(path):
    if not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def fetch_json(path):
    request = Request(BASE_URL + path, method="GET")
    with urlopen(request, timeout=5.0) as response:
        return json.loads(response.read().decode("utf-8"))


def route_for(unit_name, unit):
    slot = unit.get("filament")
    if unit.get("state") == "connect" and slot in ("A", "B", "C", "D"):
        return "%s%s" % (unit_name, slot)
    return None


def snapshot():
    server = child(fetch_json("/server/info"), "result")
    status = child(child(fetch_json(QUERY_PATH), "result"), "status")
    box = child(status, "box")
    t1 = child(box, "T1")
    t2 = child(box, "T2")
    routes = [route for route in (route_for("T1", t1), route_for("T2", t2)) if route]
    return {
        "server": {
            "klippy_state": server.get("klippy_state"),
            "failed_components": server.get("failed_components"),
            "warnings": server.get("warnings"),
        },
        "print_state": child(status, "print_stats").get("state"),
        "filename_present": bool(child(status, "print_stats").get("filename")),
        "heater_targets": [child(status, "extruder").get("target"), child(status, "heater_bed").get("target")],
        "homed_axes": child(status, "toolhead").get("homed_axes"),
        "mesh_profile": child(status, "bed_mesh").get("profile_name"),
        "routes": routes,
        "cfs_command": box.get("t_command"),
        "cfs_state": box.get("state"),
        "T1_state": t1.get("state"),
        "T2_state": t2.get("state"),
        "accepted_z_valid": child(status, "gcode_macro KCTRL_STATE").get("accepted_z_valid"),
        "accepted_z_offset": child(status, "gcode_macro KCTRL_STATE").get("accepted_z_offset"),
        "start_owner": child(status, "gcode_macro KCTRL_START_OWNER_STATE"),
        "hashes": {path: hash_file(path) for path in EXPECTED_HASHES},
    }


def validate_common(value):
    if value["server"] != {"klippy_state": "ready", "failed_components": [], "warnings": []}:
        raise RecoveryError("server_not_clean")
    if value["print_state"] != "standby" or value["filename_present"]:
        raise RecoveryError("printer_not_standby")
    if [float(item) for item in value["heater_targets"]] != [0.0, 0.0]:
        raise RecoveryError("heater_target_nonzero")
    if value["cfs_state"] != "connect" or value["T1_state"] != "connect" or value["T2_state"] != "connect":
        raise RecoveryError("cfs_disconnected")
    if value["routes"] != ["T1A"] or value["cfs_command"] not in (None, ""):
        raise RecoveryError("unique_T1A_not_stable")
    if value["accepted_z_valid"] != 1 or abs(float(value["accepted_z_offset"]) - (-0.04)) > 0.0005:
        raise RecoveryError("accepted_z_drift")
    if value["start_owner"].get("phase") != "idle" or value["start_owner"].get("watchdog_armed") not in (0, 0.0):
        raise RecoveryError("start_owner_not_idle")
    if value["hashes"] != EXPECTED_HASHES:
        raise RecoveryError("configuration_hash_drift")


def send_gcode(script):
    if script not in ALLOWED_COMMANDS:
        raise RecoveryError("gcode_not_reviewed")
    request = {"id": 7601, "method": "gcode/script", "params": {"script": script}}
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(15.0)
    try:
        client.connect("/tmp/klippy_uds")
        client.sendall((json.dumps(request) + "\x03").encode("utf-8"))
        data = b""
        while b"\x03" not in data:
            chunk = client.recv(65536)
            if not chunk:
                break
            data += chunk
    finally:
        client.close()
    if not data:
        raise RecoveryError("gcode_response_missing")
    response = json.loads(data.split(b"\x03", 1)[0].decode("utf-8"))
    if response.get("error"):
        raise RecoveryError("gcode_rejected")


def run():
    before = snapshot()
    validate_common(before)
    if before["mesh_profile"] not in ("default", BEST_PROFILE):
        raise RecoveryError("unexpected_active_mesh")
    attempted = []
    response_errors = []
    if before["mesh_profile"] != BEST_PROFILE:
        command = "BED_MESH_PROFILE LOAD=%s" % BEST_PROFILE
        attempted.append(command)
        try:
            send_gcode(command)
        except Exception as exc:
            response_errors.append("%s:%s" % (type(exc).__name__, exc))
    if before["homed_axes"] not in ("", []):
        attempted.append("M84")
        try:
            send_gcode("M84")
        except Exception as exc:
            response_errors.append("%s:%s" % (type(exc).__name__, exc))
    time.sleep(1.0)
    after_one = snapshot()
    time.sleep(1.0)
    after_two = snapshot()
    for value in (after_one, after_two):
        validate_common(value)
        if value["mesh_profile"] != BEST_PROFILE:
            raise RecoveryError("best_mesh_not_restored")
        if value["homed_axes"] not in ("", []):
            raise RecoveryError("axes_not_released")
    if after_one != after_two:
        raise RecoveryError("final_readback_not_stable")
    return {
        "schema": 1,
        "mission": MISSION,
        "action": "recover_after_wrong_stock_button",
        "status": "START_SEQUENCE_T1A_ROUTE_V1_RECOVERY_OK",
        "before": before,
        "after_one": after_one,
        "after_two": after_two,
        "attempted_commands": attempted,
        "response_errors": response_errors,
        "effects": {
            "heater_action": False,
            "motion_action": False,
            "extrusion_action": False,
            "cfs_action": False,
            "remote_write": False,
            "service_action": False,
        },
    }


def main():
    try:
        result = run()
    except Exception as exc:
        result = {
            "schema": 1,
            "mission": MISSION,
            "status": "START_SEQUENCE_T1A_ROUTE_V1_RECOVERY_KO",
            "error": "%s:%s" % (type(exc).__name__, exc),
        }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"].endswith("RECOVERY_OK") else 1


if __name__ == "__main__":
    raise SystemExit(main())
