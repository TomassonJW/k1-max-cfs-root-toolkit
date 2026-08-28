#!/usr/bin/env python3
"""Remote read-only Moonraker websocket observer for the exact K1 gate."""

from __future__ import print_function

import base64
import hashlib
import json
import os
import socket
import struct
import time


HOST = "127.0.0.1"
PORT = 7125
TIMEOUT_S = 5.0
OBSERVATION_WINDOW_S = 2.0
CONFIG_PATHS = (
    "/usr/data/printer_data/config/printer.cfg",
    "/usr/data/printer_data/config/box.cfg",
    "/usr/data/printer_data/config/gcode_macro.cfg",
)
UNITS = ("T1", "T2", "T3", "T4")
SLOTS = ("A", "B", "C", "D")
OBJECTS = {
    "print_stats": ["state"],
    "extruder": ["target"],
    "heater_bed": ["target"],
    "toolhead": ["homed_axes"],
    "bed_mesh": ["profile_name"],
    "box": None,
    "gcode_macro KCTRL_STATE": [
        "ready", "session_active", "accepted_z_valid", "accepted_z_offset", "low_moves_armed"
    ],
    "k1_control_store": [
        "ready", "integrity", "accepted_z_valid", "accepted_z_offset", "session_active", "low_moves_armed"
    ],
}


class ObserverError(RuntimeError):
    pass


def canonical_hash(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def config_hashes():
    return {path: hash_file(path) if os.path.isfile(path) else None for path in CONFIG_PATHS}


def child(value, key):
    result = value.get(key) if isinstance(value, dict) else None
    return result if isinstance(result, dict) else {}


def deep_merge(target, update):
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        else:
            target[key] = value


def connection_material(status):
    box = child(status, "box")
    return {
        "root_state": box.get("state"),
        "units": {name: child(box, name).get("state") for name in UNITS},
    }


def mapping_material(status):
    box = child(status, "box")
    return {
        "root_state": box.get("state"),
        "units": {
            name: {
                "state": child(box, name).get("state"),
                "filament": child(box, name).get("filament"),
            }
            for name in UNITS
        },
        "same_material_sha256": canonical_hash(box.get("same_material")),
    }


class WebSocketClient(object):
    def __init__(self):
        self.socket = None

    def connect(self):
        connection = socket.create_connection((HOST, PORT), timeout=TIMEOUT_S)
        connection.settimeout(TIMEOUT_S)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            "GET /websocket HTTP/1.1\r\n"
            "Host: %s:%d\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ) % (HOST, PORT, key)
        connection.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = connection.recv(4096)
            if not chunk:
                raise ObserverError("websocket_handshake_closed")
            response += chunk
            if len(response) > 16384:
                raise ObserverError("websocket_handshake_too_large")
        header = response.split(b"\r\n\r\n", 1)[0].decode("latin-1")
        if not header.startswith("HTTP/1.1 101"):
            raise ObserverError("websocket_upgrade_rejected")
        expected = base64.b64encode(hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
        ).digest()).decode("ascii")
        headers = {}
        for line in header.split("\r\n")[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()
        if headers.get("sec-websocket-accept") != expected:
            raise ObserverError("websocket_accept_invalid")
        self.socket = connection

    def _recv_exact(self, length):
        data = b""
        while len(data) < length:
            chunk = self.socket.recv(length - len(data))
            if not chunk:
                raise ObserverError("websocket_closed")
            data += chunk
        return data

    def send_json(self, value):
        payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
        mask = os.urandom(4)
        first = 0x81
        length = len(payload)
        if length < 126:
            header = struct.pack("!BB", first, 0x80 | length)
        elif length < 65536:
            header = struct.pack("!BBH", first, 0x80 | 126, length)
        else:
            header = struct.pack("!BBQ", first, 0x80 | 127, length)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(bytearray(payload)))
        self.socket.sendall(header + mask + masked)

    def recv_json(self, timeout=None):
        if timeout is not None:
            self.socket.settimeout(timeout)
        while True:
            header = self._recv_exact(2)
            first, second = struct.unpack("!BB", header)
            fin = (first & 0x80) != 0
            opcode = first & 0x0F
            masked = (second & 0x80) != 0
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if masked else None
            payload = self._recv_exact(length)
            if masked:
                payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(bytearray(payload)))
            if opcode == 0x9:
                self._send_control(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode == 0x8:
                raise ObserverError("websocket_close_frame")
            if opcode != 0x1 or not fin:
                raise ObserverError("websocket_frame_unsupported")
            return json.loads(payload.decode("utf-8"))

    def _send_control(self, opcode, payload):
        mask = os.urandom(4)
        header = struct.pack("!BB", 0x80 | opcode, 0x80 | len(payload))
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(bytearray(payload)))
        self.socket.sendall(header + mask + masked)

    def close(self):
        if self.socket is not None:
            try:
                self.socket.close()
            finally:
                self.socket = None


class StateObserver(object):
    def __init__(self, client):
        self.client = client
        self.status = {}
        self.transition_seq = 0
        self.transition_events = []

    def process_notification(self, message):
        if message.get("method") != "notify_status_update":
            return
        params = message.get("params")
        if not isinstance(params, list) or len(params) < 2 or not isinstance(params[0], dict):
            raise ObserverError("status_notification_invalid")
        before = connection_material(self.status)
        deep_merge(self.status, params[0])
        after = connection_material(self.status)
        if before != after:
            self.transition_seq += 1
            self.transition_events.append({
                "seq": self.transition_seq,
                "eventtime": params[1],
                "before_sha256": canonical_hash(before),
                "after_sha256": canonical_hash(after),
            })

    def call(self, request_id, method, params=None):
        request = {"jsonrpc": "2.0", "method": method, "id": request_id}
        if params is not None:
            request["params"] = params
        self.client.send_json(request)
        deadline = time.monotonic() + TIMEOUT_S
        while time.monotonic() < deadline:
            message = self.client.recv_json(max(0.1, deadline - time.monotonic()))
            if message.get("method"):
                self.process_notification(message)
                continue
            if message.get("id") == request_id:
                if message.get("error"):
                    raise ObserverError("rpc_error_%s" % method)
                return message.get("result")
        raise ObserverError("rpc_timeout_%s" % method)

    def drain(self, duration):
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            try:
                message = self.client.recv_json(min(0.25, max(0.05, deadline - time.monotonic())))
            except socket.timeout:
                continue
            self.process_notification(message)


def safe_observation(status, sample_seq, connection_id, eventtime, transition_seq, transition_digest):
    print_stats = child(status, "print_stats")
    extruder = child(status, "extruder")
    heater_bed = child(status, "heater_bed")
    toolhead = child(status, "toolhead")
    bed_mesh = child(status, "bed_mesh")
    box = child(status, "box")
    runtime = child(status, "gcode_macro KCTRL_STATE")
    store = child(status, "k1_control_store")
    connected = []
    engaged = []
    for unit_name in UNITS:
        unit = child(box, unit_name)
        if unit.get("state") == "connect":
            connected.append(unit_name)
            if unit.get("filament") in SLOTS:
                engaged.append(unit_name + unit.get("filament"))
    raw_command = box.get("t_command")
    command = raw_command if isinstance(raw_command, str) else ""
    active_command = "" if not command else "present:" + hashlib.sha256(command.encode("utf-8")).hexdigest()
    return {
        "schema": 2,
        "sample_seq": sample_seq,
        "observer_connection_id": connection_id,
        "observer_connection_live": True,
        "observer_eventtime": eventtime,
        "cfs_transition_seq": transition_seq,
        "cfs_transition_digest": transition_digest,
        "mapping_revision": "mapping:" + canonical_hash(mapping_material(status)),
        "printer_state": print_stats.get("state"),
        "connected_units": connected,
        "active_command": active_command,
        "stock_auto_refill": box.get("auto_refill"),
        "stock_cfs_print_enable": box.get("enable"),
        "engaged_routes": engaged,
        "protected": {
            "mesh_profile": bed_mesh.get("profile_name"),
            "runtime_accepted_z_valid": runtime.get("accepted_z_valid"),
            "runtime_accepted_z_offset_mm": runtime.get("accepted_z_offset"),
            "store_ready": store.get("ready"),
            "store_integrity": store.get("integrity"),
            "store_accepted_z_valid": store.get("accepted_z_valid"),
            "store_accepted_z_offset_mm": store.get("accepted_z_offset"),
            "homed_axes": toolhead.get("homed_axes"),
            "nozzle_target_c": extruder.get("target"),
            "bed_target_c": heater_bed.get("target"),
        },
    }


def extract_status(result, label):
    if not isinstance(result, dict) or not isinstance(result.get("status"), dict):
        raise ObserverError("%s_status_missing" % label)
    eventtime = result.get("eventtime")
    if not isinstance(eventtime, (int, float)):
        raise ObserverError("%s_eventtime_missing" % label)
    return result["status"], float(eventtime)


def extract_connection_id(result):
    if isinstance(result, int) and not isinstance(result, bool):
        return result
    if isinstance(result, dict):
        value = result.get("websocket_id", result.get("connection_id"))
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    raise ObserverError("observer_connection_id_missing")


def run():
    hashes_before = config_hashes()
    client = WebSocketClient()
    observer = StateObserver(client)
    client.connect()
    try:
        connection_id = extract_connection_id(observer.call(1, "server.websocket.id"))
        subscribed = observer.call(2, "printer.objects.subscribe", {"objects": OBJECTS})
        first_status, first_eventtime = extract_status(subscribed, "subscription")
        observer.status = first_status
        first_digest = "cfs-state:" + canonical_hash(connection_material(first_status))
        first = safe_observation(
            first_status, 1, connection_id, first_eventtime, observer.transition_seq, first_digest
        )
        observer.drain(OBSERVATION_WINDOW_S)
        queried = observer.call(3, "printer.objects.query", {"objects": OBJECTS})
        second_status, second_eventtime = extract_status(queried, "query")
        before_query = connection_material(observer.status)
        after_query = connection_material(second_status)
        if before_query != after_query:
            observer.transition_seq += 1
            observer.transition_events.append({
                "seq": observer.transition_seq,
                "eventtime": second_eventtime,
                "before_sha256": canonical_hash(before_query),
                "after_sha256": canonical_hash(after_query),
                "source": "final_query",
            })
        observer.status = second_status
        second_digest = "cfs-state:" + canonical_hash(connection_material(second_status))
        second = safe_observation(
            second_status, 2, connection_id, second_eventtime, observer.transition_seq, second_digest
        )
        hashes_after = config_hashes()
    finally:
        client.close()
    return {
        "schema": 2,
        "mission": "G4-K1-CONTROL-CFS-OWNER-OBSERVABILITY-LIVE-READ-ONLY-V2",
        "authority": "strict_read_only",
        "capture_mode": "single_ssh_persistent_moonraker_websocket_subscription",
        "identity_values_exported": False,
        "identity_fields_stripped": ["sn", "uuid"],
        "rpc_methods": [
            "server.websocket.id", "printer.objects.subscribe", "printer.objects.query"
        ],
        "state_read_count": 2,
        "observation_window_s": OBSERVATION_WINDOW_S,
        "observer_connection_id": connection_id,
        "reported_cfs_transition_count": observer.transition_seq,
        "reported_cfs_transitions": observer.transition_events,
        "observations": [first, second],
        "configuration_hashes_before": hashes_before,
        "configuration_hashes_after": hashes_after,
        "effects": {
            "remote_files_written": False,
            "gcode_sent": False,
            "heater_action": False,
            "motion_action": False,
            "cfs_action": False,
            "service_action": False,
            "guard_imported_or_called": False,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, separators=(",", ":")))
    print("CFS_OWNER_OBSERVABILITY_LIVE_READ_ONLY_V2_CAPTURE_OK")
