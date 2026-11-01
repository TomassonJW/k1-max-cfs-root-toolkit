"""Le labo des bobines (document 102, lot J) : le vrai composant sur un faux
Moonraker, au poste seulement.

Les 200 bobines synthétiques tombent dans les bons états et les emplacements
montrent ce que la fausse K1 contient ; une impression jouée se décompte sur
la bobine engagée ; le serveur ne répond qu'à ses propres pages ; le relais
vers le vrai Mainsail ne laisse monter que des lectures, et tout le reste est
refusé ici sans que la passerelle soit jointe.
"""

import base64
import collections
import hashlib
import http.client
import importlib.util
import json
import os
import re
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "packages" / "k1-control-v1" / "spool-manager-v1" / "lab" / "lab_server.py"
PATCH = ROOT / "packages" / "k1-control-v1" / "spool-choice-gate-v1" / "mainsail_overlay_patch.py"
MAINSAIL_PAGE = ("<!doctype html>\n<html>\n<head><title>Mainsail</title></head>\n"
                 "<body><div id=\"app\"></div></body>\n</html>\n")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lab_server = load("spools_lab_server", LAB)
PREFIX = lab_server.adapter.PREFIX


def serve(server):
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                              daemon=True)
    thread.start()
    return thread


def stop(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(5)


@pytest.fixture(scope="module")
def lab():
    found = lab_server.Lab(200)
    yield found
    found.close()


@pytest.fixture(scope="module")
def site(lab):
    server = lab_server.LabServer(lab, port=0)
    thread = serve(server)
    yield server
    stop(server, thread)


class Upstream(ThreadingHTTPServer):
    """The gateway as the relay sees it: every request that reaches it is kept."""
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), UpstreamHandler)
        self.seen, self.methods = [], []


class UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        self.server.seen.append(("GET", self.path))
        if self.headers.get("Upgrade", "").lower() == "websocket":
            return self.websocket()
        if self.path == "/":
            body, kind = MAINSAIL_PAGE.encode("utf-8"), "text/html; charset=utf-8"
        else:
            body, kind = json.dumps({"result": {"path": self.path}}).encode("utf-8"), "application/json"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.server.seen.append(("POST", self.path))
        self.send_response(500)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def websocket(self):
        key = self.headers["Sec-WebSocket-Key"] + lab_server.WEBSOCKET_GUID
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept",
                         base64.b64encode(hashlib.sha1(key.encode("ascii")).digest()).decode("ascii"))
        self.end_headers()
        self.close_connection = True
        while True:
            frame = lab_server.read_frame(self.rfile.read)
            if frame is None or frame[1] == 0x8:
                return
            message = json.loads(frame[2].decode("utf-8"))
            self.server.methods.append(message["method"])
            self.wfile.write(lab_server.text_frame(json.dumps(
                {"jsonrpc": "2.0", "id": message["id"], "result": {"method": message["method"]}})))


@pytest.fixture(scope="module")
def relay(lab):
    upstream = Upstream()
    upstream_thread = serve(upstream)
    server = lab_server.LabServer(lab, port=0, gateway=("127.0.0.1", upstream.server_address[1]))
    thread = serve(server)
    yield server, upstream
    stop(server, thread)
    stop(upstream, upstream_thread)


def ask(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=30)
    sent = {"Host": "127.0.0.1:%d" % server.port}
    sent.update(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        sent["Content-Type"] = "application/json"
    try:
        connection.request(method, path, body=data, headers=sent)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def status_of(lab):
    return lab.call(PREFIX + "status", {})


def spool_of(status, ident):
    return next(spool for spool in status["spools"] if spool["id"] == ident)


# ---------------------------------------------------------------- the sample
def test_the_sample_spreads_200_spools_over_every_state(lab):
    status = status_of(lab)
    assert len(status["spools"]) == 200
    assert collections.Counter(spool["state"] for spool in status["spools"]) == {
        "stock": 149, "terminee": 30, "jetee": 12, "cfs": 6, "a_ranger": 3}
    assert len(status["empty_spools"]) == 14
    assert status["read_only"] == "" and status["materials"]["error"] == ""


def test_the_slots_show_what_the_fake_box_holds(lab):
    status = status_of(lab)
    assert {view["slot"]: (view["status"], view["spool"]) for view in status["slots"]} == {
        "T1A": ("ok", "B001"), "T1B": ("ok", "B002"), "T1C": ("a_verifier", "B003"),
        "T1D": ("inconnue", ""), "T2A": ("ok", "B004"), "T2B": ("vide", ""),
        "T2C": ("ok", "B005"), "T2D": ("ok", "B006")}
    assert status["attention"] == ["T1C à vérifier", "T1D : bobine inconnue",
                                   "T2C : B-005 basse (40 g)"]


def test_the_box_serial_numbers_are_never_kept(lab):
    kept = json.dumps(status_of(lab), ensure_ascii=False)
    for path in lab.state.iterdir():
        kept += path.read_text(encoding="utf-8", errors="replace")
    assert "LAB-SN" not in kept and "LAB-UUID" not in kept


def test_a_print_played_in_the_lab_counts_on_the_engaged_spool(lab):
    before = len(status_of(lab)["prints"])
    for action, mm in (("start", 0), ("extrude", 600), ("extrude", 400), ("end", 0)):
        lab.simulate(action, mm)
    deadline = time.monotonic() + 30
    while True:  # the job closes 5 s after its end, at the next tick
        status = status_of(lab)
        if len(status["prints"]) > before:
            break
        assert time.monotonic() < deadline, "impression jamais close"
        time.sleep(0.25)
    lab.simulate("rest")
    job = status["prints"][-1]
    assert (job["file"], job["outcome"]) == (lab_server.GCODE, "complete")
    assert job["per_spool"] == [{"spool": "B001", "slot": "T1A", "mm": 1000.0, "g": 3.03, "m": 1.0}]
    assert job["planned"][0] == {"mm": 1234.5, "g": 3.7}
    assert spool_of(status, "B001")["counted_g"] == 3.03
    # Counting writes nothing to the CFS.
    assert lab.summary()["gcodes"] == []


# ---------------------------------------------------------------- the server
def test_the_pages_come_with_the_gateway_headers(site):
    code, _, body = ask(site, "GET", "/")
    assert code == 200 and lab_server.TAG.encode("utf-8") in body
    code, headers, _ = ask(site, "GET", "/bobines/")
    assert code == 200 and headers["Content-Type"] == "text/html; charset=utf-8"
    for name, value in lab_server.HEADERS:
        assert headers[name] == value
    code, headers, _ = ask(site, "GET", "/bobines")
    assert (code, headers["Location"]) == (301, "/bobines/")
    for name in ("overlay.js", "spools.js", "styles.css", "tares.json"):
        assert ask(site, "GET", "/bobines/" + name)[0] == 200


@pytest.mark.parametrize("path", [
    "/bobines/../lab/lab_server.py", "/bobines/%2e%2e/lab_server.py", "/bobines/..%5Clab_server.py",
    "/bobines/.hidden", "/bobines/sub/index.html", "/bobines/absent.js"])
def test_nothing_outside_the_page_folder_is_served(site, path):
    assert ask(site, "GET", path)[0] == 404


def test_the_api_answers_and_refuses_a_stale_revision(site):
    code, _, body = ask(site, "GET", PREFIX + "status")
    assert code == 200
    status = json.loads(body)["result"]
    spool = spool_of(status, "B150")
    edit = {"action": "edit_spool", "revision": status["revision"],
            "params": {"id": "B150", "notes": "Vue au labo", "initial_net_g": spool["initial_net_g"]}}
    code, _, body = ask(site, "POST", PREFIX + "action", edit)
    assert code == 200
    found = json.loads(body)["result"]
    assert found["status"]["revision"] == status["revision"] + 1
    assert spool_of(found["status"], "B150")["notes"] == "Vue au labo"
    code, _, body = ask(site, "POST", PREFIX + "action", edit)
    assert code == 409 and "a changé" in json.loads(body)["error"]["message"]
    assert ask(site, "GET", PREFIX + "action")[0] == 405
    assert ask(site, "PUT", PREFIX + "status", {})[0] == 405
    assert ask(site, "POST", "/printer/gcode/script?script=G28")[0] == 403
    assert ask(site, "POST", "/lab/simulate?action=reboot")[0] == 400


def test_only_the_lab_own_pages_may_call(site):
    assert ask(site, "GET", "/", headers={"Host": "localhost:%d" % site.port})[0] == 200
    assert ask(site, "GET", "/", headers={"Host": "rebound.test:%d" % site.port})[0] == 421
    code, _, _ = ask(site, "POST", PREFIX + "action", {"action": "finish", "params": {"id": "B150"}},
                     {"Origin": "http://rebound.test"})
    assert code == 403
    assert spool_of(status_of(site.lab), "B150")["state"] == "stock"


# ---------------------------------------------------------------- the relay
@pytest.mark.parametrize("message, refusal", [
    (b"pas du json", (None, "message illisible")),
    (b"[1, 2]", (None, "message illisible")),
    ({"id": 3, "method": "printer.gcode.script", "params": {"script": "G28"}},
     (3, "refusé par le labo, lecture seule : printer.gcode.script")),
    ({"id": 4, "method": "printer.print.start", "params": {"filename": "x.gcode"}},
     (4, "refusé par le labo, lecture seule : printer.print.start")),
    ({"id": 5, "method": "machine.update.status", "params": {"refresh": True}},
     (5, "refusé par le labo, lecture seule : rafraîchissement des mises à jour")),
    ({"id": 6}, (6, "refusé par le labo, lecture seule : None")),
    ({"id": 7, "method": "machine.update.status", "params": {"refresh": False}}, None),
    ({"id": 8, "method": "printer.objects.subscribe", "params": {"objects": {"box": None}}}, None),
])
def test_only_read_methods_go_up_the_websocket(message, refusal):
    data = message if isinstance(message, bytes) else json.dumps(message).encode("utf-8")
    assert lab_server.screen(data) == refusal


@pytest.mark.parametrize("value, gateway", [
    ("k1.test:4409", ("k1.test", 4409)), (" k1.test:4409 ", ("k1.test", 4409)),
    ("k1.test", None), (":4409", None), ("k1.test:0", None), ("k1.test:65536", None),
    ("k1.test:http", None), ("", None)])
def test_the_gateway_is_read_as_host_and_port(value, gateway):
    assert lab_server.parse_gateway(value) == gateway


def test_the_relay_never_starts_without_its_gateway(monkeypatch):
    monkeypatch.delenv("K1_GATEWAY", raising=False)
    with pytest.raises(SystemExit):
        lab_server.main(["--mainsail"])


def test_the_relay_marks_mainsail_once(relay):
    server, upstream = relay
    code, _, body = ask(server, "GET", "/")
    text = body.decode("utf-8")
    assert code == 200 and ("GET", "/") in upstream.seen
    assert text.count(lab_server.TAG) == 1
    assert lab_server.MARK + lab_server.TAG + "</body>" in text
    code, _, body = ask(server, "GET", "/server/info")
    assert code == 200 and json.loads(body) == {"result": {"path": "/server/info"}}


@pytest.mark.parametrize("method, path", [
    ("GET", "/printer/gcode/script?script=G28"), ("GET", "/machine/reboot"),
    ("GET", "/access/oneshot_token"), ("GET", "/server/files/delete_file"),
    ("POST", "/printer/print/start?filename=x.gcode"), ("POST", "/printer/gcode/script"),
    ("POST", "/server/files/upload"), ("POST", "/machine/services/restart?service=klipper")])
def test_the_relay_refuses_writes_without_reaching_the_gateway(relay, method, path):
    server, upstream = relay
    seen = len(upstream.seen)
    assert ask(server, method, path, {} if method == "POST" else None)[0] == 403
    assert len(upstream.seen) == seen


def test_the_relay_keeps_the_spools_of_the_lab(relay):
    server, upstream = relay
    seen = len(upstream.seen)
    code, _, body = ask(server, "GET", PREFIX + "status")
    assert code == 200 and len(json.loads(body)["result"]["spools"]) == 200
    assert len(upstream.seen) == seen


def masked(message):
    data, mask = json.dumps(message).encode("utf-8"), os.urandom(4)
    return struct.pack("!BB", 0x81, 0x80 | len(data)) + mask + lab_server.unmask(data, mask)


def handshake(server, origin):
    sock = socket.create_connection(("127.0.0.1", server.port), timeout=10)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    sock.sendall(("GET /websocket HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nUpgrade: websocket\r\n"
                  "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n"
                  "Origin: %s\r\n\r\n" % (server.port, key, origin)).encode("ascii"))
    stream = lab_server.Stream(sock)
    return sock, stream, stream.until(b"\r\n\r\n", 16384).decode("latin-1")


def test_the_websocket_relay_answers_a_write_itself(relay):
    server, upstream = relay
    sock, stream, head = handshake(server, "http://127.0.0.1:%d" % server.port)
    try:
        assert head.startswith("HTTP/1.1 101")
        sock.sendall(masked({"jsonrpc": "2.0", "id": 7, "method": "printer.gcode.script",
                             "params": {"script": "G28"}}))
        sock.sendall(masked({"jsonrpc": "2.0", "id": 8, "method": "printer.info"}))
        replies = {}
        for _ in range(2):
            reply = json.loads(lab_server.read_frame(stream.read)[2].decode("utf-8"))
            replies[reply["id"]] = reply
        assert replies[7]["error"] == {
            "code": 403, "message": "refusé par le labo, lecture seule : printer.gcode.script"}
        assert replies[8]["result"] == {"method": "printer.info"}
        assert upstream.methods == ["printer.info"]
        sock.sendall(struct.pack("!BB", 0x88, 0x80) + os.urandom(4))
    finally:
        sock.close()


def test_the_websocket_relay_refuses_another_origin(relay):
    server, upstream = relay
    seen = len(upstream.seen)
    sock, stream, head = handshake(server, "http://rebound.test")
    try:
        assert head.startswith("HTTP/1.1 403")
        # Read to the end: a socket closed on unread bytes resets the server's.
        length = int(re.search(r"Content-Length: (\d+)", head).group(1))
        assert json.loads(stream.read(length))["error"]["message"] == "origine refusée par le labo"
    finally:
        sock.close()
    assert len(upstream.seen) == seen


# ---------------------------------------------------------------- the rest
def test_the_lab_marks_mainsail_as_the_installer_does():
    patch = load("mainsail_overlay_patch_for_lab", PATCH)
    assert (lab_server.TAG, lab_server.MARK) == (patch.TAG, patch.MARK)


def test_200_spools_stay_far_below_the_moonraker_budget():
    found = lab_server.measure(200)
    # Measured on 1 November: 425 KiB kept, 314 KiB for a status, 574 KiB
    # for an export, against 45 MiB for the whole of Moonraker.
    assert found["resident_kib"] < 2048
    assert found["status_peak_kib"] < 1024
    assert found["export_peak_kib"] < 2048
    assert found["library_bytes"] < 256 * 1024
