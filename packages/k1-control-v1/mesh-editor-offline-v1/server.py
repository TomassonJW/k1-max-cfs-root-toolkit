#!/usr/bin/env python3
"""Loopback-only static server and fake API for MESH-EDITOR-OFFLINE-V1."""

from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import unquote, urlsplit

from fake_api import FakeMeshEditorApi


BASE_DIR = Path(__file__).resolve().parent
WEB_ROOT = (BASE_DIR / "www").resolve()
MAX_BODY_BYTES = 1024 * 1024
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


def _host_without_port(value: str) -> str:
    value = value.strip().lower()
    if value.startswith("["):
        closing = value.find("]")
        return value[: closing + 1] if closing >= 0 else value
    return value.split(":", 1)[0]


class OfflineHandler(BaseHTTPRequestHandler):
    server_version = "K1MeshEditorOffline/1"

    def _request_is_local(self) -> bool:
        client_host = self.client_address[0]
        host = _host_without_port(self.headers.get("Host", ""))
        return client_host in ("127.0.0.1", "::1") and host in ALLOWED_HOSTS

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, value: Any) -> None:
        body = (
            json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _read_json(self) -> Dict[str, Any]:
        length_text = self.headers.get("Content-Length", "0")
        try:
            length = int(length_text)
        except ValueError:
            raise ValueError("taille de requête invalide")
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("requête trop volumineuse")
        if length == 0:
            return {}
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("le corps JSON doit être un objet")
        return value

    def _serve_api(self, method: str, path: str) -> None:
        try:
            payload = self._read_json() if method == "POST" else {}
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self._send_json(400, {"error": "bad_request", "message": str(error)})
            return
        api = getattr(self.server, "mesh_editor_api")
        status, body, content_type = api.handle(method, path, payload)
        if isinstance(body, str):
            self._send_bytes(status, body.encode("utf-8"), content_type)
        else:
            self._send_json(status, body)

    def _serve_static(self, path: str) -> None:
        relative = "index.html" if path == "/" else unquote(path.lstrip("/"))
        candidate = (WEB_ROOT / relative).resolve()
        try:
            candidate.relative_to(WEB_ROOT)
        except ValueError:
            self._send_json(404, {"error": "not_found"})
            return
        if not candidate.is_file():
            self._send_json(404, {"error": "not_found"})
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in (
            "application/javascript",
            "application/json",
        ):
            content_type += "; charset=utf-8"
        self._send_bytes(200, candidate.read_bytes(), content_type)

    def do_GET(self) -> None:
        if not self._request_is_local():
            self._send_json(403, {"error": "loopback_only"})
            return
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            self._serve_api("GET", path)
        else:
            self._serve_static(path)

    def do_POST(self) -> None:
        if not self._request_is_local():
            self._send_json(403, {"error": "loopback_only"})
            return
        path = urlsplit(self.path).path
        if not path.startswith("/api/"):
            self._send_json(404, {"error": "not_found"})
            return
        self._serve_api("POST", path)

    def log_message(self, _format: str, *_arguments: Any) -> None:
        return


def create_server(port: int = 8765) -> ThreadingHTTPServer:
    if not 0 <= port <= 65535:
        raise ValueError("le port doit être compris entre 0 et 65535")
    server = ThreadingHTTPServer(("127.0.0.1", port), OfflineHandler)
    server.mesh_editor_api = FakeMeshEditorApi()
    return server


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lance uniquement la simulation locale MESH-EDITOR-OFFLINE-V1."
    )
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = create_server(args.port)
    print("MESH_EDITOR_OFFLINE_V1_READY http://127.0.0.1:{0}/".format(args.port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
