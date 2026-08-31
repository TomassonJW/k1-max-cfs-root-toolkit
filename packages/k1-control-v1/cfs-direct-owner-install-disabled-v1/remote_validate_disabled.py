#!/usr/bin/env python3
"""Valide la pose Klipper désactivée sans ouvrir le transport CFS."""

import json
import socket


SOCKET = "/tmp/klippy_uds"


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


rpc(
    1,
    "gcode/script",
    {"script": "KCTRL_CFS_DIRECT_DISABLED_SELFTEST"},
)
result = rpc(
    2,
    "objects/query",
    {"objects": {"k1_control_cfs_direct_owner": None}},
)
status = result.get("status", {}).get("k1_control_cfs_direct_owner", {})
expected = {
    "owner": "k1_control_direct",
    "version": "install-disabled-v1",
    "enabled": False,
    "phase": "disabled",
    "active_route": None,
    "failure_code": None,
    "transport_bound": False,
    "stock_commands_blocked": False,
    "stock_commands_replaced": [],
    "automatic_retry_count": 0,
    "frames_sent_count": 0,
    "tip_pull_count": 0,
    "load_count": 0,
    "unload_count": 0,
    "temperature_commands": [],
    "geometry_commands": [],
    "mesh_commands": [],
    "purge_commands": [],
}
for key, value in expected.items():
    if status.get(key) != value:
        raise RuntimeError("disabled_status_invalid:%s" % key)
if not isinstance(status.get("disabled_selftest_count"), int) or status.get(
    "disabled_selftest_count"
) < 1:
    raise RuntimeError("disabled_selftest_count_invalid")

safe = {key: status.get(key) for key in sorted(expected)}
safe["disabled_selftest_count"] = status.get("disabled_selftest_count")
print(json.dumps(safe, sort_keys=True, separators=(",", ":")))
print("REMOTE_CFS_DIRECT_OWNER_DISABLED_VALIDATE_OK")
