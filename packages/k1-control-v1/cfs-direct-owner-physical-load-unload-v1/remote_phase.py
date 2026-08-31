#!/usr/bin/env python3
"""Pilote distant borné pour une qualification physique directe T1A.

Le programme passe uniquement par le socket Klipper local. Il n'écrit aucun
fichier distant, ne déplace aucun axe, ne touche ni au mesh ni au Z, n'imprime
et ne purge jamais. Chaque effet filament possède un identifiant unique et ne
peut pas être rejoué automatiquement.
"""

from __future__ import print_function

from hashlib import sha256
import json
import re
import socket
import sys
import time


MISSION = "G4-K1-CONTROL-CFS-DIRECT-OWNER-PHYSICAL-LOAD-UNLOAD-V1"
V1_CLOSED_KO = True
SOCKET_PATH = "/tmp/klippy_uds"
BEST_MESH = "k1_p001_t055_r001_n11x11"
ACCEPTED_Z_MM = -0.04
ROUTE = "T1A"
NOZZLE_C = 220.0
MATERIAL_MIN_C = 190.0
MATERIAL_MAX_C = 230.0
TEMPERATURE_TIMEOUT_S = 180.0
ALLOWED_ACTIONS = {
    "snapshot",
    "preflight",
    "disable_auto_refill",
    "active_preflight",
    "prepare_clear",
    "load",
    "unload",
    "shutdown",
    "restore_auto_refill",
    "final_validate",
}
SAFE_CAPTURE_ID = re.compile(
    r"^[0-9]{8}-[0-9]{6}-g4-k1-control-cfs-direct-owner-physical-load-unload-v1$"
)


class GateError(RuntimeError):
    def __init__(self, code):
        RuntimeError.__init__(self, code)
        self.code = code


def require(condition, code):
    if not condition:
        raise GateError(code)


def rpc(request_id, method, params=None, timeout_s=20.0):
    request = {"id": request_id, "method": method, "params": params or {}}
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout_s)
    try:
        client.connect(SOCKET_PATH)
        client.sendall((json.dumps(request) + "\x03").encode("utf-8"))
        data = b""
        while b"\x03" not in data:
            chunk = client.recv(65536)
            if not chunk:
                break
            data += chunk
    finally:
        client.close()
    require(bool(data), "klipper_response_missing")
    message = json.loads(data.split(b"\x03", 1)[0].decode("utf-8"))
    if message.get("error"):
        raise GateError("klipper_command_rejected")
    return message.get("result", {})


OBJECTS = {
    "webhooks": ["state", "state_message"],
    "print_stats": ["state", "filename"],
    "extruder": ["target", "temperature", "can_extrude"],
    "heater_bed": ["target", "temperature"],
    "toolhead": ["homed_axes", "position"],
    "bed_mesh": ["profile_name"],
    "box": None,
    "configfile": ["warnings"],
    "gcode_macro KCTRL_STATE": None,
    "gcode_macro KCTRL_START_OWNER_STATE": None,
    "filament_switch_sensor filament_sensor": ["filament_detected"],
    "filament_switch_sensor filament_sensor_2": ["filament_detected"],
    "k1_control_cfs_direct_owner": None,
}


def query_status():
    return rpc(7101, "objects/query", {"objects": OBJECTS}).get("status", {})


def bool_sensor(status, name):
    value = status.get(name, {}).get("filament_detected")
    require(value in (True, False), "sensor_status_invalid")
    return bool(value)


def box_projection(box):
    units = {}
    routes = []
    for name in ("T1", "T2", "T3", "T4"):
        unit = box.get(name, {}) if isinstance(box, dict) else {}
        filament = unit.get("filament")
        units[name] = {"state": unit.get("state"), "filament": filament}
        if filament not in (None, "", "None", "none"):
            routes.append("%s%s" % (name, filament))
    return {
        "state": box.get("state") if isinstance(box, dict) else None,
        "t_command": box.get("t_command") if isinstance(box, dict) else None,
        "auto_refill": box.get("auto_refill") if isinstance(box, dict) else None,
        "enable": box.get("enable") if isinstance(box, dict) else None,
        "units": units,
        "logical_routes": routes,
    }


def snapshot():
    status = query_status()
    runtime = status.get("gcode_macro KCTRL_STATE", {})
    owner = status.get("k1_control_cfs_direct_owner", {})
    return {
        "webhooks": status.get("webhooks", {}),
        "print_state": status.get("print_stats", {}).get("state"),
        "extruder": status.get("extruder", {}),
        "heater_bed": status.get("heater_bed", {}),
        "toolhead": status.get("toolhead", {}),
        "mesh_profile": status.get("bed_mesh", {}).get("profile_name"),
        "runtime": {
            "accepted_z_valid": runtime.get("accepted_z_valid"),
            "accepted_z_offset": runtime.get("accepted_z_offset"),
            "store_integrity": runtime.get("store_integrity"),
        },
        "start_owner_phase": status.get(
            "gcode_macro KCTRL_START_OWNER_STATE", {}
        ).get("phase"),
        "box": box_projection(status.get("box", {})),
        "sensors": {
            "head": bool_sensor(status, "filament_switch_sensor filament_sensor"),
            "after_cutter": bool_sensor(
                status, "filament_switch_sensor filament_sensor_2"
            ),
        },
        "owner": owner,
        "config_warning_count": len(
            status.get("configfile", {}).get("warnings", []) or []
        ),
        "identity_values_exported": False,
    }


def require_common(value, auto_refill):
    require(value["webhooks"].get("state") == "ready", "klipper_not_ready")
    require(value["print_state"] == "standby", "printer_not_standby")
    require(float(value["heater_bed"].get("target")) == 0.0, "bed_target_nonzero")
    require(value["toolhead"].get("homed_axes") in ("", []), "axes_homed")
    require(value["mesh_profile"] == BEST_MESH, "mesh_profile_drift")
    require(value["runtime"]["accepted_z_valid"] in (1, True), "accepted_z_invalid")
    require(
        abs(float(value["runtime"]["accepted_z_offset"]) - ACCEPTED_Z_MM)
        <= 0.0005,
        "accepted_z_drift",
    )
    require(value["runtime"]["store_integrity"] == "ok", "store_integrity_invalid")
    require(value["start_owner_phase"] == "idle", "start_owner_not_idle")
    require(value["box"]["state"] == "connect", "CFS_not_connected")
    require(value["box"]["units"]["T1"]["state"] == "connect", "CFS_T1_not_connected")
    require(value["box"]["units"]["T2"]["state"] == "connect", "CFS_T2_not_connected")
    require(value["box"]["t_command"] == "", "stock_command_active")
    require(value["box"]["enable"] in (1, True), "cfs_interface_disabled")
    require(value["box"]["auto_refill"] == auto_refill, "stock_auto_refill_invalid")
    require(value["box"]["logical_routes"] == [], "stock_logical_route_present")
    require(value["config_warning_count"] == 0, "configuration_warning_present")


def require_disabled(value):
    require_common(value, 1)
    require(float(value["extruder"].get("target")) == 0.0, "nozzle_target_nonzero")
    owner = value["owner"]
    require(owner.get("enabled") is False, "direct_owner_not_disabled")
    require(owner.get("phase") == "disabled", "disabled_phase_invalid")
    require(owner.get("transport_bound") is False, "disabled_transport_bound")
    require(owner.get("stock_commands_blocked") is False, "stock_commands_blocked_while_disabled")
    require(owner.get("frames_sent_count") == 0, "disabled_owner_sent_frame")


def require_active(value):
    require_common(value, 0)
    owner = value["owner"]
    require(owner.get("enabled") is True, "direct_owner_not_enabled")
    require(owner.get("stock_commands_blocked") is True, "stock_commands_not_blocked")
    require(len(owner.get("stock_commands_replaced", [])) > 0, "stock_surface_not_replaced")
    require(owner.get("automatic_retry_count", 0) == 0, "automatic_retry_detected")
    require(owner.get("geometry_commands", []) == [], "geometry_command_detected")
    require(owner.get("mesh_commands", []) == [], "mesh_command_detected")
    require(owner.get("purge_commands", []) == [], "purge_command_detected")
    require(owner.get("temperature_commands", []) == [], "CFS_temperature_command_detected")


def send_gcode(script, request_id, timeout_s=30.0):
    allowed_static = {
        "BOX_ENABLE_AUTO_REFILL ENABLE=0",
        "BOX_ENABLE_AUTO_REFILL ENABLE=1",
        "KCTRL_CFS_DIRECT_PREFLIGHT",
        "M104 S220",
        "TURN_OFF_HEATERS",
    }
    allowed_prefixes = (
        "KCTRL_CFS_DIRECT_RECONCILE ROUTE=T1A OBSERVATION_ID=",
        "KCTRL_CFS_DIRECT_LOAD ROUTE=T1A EFFECT_ID=",
        "KCTRL_CFS_DIRECT_UNLOAD ROUTE=T1A EFFECT_ID=",
    )
    require(
        script in allowed_static or script.startswith(allowed_prefixes),
        "gcode_not_reviewed",
    )
    return rpc(
        request_id,
        "gcode/script",
        {"script": script},
        timeout_s=timeout_s,
    )


def effect_id(capture_id, label):
    return "%s-%s" % (label, sha256(capture_id.encode("ascii")).hexdigest()[:16])


def turn_off_heaters():
    send_gcode("TURN_OFF_HEATERS", 7199, timeout_s=20.0)
    deadline = time.time() + 15.0
    while time.time() < deadline:
        value = snapshot()
        if (
            float(value["extruder"].get("target")) == 0.0
            and float(value["heater_bed"].get("target")) == 0.0
        ):
            return value
        time.sleep(0.5)
    raise GateError("heater_shutdown_unproven")


def heat_nozzle():
    send_gcode("M104 S220", 7120, timeout_s=20.0)
    deadline = time.time() + TEMPERATURE_TIMEOUT_S
    while time.time() < deadline:
        value = snapshot()
        require_active(value)
        target = float(value["extruder"].get("target"))
        actual = float(value["extruder"].get("temperature"))
        require(abs(target - NOZZLE_C) <= 0.5, "nozzle_target_drift")
        if abs(actual - NOZZLE_C) <= 5.0 and value["extruder"].get("can_extrude") is True:
            return value
        time.sleep(1.0)
    raise GateError("nozzle_temperature_timeout")


def owner_command(action, capture_id):
    if action == "reconcile":
        command = (
            "KCTRL_CFS_DIRECT_RECONCILE ROUTE=T1A OBSERVATION_ID=%s"
            % effect_id(capture_id, "reconcile")
        )
        timeout_s = 30.0
    else:
        command = (
            "KCTRL_CFS_DIRECT_%s ROUTE=T1A EFFECT_ID=%s "
            "EXPECTED_C=220 MATERIAL_MIN_C=190 MATERIAL_MAX_C=230"
            % (action.upper(), effect_id(capture_id, action))
        )
        timeout_s = 180.0
    send_gcode(command, 7130 if action == "load" else 7140, timeout_s=timeout_s)


def stable_snapshot(expected_auto_refill, count=2):
    values = []
    for _index in range(count):
        value = snapshot()
        require_common(value, expected_auto_refill)
        values.append(value)
        time.sleep(0.5)
    return values[-1]


def run(action, capture_id):
    result = {
        "schema": 1,
        "mission": MISSION,
        "action": action,
        "capture_id": capture_id,
        "status": None,
        "effect_attempted": False,
        "automatic_retry_count": 0,
        "physical_action": False,
        "heater_action": False,
        "axis_motion": False,
        "mesh_action": False,
        "probe_action": False,
        "purge_action": False,
    }
    try:
        if action == "snapshot":
            result["snapshot"] = snapshot()
            result["status"] = "SNAPSHOT_OK"
        elif action == "preflight":
            value = stable_snapshot(1)
            require_disabled(value)
            result["snapshot"] = value
            result["status"] = "PREFLIGHT_OK_DISABLED"
        elif action == "disable_auto_refill":
            value = snapshot()
            require_disabled(value)
            send_gcode("BOX_ENABLE_AUTO_REFILL ENABLE=0", 7150)
            value = stable_snapshot(0)
            result["snapshot"] = value
            result["status"] = "AUTO_REFILL_DISABLED_OK"
        elif action == "active_preflight":
            value = stable_snapshot(0)
            require_active(value)
            require(value["owner"].get("phase") == "idle", "active_phase_not_idle")
            require(value["owner"].get("frames_sent_count") == 0, "frame_before_preflight")
            send_gcode("KCTRL_CFS_DIRECT_PREFLIGHT", 7160)
            value = stable_snapshot(0)
            require_active(value)
            require(value["owner"].get("transport_bound") is True, "transport_not_bound")
            require(value["owner"].get("frames_sent_count") == 0, "preflight_sent_frame")
            result["snapshot"] = value
            result["status"] = "ACTIVE_PREFLIGHT_OK_NO_FRAME"
        elif action == "prepare_clear":
            before = stable_snapshot(0)
            require_active(before)
            sensors = before["sensors"]
            require(sensors["head"] == sensors["after_cutter"], "initial_sensor_mismatch")
            if not sensors["head"]:
                require(before["owner"].get("phase") == "idle", "clear_path_owner_not_idle")
                require(before["owner"].get("active_route") is None, "clear_path_route_present")
                after = turn_off_heaters()
                branch = "already_clear"
            else:
                require(before["owner"].get("phase") == "idle", "reconcile_owner_not_idle")
                result["effect_attempted"] = True
                owner_command("reconcile", capture_id)
                reconciled = stable_snapshot(0)
                require_active(reconciled)
                require(reconciled["owner"].get("phase") == "loaded", "reconcile_phase_invalid")
                require(reconciled["owner"].get("active_route") == ROUTE, "reconcile_route_invalid")
                heat_nozzle()
                result["heater_action"] = True
                result["physical_action"] = True
                owner_command("unload", capture_id)
                after = turn_off_heaters()
                require_active(after)
                require(after["sensors"] == {"head": False, "after_cutter": False}, "preclear_unload_sensor_not_clear")
                require(after["owner"].get("phase") == "idle", "preclear_unload_phase_invalid")
                require(after["owner"].get("active_route") is None, "preclear_unload_route_present")
                branch = "reconciled_then_unloaded"
            result["branch"] = branch
            result["snapshot"] = after
            result["status"] = "PREPARE_CLEAR_OK"
        elif action == "load":
            before = stable_snapshot(0)
            require_active(before)
            require(before["sensors"] == {"head": False, "after_cutter": False}, "load_path_not_clear")
            require(before["owner"].get("phase") == "idle", "load_owner_not_idle")
            require(before["owner"].get("active_route") is None, "load_route_present")
            heat_nozzle()
            result["heater_action"] = True
            result["physical_action"] = True
            result["effect_attempted"] = True
            owner_command("load", capture_id)
            after = turn_off_heaters()
            require_active(after)
            require(after["sensors"] == {"head": True, "after_cutter": True}, "load_sensor_proof_missing")
            require(after["owner"].get("phase") == "loaded", "load_phase_invalid")
            require(after["owner"].get("active_route") == ROUTE, "load_route_invalid")
            require(after["owner"].get("load_count") == 1, "load_count_invalid")
            result["snapshot"] = after
            result["status"] = "LOAD_T1A_OK"
        elif action == "unload":
            before = stable_snapshot(0)
            require_active(before)
            require(before["sensors"] == {"head": True, "after_cutter": True}, "unload_sensor_proof_missing")
            require(before["owner"].get("phase") == "loaded", "unload_owner_not_loaded")
            require(before["owner"].get("active_route") == ROUTE, "unload_route_invalid")
            heat_nozzle()
            result["heater_action"] = True
            result["physical_action"] = True
            result["effect_attempted"] = True
            owner_command("unload", capture_id)
            after = turn_off_heaters()
            require_active(after)
            require(after["sensors"] == {"head": False, "after_cutter": False}, "final_unload_sensor_not_clear")
            require(after["owner"].get("phase") == "idle", "final_unload_phase_invalid")
            require(after["owner"].get("active_route") is None, "final_unload_route_present")
            require(after["owner"].get("load_count") == 1, "final_load_count_invalid")
            require(after["owner"].get("tip_pull_count") in (1, 2), "tip_pull_count_invalid")
            result["snapshot"] = after
            result["status"] = "UNLOAD_T1A_OK"
        elif action == "shutdown":
            result["snapshot"] = turn_off_heaters()
            result["status"] = "HEATERS_OFF_OK"
        elif action == "restore_auto_refill":
            value = snapshot()
            require_common(value, 0)
            require(value["owner"].get("enabled") is False, "owner_enabled_during_restore")
            send_gcode("BOX_ENABLE_AUTO_REFILL ENABLE=1", 7170)
            value = stable_snapshot(1)
            require_disabled(value)
            result["snapshot"] = value
            result["status"] = "AUTO_REFILL_RESTORED_OK"
        elif action == "final_validate":
            value = stable_snapshot(1)
            require_disabled(value)
            require(value["sensors"] == {"head": False, "after_cutter": False}, "final_filament_path_not_clear")
            result["snapshot"] = value
            result["status"] = "FINAL_DISABLED_SAFE_CLEAR_OK"
        else:
            raise GateError("action_invalid")
    except Exception as error:
        if action not in ("snapshot", "preflight"):
            try:
                result["shutdown_snapshot"] = turn_off_heaters()
            except Exception as shutdown_error:
                result["shutdown_error"] = getattr(shutdown_error, "code", str(shutdown_error))
        try:
            result["failure_snapshot"] = snapshot()
        except Exception as snapshot_error:
            result["snapshot_error"] = getattr(snapshot_error, "code", str(snapshot_error))
        result["status"] = "CLOSED_KO_NO_RETRY"
        result["reason"] = getattr(error, "code", str(error))
    return result


def main(argv):
    if V1_CLOSED_KO:
        print(
            json.dumps(
                {
                    "mission": MISSION,
                    "status": "CLOSED_KO_NO_RETRY",
                    "reason": "v1_closed_cutter_and_bin_purge_required",
                },
                sort_keys=True,
            )
        )
        return 2
    require(len(argv) == 3, "arguments_invalid")
    action = argv[1]
    capture_id = argv[2]
    require(action in ALLOWED_ACTIONS, "action_invalid")
    require(bool(SAFE_CAPTURE_ID.fullmatch(capture_id)), "capture_id_invalid")
    result = run(action, capture_id)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("CFS_DIRECT_OWNER_PHYSICAL_PHASE_CLOSED action=%s" % action)
    return 0 if not result["status"].startswith("CLOSED_KO") else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except GateError as error:
        print(json.dumps({"status": "CLOSED_KO_NO_RETRY", "reason": error.code}, sort_keys=True))
        raise SystemExit(2)
