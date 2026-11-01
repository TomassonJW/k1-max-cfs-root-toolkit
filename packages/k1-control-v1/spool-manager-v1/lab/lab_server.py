#!/usr/bin/env python3
"""The spool manager lab, on the workstation only.

Document 102, lot J. The real kctrl_spools component runs over a fake
Moonraker: a K1 at rest, two CFS units online and two absent, the synthetic
material database of this folder and a library of 200 spools drawn from the
empty-spool catalogue. The server listens on 127.0.0.1 only and serves the
pages of www/bobines, a copy of the Mainsail top bar and the component's
endpoints; nothing is sent to a printer.

    python lab_server.py [--port 8781] [--spools 200] [--state FOLDER]
    python lab_server.py --measure

With --mainsail it relays, read-only, the real Mainsail of the gateway whose
host:port is in the K1_GATEWAY variable, never in a tracked file: static
files, GET requests from a closed list and read-only websocket methods.
Everything else gets a refusal here and is never sent. The spools stay those
of the lab. Use another port than the lab, so that the Mainsail service
worker never touches the lab's origin, and only while the K1 is at rest.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import copy
import enum
import hashlib
import http.client
import importlib
import json
import os
import socket
import struct
import sys
import tempfile
import threading
import time
import tracemalloc
import types
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
WWW = PACKAGE.parent / "spool-choice-gate-v1" / "www" / "bobines"
SYNTHETIC = HERE / "material_database.synthetic.json"
PAGE = HERE / "index.html"
TAG = '<script type="module" src="/bobines/overlay.js"></script>'
MARK = "<!-- k1-control: bobines -->"
# The gateway's own headers: no CSP there either.
HEADERS = (("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
           ("X-Frame-Options", "SAMEORIGIN"), ("Referrer-Policy", "no-referrer"))
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json",
         ".txt": "text/plain; charset=utf-8"}
CALL_TIMEOUT_S = 90
MAX_BODY = 16 << 20
MAX_HTML = 4 << 20
MAX_FRAME = 8 << 20
GCODE = "lab-cube.gcode"
GCODE_TEXT = ("; K1 Control lab, synthetic file\nG28\nG1 X10 Y10 E1\n"
              "; filament used [mm] = 1234.5, 0.00\n; filament used [g] = 3.7, 0.00\n")

# Read-only websocket methods Mainsail needs to draw its pages. Any other
# method gets an error from here and never reaches the gateway.
READ_METHODS = frozenset((
    "server.connection.identify", "server.websocket.id", "server.info", "server.config",
    "server.temperature_store", "server.gcode_store", "server.files.roots", "server.files.list",
    "server.files.get_directory", "server.files.metadata", "server.database.list",
    "server.database.get_item", "server.history.list", "server.history.totals",
    "server.job_queue.status", "server.announcements.list", "server.webcams.list",
    "server.sensors.list", "server.spoolman.status", "printer.info", "printer.objects.list",
    "printer.objects.subscribe", "printer.objects.query", "printer.gcode.help",
    "machine.system_info", "machine.proc_stats", "machine.device_power.devices",
    "machine.update.status", "access.info", "access.get_user"))
READ_PATHS = frozenset((
    "/server/info", "/server/config", "/printer/info", "/printer/objects/list",
    "/printer/objects/query", "/server/files/list", "/server/files/roots",
    "/server/files/metadata", "/server/files/directory", "/server/database/list",
    "/server/database/item", "/machine/system_info", "/server/webcams/list",
    "/server/history/list", "/server/history/totals", "/access/info"))
READ_PREFIXES = ("/server/files/gcodes/", "/server/files/config/.theme/")
API = ("/access/", "/api/", "/machine/", "/printer/", "/server/")
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


# ---------------------------------------------------------------- the component
def load_component():
    """kctrl_spools imported as Moonraker imports it, beside a minimal `common`."""
    root = types.ModuleType("k1lab")
    root.__path__ = []
    common = types.ModuleType("k1lab.common")

    class RequestType(enum.Flag):
        GET = enum.auto()
        POST = enum.auto()
        DELETE = enum.auto()

    class WebRequest(object):
        def __init__(self, args):
            self.args = args

        def get_args(self):
            return self.args

    common.RequestType, common.WebRequest = RequestType, WebRequest
    components = types.ModuleType("k1lab.components")
    components.__path__ = [str(PACKAGE)]
    root.common, root.components = common, components
    for module in (root, common, components):
        sys.modules[module.__name__] = module
    return importlib.import_module("k1lab.components.kctrl_spools")


adapter = load_component()
spools, counting, storage = adapter.spools, adapter.counting, adapter.storage
WebRequest = sys.modules["k1lab.common"].WebRequest
RequestType = sys.modules["k1lab.common"].RequestType


# ---------------------------------------------------------------- the sample
PLACES = ("Étagère haute", "Étagère basse", "Bac sec 1", "Bac sec 2", "Carton garage")
CATALOGUE = (
    "Creality|1000|225|plastique", "Creality|1000|120|inconnue", "ELEGOO|1000|154|carton",
    "ELEGOO|1000|154|plastique", "Sunlu|1000|189|plastique", "Sunlu|1000|189|inconnue",
    "eSun|1000|170|carton", "eSun|1000|153|carton", "Polymaker|1000|140|inconnue",
    "Prusament|1000|193|plastique", "Overture|1000|174|carton", "GEEETECH|1000|180|plastique")
TYPED = (
    ("recyclee", {"manufacturer": "Recyclée", "name": "Bobine carton recyclée",
                  "spool_material": "carton", "tare_g": 212, "nominal_net_g": 1000,
                  "source": "pesee"}),
    ("noire", {"manufacturer": "Sans marque", "name": "Bobine plastique noire",
               "spool_material": "plastique", "tare_g": 245, "nominal_net_g": 1000,
               "source": "manuel"}),
)
# manufacturer, name, Creality id, colour, empty spool (catalogue key or TYPED name)
FICHES = (
    ("Creality", "Hyper PLA", "01001", "FFFFFF", "Creality|1000|225|plastique"),
    ("Creality", "Hyper PLA", "01001", "000000", "Creality|1000|225|plastique"),
    ("Creality", "Hyper PLA", "01001", "1E5AA8", "Creality|1000|225|plastique"),
    ("Creality", "Hyper PLA", "01001", "C0392B", "Creality|1000|225|plastique"),
    ("Creality", "CR-PLA", "01002", "F1C40F", "Creality|1000|120|inconnue"),
    ("Creality", "CR-PLA", "01002", "27AE60", "Creality|1000|120|inconnue"),
    ("Creality", "Hyper PETG", "01003", "2C3E50", "Creality|1000|225|plastique"),
    ("Creality", "Hyper PETG", "01003", "D5D8DC", "Creality|1000|225|plastique"),
    ("ELEGOO", "PLA Matte", "00001", "8E44AD", "ELEGOO|1000|154|carton"),
    ("eSun", "PLA+", "00001", "16A085", "eSun|1000|170|carton"),
    ("Polymaker", "PolyTerra PLA", "00001", "A3C1AD", "Polymaker|1000|140|inconnue"),
    ("GEEETECH", "PLA Luminous", "00001", "C8F7C5", "GEEETECH|1000|180|plastique"),
    ("ELEGOO", "PLA Silk", "00002", "B87333", "ELEGOO|1000|154|plastique"),
    ("eSun", "PLA Silk Magic", "00002", "D4AF37", "eSun|1000|153|carton"),
    ("Sunlu", "PETG", "00003", "E67E22", "Sunlu|1000|189|plastique"),
    ("Prusament", "PETG Jet Black", "00003", "1B1B1B", "Prusament|1000|193|plastique"),
    ("Sunlu", "ABS", "00004", "7F8C8D", "Sunlu|1000|189|inconnue"),
    ("Overture", "TPU 95A", "00005", "E74C3C", "Overture|1000|174|carton"),
    ("Acme", "PLA Pastel", "02001", "F5B7B1", "noire"),
    ("Nodensity", "Mystery PA", "03001", "34495E", "recyclee"),
)
# What the box shows in each slot: (fiche of the spool put there, material,
# colour, vender). T1C shows another blue than its fiche, T1D a spool the CFS
# cannot identify and nobody put there, T2B nothing; T2C holds 40 g.
SEEN = {
    "T1A": (0, "001001", "0ffffff", "unknown"),
    "T1B": (1, "001001", "0000000", "unknown"),
    "T1C": (2, "001001", "01f6fb5", "unknown"),
    "T1D": (None, "-1", "-1", "unknown"),
    "T2A": (14, "000003", "0e67e22", "unknown"),
    "T2C": (9, "000001", "016a085", "unknown"),
    "T2D": (12, "000002", "0b87333", "unknown"),
}
TO_STORE, FINISHED, DISCARDED = 3, 30, 12


def sample_box():
    """The box object as the K1 publishes it, its serial numbers included."""
    box = {"enable": 1, "state": "connect", "t_command": ""}
    for number in "1234":
        name = "T" + number
        if number in "34":
            box[name] = {"sn": "LAB-SN-" + name, "uuid": "LAB-UUID-" + name, "state": "None",
                         "filament": "None", "material_type": ["None"] * 4,
                         "color_value": ["None"] * 4, "vender": ["-1"] * 4,
                         "remain_len": ["-1"] * 4}
            continue
        unit = {"sn": "LAB-SN-" + name, "uuid": "LAB-UUID-" + name, "state": "connect",
                "filament": "A" if number == "1" else "None", "material_type": ["-1"] * 4,
                "color_value": ["-1"] * 4, "vender": ["none"] * 4, "remain_len": ["-1"] * 4}
        for index, letter in enumerate("ABCD"):
            seen = SEEN.get(name + letter)
            if seen is not None:
                unit["material_type"][index], unit["color_value"][index] = seen[1], seen[2]
                unit["vender"][index] = seen[3]
                unit["remain_len"][index] = "100" if seen[1] != "-1" else "-1"
        box[name] = unit
    return box


def sample(count, now):
    """(library, journal events, box): `count` spools over the CFS, the stock and the archives."""
    materials, error = spools.read_materials(str(SYNTHETIC))
    if error:
        raise RuntimeError(error)
    box = sample_box()
    observations = spools.observe_box(box)
    work = {"library": spools.empty_library(), "events": []}

    def act(name, params, when):
        library, events, result = spools.apply(work["library"], name, params,
                                               spools.Context(when, materials, observations))
        work["library"] = library
        work["events"].extend(events)
        return result.get("id", "")

    start = int(now) - 120 * 86400
    tares = {entry["key"]: entry
             for entry in json.loads((WWW / "tares.json").read_text(encoding="utf-8"))["entries"]}
    empties = {}
    for key in CATALOGUE:
        entry = tares[key]
        material = entry["spool_material"]
        # The name the window proposes when a catalogue entry fills the form.
        name = "Bobine %d g" % entry["net_g"] + ("" if material == "inconnue" else " " + material)
        empties[key] = act("create_empty_spool", {
            "manufacturer": entry["manufacturer"], "name": name, "spool_material": material,
            "tare_g": entry["tare_g"], "nominal_net_g": entry["net_g"], "source": "spoolmandb",
            "catalogue": key}, start)
    for key, params in TYPED:
        empties[key] = act("create_empty_spool", dict(params), start)
    fiches = []
    for manufacturer, name, creality_id, colour, empty in FICHES:
        params = {"manufacturer": manufacturer, "name": name, "creality_id": creality_id,
                  "colour": colour}
        if creality_id == "03001":
            params["density"] = 1.14  # the database gives none
        fiches.append((act("create_filament", params, start), empties[empty]))

    placed = [slot for slot in sorted(SEEN) if SEEN[slot][0] is not None][:count]
    for slot in placed:
        fiche, empty = fiches[SEEN[slot][0]]
        params = {"filament": fiche, "empty_spool": empty, "state": "cfs", "slot": slot}
        if slot == "T2C":
            params.update(basis_kind="estimation", value_g=40)
        act("create_spool", params, start + 3600)
    for index in range(count - len(placed)):
        fiche, empty = fiches[index % len(fiches)]
        when = start + 7200 + index * 39600
        params = {"filament": fiche, "empty_spool": empty}
        if index % 3 == 1:
            params.update(basis_kind="estimation", value_g=min(50 + (index * 137) % 900, 1000))
        elif index % 3 == 2:
            tare = work["library"]["empty_spools"][empty]["tare_g"]
            params.update(basis_kind="pesee", value_g=tare + (index * 89) % 950)
        if index % 17 == 0:
            params["notes"] = "Séchée 6 h à 50 °C"
        if index < TO_STORE:
            params["state"] = "a_ranger"
            act("create_spool", params, when)
            continue
        if index < TO_STORE + FINISHED + DISCARDED:
            ident = act("create_spool", params, when)
            act("finish" if index < TO_STORE + FINISHED else "discard", {"id": ident}, when + 600)
            continue
        params.update(state="stock", place=PLACES[index % len(PLACES)])
        act("create_spool", params, when)
    return work["library"], work["events"], box


def rest_status(box):
    return {
        "box": box,
        "toolhead": {"position": [0.0, 0.0, 0.0, 0.0]},
        counting.SENSOR: {"filament_detected": True, "enabled": True},
        "print_stats": {"state": "standby", "filename": ""},
        "kctrl_end": {"phase": "idle", "job_epoch": 0, "pending": False},
        "kctrl_tool_change": {"last": None, "last_reload": None},
        "webhooks": {"state": "ready"},
        "idle_timeout": {"state": "Idle"},
        "kctrl_print_gate": {"pending": 0},
    }


# ---------------------------------------------------------------- the fake Moonraker
class LabError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class FakeKlippy(object):
    """klippy_apis of a K1 at rest; the only G-code it takes is KCTRL_FILAMENT."""

    def __init__(self, status):
        self.status = status
        self.callbacks = []
        self.gcodes = []

    def select(self, objects):
        found = {}
        for name, fields in objects.items():
            values = self.status.get(name)
            if isinstance(values, dict):
                keys = [key for key in fields if key in values] if fields else list(values)
                found[name] = copy.deepcopy({key: values[key] for key in keys})
        return found

    async def subscribe_objects(self, objects, callback=None, default=None):
        if callback is not None:
            self.callbacks.append(callback)
        return self.select(objects)

    async def query_objects(self, objects):
        return self.select(objects)

    async def run_gcode(self, script):
        self.gcodes.append(script)
        words = script.split()
        if not words or words[0] != "KCTRL_FILAMENT":
            raise LabError("G-code refusé par le labo : %s" % (words[0] if words else "vide"))
        values = dict(word.split("=", 1) for word in words[1:] if "=" in word)
        slot = values.get("SLOT", "")
        unit = self.status["box"].get(slot[:2]) if len(slot) == 3 else None
        if not isinstance(unit, dict) or unit.get("state") != "connect" or slot[2] not in "ABCD":
            raise LabError("emplacement inconnu : %s" % slot)
        index = "ABCD".index(slot[2])
        if "MATERIAL" in values:
            unit["material_type"][index] = values["MATERIAL"]
        if "COLOR" in values:
            unit["color_value"][index] = values["COLOR"]
        asyncio.get_running_loop().call_soon(self.push, {"box": {slot[:2]: copy.deepcopy(unit)}})
        return "ok"

    def push(self, diff):
        for name, fields in diff.items():
            self.status.setdefault(name, {}).update(copy.deepcopy(fields))
        for callback in list(self.callbacks):
            callback(copy.deepcopy(diff), time.monotonic())


class Connection(object):
    def is_ready(self):
        return True


class LabLoop(object):
    def __init__(self, loop):
        self.loop = loop

    async def run_in_thread(self, fn, *args):
        return await self.loop.run_in_executor(None, fn, *args)


class FakeServer(object):
    def __init__(self, klippy, loop):
        self.components = {"klippy_apis": klippy, "klippy_connection": Connection()}
        self.endpoints, self.handlers, self.notifications = {}, {}, []
        self.sent = 0
        self.loop = LabLoop(loop)

    def lookup_component(self, name, default=None):
        return self.components.get(name, default)

    def register_endpoint(self, path, kind, handler):
        self.endpoints[path] = (kind, handler)

    def register_event_handler(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    def register_notification(self, name):
        self.notifications.append(name)

    def send_event(self, name, *args):
        self.sent += 1

    def get_event_loop(self):
        return self.loop

    def error(self, message, code=400):
        return LabError(message, code)


class FakeConfig(object):
    def __init__(self, server, values):
        self.server, self.values = server, values

    def get_server(self):
        return self.server

    def get(self, key, default=None):
        return self.values.get(key, default)


class Lab(object):
    """The component on an event loop of its own, over a seeded or given state folder."""

    def __init__(self, count=200, state=None, now=None):
        self.now = int(time.time() if now is None else now)
        self.folder = tempfile.TemporaryDirectory(prefix="kctrl-spools-lab-")
        root = Path(self.folder.name)
        self.state = Path(state) if state else root / "state"
        self.gcodes = root / "gcodes"
        self.gcodes.mkdir()
        (self.gcodes / GCODE).write_text(GCODE_TEXT, encoding="utf-8")
        self.materials, error = spools.read_materials(str(SYNTHETIC))
        library, events, box = sample(count, self.now)
        store = storage.SpoolStore(str(self.state))
        if store.load_library()[0] is None:
            store.save_library(library)
            for event in events:
                store.append_journal(event)
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, name="spools-lab", daemon=True)
        self.thread.start()
        self.klippy = FakeKlippy(rest_status(box))
        self.server = FakeServer(self.klippy, self.loop)
        self.config = FakeConfig(self.server, {"state_path": str(self.state),
                                               "material_database": str(SYNTHETIC),
                                               "gcodes_path": str(self.gcodes)})
        self.component = self.run(self._start())

    async def _start(self):
        component = adapter.load_component(self.config)
        await component.component_init()
        # The 20 s the box takes to settle after a Klipper restart are skipped:
        # the lab opens on the slots already synced, as a K1 up for a while.
        component.ready_at -= adapter.RESTART_SETTLE_S
        if component.sync_due is not None:
            component.sync_due = component.clock()
        await component._tick()
        return component

    def run(self, coroutine, timeout=CALL_TIMEOUT_S):
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result(timeout)

    def call(self, path, args):
        return self.run(self.server.endpoints[path][1](WebRequest(dict(args))))

    # What the start window asks the printer, answered from the fake K1.
    def query(self, names):
        async def read():
            found = {}
            for name in names:
                if name == "kctrl_print_gate":
                    found[name] = self._gate()
                elif name in self.klippy.status:
                    found[name] = copy.deepcopy(self.klippy.status[name])
            return {"eventtime": time.monotonic(), "status": found}
        return self.run(read())

    def _gate(self):
        slots, units = {}, []
        box = self.klippy.status["box"]
        for number in "1234":
            unit = box.get("T" + number) or {}
            if unit.get("state") != "connect":
                continue
            units.append("T" + number)
            for index, letter in enumerate("ABCD"):
                material = str(unit["material_type"][index])
                remain = int(unit["remain_len"][index])
                record = self.materials.get(material[1:]) if material not in ("-1", "None") else None
                if material in ("-1", "None"):
                    slots["T" + number + letter] = {"loaded": 0, "type": "", "colour": "",
                                                    "material": "", "remain": remain}
                    continue
                slots["T" + number + letter] = {
                    "loaded": 1, "type": record["type"] if record else "", "material": material,
                    "colour": "#" + str(unit["color_value"][index])[-6:].upper(), "remain": remain}
        end = self.klippy.status["kctrl_end"]
        return {"end": {"enabled": True, "pending": False, "phase": "idle",
                        "job_epoch": end.get("job_epoch", 0), "failure": "", "thermal_failure": ""},
                "wrapped": 1, "page": "/bobines/", "pending": 0, "file": "", "name": "",
                "since": 0, "note": "", "filaments": [], "used_count": 0, "declared_count": 0,
                "slots": slots, "units": units, "table": {}, "confirmed_file": "",
                "confirmed_name": "", "confirmed_at": 0, "confirmed_map": {}, "last": None}

    def files(self):
        found = (self.gcodes / GCODE).stat()
        return [{"path": GCODE, "modified": found.st_mtime, "size": found.st_size,
                 "permissions": "rw"}]

    # A print played on the fake K1, step by step, for the counter.
    def simulate(self, action, value=0.0):
        async def play():
            status = self.klippy.status
            if action == "start":
                self.klippy.push({"print_stats": {"state": "printing", "filename": GCODE},
                                  "idle_timeout": {"state": "Printing"}})
            elif action == "extrude":
                position = list(status["toolhead"]["position"])
                position[3] += value
                self.klippy.push({"toolhead": {"position": position}})
            elif action == "end":
                self.klippy.push({"print_stats": {"state": "complete"},
                                  "kctrl_end": {"phase": "idle"}, "idle_timeout": {"state": "Idle"}})
            elif action == "rest":
                self.klippy.push({"print_stats": {"state": "standby", "filename": ""},
                                  "idle_timeout": {"state": "Idle"}})
            else:
                raise LabError("simulation inconnue : %s" % action)
            return self._summary()
        return self.run(play())

    def summary(self):
        async def read():
            return self._summary()
        return self.run(read())

    def _summary(self):
        return {"print": self.klippy.status["print_stats"]["state"],
                "e_mm": self.klippy.status["toolhead"]["position"][3],
                "gcodes": list(self.klippy.gcodes[-20:]), "notifications": self.server.sent}

    def close(self):
        async def stop():
            self.component.close()
            if self.component.task is not None:
                await asyncio.gather(self.component.task, return_exceptions=True)
            await self.loop.shutdown_default_executor()
        try:
            self.run(stop(), 15)
        finally:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(15)
            self.loop.close()
            self.folder.cleanup()


# ---------------------------------------------------------------- the websocket relay
def unmask(data, mask):
    if not data:
        return b""
    key = (mask * (len(data) // 4 + 1))[:len(data)]
    return (int.from_bytes(data, "big") ^ int.from_bytes(key, "big")).to_bytes(len(data), "big")


def read_frame(read):
    """(fin, opcode, payload, raw bytes) of the next frame; None when the stream ends."""
    head = read(2)
    if len(head) < 2:
        return None
    fin, opcode = bool(head[0] & 0x80), head[0] & 0x0F
    masked, length = bool(head[1] & 0x80), head[1] & 0x7F
    extra = b""
    if length in (126, 127):
        extra = read(2 if length == 126 else 8)
        if len(extra) != (2 if length == 126 else 8):
            return None
        length = struct.unpack("!H" if length == 126 else "!Q", extra)[0]
    if length > MAX_FRAME:
        raise ValueError("trame trop longue")
    mask = read(4) if masked else b""
    payload = read(length) if length else b""
    if len(mask) != (4 if masked else 0) or len(payload) != length:
        return None
    return fin, opcode, unmask(payload, mask) if masked else payload, head + extra + mask + payload


def text_frame(text):
    data = text.encode("utf-8")
    if len(data) < 126:
        head = struct.pack("!BB", 0x81, len(data))
    elif len(data) < 65536:
        head = struct.pack("!BBH", 0x81, 126, len(data))
    else:
        head = struct.pack("!BBQ", 0x81, 127, len(data))
    return head + data


def screen(data):
    """None when a browser message may go up to the gateway; else (its id, why not)."""
    try:
        message = json.loads(data.decode("utf-8"))
    except ValueError:
        return None, "message illisible"
    if not isinstance(message, dict):
        return None, "message illisible"
    ident, method, params = message.get("id"), message.get("method"), message.get("params")
    if not isinstance(method, str) or method not in READ_METHODS:
        return ident, "refusé par le labo, lecture seule : %s" % method
    if method == "machine.update.status" and isinstance(params, dict) and params.get("refresh"):
        return ident, "refusé par le labo, lecture seule : rafraîchissement des mises à jour"
    return None


def relayed(path):
    """Whether a GET for `path` may go to the gateway."""
    if not path.startswith(API):
        return True
    return path in READ_PATHS or path.startswith(READ_PREFIXES)


class Stream(object):
    """A socket read in exact sizes, the bytes after the handshake included."""

    def __init__(self, sock):
        self.sock, self.data = sock, bytearray()

    def read(self, size):
        while len(self.data) < size:
            chunk = self.sock.recv(65536)
            if not chunk:
                break
            self.data += chunk
        found = bytes(self.data[:size])
        del self.data[:size]
        return found

    def until(self, marker, limit):
        while marker not in self.data:
            if len(self.data) > limit:
                raise ValueError("en-têtes trop longs")
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ValueError("passerelle fermée")
            self.data += chunk
        end = self.data.index(marker) + len(marker)
        found = bytes(self.data[:end])
        del self.data[:end]
        return found


class Pipe(object):
    """One websocket between the browser and the gateway; only read methods go up."""

    def __init__(self, handler, upstream, stream):
        self.handler, self.upstream, self.stream = handler, upstream, stream
        self.lock = threading.Lock()
        self.fragment = False
        self.refused = []

    def run(self):
        down = threading.Thread(target=self.down, name="spools-lab-down", daemon=True)
        down.start()
        try:
            self.up()
        except (OSError, ValueError):
            pass
        finally:
            self.shut()
            down.join(5)

    def up(self):
        read = self.handler.rfile.read
        while True:
            frame = read_frame(read)
            if frame is None:
                return
            fin, opcode, data, raw = frame
            if opcode in (0x9, 0xA):
                self.upstream.sendall(raw)
                continue
            if opcode == 0x8:
                self.upstream.sendall(raw)
                return
            if opcode != 0x1 or not fin:
                return  # binary or fragmented: Mainsail sends neither, so the pipe closes
            refusal = screen(data)
            if refusal is None:
                self.upstream.sendall(raw)
                continue
            ident, why = refusal
            self.refused.append(why)
            if ident is None:
                continue
            reply = json.dumps({"jsonrpc": "2.0", "id": ident,
                                "error": {"code": 403, "message": why}}, ensure_ascii=False)
            with self.lock:
                if not self.fragment:
                    self.handler.wfile.write(text_frame(reply))

    def down(self):
        try:
            while True:
                frame = read_frame(self.stream.read)
                if frame is None:
                    return
                fin, opcode, _, raw = frame
                with self.lock:
                    if opcode in (0x0, 0x1, 0x2):
                        self.fragment = not fin
                    self.handler.wfile.write(raw)
                if opcode == 0x8:
                    return
        except (OSError, ValueError):
            pass
        finally:
            self.shut()

    def shut(self):
        for close in (lambda: self.upstream.shutdown(socket.SHUT_RDWR), self.upstream.close,
                      lambda: self.handler.connection.shutdown(socket.SHUT_RDWR)):
            try:
                close()
            except OSError:
                pass


# ---------------------------------------------------------------- HTTP
class LabServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, lab, port=8781, gateway=None, verbose=False):
        self.lab, self.gateway, self.verbose = lab, gateway, verbose
        super().__init__(("127.0.0.1", port), Handler)
        self.port = self.server_address[1]
        self.hosts = frozenset(("127.0.0.1:%d" % self.port, "localhost:%d" % self.port))
        self.origins = frozenset("http://" + host for host in self.hosts)


class Handler(BaseHTTPRequestHandler):
    server_version = "K1ControlLab/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if self.server.verbose:
            super().log_message(fmt, *args)

    def send(self, code, body, kind="application/json", extra=()):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        for name, value in HEADERS + tuple(extra):
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def answer(self, code, value):
        self.send(code, json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def refuse(self, code, message):
        self.answer(code, {"error": {"code": code, "message": message}})

    def checked(self):
        """Only this machine's own pages may call: DNS rebinding and other sites stay out."""
        if self.headers.get("Host", "") not in self.server.hosts:
            self.refuse(421, "hôte refusé par le labo")
            return False
        origin = self.headers.get("Origin")
        if self.command != "GET" and origin is not None and origin not in self.server.origins:
            self.refuse(403, "origine refusée par le labo")
            return False
        return True

    def do_GET(self):
        if not self.checked():
            return
        url = urllib.parse.urlsplit(self.path)
        path = url.path
        if path.startswith(adapter.PREFIX):
            return self.endpoint(path, url.query, {})
        if path == "/bobines":
            return self.send(301, b"", "text/plain", (("Location", "/bobines/"),))
        if path.startswith("/bobines/"):
            return self.page(path[len("/bobines/"):] or "index.html")
        if path == "/favicon.ico":
            return self.send(204, b"", "image/x-icon")
        if path == "/lab/status":
            return self.answer(200, {"result": self.server.lab.summary()})
        if self.server.gateway is not None:
            if path == "/websocket" and self.headers.get("Upgrade", "").lower() == "websocket":
                return self.websocket()
            if not relayed(path):
                return self.refuse(403, "refusé par le labo, lecture seule : %s" % path)
            return self.relay()
        if path in ("/", "/index.html"):
            return self.send(200, PAGE.read_bytes(), TYPES[".html"])
        if path == "/printer/objects/query":
            names = list(urllib.parse.parse_qs(url.query, keep_blank_values=True))
            return self.answer(200, {"result": self.server.lab.query(names)})
        if path == "/server/files/list":
            return self.answer(200, {"result": self.server.lab.files()})
        return self.refuse(404, "inconnu du labo : %s" % path)

    do_HEAD = do_GET

    def do_POST(self):
        if not self.checked():
            return
        url = urllib.parse.urlsplit(self.path)
        body = self.body()
        if body is None:
            return
        if url.path.startswith(adapter.PREFIX):
            return self.endpoint(url.path, url.query, body)
        if url.path == "/lab/simulate":
            args = dict(urllib.parse.parse_qsl(url.query))
            try:
                found = self.server.lab.simulate(args.get("action", ""), float(args.get("mm", 0)))
            except (LabError, ValueError) as error:
                return self.refuse(400, str(error))
            return self.answer(200, {"result": found})
        return self.refuse(403, "refusé par le labo, rien n'est envoyé à une imprimante : %s"
                           % url.path)

    def do_PUT(self):
        self.refuse(405, "méthode refusée par le labo")

    do_DELETE = do_PATCH = do_PUT

    def body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 <= length <= MAX_BODY:
            self.refuse(413, "corps refusé")
            return None
        data = self.rfile.read(length) if length else b""
        if not data:
            return {}
        try:
            value = json.loads(data.decode("utf-8"))
        except ValueError:
            self.refuse(400, "JSON illisible")
            return None
        if not isinstance(value, dict):
            self.refuse(400, "objet JSON attendu")
            return None
        return value

    def endpoint(self, path, query, body):
        entry = self.server.lab.server.endpoints.get(path)
        if entry is None:
            return self.refuse(404, "point d'accès inconnu : %s" % path)
        kind, handler = entry
        if not kind & (RequestType.POST if self.command == "POST" else RequestType.GET):
            return self.refuse(405, "%s refusé pour %s" % (self.command, path))
        args = dict(urllib.parse.parse_qsl(query, keep_blank_values=True))
        args.update(body)
        try:
            result = self.server.lab.run(handler(WebRequest(args)))
        except LabError as error:
            return self.refuse(error.status_code, error.message)
        except Exception as error:  # shown as Moonraker shows an unexpected error
            return self.refuse(500, "%s: %s" % (type(error).__name__, error))
        self.answer(200, {"result": result})

    def page(self, name):
        if "/" in name or "\\" in name or name.startswith(".") or name not in os.listdir(WWW):
            return self.refuse(404, "inconnu du labo : /bobines/%s" % name)
        target = WWW / name
        if not target.is_file():
            return self.refuse(404, "inconnu du labo : /bobines/%s" % name)
        self.send(200, target.read_bytes(), TYPES.get(target.suffix, "application/octet-stream"))

    # -- the read-only relay to the real Mainsail
    def relay(self):
        host, port = self.server.gateway
        target = "%s:%d" % (host, port)
        headers = {"Host": target, "Accept-Encoding": "identity"}
        for name in ("Accept", "Accept-Language", "User-Agent"):
            if self.headers.get(name):
                headers[name] = self.headers[name]
        connection = http.client.HTTPConnection(host, port, timeout=30)
        started = False
        try:
            connection.request(self.command, self.path, headers=headers)
            response = connection.getresponse()
            kind = response.getheader("Content-Type", "application/octet-stream")
            extra = []
            location = response.getheader("Location")
            if location:
                extra.append(("Location", location.replace("http://" + target, "", 1)))
            if self.command == "GET" and kind.startswith("text/html"):
                body = response.read(MAX_HTML + 1)
                if len(body) > MAX_HTML:
                    return self.refuse(502, "page trop longue")
                text = body.decode("utf-8", "replace")
                if TAG not in text and "</body>" in text:
                    text = text.replace("</body>", MARK + TAG + "</body>", 1)
                return self.send(response.status, text.encode("utf-8"), kind, extra)
            length = response.getheader("Content-Length")
            self.send_response(response.status)
            started = True
            self.send_header("Content-Type", kind)
            if length is not None:
                self.send_header("Content-Length", length)
            else:
                self.send_header("Connection", "close")
                self.close_connection = True
            for name, value in HEADERS + tuple(extra):
                self.send_header(name, value)
            self.end_headers()
            if self.command == "HEAD":
                return
            while True:
                chunk = response.read(65536)
                if not chunk:
                    return
                self.wfile.write(chunk)
        except (OSError, http.client.HTTPException) as error:
            if started:
                self.close_connection = True
            else:
                self.refuse(502, "passerelle injoignable (%s)" % type(error).__name__)
        finally:
            connection.close()

    def websocket(self):
        if self.headers.get("Origin", "") not in self.server.origins:
            return self.refuse(403, "origine refusée par le labo")
        key = self.headers.get("Sec-WebSocket-Key", "")
        if not key or self.headers.get("Sec-WebSocket-Version") != "13":
            return self.refuse(400, "poignée de main websocket incomplète")
        accept = base64.b64encode(hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest())
        host, port = self.server.gateway
        target = "%s:%d" % (host, port)
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError as error:
            return self.refuse(502, "passerelle injoignable (%s)" % type(error).__name__)
        try:
            # No Sec-WebSocket-Extensions: frames stay uncompressed, so they can be read here.
            upstream.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\n"
                              "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
                              "Sec-WebSocket-Version: 13\r\nOrigin: http://%s\r\n\r\n"
                              % (self.path, target, key, target)).encode("latin-1"))
            stream = Stream(upstream)
            lines = stream.until(b"\r\n\r\n", 16384).decode("latin-1").split("\r\n")
            fields = {}
            for line in lines[1:]:
                name, _, value = line.partition(":")
                fields[name.strip().lower()] = value.strip()
            status = lines[0].split()
            if (len(status) < 2 or status[1] != "101"
                    or fields.get("sec-websocket-accept") != accept.decode("ascii")
                    or "sec-websocket-extensions" in fields):
                raise ValueError("réponse websocket inattendue")
            upstream.settimeout(None)
        except (OSError, ValueError) as error:
            upstream.close()
            return self.refuse(502, "passerelle : %s" % (error if isinstance(error, ValueError)
                                                          else type(error).__name__))
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept.decode("ascii"))
        self.end_headers()
        self.close_connection = True
        Pipe(self, upstream, stream).run()


# ---------------------------------------------------------------- main
def measure(count):
    """Python memory of the component with `count` spools, one status and one export."""
    tracemalloc.start()
    try:
        lab = Lab(count)
        try:
            found = {"spools": count, "resident_kib": round(tracemalloc.get_traced_memory()[0] / 1024),
                     "library_bytes": (lab.state / storage.LIBRARY).stat().st_size}
            for name in ("status", "export"):
                tracemalloc.reset_peak()
                base = tracemalloc.get_traced_memory()[0]
                result = lab.call(adapter.PREFIX + name, {})
                found[name + "_peak_kib"] = round((tracemalloc.get_traced_memory()[1] - base) / 1024)
                found[name + "_bytes"] = len(json.dumps(result, ensure_ascii=False).encode("utf-8"))
                del result
            return found
        finally:
            lab.close()
    finally:
        tracemalloc.stop()


def parse_gateway(value):
    host, _, port = value.strip().rpartition(":")
    if not host or not port.isdigit() or not 0 < int(port) < 65536:
        return None
    return host, int(port)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Labo local du gestionnaire de bobines.")
    parser.add_argument("--port", type=int, default=8781)
    parser.add_argument("--spools", type=int, default=200)
    parser.add_argument("--state", default="", help="dossier d'état gardé entre deux lancements")
    parser.add_argument("--mainsail", action="store_true",
                        help="relais en lecture seule vers la passerelle de K1_GATEWAY")
    parser.add_argument("--measure", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.measure:
        print(json.dumps(measure(args.spools), indent=2))
        return 0
    gateway = None
    if args.mainsail:
        gateway = parse_gateway(os.environ.get("K1_GATEWAY", ""))
        if gateway is None:
            parser.error("K1_GATEWAY attendu sous la forme hôte:port")
    lab = Lab(args.spools, args.state or None)
    server = LabServer(lab, args.port, gateway, args.verbose)
    print("Labo des bobines sur http://127.0.0.1:%d/%s" % (
        server.port, " (relais Mainsail en lecture seule)" if gateway else ""), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        lab.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
