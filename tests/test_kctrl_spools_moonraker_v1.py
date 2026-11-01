"""Le composant Moonraker des bobines (document 102, lot F), contre un faux Moonraker.

La K1 se lit par abonnement seulement, sans requête pendant une impression ;
le CFS ne s'écrit qu'au repos, relu juste avant ; une écriture demandée
pendant une impression attend sa fin ; un écart se montre et ne se renvoie
jamais ; une impression se compte une fois, même après un redémarrage ; le
numéro de série et l'uuid du CFS ne sont jamais gardés ; la bibliothèque ne se
réécrit pas d'elle-même pendant une impression.
"""

import asyncio
import copy
import enum
import importlib
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "spool-manager-v1"
SYNTHETIC = PACKAGE / "lab" / "material_database.synthetic.json"


def fake_moonraker():
    """The adapter imported as Moonraker imports it, beside a fake `common`."""
    root = types.ModuleType("fakemr")
    root.__path__ = []
    common = types.ModuleType("fakemr.common")

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
    components = types.ModuleType("fakemr.components")
    components.__path__ = [str(PACKAGE)]
    root.common, root.components = common, components
    for module in (root, common, components):
        sys.modules[module.__name__] = module
    return importlib.import_module("fakemr.components.kctrl_spools")


adapter = fake_moonraker()
spools, counting, storage = adapter.spools, adapter.counting, adapter.storage
WebRequest = sys.modules["fakemr.common"].WebRequest
MATERIALS, _ = spools.read_materials(str(SYNTHETIC))
NOW = 1_790_000_000
RED = ("000001", "0ff1e1e")  # F001, Geeetech PLA FF1E1E
WHITE = ("001001", "0ffffff")  # F002, Creality Hyper PLA FFFFFF
WRITE_RED = "KCTRL_FILAMENT SLOT=T1A MATERIAL=000001 COLOR=0ff1e1e"
WRITE_WHITE_T1B = "KCTRL_FILAMENT SLOT=T1B MATERIAL=001001 COLOR=0ffffff"
PRINTING = {"print_stats": {"state": "printing", "filename": "cube.gcode"}}
ENDED = {"print_stats": {"state": "complete"}, "kctrl_end": {"phase": "idle"}}
FOOTER = "G1 X1\n; filament used [mm] = 1234.5, 0.00\n; filament used [g] = 3.7, 0.00\n"
BASE = (
    ("create_empty_spool", {"manufacturer": "GEEETECH", "name": "Bobine plastique fine",
                            "spool_material": "plastique", "tare_g": 180, "nominal_net_g": 1000,
                            "source": "spoolmandb", "catalogue": "GEEETECH|1000|180|plastique"}),
    ("create_filament", {"manufacturer": "Geeetech", "name": "PLA", "material": "PLA", "colour": "#FF1E1E"}),
    ("create_filament", {"manufacturer": "Creality", "name": "Hyper PLA", "material": "PLA",
                         "colour": "FFFFFF"}),
    ("create_spool", {"filament": "F001", "empty_spool": "V001"}),
    ("put_in_cfs", {"id": "B001", "slot": "T1A"}),
)
SECOND = (("create_spool", {"filament": "F002", "empty_spool": "V001"}),
          ("put_in_cfs", {"id": "B002", "slot": "T1B"}))


def library(*steps):
    work = spools.empty_library()
    for name, params in steps:
        work = spools.apply(work, name, params, spools.Context(NOW, MATERIALS))[0]
    return work


class FakeError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class FakeLoop(object):
    async def run_in_thread(self, fn, *args):
        return fn(*args)


class FakeConnection(object):
    def __init__(self):
        self.ready = True

    def is_ready(self):
        return self.ready


class FakeApis(object):
    """klippy_apis: the subscription, the queries and the G-code sent."""

    def __init__(self, status):
        self.status = status
        self.callbacks, self.subscriptions, self.queries, self.gcodes = [], [], [], []
        self.connected = True
        self.mode = ""

    def select(self, objects):
        found = {}
        for name, fields in objects.items():
            values = self.status.get(name)
            if isinstance(values, dict):
                found[name] = copy.deepcopy({key: values[key] for key in fields if key in values})
        return found

    async def subscribe_objects(self, objects, callback=None, default=None):
        self.subscriptions.append(copy.deepcopy(objects))
        if not self.connected:
            return default
        self.callbacks.append(callback)
        return self.select(objects)

    async def query_objects(self, objects):
        self.queries.append(sorted(objects))
        if not self.connected:
            raise FakeError("Klippy Disconnected", 503)
        return self.select(objects)

    async def run_gcode(self, script):
        self.gcodes.append(script)
        if self.mode == "raise":
            raise FakeError("Unknown command")
        if self.mode == "timeout":
            await asyncio.sleep(3600)
        if self.mode == "silent":
            return "ok"
        words = dict(word.split("=", 1) for word in script.split()[1:])
        if self.mode == "different":
            if "COLOR" in words:
                words["COLOR"] = "0000000"
            else:
                words["MATERIAL"] = "000005"
        slot = words["SLOT"]
        unit = self.status["box"]["T" + slot[1]]
        index = "ABCD".index(slot[2])
        if "MATERIAL" in words:
            unit["material_type"][index] = words["MATERIAL"]
        if "COLOR" in words:
            unit["color_value"][index] = words["COLOR"]
        asyncio.get_running_loop().call_soon(self.push, {"box": {"T" + slot[1]: copy.deepcopy(unit)}})
        return "ok"

    def push(self, diff):
        for name, fields in diff.items():
            self.status.setdefault(name, {}).update(copy.deepcopy(fields))
        shared = copy.deepcopy(diff)
        for callback in list(self.callbacks):
            callback(shared, 0.0)
        assert shared == diff, "un abonné a modifié le diff que Moonraker partage"

    def disconnect(self):
        self.callbacks = []
        self.connected = False


class FakeServer(object):
    def __init__(self, apis, connection):
        self.components = {"klippy_apis": apis, "klippy_connection": connection}
        self.endpoints, self.handlers, self.notifications, self.events = {}, {}, [], []
        self.loop = FakeLoop()

    def lookup_component(self, name, default=None):
        return self.components.get(name, default)

    def register_endpoint(self, path, kind, handler):
        self.endpoints[path] = (kind, handler)

    def register_event_handler(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    def register_notification(self, name):
        self.notifications.append(name)

    def send_event(self, name, *args):
        self.events.append((name, args))

    def get_event_loop(self):
        return self.loop

    def error(self, message, code=400):
        return FakeError(message, code)


class FakeConfig(object):
    def __init__(self, server, values):
        self.server, self.values = server, values

    def get_server(self):
        return self.server

    def get(self, key, default=None):
        return self.values.get(key, default)


def unit(number, slots, engaged=""):
    """One connected CFS unit; `slots` is {letter: (material, colour[, vender, remain])}."""
    values = {"sn": "SERIAL-T%d" % number, "uuid": "UUID-T%d" % number, "state": "connect",
              "filament": engaged or "None", "material_type": ["-1"] * 4, "color_value": ["-1"] * 4,
              "vender": ["none"] * 4, "remain_len": ["0"] * 4}
    for letter, seen in slots.items():
        index = "ABCD".index(letter)
        values["material_type"][index], values["color_value"][index] = seen[0], seen[1]
        values["vender"][index] = seen[2] if len(seen) > 2 else "unknown"
        values["remain_len"][index] = seen[3] if len(seen) > 3 else "100"
    return values


def offline(number):
    return {"sn": "SERIAL-T%d" % number, "uuid": "UUID-T%d" % number, "state": "None",
            "filament": "None", "material_type": ["None"] * 4, "color_value": ["None"] * 4,
            "vender": ["-1"] * 4, "remain_len": ["-1"] * 4}


def rest_status(slots=None, engaged="", e=0.0, connected=("1", "2")):
    """The K1 at rest; `slots` is {"T1A": (material, colour, ...)}, `engaged` the route."""
    slots = {"T1A": WHITE} if slots is None else slots
    box = {"enable": 1, "state": "connect", "t_command": ""}
    for number in (1, 2, 3, 4):
        name = "T%d" % number
        if str(number) not in connected:
            box[name] = offline(number)
            continue
        mine = {slot[2]: seen for slot, seen in slots.items() if slot[:2] == name}
        box[name] = unit(number, mine, engaged[2] if engaged[:2] == name else "")
    return {
        "box": box,
        "toolhead": {"position": [0.0, 0.0, 0.0, float(e)]},
        counting.SENSOR: {"filament_detected": True, "enabled": True},
        "print_stats": {"state": "standby", "filename": ""},
        "kctrl_end": {"phase": "idle", "job_epoch": 0, "pending": False},
        "kctrl_tool_change": {"last": None, "last_reload": None},
        "webhooks": {"state": "ready"},
        "idle_timeout": {"state": "Idle"},
        "kctrl_print_gate": {"pending": 0},
    }


def printing_status(**options):
    status = rest_status(**options)
    status.update(copy.deepcopy(PRINTING))
    return status


def at(e):
    return {"toolhead": {"position": [0.0, 0.0, 0.0, float(e)]}}


def full_disk(step):
    """A store fault: the library cannot be written, everything else can."""
    if step == "library:write":
        raise OSError("disque plein")


def files(directory):
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in sorted(directory.rglob("*")) if path.is_file()}


def checkpoints(directory):
    return {name: (directory / name).read_bytes()
            for name in storage.CHECKPOINTS if (directory / name).exists()}


def restore(directory, kept):
    for name in storage.CHECKPOINTS:
        if name in kept:
            (directory / name).write_bytes(kept[name])
        elif (directory / name).exists():
            (directory / name).unlink()


def spool_of(public, ident):
    return next(spool for spool in public["spools"] if spool["id"] == ident)


class Rig(object):
    """One component on its own event loop, with a clock that moves only when told."""

    def __init__(self, tmp_path, status=None, saved=None, start=NOW, materials=True):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.clock = [float(start)]
        self.state = tmp_path / "state"
        self.gcodes = tmp_path / "gcodes"
        self.gcodes.mkdir(exist_ok=True)
        if saved is not None:
            storage.SpoolStore(str(self.state)).save_library(saved)
        self.apis = FakeApis(rest_status() if status is None else status)
        self.connection = FakeConnection()
        self.server = FakeServer(self.apis, self.connection)
        self.config = FakeConfig(self.server, {
            "state_path": str(self.state),
            "material_database": str(SYNTHETIC if materials else tmp_path / "absent.json"),
            "gcodes_path": str(self.gcodes)})
        self.component = None
        self.closed = False

    @property
    def now(self):
        return self.clock[0]

    def create(self):
        self.component = adapter.load_component(self.config)
        self.component.clock = lambda: self.clock[0]
        return self.component

    def build(self):
        if self.component is None:
            self.create()
        self.run(self.component.component_init())
        return self

    def run(self, awaitable):
        return self.loop.run_until_complete(awaitable)

    def call(self, name, args=None):
        handler = self.server.endpoints[adapter.PREFIX + name][1]
        return self.run(handler(WebRequest(dict(args or {}))))

    def refused(self, name, args, code, fragment):
        with pytest.raises(FakeError) as caught:
            self.call(name, args)
        assert caught.value.status_code == code, caught.value.message
        assert fragment in caught.value.message, caught.value.message
        return caught.value.message

    def tick(self, seconds=0.0):
        self.clock[0] += seconds
        self.run(self.component._tick())

    def push(self, diff, seconds=0.0):
        self.clock[0] += seconds
        self.apis.push(diff)

    def public(self):
        return self.component._public()

    def view(self, slot):
        return next(view for view in self.public()["slots"] if view["slot"] == slot)

    def journal(self, kind=None):
        entries = storage.SpoolStore(str(self.state)).read_journal(1000)
        return [entry for entry in entries if kind is None or entry.get("kind") == kind]

    def saved_checkpoint(self):
        return storage.SpoolStore(str(self.state)).load_checkpoint()[0]

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.component is not None:
            self.component.close()
            if self.component.task is not None:
                self.run(asyncio.gather(self.component.task, return_exceptions=True))
        self.loop.close()
        asyncio.set_event_loop(None)


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    monkeypatch.setattr(adapter, "TICK_S", 3600)
    monkeypatch.setattr(adapter, "READBACK_S", 1 / 16)
    monkeypatch.setattr(adapter, "READBACK_STEP_S", 1 / 64)  # four readings, then one query
    monkeypatch.setattr(adapter, "WRITE_TIMEOUT_S", 0.05)


@pytest.fixture
def make(tmp_path):
    rigs = []

    def made(build=True, **options):
        rig = Rig(tmp_path, **options)
        rigs.append(rig)
        return rig.build() if build else rig

    yield made
    for rig in reversed(rigs):
        rig.close()


# ---------------------------------------------------------------- writing the CFS
def test_a_write_asked_during_a_print_waits_for_its_end(make):
    rig = make(status=printing_status(), saved=library(*BASE))
    assert rig.public()["revision"] == 1
    answer = rig.call("cfs-write", {"slot": "T1A"})
    assert answer["result"] == {"slot": "T1A", "queued": True, "written": False, "result": "en_attente",
                                "detail": "sera envoyé au CFS à la fin de l'impression"}
    assert rig.apis.queries == [] and rig.apis.gcodes == []
    assert rig.view("T1A")["status"] == "en_attente_cfs"
    assert rig.public()["pending_cfs"]["T1A"]["spool"] == "B001"
    assert rig.public()["revision"] == 2
    assert [entry["result"] for entry in rig.journal("ecriture_cfs")] == ["en attente"]


def test_a_print_only_the_rest_reading_shows_also_queues_the_write(make):
    rig = make(saved=library(*BASE))
    rig.apis.status["print_stats"]["state"] = "printing"
    assert rig.call("cfs-write", {"slot": "T1A"})["result"]["queued"] is True
    assert len(rig.apis.queries) == 1 and rig.apis.gcodes == []


def test_a_write_at_rest_reads_the_rest_once_then_sees_the_box_change(make):
    rig = make(saved=library(*BASE))
    answer = rig.call("cfs-write", {"slot": "T1A"})
    assert rig.apis.queries == [["box", "idle_timeout", "kctrl_end", "kctrl_print_gate", "print_stats",
                                 "webhooks"]]
    assert rig.apis.gcodes == [WRITE_RED]
    assert answer["result"] == {"slot": "T1A", "queued": False, "written": True, "result": "ok", "detail": ""}
    view = rig.view("T1A")
    assert view["status"] == "ok"
    assert view["last_write"]["result"] == "ok"
    assert [entry["result"] for entry in rig.journal("ecriture_cfs")] == ["ok"]


@pytest.mark.parametrize("mode, result, detail", [
    ("different", "ecart", "le CFS montre autre chose après l'écriture"),
    ("silent", "ecart", "le CFS montre autre chose après l'écriture"),
    ("raise", "erreur", "refusé par Klipper : Unknown command"),
    ("timeout", "erreur", "pas de réponse de Klipper en 0.05 s"),
])
def test_a_failed_write_shows_its_gap_and_is_never_sent_again(make, mode, result, detail):
    rig = make(saved=library(*BASE))
    rig.apis.mode = mode
    answer = rig.call("cfs-write", {"slot": "T1A"})["result"]
    assert (answer["written"], answer["result"], answer["detail"]) == (False, result, detail)
    assert len(rig.apis.queries) == 2  # the rest, then the box once more
    rig.apis.mode = ""
    rig.tick(21)
    rig.tick(31)
    assert rig.apis.gcodes == [WRITE_RED]
    assert rig.view("T1A")["last_write"]["result"] == result
    attention = rig.public()["attention"]
    assert "T1A à vérifier" in attention
    assert "T1A : écriture au CFS non confirmée" in attention


@pytest.mark.parametrize("name, field, value, problem", [
    ("kctrl_print_gate", "pending", 1, "un départ attend le choix des bobines"),
    ("idle_timeout", "state", "Printing", "Klipper occupé"),
    ("kctrl_end", "phase", "purge", "fin d'impression en cours"),
    ("kctrl_end", "pending", True, "fin d'impression en cours"),
    ("webhooks", "state", "startup", "Klipper n'est pas prêt"),
    ("box", "t_command", "T1A", "le CFS exécute une commande"),
    ("box", "enable", 0, "CFS non prêt"),
    ("print_stats", None, None, "état d'impression inconnu (absent)"),
])
def test_a_write_is_refused_unless_the_k1_rests(make, name, field, value, problem):
    rig = make(saved=library(*BASE))
    if field is None:
        del rig.apis.status[name]
    else:
        rig.apis.status[name][field] = value
    rig.refused("cfs-write", {"slot": "T1A"}, 409, "écriture refusée : " + problem)
    assert rig.apis.gcodes == [] and rig.public()["pending_cfs"] == {}


def test_a_k1_without_the_end_of_print_object_still_rests(make):
    rig = make(saved=library(*BASE))
    del rig.apis.status["kctrl_end"]
    assert rig.call("cfs-write", {"slot": "T1A"})["result"]["result"] == "ok"


def test_the_rest_reading():
    assert adapter.rest_problem(None) == "état de la K1 illisible"
    assert adapter.rest_problem({}) == "Klipper n'est pas prêt"
    assert adapter.rest_problem(rest_status()) == ""
    for state in ("printing", "paused"):
        status = rest_status()
        status["print_stats"]["state"] = state
        assert adapter.rest_problem(status) == adapter.PRINTING_NOW
    status = rest_status()
    del status["box"]
    assert adapter.rest_problem(status) == "CFS illisible"


def test_writes_queued_during_a_print_go_out_at_its_end_in_slot_order(make):
    rig = make(status=printing_status(slots={"T1A": WHITE, "T1B": RED}), saved=library(*BASE, *SECOND))
    for slot in ("T1B", "T1A"):
        assert rig.call("cfs-write", {"slot": slot})["result"]["queued"] is True
    revision = rig.public()["revision"]
    rig.tick(21)
    assert rig.apis.queries == [] and rig.apis.gcodes == []
    rig.push(ENDED, 1)
    rig.tick(6)
    assert rig.apis.gcodes == [WRITE_RED, WRITE_WHITE_T1B]
    public = rig.public()
    assert public["pending_cfs"] == {}
    assert [rig.view(slot)["status"] for slot in ("T1A", "T1B")] == ["ok", "ok"]
    assert len(public["prints"]) == 1
    assert public["revision"] == revision + 4  # the print, the slots, two writes
    notes = public["prints"][0]["notes"]
    assert counting.MIDWAY in notes
    assert any(note.startswith("fichier illisible") for note in notes)


def test_a_queued_write_klipper_refuses_holds_the_next_until_the_retry(make):
    rig = make(status=printing_status(slots={"T1A": WHITE, "T1B": RED}), saved=library(*BASE, *SECOND))
    for slot in ("T1A", "T1B"):
        rig.call("cfs-write", {"slot": slot})
    rig.apis.mode = "raise"
    rig.push(ENDED, 1)
    rig.tick(6)
    assert rig.apis.gcodes == [WRITE_RED]
    assert sorted(rig.public()["pending_cfs"]) == ["T1B"]
    rig.apis.mode = ""
    rig.tick(31)
    assert rig.apis.gcodes == [WRITE_RED, WRITE_WHITE_T1B]
    assert rig.public()["pending_cfs"] == {}
    assert rig.view("T1A")["last_write"]["result"] == "erreur"


def test_a_slot_without_a_chip_is_written_like_any_other(make):
    rig = make(status=rest_status(slots={"T1A": ("-1", "-1", "unknown")}), saved=library(*BASE))
    assert rig.view("T1A")["status"] == "a_verifier"
    assert rig.call("cfs-write", {"slot": "T1A"})["result"]["result"] == "ok"
    assert rig.apis.gcodes == [WRITE_RED]
    assert rig.view("T1A")["status"] == "ok"


def test_a_write_result_that_cannot_be_saved_is_kept_then_saved_first(make):
    rig = make(saved=library(*BASE))
    rig.component.store._step = full_disk
    answer = rig.call("cfs-write", {"slot": "T1A"})
    assert answer["result"]["result"] == "ok"
    assert answer["status"]["unsaved_writes"] == ["T1A"]
    del rig.component.store._step
    rig.call("action", {"action": "settings", "params": {"low_g": 150}})
    assert [entry["kind"] for entry in rig.journal()] == ["reglages", "ecriture_cfs"]
    assert rig.public()["unsaved_writes"] == []
    assert rig.view("T1A")["last_write"]["result"] == "ok"
    assert rig.apis.gcodes == [WRITE_RED]


def test_a_write_result_that_cannot_be_saved_is_saved_by_a_later_tick(make):
    rig = make(saved=library(*BASE))
    rig.component.store._step = full_disk
    rig.call("cfs-write", {"slot": "T1A"})
    del rig.component.store._step
    rig.component.sync_due = None
    rig.tick(31)
    assert rig.public()["unsaved_writes"] == []
    assert [entry["result"] for entry in rig.journal("ecriture_cfs")] == ["ok"]
    assert rig.apis.gcodes == [WRITE_RED]


# ---------------------------------------------------------------- counting the prints
def test_a_print_is_counted_once_even_when_k1_control_restarts_before_its_checkpoint(make):
    first = make(status=rest_status(slots={"T1A": RED}, engaged="T1A"), saved=library(*BASE))
    (first.gcodes / "cube.gcode").write_bytes(FOOTER.encode("ascii"))
    first.tick(21)
    first.push(PRINTING, 1)
    first.push(at(100))
    first.push(at(250))
    first.tick(60)
    middle = checkpoints(first.state)
    first.push(ENDED, 1)
    first.tick(6)
    public = first.public()
    assert len(public["prints"]) == 1
    printed = public["prints"][0]
    assert printed["planned"] == [{"mm": 1234.5, "g": 3.7}, {"mm": 0.0, "g": 0.0}]
    assert [(line["spool"], line["mm"]) for line in printed["per_spool"]] == [("B001", 250.0)]
    counted = spool_of(public, "B001")["counted_g"]
    assert counted > 0
    revision = public["revision"]
    first.close()
    restore(first.state, middle)  # cut after the print was saved, before its checkpoint
    status = rest_status(slots={"T1A": RED}, engaged="T1A", e=250)
    status["print_stats"] = {"state": "complete", "filename": "cube.gcode"}
    second = make(status=status, start=first.now + 30)
    assert second.public()["counter"]["restored"] is True
    second.tick(6)
    public = second.public()
    assert len(public["prints"]) == 1
    assert spool_of(public, "B001")["counted_g"] == counted
    assert len(second.journal("impression")) == 1
    assert public["revision"] == revision


def test_the_checkpoint_keeps_the_closing_print_while_its_report_cannot_be_saved(make):
    rig = make(status=rest_status(slots={"T1A": RED}, engaged="T1A"), saved=library(*BASE))
    rig.tick(21)
    rig.push(PRINTING, 1)
    rig.push(at(80))
    rig.tick(60)
    rig.component.store._step = full_disk
    rig.push(ENDED, 1)
    rig.tick(6)
    assert rig.public()["reports_waiting"] == 1
    assert rig.saved_checkpoint()["period"]["kind"] == "job"
    del rig.component.store._step
    rig.tick(31)
    public = rig.public()
    assert public["reports_waiting"] == 0 and len(public["prints"]) == 1
    assert rig.saved_checkpoint()["period"] is None


def test_route_changes_during_a_print_write_only_the_journal_and_the_checkpoint(make):
    mine = {"A": RED, "B": WHITE}
    rig = make(status=rest_status(slots={"T1A": RED, "T1B": WHITE}, engaged="T1A"),
               saved=library(*BASE, *SECOND))
    rig.tick(21)
    revision = rig.public()["revision"]
    rig.push(PRINTING, 1)
    rig.push(at(50))
    rig.push({"box": {"T1": unit(1, mine)}})
    rig.push({"box": {"T1": unit(1, mine, "B")}})
    rig.push(at(80))
    rig.push({"box": {"T1": unit(1, mine)}})
    rig.push({"box": {"T1": unit(1, mine, "A")}})
    rig.push(at(100))
    rig.tick(3)
    assert rig.public()["revision"] == revision
    assert rig.apis.queries == []
    sizes = [path.stat().st_size for path in rig.state.glob("checkpoint.*")]
    assert sizes and set(sizes) == {4096}
    routes = [{key: entry[key] for key in ("slot", "from", "spool")} for entry in rig.journal("route")]
    assert routes == [{"slot": "T1A", "from": "T1B", "spool": "B001"},
                      {"slot": "T1B", "from": "T1A", "spool": "B002"}]
    rig.push({"box": {"T2": unit(2, {"A": RED})}})
    assert rig.server.events[-1][1][0]["reason"] == "cfs"
    rig.tick(5)
    assert rig.public()["revision"] == revision  # the slots are synced after the print
    rig.push(ENDED, 1)
    rig.tick(6)
    assert rig.public()["revision"] == revision + 2  # the print, then the slots


def test_closing_saves_the_queued_journal_and_the_counter(make):
    rig = make(status=rest_status(slots={"T1A": RED, "T1B": WHITE}, engaged="T1A"),
               saved=library(*BASE, *SECOND))
    rig.tick(21)
    rig.push(PRINTING, 1)
    rig.push({"box": {"T1": unit(1, {"A": RED, "B": WHITE}, "B")}})
    rig.close()
    assert [entry["slot"] for entry in rig.journal("route")] == ["T1B"]
    assert rig.saved_checkpoint()["route"] == "T1B"


def test_an_announced_tool_change_is_expected_on_its_slot(make):
    rig = make(status=rest_status(slots={"T1A": RED, "T1B": WHITE}, engaged="T1A"),
               saved=library(*BASE, *SECOND))
    rig.server.handlers["server:gcode_response"][0]("// K1 Control: T1 -> filament 2 (T1B) sur T1B, PLA FFFFFF")
    assert rig.component.counter.state["expect"]["slot"] == "T1B"


# ---------------------------------------------------------------- what is kept
def test_the_serial_number_and_uuid_of_the_cfs_are_never_kept(make):
    kept = adapter.keep({"box": {"enable": 1, "T1": unit(1, {"A": RED})}, "other": {"x": 1}})
    assert sorted(kept) == ["box"] and sorted(kept["box"]["T1"]) == sorted(adapter.UNIT_FIELDS)
    rig = make(saved=library(*BASE))
    rig.call("cfs-write", {"slot": "T1A"})
    rig.tick(21)
    rig.push(PRINTING, 1)
    rig.push(at(10))
    rig.tick(3)
    exported = rig.call("export")
    texts = [json.dumps(value, ensure_ascii=False, default=str) for value in (
        rig.component.merged, rig.component.observations, rig.public(), rig.journal(), exported)]
    texts += [data.decode("utf-8", "replace") for data in files(rig.state).values()]
    for text in texts:
        assert "SERIAL-T" not in text and "UUID-T" not in text


def test_the_shared_status_diff_is_never_changed(make):
    rig = make(saved=library(*BASE))
    diff = {"box": {"T1": unit(1, {"A": RED})}, "toolhead": {"position": [0.0, 0.0, 0.0, 5.0]},
            "print_stats": {"state": "standby"}, "other": {"x": 1}}
    before = copy.deepcopy(diff)
    rig.component._on_status(diff, 0.0)
    assert diff == before


def test_a_library_from_a_newer_version_locks_everything_and_writes_nothing(make):
    rig = make(build=False)
    rig.state.mkdir()
    body = storage.encode(library(*BASE))
    header = {"format": storage.LIBRARY_FORMAT, "schema": 2, "revision": 1, "saved": 0,
              "bytes": len(body), "sha256": storage.digest(body)}
    (rig.state / storage.LIBRARY).write_bytes(storage.encode(header) + b"\n" + body + b"\n")
    before = files(rig.state)
    rig.build()
    assert rig.public()["read_only"].startswith("stockage verrouillé")
    rig.refused("action", {"action": "settings", "params": {"low_g": 150}}, 503, "lecture seule")
    rig.refused("cfs-write", {"slot": "T1A"}, 503, "lecture seule")
    rig.refused("export", {}, 409, "export impossible")
    rig.refused("import", {"document": {}}, 409, "import refusé : ")
    rig.tick(21)
    rig.close()
    assert files(rig.state) == before


def test_an_incoherent_library_is_kept_for_export_until_an_import_replaces_it(make):
    broken = library(*BASE)
    broken["spools"]["B001"]["filament"] = "F999"
    rig = make(saved=broken)
    assert rig.public()["read_only"] == "bibliothèque incohérente : bobine B001 mal formée"
    rig.refused("action", {"action": "settings", "params": {"low_g": 150}}, 503, "lecture seule")
    assert rig.call("export")["library"]["spools"]["B001"]["filament"] == "F999"
    answer = rig.call("import", {"document": spools.export_document(library(*BASE), [], NOW)})
    assert answer["result"] == {"revision": 2}
    assert answer["status"]["read_only"] == ""


def test_an_import_replaces_the_library_and_never_sends_its_queued_writes(make):
    saved = spools.apply(library(*BASE), "queue_cfs", {"slot": "T1A", "spool": "B001", "material": RED[0],
                                                       "colour": RED[1]}, spools.Context(NOW, MATERIALS), True)[0]
    rig = make(saved=saved)
    exported = rig.call("export")
    assert exported["format"] == "kctrl_spools.export"
    assert sorted(exported["library"]["pending_cfs"]) == ["T1A"]
    revision = rig.public()["revision"]
    answer = rig.call("import", {"document": exported, "revision": revision})
    assert answer["result"] == {"revision": revision + 1}
    assert answer["status"]["pending_cfs"] == {}
    rig.tick(31)
    assert rig.apis.gcodes == []


def test_a_stale_or_malformed_revision_is_refused(make):
    rig = make(saved=library(*BASE))
    revision = rig.public()["revision"]
    settings = {"action": "settings", "params": {"low_g": 150}}
    rig.refused("action", dict(settings, revision=revision - 1), 409, "a changé entre-temps")
    rig.refused("import", {"document": rig.call("export"), "revision": revision + 1}, 409, "a changé entre-temps")
    rig.refused("action", dict(settings, revision=True), 400, "révision mal formée")
    rig.refused("cfs-write", {"slot": "T1A", "revision": "x"}, 400, "révision mal formée")
    assert rig.call("action", dict(settings, revision=revision))["status"]["revision"] == revision + 1
    rig.push(PRINTING)
    rig.refused("import", {"document": rig.call("export")}, 409, "import refusé pendant une impression")


# ---------------------------------------------------------------- Klipper and time
def test_klipper_going_away_and_coming_back_subscribes_once(make):
    rig = make(saved=library(*BASE))
    assert rig.public()["klippy"]["connected"] is True
    rig.apis.disconnect()
    rig.component._on_disconnect()
    assert rig.public()["klippy"]["connected"] is False
    assert rig.view("T1A")["status"] == "hors_ligne"
    rig.apis.connected = True
    rig.run(rig.component._on_ready())
    rig.run(rig.component._on_ready())
    assert len(rig.apis.callbacks) == 1
    assert rig.public()["klippy"]["connected"] is True


def test_a_klipper_found_ready_by_the_tick_settles_the_box_as_after_its_event(make):
    rig = make(build=False)
    rig.connection.ready = False
    rig.build()
    assert rig.apis.callbacks == []
    rig.connection.ready = True
    rig.tick(2)
    assert len(rig.apis.callbacks) == 1
    assert rig.public()["revision"] == 0
    rig.tick(4)
    assert rig.public()["revision"] == 0  # a box still for three seconds is not enough after a restart
    rig.tick(17)
    assert rig.public()["revision"] == 1


def test_the_slots_are_synced_once_the_box_holds_still(make):
    rig = make()
    revision = rig.public()["revision"]
    rig.tick(10)
    assert rig.public()["revision"] == revision  # twenty seconds after Klipper is ready
    rig.tick(11)
    assert rig.public()["revision"] == revision + 1
    rig.push({"box": {"T1": unit(1, {"A": WHITE, "B": RED})}})
    rig.tick(2)
    assert rig.public()["revision"] == revision + 1  # three seconds of a still box
    rig.tick(1)
    assert rig.public()["revision"] == revision + 2
    rig.push({"box": {"enable": 0, "T1": unit(1, {"A": RED})}})
    rig.tick(4)
    assert rig.public()["revision"] == revision + 2  # a box that is not ready is not synced


def test_a_sync_that_sees_nothing_new_writes_nothing(make):
    rig = make(saved=library(*BASE))
    rig.tick(21)
    revision, events = rig.public()["revision"], len(rig.server.events)
    rig.component.sync_due = rig.now
    rig.run(rig.component._sync_slots(rig.now))
    assert rig.public()["revision"] == revision
    assert len(rig.server.events) == events


def test_the_ticker_survives_a_failing_tick(make, monkeypatch):
    monkeypatch.setattr(adapter, "TICK_S", 0.01)
    rig = make(build=False)
    component = rig.create()
    calls = []

    async def failing():
        calls.append(rig.now)
        if len(calls) == 1:
            raise RuntimeError("tick cassé")

    component._tick = failing
    rig.build()
    rig.run(asyncio.sleep(0.1))
    assert len(calls) >= 2


# ---------------------------------------------------------------- start and requests
def test_a_missing_material_database_is_shown_without_locking_the_library(make):
    public = make(materials=False).public()
    assert public["materials"]["error"].startswith("base matériau de la K1 illisible")
    assert public["materials"]["count"] == 0
    assert public["read_only"] == ""


def test_a_start_that_fails_leaves_the_component_read_only(make, monkeypatch):
    def broken(self):
        raise OSError("disque absent")

    monkeypatch.setattr(storage.SpoolStore, "load_library", broken)
    rig = make()
    assert rig.public()["read_only"] == "démarrage impossible : disque absent"
    assert rig.public()["klippy"]["connected"] is True


def test_the_material_list_is_sorted_by_brand_then_name(make):
    answer = make().call("materials")
    assert answer["error"] == "" and answer["materials"]
    keys = [(record["brand"].casefold(), record["name"].casefold(), record["id"])
            for record in answer["materials"]]
    assert keys == sorted(keys)


def test_malformed_requests_are_refused_with_their_reason(make):
    rig = make(status=rest_status(slots={"T1A": RED}), saved=library(*BASE))
    rig.refused("journal", {"limit": "abc"}, 400, "limite mal formée")
    rig.refused("action", {}, 400, "action attendue")
    rig.refused("action", {"action": "settings", "params": [1]}, 400, "paramètres attendus")
    rig.refused("action", {"action": "observe"}, 409, "action inconnue : observe")
    rig.refused("cfs-write", {"slot": "T1C"}, 409, "aucune bobine attendue en T1C")
    rig.refused("cfs-write", {}, 400, "emplacement attendu")
    rig.refused("cfs-write", {"slot": "T1A"}, 409, "rien à écrire en T1A")
    rig.component._on_disconnect()
    rig.refused("cfs-write", {"slot": "T1A"}, 503, "Klipper non connecté")
    assert rig.apis.gcodes == []
