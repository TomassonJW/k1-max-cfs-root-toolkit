"""Serve the live mesh editor and talk to Klipper for it.

The page is served from this same process on purpose. Moonraker sits on another
port, so a page served anywhere else would be cross origin and would need CORS
opened on the printer's API - a permanent change to the machine to make one
local tool work. Serving both the page and its API here keeps that change
unnecessary and keeps the editor entirely self contained.

Writes never go through this server. It hands the edited matrix to Klipper as a
JSON file and lets KCTRL_MESH_APPLY validate, back up and persist it, so the
in-memory profile and printer.cfg can never disagree.

Standard library only: the printer runs Python 3.8 on mipsel and has no wheels.
"""

import json
import os
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KLIPPY_SOCKET = "/tmp/klippy_uds"
HANDOFF = "/tmp/kctrl-mesh-editor-apply.json"
WWW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "www")
DEFAULT_PORT = 7130
# The same window KCTRL_Z_SAVE enforces on the printer. Refusing here too
# means a typed 40 instead of 0.40 never leaves the page.
Z_LIMIT = 2.0
# Klipper frames every message on its unix socket with this byte.
SEPARATOR = bytes([3])

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
}


def console_lines(message):
    """Pull the console text out of one Klipper notification.

    The payload arrives as a dict keyed by the template - {"response": "..."} -
    not as the list of strings the shape of the message suggests. Iterating it
    blindly yields the key name, so a save once reported the word "response"
    where the backup file name belonged. Both shapes are accepted here because
    the framing is the printer's to change, not ours.
    """
    params = message.get("params")
    if isinstance(params, dict):
        candidates = [params.get("response", "")]
    elif isinstance(params, (list, tuple)):
        candidates = list(params)
    else:
        candidates = []
    out = []
    for candidate in candidates:
        text = str(candidate).strip()
        if text and not text.startswith(("B:", "T0:")):
            out.append(text)
    return out


class KlippyError(Exception):
    pass


class Refused(ValueError):
    """A request turned down here, before anything reaches the printer.

    It is a ValueError so a caller that only knows the standard exception keeps
    working, but do_POST answers it with the sentence alone: "corps illisible"
    in front of "Z 40 hors de la plage" describes the wrong failure.
    """


class Klippy:
    """One short lived request to the Klipper unix socket.

    A fresh connection per request is deliberate. The editor is idle most of the
    time while its operator reads a printed square, and a long lived socket that
    silently died during a firmware restart is a worse failure than reconnecting.
    """

    def __init__(self, path=KLIPPY_SOCKET):
        self.path = path

    def _converse(self, method, params=None, timeout=30.0, collect=False):
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.path)
        except OSError as exc:
            raise KlippyError("Klipper injoignable (%s)" % exc)
        responses = []
        buffer = b""
        try:
            if collect:
                # The response_template is not optional: without it Klipper
                # registers the subscription and then never sends a single
                # line, silently. That is why a save used to report a bare
                # "saved" instead of what the macro actually did.
                sock.sendall(json.dumps({
                    "id": 1,
                    "method": "gcode/subscribe_output",
                    "params": {
                        "response_template": {"method": "notify_gcode_response"},
                    },
                }).encode() + SEPARATOR)
                # Wait for the subscription to be acknowledged before the
                # command goes out. Sending both back to back loses the
                # first console lines, which are exactly the ones worth
                # showing: how many points moved, and where the backup went.
                ready = time.time() + 5.0
                while time.time() < ready:
                    sock.settimeout(max(0.05, ready - time.time()))
                    try:
                        chunk = sock.recv(65536)
                    except socket.timeout:
                        break
                    if not chunk:
                        break
                    buffer += chunk
                    parts = buffer.split(SEPARATOR)
                    buffer = parts.pop()
                    acknowledged = False
                    for raw in parts:
                        try:
                            message = json.loads(raw)
                        except ValueError:
                            continue
                        if message.get("id") == 1:
                            acknowledged = True
                    if acknowledged:
                        break
            request = {"id": 2, "method": method}
            if params is not None:
                request["params"] = params
            sock.sendall(json.dumps(request).encode() + SEPARATOR)
            deadline = time.time() + timeout
            while time.time() < deadline:
                sock.settimeout(max(0.05, deadline - time.time()))
                try:
                    chunk = sock.recv(65536)
                except socket.timeout:
                    break
                if not chunk:
                    break
                buffer += chunk
                while SEPARATOR in buffer:
                    raw, buffer = buffer.split(SEPARATOR, 1)
                    try:
                        message = json.loads(raw)
                    except ValueError:
                        continue
                    if message.get("method") == "notify_gcode_response":
                        responses.extend(console_lines(message))
                    elif message.get("id") == 2:
                        if "error" in message:
                            raise KlippyError(self._readable(message["error"]))
                        result = message.get("result", {})
                        if not collect:
                            return result, responses
                        # The command result can land before the info lines the
                        # macro emitted. Draining a moment longer is what makes
                        # the backup file name reach the operator instead of a
                        # bare "saved".
                        grace = time.time() + 0.6
                        while time.time() < grace:
                            sock.settimeout(max(0.05, grace - time.time()))
                            try:
                                more = sock.recv(65536)
                            except socket.timeout:
                                break
                            if not more:
                                break
                            buffer += more
                            while SEPARATOR in buffer:
                                raw, buffer = buffer.split(SEPARATOR, 1)
                                try:
                                    extra = json.loads(raw)
                                except ValueError:
                                    continue
                                if extra.get("method") == "notify_gcode_response":
                                    responses.extend(console_lines(extra))
                        return result, responses
            raise KlippyError("Klipper n'a pas répondu en %.0f s" % timeout)
        finally:
            sock.close()

    @staticmethod
    def _readable(error):
        # Klipper wraps its errors in a JSON envelope with a key code. The
        # operator needs the sentence, not the envelope.
        text = str(error.get("message", error))
        try:
            # strict=False is not cosmetic: a macro refusal carries a real
            # newline inside the JSON string, which the strict parser rejects.
            # Without it the operator got the whole envelope, code and values
            # included, instead of the one sentence that says what went wrong.
            inner = json.loads(text, strict=False)
            return str(inner.get("msg", text)).strip()
        except (ValueError, AttributeError):
            return text.strip()

    def query(self, objects):
        result, _ = self._converse(
            "objects/query", {"objects": objects}, timeout=15.0)
        return result.get("status", {})

    def script(self, command, timeout=120.0):
        _, responses = self._converse(
            "gcode/script", {"script": command}, timeout=timeout, collect=True)
        return responses


class Handler(BaseHTTPRequestHandler):
    server_version = "KctrlMeshEditor/1"
    klippy = Klippy()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # ------------------------------------------------------------------ output
    def _send(self, code, body, content_type="application/json"):
        payload = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, code, payload):
        self._send(code, json.dumps(payload))

    def _fail(self, code, message):
        self._json(code, {"error": message})

    # ------------------------------------------------------------------- routes
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        try:
            if path in ("/", "/index.html"):
                return self._static("index.html")
            if path == "/api/state":
                return self._json(200, self._state())
            if path.startswith("/api/profile/"):
                return self._json(200, self._profile(path.rsplit("/", 1)[-1]))
            if path.startswith("/") and "/" not in path[1:]:
                return self._static(path[1:])
            return self._fail(404, "inconnu: %s" % path)
        except KlippyError as exc:
            return self._fail(503, str(exc))
        except FileNotFoundError:
            return self._fail(404, "fichier absent")
        except Exception as exc:  # pragma: no cover - last resort
            return self._fail(500, "%s: %s" % (type(exc).__name__, exc))

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/save":
                return self._json(200, self._save(body))
            if path == "/api/z":
                return self._json(200, self._zsave(body))
            return self._fail(404, "inconnu: %s" % path)
        except KlippyError as exc:
            return self._fail(503, str(exc))
        except Refused as exc:
            return self._fail(400, str(exc))
        except ValueError as exc:
            return self._fail(400, "corps illisible: %s" % exc)
        except Exception as exc:  # pragma: no cover - last resort
            return self._fail(500, "%s: %s" % (type(exc).__name__, exc))

    # ------------------------------------------------------------------ helpers
    def _static(self, name):
        if "/" in name or "\\" in name or name.startswith("."):
            return self._fail(400, "chemin refusé")
        full = os.path.join(WWW, name)
        if not os.path.isfile(full):
            return self._fail(404, "fichier absent: %s" % name)
        handle = open(full, "rb")
        try:
            data = handle.read()
        finally:
            handle.close()
        extension = os.path.splitext(name)[1]
        return self._send(
            200, data, CONTENT_TYPES.get(extension, "application/octet-stream"))

    def _state(self):
        status = self.klippy.query({
            "bed_mesh": None,
            "print_stats": None,
            "webhooks": None,
            "save_variables": None,
            "gcode_move": None,
        })
        mesh = status.get("bed_mesh", {})
        profiles = sorted(
            name for name in mesh.get("profiles", {}) if name != "default")
        variables = status.get("save_variables", {}).get("variables", {})
        return {
            "profiles": profiles,
            "active": mesh.get("profile_name"),
            "printer_state": status.get("print_stats", {}).get("state"),
            "klipper": status.get("webhooks", {}).get("state"),
            "z_offsets": {
                key[2:]: value for key, value in variables.items()
                if key.startswith("z_")
            },
            # The offset in force right now, which is what the operator just
            # dialled in from Fluidd while watching the first layer. Without it
            # that number dies with the print and has to be found again.
            # Rounded: a zeroed offset comes back as -1.7e-18 and the page
            # would print it as -0.000, which reads like a real correction.
            "live_z": round(float(status.get("gcode_move", {}).get(
                "homing_origin", [0, 0, 0, 0])[2]), 4),
        }

    def _profile(self, name):
        status = self.klippy.query({"bed_mesh": None})
        mesh = status.get("bed_mesh", {})
        profile = mesh.get("profiles", {}).get(name)
        if profile is None:
            raise FileNotFoundError(name)
        params = profile["mesh_params"]
        return {
            "name": name,
            "active": mesh.get("profile_name") == name,
            "points": profile["points"],
            "min_x": float(params["min_x"]), "max_x": float(params["max_x"]),
            "min_y": float(params["min_y"]), "max_y": float(params["max_y"]),
            "x_count": int(params["x_count"]),
            "y_count": int(params["y_count"]),
        }

    def _save(self, body):
        name = body.get("profile")
        points = body.get("points")
        if not name or not isinstance(points, list):
            raise Refused("il faut un profil et une matrice")
        payload = {"profile": name, "points": points}
        temporary = HANDOFF + ".part"
        handle = open(temporary, "w")
        try:
            handle.write(json.dumps(payload))
        finally:
            handle.close()
        os.rename(temporary, HANDOFF)
        lines = self.klippy.script("KCTRL_MESH_APPLY FILE=%s" % HANDOFF)
        return {"messages": lines, "profile": self._profile(name)}

    def _zsave(self, body):
        """Write the accepted Z of one mesh profile, through the stock macro.

        Nothing is computed here. KCTRL_Z_SAVE owns the rule - the profile must
        exist, the value must stay inside two millimetres - and it is the only
        writer, so the number the editor shows and the number START_PRINT reads
        can never be two different things.
        """
        name = body.get("profile")
        if not isinstance(name, str) or not name:
            raise Refused("il faut un profil")
        # The name goes into a G-code command. Only what Klipper itself already
        # holds as a profile may travel, so nothing can be smuggled in a name.
        profiles = self.klippy.query({"bed_mesh": None}).get(
            "bed_mesh", {}).get("profiles", {})
        if name not in profiles:
            raise Refused("profil inconnu: %s" % name)
        try:
            z = float(body.get("z"))
        except (TypeError, ValueError):
            raise Refused("il faut un Z en millimetres")
        if z != z or z in (float("inf"), float("-inf")):
            raise Refused("il faut un Z en millimetres")
        if abs(z) > Z_LIMIT:
            raise Refused(
                "Z %.4f hors de la plage -%.0f..%.0f mm" % (z, Z_LIMIT, Z_LIMIT))
        lines = self.klippy.script("KCTRL_Z_SAVE PROFILE=%s Z=%.4f" % (name, z))
        state = self._state()
        return {
            "messages": lines,
            "saved": z,
            "z_offsets": state["z_offsets"],
            "live_z": state["live_z"],
        }


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    sys.stderr.write("editeur de maillage sur le port %d\n" % port)
    sys.stderr.flush()
    server.serve_forever()


if __name__ == "__main__":
    main()
