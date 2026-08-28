#!/usr/bin/env python3
"""One-shot live exclusion and exact restore under a continuous observer."""

from copy import deepcopy
import json
import os
import socket
import time


MISSION = "G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-EFFECT-V1"
BEST_CURRENT_MESH = "k1_p001_t055_r001_n11x11"
ACCEPTED_Z_MM = -0.04
EXPECTED_MAPPING_REVISION = "mapping:8d2eaac150bcf43a728dcbc17e9614c9002a408d1eb6db04fa78e0cc6cc5849d"
EXPECTED_CFS_DIGEST = "cfs-state:6e46a8be47371fb4a440e5edc286b8ab18e020eb26ed83671063f24f2c90c6c0"
EXPECTED_HASHES = {
    "/usr/data/printer_data/config/printer.cfg": "f88d6b52477592805384fca2b4d7abd00298deecd82227af2fa580085fe26fa2",
    "/usr/data/printer_data/config/box.cfg": "e7a6b26df58a9fa8e49d3af6845f5a0937a790c8ef494b96ec72fd7392abc7a7",
    "/usr/data/printer_data/config/gcode_macro.cfg": "864fedde88fbb345c220ae5658f7b04779b3981bd78d68eda6fa63c59c79a04f",
}
DISABLE_COMMAND = "BOX_ENABLE_AUTO_REFILL ENABLE=0"
RESTORE_COMMAND = "BOX_ENABLE_AUTO_REFILL ENABLE=1"


class EffectGateError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def require(condition, code):
    if not condition:
        raise EffectGateError(code)


def query_observation(observer, connection_id, sample_seq):
    result = observer.call(100 + sample_seq, "printer.objects.query", {"objects": OBJECTS})
    status, eventtime = extract_status(result, "query_%d" % sample_seq)
    before = connection_material(observer.status)
    after = connection_material(status)
    if before != after:
        observer.transition_seq += 1
        observer.transition_events.append({
            "seq": observer.transition_seq,
            "eventtime": eventtime,
            "before_sha256": canonical_hash(before),
            "after_sha256": canonical_hash(after),
            "source": "query",
        })
    observer.status = status
    digest = "cfs-state:" + canonical_hash(connection_material(status))
    return safe_observation(
        status, sample_seq, connection_id, eventtime, observer.transition_seq, digest
    )


def fresh_pair(observer, connection_id, sample_seq):
    first = query_observation(observer, connection_id, sample_seq)
    observer.drain(1.0)
    second = query_observation(observer, connection_id, sample_seq + 1)
    return [first, second]


def normalized(observation):
    result = deepcopy(observation)
    result.pop("sample_seq", None)
    result.pop("observer_eventtime", None)
    return result


def validate_pair(pair, expected_auto_refill, connection_id, initial_transition_seq):
    require(isinstance(pair, list) and len(pair) == 2, "pair_count_invalid")
    first, second = pair
    require(first["sample_seq"] < second["sample_seq"], "sample_sequence_invalid")
    require(first["observer_connection_id"] == connection_id, "observer_connection_changed")
    require(second["observer_connection_id"] == connection_id, "observer_connection_changed")
    require(first["observer_connection_live"] is True, "observer_connection_not_live")
    require(second["observer_connection_live"] is True, "observer_connection_not_live")
    require(first["cfs_transition_seq"] == initial_transition_seq, "cfs_transition_observed")
    require(second["cfs_transition_seq"] == initial_transition_seq, "cfs_transition_observed")
    require(first["cfs_transition_digest"] == EXPECTED_CFS_DIGEST, "cfs_connection_state_drift")
    require(second["cfs_transition_digest"] == EXPECTED_CFS_DIGEST, "cfs_connection_state_drift")
    require(normalized(first) == normalized(second), "stable_pair_changed")
    require(first["mapping_revision"] == EXPECTED_MAPPING_REVISION, "mapping_revision_drift")
    require(first["printer_state"] == "standby", "printer_not_standby")
    require(first["connected_units"] == ["T1", "T2"], "connected_units_invalid")
    require(first["active_command"] == "", "stock_command_active")
    require(first["stock_auto_refill"] == expected_auto_refill, "stock_auto_refill_unproven")
    require(first["stock_cfs_print_enable"] == 1, "stock_cfs_print_disabled")
    require(first["engaged_routes"] == [], "engaged_route_present")
    protected = first["protected"]
    require(protected["mesh_profile"] == BEST_CURRENT_MESH, "mesh_profile_drift")
    require(protected["runtime_accepted_z_valid"] == 1, "accepted_z_invalid")
    require(abs(float(protected["runtime_accepted_z_offset_mm"]) - ACCEPTED_Z_MM) <= 0.0005, "accepted_z_drift")
    require(protected["store_integrity"] == "ok", "store_integrity_invalid")
    require(protected["store_ready"] is None, "store_shape_drift")
    require(protected["store_accepted_z_valid"] is None, "store_shape_drift")
    require(protected["store_accepted_z_offset_mm"] is None, "store_shape_drift")
    require(protected["homed_axes"] in ("", []), "axes_homed")
    require(float(protected["nozzle_target_c"]) == 0.0, "nozzle_target_nonzero")
    require(float(protected["bed_target_c"]) == 0.0, "bed_target_nonzero")
    return first


def non_target_signature(observation):
    result = deepcopy(observation)
    result.pop("sample_seq", None)
    result.pop("observer_eventtime", None)
    result.pop("stock_auto_refill", None)
    return result


def send_reviewed_gcode(command):
    require(command in {DISABLE_COMMAND, RESTORE_COMMAND}, "gcode_not_reviewed")
    request = {"id": 8801 if command == DISABLE_COMMAND else 8802, "method": "gcode/script", "params": {"script": command}}
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
    require(bool(data), "gcode_response_missing")
    response = json.loads(data.split(b"\x03", 1)[0].decode("utf-8"))
    require(not response.get("error"), "gcode_rejected")
    return {"response_received": True, "error": False}


def capture_pair_record(pair):
    return pair


def run_effect_gate():
    hashes = {"before": config_hashes()}
    require(hashes["before"] == EXPECTED_HASHES, "configuration_hash_preflight_drift")
    client = WebSocketClient()
    observer = StateObserver(client)
    commands = []
    restore_attempted = False
    disable_attempted = False
    result = None
    client.connect()
    try:
        connection_id = extract_connection_id(observer.call(1, "server.websocket.id"))
        subscribed = observer.call(2, "printer.objects.subscribe", {"objects": OBJECTS})
        status, unused_eventtime = extract_status(subscribed, "subscription")
        observer.status = status
        initial_transition_seq = observer.transition_seq
        require(initial_transition_seq == 0, "transition_before_baseline")
        preflight = fresh_pair(observer, connection_id, 1)
        baseline = validate_pair(preflight, 1, connection_id, initial_transition_seq)
        baseline_signature = non_target_signature(baseline)
        hashes["pre_disable"] = config_hashes()
        require(hashes["pre_disable"] == EXPECTED_HASHES, "configuration_hash_pre_disable_drift")

        disable_attempted = True
        disable_ack = send_reviewed_gcode(DISABLE_COMMAND)
        commands.append(DISABLE_COMMAND)
        observer.drain(1.0)
        after_disable = fresh_pair(observer, connection_id, 3)
        disabled = validate_pair(after_disable, 0, connection_id, initial_transition_seq)
        require(non_target_signature(disabled) == baseline_signature, "non_target_drift_after_disable")
        hashes["post_disable"] = config_hashes()
        require(hashes["post_disable"] == EXPECTED_HASHES, "configuration_hash_post_disable_drift")

        before_restore = fresh_pair(observer, connection_id, 5)
        release = validate_pair(before_restore, 0, connection_id, initial_transition_seq)
        require(non_target_signature(release) == baseline_signature, "non_target_drift_before_restore")

        restore_attempted = True
        restore_ack = send_reviewed_gcode(RESTORE_COMMAND)
        commands.append(RESTORE_COMMAND)
        observer.drain(1.0)
        after_restore = fresh_pair(observer, connection_id, 7)
        restored = validate_pair(after_restore, 1, connection_id, initial_transition_seq)
        require(non_target_signature(restored) == baseline_signature, "non_target_drift_after_restore")
        hashes["final"] = config_hashes()
        require(hashes["final"] == EXPECTED_HASHES, "configuration_hash_final_drift")
        result = {
            "schema": 1,
            "mission": MISSION,
            "status": "CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED",
            "observer_connection_id": connection_id,
            "reported_cfs_transition_count": observer.transition_seq,
            "reported_cfs_transitions": observer.transition_events,
            "saved_stock_auto_refill": 1,
            "commands_attempted": commands,
            "attempts": {"disable": 1, "restore": 1},
            "acknowledgements": {"disable": disable_ack, "restore": restore_ack},
            "proof": {
                "before_disable": capture_pair_record(preflight),
                "after_disable": capture_pair_record(after_disable),
                "before_restore": capture_pair_record(before_restore),
                "after_restore": capture_pair_record(after_restore),
            },
            "configuration_hashes": hashes,
            "effects": {
                "gcode_commands_attempted": 2,
                "stock_auto_refill_policy_changed": True,
                "stock_auto_refill_restored": True,
                "filament_action": False,
                "heater_action": False,
                "motion_action": False,
                "remote_files_written": False,
                "service_action": False,
            },
        }
    except Exception as exc:
        rollback = {"attempted": False, "verified": False, "error": None}
        if disable_attempted and not restore_attempted:
            try:
                restore_attempted = True
                rollback["attempted"] = True
                send_reviewed_gcode(RESTORE_COMMAND)
                commands.append(RESTORE_COMMAND)
                observer.drain(1.0)
                recovery_pair = fresh_pair(observer, connection_id, 50)
                validate_pair(recovery_pair, 1, connection_id, initial_transition_seq)
                rollback["verified"] = True
            except Exception as rollback_exc:
                rollback["error"] = getattr(rollback_exc, "code", str(rollback_exc))
        result = {
            "schema": 1,
            "mission": MISSION,
            "status": "CLOSED_KO_ROLLBACK_VERIFIED" if rollback["verified"] else "BLOCKED_UNKNOWN_RESTORE_REQUIRED",
            "reason": getattr(exc, "code", str(exc)),
            "commands_attempted": commands,
            "attempts": {"disable": 1 if disable_attempted else 0, "restore": 1 if restore_attempted else 0},
            "rollback": rollback,
            "configuration_hashes": hashes,
            "effects": {
                "filament_action": False,
                "heater_action": False,
                "motion_action": False,
                "remote_files_written": False,
                "service_action": False,
            },
        }
    finally:
        client.close()
    return result


if __name__ == "__main__" and os.environ.get("K1_EFFECT_LIBRARY") != "1":
    gate_result = run_effect_gate()
    print(json.dumps(gate_result, sort_keys=True, separators=(",", ":")))
    print("CFS_OWNER_EXCLUSION_GUARD_LIVE_EFFECT_V1_CAPTURE_CLOSED")
    raise SystemExit(0 if gate_result["status"] == "CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED" else 2)
