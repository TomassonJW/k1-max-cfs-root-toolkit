"""Small loopback-only Moonraker simulator for the K1 Control prototype.

It serves the static interface and a deliberately tiny subset of Moonraker's
HTTP API.  It never opens a printer connection and binds to 127.0.0.1 only.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shlex
from typing import Any, Mapping
from urllib.parse import urlparse

from prototype.control_state import (
    CalibrationRecord,
    MachineContext,
    ProductionBlocked,
    ZCalibrationController,
)


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "prototype" / "k1-control"
DEFAULT_STATE = UI_ROOT / "mock-state.json"


class MoonrakerSimulation:
    """In-memory product state exposed with Moonraker-shaped replies."""

    def __init__(self, state_path: Path = DEFAULT_STATE) -> None:
        self.state = json.loads(state_path.read_text(encoding="utf-8"))
        self.state["connection"] = "Faux Moonraker local · API HTTP"
        self.context = MachineContext(
            plate_id=self.state["plate"]["id"],
            bed_temperature_band_c=self.state["plate"]["temperatureBandC"],
            nozzle_id="unicorn-a",
            nozzle_diameter_mm=0.4,
            probe_reference_revision=self.state["calibration"]["probeReference"],
            relevant_config_hashes={"homing": "simulation", "probe": "simulation"},
        )
        self.z = ZCalibrationController(
            accepted=CalibrationRecord(
                offset_mm=float(self.state["calibration"]["offsetMm"]),
                context_signature=self.context.signature(),
                plate_id=self.context.plate_id,
                bed_temperature_band_c=self.context.bed_temperature_band_c,
                nozzle_id=self.context.nozzle_id,
                nozzle_diameter_mm=self.context.nozzle_diameter_mm,
                probe_reference_revision=self.context.probe_reference_revision,
                accepted_at=self.state["calibration"]["acceptedAt"],
            )
        )
        self._sync_state()

    def snapshot(self) -> dict[str, Any]:
        self._sync_state()
        return deepcopy(self.state)

    def dispatch_script(self, script: str) -> None:
        tokens = shlex.split(script)
        if not tokens:
            raise ValueError("empty simulated G-code script")
        command = tokens[0].upper()
        params = {}
        for token in tokens[1:]:
            if "=" not in token:
                raise ValueError(f"invalid simulated parameter: {token}")
            key, value = token.split("=", 1)
            params[key.upper()] = value

        if command == "K1_Z_SESSION_START":
            seed = float(params["SEED"])
            self.z.start_session(self.context, seed_offset_mm=seed)
            self._event(f"Session Z ouverte à {self._format_offset(seed)} mm. Rien n'est enregistré.")
        elif command == "K1_Z_ADJUST":
            value = self.z.adjust(float(params["DELTA"]))
            self._event(f"Réglage provisoire : {self._format_offset(value)} mm.")
        elif command == "K1_Z_COMMIT":
            record = self.z.commit(accepted_at=datetime.now(timezone.utc).isoformat())
            self.state["calibration"]["provisionalSeedMm"] = record.offset_mm
            self._event(
                f"Calibration Z enregistrée explicitement à {self._format_offset(record.offset_mm)} mm."
            )
        elif command == "K1_Z_CANCEL":
            self.z.cancel()
            self._event("Session annulée : la calibration acceptée précédente n'a pas changé.")
        elif command == "K1_Z_RESTORE_PREVIOUS":
            record = self.z.restore_previous()
            self.state["calibration"]["provisionalSeedMm"] = record.offset_mm
            self._event(f"Calibration précédente restaurée à {self._format_offset(record.offset_mm)} mm.")
        elif command == "K1_SIM_REFERENCE_CALIBRATION":
            self.z.invalidate("nouvelle calibration de référence simulée")
            self._event(
                "Nouvelle référence simulée : l'ancienne valeur reste dans l'historique mais est bloquée."
            )
        elif command == "K1_SIM_RESTART":
            self.z.on_restart()
            self._event(self._preserved_message("Redémarrage simulé"))
        elif command == "K1_SIM_PRINT_END":
            self.z.on_print_end()
            self._event(self._preserved_message("Fin d'impression simulée"))
        elif command == "K1_SIM_EXPERT_NOTICE":
            self._event("Mainsail est représenté par le même faux Moonraker dans ce prototype local.")
        else:
            raise ValueError(f"command not exposed by the simulator: {command}")
        self._sync_state()

    def _sync_state(self) -> None:
        calibration = self.state["calibration"]
        calibration["session"] = None
        if self.z.session is not None:
            calibration["session"] = {
                "seedOffsetMm": self.z.session.seed_offset_mm,
                "currentOffsetMm": self.z.session.current_offset_mm,
            }
        if self.z.accepted is not None:
            calibration["offsetMm"] = self.z.accepted.offset_mm
            calibration["acceptedAt"] = self.z.accepted.accepted_at
        calibration["status"] = "invalid" if self.z.invalid_reason else "accepted"
        calibration["canRestore"] = bool(self.z.history)
        self.state["ready"] = self.z.accepted is not None and self.z.invalid_reason is None
        self.state["blockReason"] = (
            None
            if self.state["ready"]
            else "Une nouvelle calibration de référence a invalidé le Z accepté. Recalibration requise."
        )

    def _event(self, message: str) -> None:
        self.state["events"].insert(0, message)
        self.state["events"] = self.state["events"][:6]

    def _preserved_message(self, label: str) -> str:
        if self.z.accepted is None:
            return f"{label} : aucune calibration acceptée."
        return f"{label} : la calibration acceptée reste {self._format_offset(self.z.accepted.offset_mm)} mm."

    @staticmethod
    def _format_offset(value: float) -> str:
        return f"{value:+.3f}".replace(".", ",")


class SimulationHandler(SimpleHTTPRequestHandler):
    simulation: MoonrakerSimulation

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(UI_ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        if parsed.path == "/server/info":
            self._send_json(
                {
                    "result": {
                        "klippy_connected": True,
                        "klippy_state": "ready",
                        "moonraker_version": "simulation-k1-control-v1",
                        "components": ["server", "klippy_connection", "k1_control"],
                    }
                }
            )
            return
        if parsed.path == "/printer/objects/query":
            self._send_json(
                {
                    "result": {
                        "eventtime": 0.0,
                        "status": {"k1_control": self.simulation.snapshot()},
                    }
                }
            )
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        if parsed.path != "/printer/gcode/script":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            self.simulation.dispatch_script(str(payload["script"]))
        except (KeyError, TypeError, ValueError, ProductionBlocked) as exc:
            self._send_json({"error": {"code": 400, "message": str(exc)}}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json({"result": "ok"})

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send_json(self, payload: Mapping[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)


def create_server(port: int = 8765) -> ThreadingHTTPServer:
    simulation = MoonrakerSimulation()

    class BoundHandler(SimulationHandler):
        pass

    BoundHandler.simulation = simulation
    return ThreadingHTTPServer(("127.0.0.1", port), BoundHandler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = create_server(args.port)
    print(f"K1 Control simulation: http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
