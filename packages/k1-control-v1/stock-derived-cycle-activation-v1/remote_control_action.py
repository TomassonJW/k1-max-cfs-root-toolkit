#!/usr/bin/env python3
"""Appelle une entree bornee du cycle local Moonraker depuis stdin SSH."""

import base64
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:7125/machine/k1_control/stock-cycle"
ALLOWED = {
    "status": ("GET", "/status"),
    "files": ("GET", "/files"),
    "inventory": ("POST", "/inventory"),
    "select": ("POST", "/select"),
    "begin": ("POST", "/begin"),
    "clean-confirm": ("POST", "/clean-confirm"),
    "camera-verdict": ("POST", "/camera-verdict"),
    "tool-change": ("POST", "/tool-change"),
    "abort": ("POST", "/abort"),
}


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ALLOWED:
        raise RuntimeError("bounded_action_invalid")
    action = sys.argv[1]
    payload = json.loads(base64.b64decode(sys.argv[2]).decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("payload_not_object")
    method, path = ALLOWED[action]
    data = None
    headers = {}
    if method == "POST":
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif payload:
        raise RuntimeError("get_payload_forbidden")
    request = Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        response = urlopen(request, timeout=300.0)
    except HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        print(body)
        return 1
    try:
        document = json.loads(response.read().decode("utf-8"))
    finally:
        response.close()
    print(json.dumps(document, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
