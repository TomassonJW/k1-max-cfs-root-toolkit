"""Serveur local sans effet pour la vérification visuelle de l'interface."""

from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
STATE: dict[str, Any] = {
    "owner": "k1_control_stock_cycle",
    "version": "activation-v1-preview",
    "enabled": True,
    "phase": "idle",
    "pending_ticket": None,
    "last_error": None,
    "active_route": None,
    "filament_loaded": False,
    "tool_changes": 0,
    "equivalent_refills": 0,
    "camera_checkpoint": None,
    "last_camera_evidence_id": None,
    "last_failure": None,
    "selected": None,
    "effect_dispatch_count": 0,
    "automatic_retry_count": 0,
    "camera_pass_count": 0,
    "camera_fail_count": 0,
    "state_write_count": 0,
    "stock_BOX_effect_count": 0,
    "post_filament_probe_count": 0,
    "mesh_recalculation_count": 0,
    "run_state_present": False,
    "runout_owner": "k1_control_cfs_runout_owner",
}
FILES = [{
    "filename": "K1-CONTROL-PREVIEW-2LAYER.gcode",
    "modified": 0,
    "size": 4096,
    "filament_type": "PLA",
    "first_layer_extr_temp": 190,
    "first_layer_bed_temp": 55,
}]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(HERE), **kwargs)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def _json(self, value: Any, status: int = 200) -> None:
        payload = json.dumps({"result": value}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/machine/k1_control/stock-cycle/status":
            self._json(STATE)
        elif self.path == "/machine/k1_control/stock-cycle/files":
            self._json({"files": FILES, "selected": STATE["selected"]})
        else:
            super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        body = self._body()
        if self.path.endswith("/inventory"):
            inventory = json.loads(body["inventory_json"])
            STATE["selected"] = {"inventory": inventory, "job": None}
        elif self.path.endswith("/select"):
            assert STATE["selected"] is not None
            STATE["selected"]["job"] = {
                "filename": body["filename"],
                "initial_route": body["initial_route"],
                "material_type": "PLA",
                "first_nozzle_c": 190,
                "bed_c": 55,
            }
        elif self.path.endswith("/begin"):
            STATE["phase"] = "await_manual_clean"
            STATE["run_state_present"] = True
        elif self.path.endswith("/clean-confirm"):
            STATE["phase"] = "await_release_camera"
            STATE["active_route"] = STATE["selected"]["job"]["initial_route"]
            STATE["filament_loaded"] = True
            STATE["camera_checkpoint"] = "PURGE_BIN_RELEASE"
        elif self.path.endswith("/abort"):
            STATE["phase"] = "closed_safe"
            STATE["camera_checkpoint"] = None
            STATE["filament_loaded"] = False
            STATE["active_route"] = None
        self._json(STATE)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8766), Handler)
    print("PREVIEW_STOCK_DERIVED_CYCLE_UI_V1 http://127.0.0.1:8766/", flush=True)
    server.serve_forever()
