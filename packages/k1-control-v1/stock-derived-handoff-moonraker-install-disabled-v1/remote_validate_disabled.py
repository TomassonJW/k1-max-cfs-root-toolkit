#!/usr/bin/env python3
"""Valide la pose combinée désactivée sans appeler une entrée d'effet."""

import json
import os
import socket
from urllib.request import urlopen


SOCKET = "/tmp/klippy_uds"
BASE_URL = "http://127.0.0.1:7125"
STATE_PATH = "/usr/data/k1-control-v1/state/stock-derived-cycle-state.json"


def rpc(request_id, method, params=None):
    request = {"id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(15.0)
    try:
        client.connect(SOCKET)
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
        raise RuntimeError("klippy_response_missing")
    response = json.loads(data.split(b"\x03", 1)[0].decode("utf-8"))
    if response.get("error"):
        raise RuntimeError("klippy_rpc_error:%s" % response["error"])
    return response.get("result", {})


def get_json(path):
    response = urlopen(BASE_URL + path, timeout=10.0)
    try:
        return json.loads(response.read().decode("utf-8"))
    finally:
        response.close()


rpc(1, "gcode/script", {"script": "KCTRL_STOCK_CYCLE_DISABLED_SELFTEST_V1"})
rpc(
    2,
    "gcode/script",
    {"script": "KCTRL_STOCK_GEOMETRY_HANDOFF_DISABLED_SELFTEST_V1"},
)
result = rpc(
    3,
    "objects/query",
    {
        "objects": {
            "k1_control_stock_cycle_owner": None,
            "k1_control_stock_geometry_handoff": None,
        }
    },
)
statuses = result.get("status", {})
owner = statuses.get("k1_control_stock_cycle_owner", {})
geometry = statuses.get("k1_control_stock_geometry_handoff", {})

owner_expected = {
    "owner": "k1_control_stock_derived_cycle",
    "version": "install-disabled-v1",
    "enabled": False,
    "effect_count": 0,
    "automatic_retry_count": 0,
    "stock_BOX_effect_count": 0,
    "probe_command_count": 0,
    "mesh_recalculation_count": 0,
    "command_count": 0,
    "claimed_effect_count": 0,
}
geometry_expected = {
    "owner": "k1_control_stock_geometry_handoff",
    "version": "install-disabled-v1",
    "enabled": False,
    "handoff_count": 0,
    "automatic_retry_count": 0,
    "heat_command_count": 0,
    "motion_command_count": 0,
    "probe_command_count": 0,
    "mesh_recalculation_count": 0,
    "cfs_frame_count": 0,
    "command_count": 0,
    "claimed_effect_count": 0,
}
for label, status, expected in (
    ("owner", owner, owner_expected),
    ("geometry", geometry, geometry_expected),
):
    for key, value in expected.items():
        if status.get(key) != value:
            raise RuntimeError("disabled_status_invalid:%s:%s" % (label, key))
    count = status.get("disabled_selftest_count")
    if not isinstance(count, int) or count < 1:
        raise RuntimeError("disabled_selftest_count_invalid:%s" % label)

moonraker_response = get_json(
    "/machine/k1_control/stock-cycle/disabled-selftest"
)
moonraker = moonraker_response.get("result", moonraker_response)
if moonraker.get("status") != "K1_CONTROL_STOCK_CYCLE_DISABLED_SELFTEST_V1_OK":
    raise RuntimeError("moonraker_disabled_selftest_invalid")
if moonraker.get("enabled") is not False or moonraker.get(
    "refused_effect_endpoints"
) != 6:
    raise RuntimeError("moonraker_disabled_state_invalid")
for field in (
    "effect_request_count",
    "state_file_read_count",
    "state_file_write_count",
    "klippy_query_count",
    "gcode_dispatch_count",
    "camera_request_count",
    "automatic_retry_count",
    "stock_BOX_effect_count",
):
    if moonraker.get(field) != 0:
        raise RuntimeError("moonraker_effect_history:%s" % field)
if os.path.exists(STATE_PATH):
    raise RuntimeError("disabled_component_created_state_file")

safe = {
    "klipper_owner": owner,
    "klipper_geometry": geometry,
    "moonraker": moonraker,
    "state_file_exists": False,
}
print(json.dumps(safe, sort_keys=True, separators=(",", ":")))
print("REMOTE_STOCK_DERIVED_HANDOFF_MOONRAKER_DISABLED_VALIDATE_OK")
