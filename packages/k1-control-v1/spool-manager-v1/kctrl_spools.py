"""Spool library and CFS sync, the Moonraker side.

Document 102, lot F. The component loads the library from kctrl_spools_store,
reads the box, the extruder and the print by subscription only, feeds
kctrl_spools_counter and answers the Bobines window. Every change goes through
kctrl_spools_model.apply on a copy, saved before it is swapped in.

The CFS is written only by KCTRL_FILAMENT, at rest, the rest read again just
before: during a print a write waits and the window says so. A write counts
once the box shows the same value; otherwise the gap is recorded and nothing
is sent again. A print started in the instant between that reading and the
write still gets it: KCTRL_FILAMENT changes the slot's data only.

During a print the library is not rewritten by itself: slot changes wait for
the end, and only the counter's fixed-size checkpoint and one journal line per
engaged route are written. Serial numbers and identifiers of the CFS never get
past keep().
"""

from __future__ import annotations

import asyncio
import copy
import logging
import os
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from ..common import RequestType, WebRequest
from . import kctrl_spools_counter as counting
from . import kctrl_spools_model as spools
from . import kctrl_spools_store as storage

if TYPE_CHECKING:
    from ..confighelper import ConfigHelper

VERSION = 1
NOTIFICATION = "k1_control:spools_update"
PREFIX = "/machine/k1_control/spools/"
UNITS = ("T1", "T2", "T3", "T4")
BOX_FIELDS = ("enable", "state", "t_command")
UNIT_FIELDS = ("state", "filament", "material_type", "color_value", "vender", "remain_len")
OBJECTS = {
    "box": list(BOX_FIELDS) + list(UNITS),
    "toolhead": ["position"],
    counting.SENSOR: ["filament_detected", "enabled"],
    "print_stats": ["state", "filename"],
    "kctrl_end": ["phase", "job_epoch"],
    "kctrl_tool_change": ["last", "last_reload"],
}
# Read once just before a write to the CFS, never subscribed.
REST_QUERY = {
    "webhooks": ["state"],
    "print_stats": ["state"],
    "idle_timeout": ["state"],
    "kctrl_end": ["phase", "pending"],
    "kctrl_print_gate": ["pending"],
    "box": list(BOX_FIELDS),
}
PRINTING_NOW = "impression en cours"
TICK_S = 2
SLOT_SETTLE_S = 3  # a slot reading holds that long before it is synced
RESTART_SETTLE_S = 20  # and the box that long after Klipper is ready
MATERIALS_EVERY_S = 60
FLUSH_RETRY_S = 30
WRITE_TIMEOUT_S = 30
QUERY_TIMEOUT_S = 10
READBACK_S = 3.0
READBACK_STEP_S = 0.25
JOURNAL_SHOWN = 200
JOURNAL_EXPORTED = 10000
JOURNAL_QUEUED = 100
REPORTS_KEPT = 20
NOTES_KEPT = 10
STATE_PATH = "/usr/data/k1-control-v1/state/spools"
MATERIAL_DATABASE = "/usr/data/creality/userdata/box/material_database.json"
GCODES_PATH = "/usr/data/printer_data/gcodes"


def keep(status: Any) -> Dict[str, Dict[str, Any]]:
    """The fields read here, out of Moonraker's shared status.

    The subscription is shared with every component, and a box unit always
    comes whole, its serial number and uuid included: only UNIT_FIELDS pass.
    """
    found = {}  # type: Dict[str, Dict[str, Any]]
    if not isinstance(status, dict):
        return found
    for name, fields in OBJECTS.items():
        values = status.get(name)
        if not isinstance(values, dict):
            continue
        kept = {}  # type: Dict[str, Any]
        for field in fields:
            if field not in values:
                continue
            value = values[field]
            if name == "box" and field in UNITS:
                value = ({key: value[key] for key in UNIT_FIELDS if key in value}
                         if isinstance(value, dict) else None)
            kept[field] = copy.deepcopy(value)
        if kept:
            found[name] = kept
    return found


def _field(status: Any, name: str, key: str) -> Any:
    values = status.get(name) if isinstance(status, dict) else None
    return values.get(key) if isinstance(values, dict) else None


def rest_problem(status: Any) -> str:
    """Why the CFS may not be written now; "" when the K1 is at rest."""
    if not isinstance(status, dict):
        return "état de la K1 illisible"
    if _field(status, "webhooks", "state") != "ready":
        return "Klipper n'est pas prêt"
    state = str(_field(status, "print_stats", "state") or "")
    if state in counting.PRINTING:
        return PRINTING_NOW
    if state not in counting.TERMINAL:
        return "état d'impression inconnu (%s)" % (state or "absent")
    if _field(status, "idle_timeout", "state") == "Printing":
        return "Klipper occupé"
    phase = _field(status, "kctrl_end", "phase")
    if _field(status, "kctrl_end", "pending") or (phase is not None and phase not in counting.END_IDLE):
        return "fin d'impression en cours"
    if _field(status, "kctrl_print_gate", "pending"):
        return "un départ attend le choix des bobines"
    box = status.get("box")
    if not isinstance(box, dict):
        return "CFS illisible"
    if box.get("enable") != 1 or box.get("state") != "connect":
        return "CFS non prêt"
    if box.get("t_command"):
        return "le CFS exécute une commande"
    return ""


def _stat(path: str) -> Optional[Tuple[float, int]]:
    try:
        found = os.stat(path)
    except OSError:
        return None
    return found.st_mtime, found.st_size


class KctrlSpools(object):
    """One per Moonraker process: the library, the counter and the endpoints."""

    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.klippy_apis = self.server.lookup_component("klippy_apis")
        self.state_path = config.get("state_path", STATE_PATH)
        self.material_database = config.get("material_database", MATERIAL_DATABASE)
        self.gcodes_path = config.get("gcodes_path", GCODES_PATH)
        self.store = storage.SpoolStore(self.state_path)
        self.library = spools.empty_library()  # type: Dict[str, Any]
        self.raw_library = None  # type: Any
        self.read_only = ""
        self.store_report = {}  # type: Dict[str, Any]
        self.revision = 0
        self.materials = {}  # type: Dict[str, Dict[str, Any]]
        self.materials_error = ""
        self.materials_warned = ""
        self.materials_stat = None  # type: Optional[Tuple[float, int]]
        self.materials_checked = 0.0
        self.counter = counting.Counter()
        self.merged = {}  # type: Dict[str, Dict[str, Any]]
        self.observations = {}  # type: Dict[str, Dict[str, Any]]
        self.projection = None  # type: Optional[Tuple[Any, ...]]
        self.sync_due = None  # type: Optional[float]
        self.reports = []  # type: List[Dict[str, Any]]
        self.journal_queue = []  # type: List[Dict[str, Any]]
        self.journal_dropped = 0
        self.flush_after = 0.0
        self.unsaved = {}  # type: Dict[str, Dict[str, Any]]
        self.last_engaged = ""
        self.subscribed = False
        self.connected = False
        self.closed = False
        self.ready_at = 0.0
        self.task = None  # type: Optional[asyncio.Future]
        self.lock = asyncio.Lock()
        self.clock = time.time  # type: Callable[[], float]
        self.server.register_notification(NOTIFICATION)
        for name, kind, handler in (
                ("status", RequestType.GET, self._status),
                ("materials", RequestType.GET, self._materials),
                ("action", RequestType.POST, self._action),
                ("journal", RequestType.GET, self._journal),
                ("export", RequestType.GET, self._export),
                ("import", RequestType.POST, self._import),
                ("cfs-write", RequestType.POST, self._cfs_write)):
            self.server.register_endpoint(PREFIX + name, kind, self._guard(handler))
        self.server.register_event_handler("server:klippy_ready", self._on_ready)
        self.server.register_event_handler("server:klippy_disconnect", self._on_disconnect)
        self.server.register_event_handler("server:klippy_shutdown", self._on_shutdown)
        self.server.register_event_handler("server:gcode_response", self._on_gcode_response)

    def _guard(self, handler: Callable[[WebRequest], Any]) -> Callable[[WebRequest], Any]:
        async def guarded(web_request: WebRequest) -> Any:
            try:
                return await handler(web_request)
            except spools.ModelError as error:
                raise self.server.error(str(error), 409) from error
            except storage.StoreError as error:
                raise self.server.error("enregistrement impossible : %s" % error, 500) from error
        return guarded

    # ------------------------------------------------------------ life
    async def component_init(self) -> None:
        try:
            await self._start()
        except Exception as error:
            logging.exception("K1 Control spools: start failed")
            self.read_only = "démarrage impossible : %s" % error
        self.task = asyncio.ensure_future(self._ticker())
        if self._klippy_ready():
            self.ready_at = self.clock()
            await self._subscribe()

    async def _start(self) -> None:
        library, report = await self._run(self.store.load_library)
        self.store_report = report
        self.revision = int(report.get("revision") or 0)
        if self.store.locked:
            self.read_only = "stockage verrouillé : %s" % self.store.locked
        elif library is not None:
            if isinstance(library, dict):
                spools.normalise(library)
            errors = spools.check(library)
            if errors:
                # Kept as it is for the export; nothing is written until an
                # import replaces it.
                self.read_only = "bibliothèque incohérente : %s" % errors[0]
                self.raw_library = library
            else:
                self.library = library
        state, _ = await self._run(self.store.load_checkpoint)
        self.counter = counting.Counter(state)
        self._links()
        await self._reload_materials(self.clock(), force=True)

    async def _ticker(self) -> None:
        while not self.closed:
            await asyncio.sleep(TICK_S)
            try:
                await self._tick()
            except Exception:
                logging.exception("K1 Control spools: tick failed")

    def close(self) -> None:
        self.closed = True
        if self.task is not None:
            self.task.cancel()
        if self.read_only:
            return
        for entry in self.journal_queue:
            try:
                self.store.append_journal(entry)
            except Exception:
                logging.exception("K1 Control spools: journal not saved on close")
        self.journal_queue = []
        if self.reports or not self.counter.dirty:
            return  # a waiting report is counted again from the checkpoint kept
        try:
            self.store.save_checkpoint(self.counter.snapshot(self.clock()))
        except Exception:
            logging.exception("K1 Control spools: checkpoint not saved on close")

    # ------------------------------------------------------------ Klipper
    async def _subscribe(self) -> None:
        if self.subscribed or self.closed:
            return
        self.subscribed = True
        try:
            # Copies: Moonraker keeps the lists it is given.
            status = await self.klippy_apis.subscribe_objects(
                {name: list(fields) for name, fields in OBJECTS.items()}, self._on_status, None)
        except Exception:
            logging.exception("K1 Control spools: subscription failed")
            status = None
        if not self.subscribed:
            return  # Klipper went away meanwhile; the next ready subscribes again
        if not isinstance(status, dict):
            self.subscribed = False
            return
        self.connected = True
        self._on_status(status, 0.0)
        self._notify("klippy")

    async def _on_ready(self) -> None:
        self.ready_at = self.clock()
        await self._subscribe()

    def _on_disconnect(self) -> None:
        self.subscribed = self.connected = False
        self.merged, self.observations = {}, {}
        self.projection = self.sync_due = None
        try:
            self.counter.lost(self.clock(), "Klipper déconnecté")
        except Exception:
            logging.exception("K1 Control spools: counter failed")
        self._notify("klippy")

    def _on_shutdown(self) -> None:
        try:
            self.counter.lost(self.clock(), "Klipper arrêté")
        except Exception:
            logging.exception("K1 Control spools: counter failed")

    def _on_gcode_response(self, line: str) -> None:
        try:
            self.counter.gcode_response(self.clock(), str(line))
        except Exception:
            logging.exception("K1 Control spools: counter failed")

    def _klippy_ready(self) -> bool:
        try:
            connection = self.server.lookup_component("klippy_connection", None)
            if connection is None:
                connection = getattr(self.server, "klippy_connection", None)
            ready = getattr(connection, "is_ready", None)
            return bool(ready()) if callable(ready) else False
        except Exception:
            return False

    def _on_status(self, status: Dict[str, Any], eventtime: float) -> None:
        # The diff is shared by every callback: never changed here.
        found = keep(status)
        if not found:
            return
        for name, fields in found.items():
            self.merged.setdefault(name, {}).update(fields)
        now = self.clock()
        first = self.counter.values is None
        before = self.counter.state["route"]
        try:
            reports = self.counter.observe(now, self.merged)
        except Exception:
            logging.exception("K1 Control spools: counter failed")
            reports = []
        self._take_reports(reports)
        after = self.counter.state["route"]
        if after and after != before and not first:
            period = self.counter.state["period"]
            self._queue_journal({"kind": "route", "slot": after,
                                 "spool": self.counter.state["links"].get(after, ""),
                                 "from": self.last_engaged,
                                 "job": period["id"] if isinstance(period, dict) else "",
                                 "t": int(now)})
            self._notify("route")
        if after:
            self.last_engaged = after
        if "box" in found:
            self.observations = spools.observe_box(self.merged["box"])
            self._project(now)

    def _project(self, now: float) -> None:
        box = self.merged.get("box") or {}
        ready = box.get("enable") == 1 and box.get("state") == "connect"
        slots = tuple(sorted((slot, seen["connected"], seen["present"], seen["material"], seen["colour"])
                             for slot, seen in self.observations.items()))  # the chip is left out
        projection = (ready, slots)
        if projection != self.projection:
            self.projection = projection
            self.sync_due = max(now + SLOT_SETTLE_S, self.ready_at + RESTART_SETTLE_S)
            self._notify("cfs")

    async def _sync_slots(self, now: float) -> None:
        if self.sync_due is None or now < self.sync_due:
            return
        if self._printing() or self._job_open():
            return  # synced after the print: the library is not rewritten during it
        self.sync_due = None
        if self.read_only or self.projection is None or not self.projection[0]:
            return
        try:
            await self._mutate("observe", {}, True)
        except (spools.ModelError, storage.StoreError):
            logging.exception("K1 Control spools: slot sync failed")
            self.sync_due = now + FLUSH_RETRY_S

    # ------------------------------------------------------------ time
    async def _tick(self) -> None:
        now = self.clock()
        if not self.subscribed and not self.closed and self._klippy_ready():
            self.ready_at = now  # Klipper seen ready without its event: the box settles as after one
            await self._subscribe()
        try:
            self._take_reports(self.counter.tick(now))
        except Exception:
            logging.exception("K1 Control spools: counter tick failed")
        async with self.lock:
            for step in (self._flush_journal, self._flush_reports, self._sync_slots,
                         self._flush_writes, self._save_checkpoint):
                try:
                    await step(now)
                except Exception:
                    logging.exception("K1 Control spools: %s failed", step.__name__)
        await self._reload_materials(now)

    def _take_reports(self, reports: List[Dict[str, Any]]) -> None:
        lost = 0
        for report in reports:
            if len(self.reports) < REPORTS_KEPT:
                self.reports.append(report)
            else:
                lost += 1
                logging.error("K1 Control spools: print report lost: %s", report.get("job"))
        if lost:
            self._queue_journal({"kind": "erreur", "detail": "%d rapport(s) d'impression perdus" % lost,
                                 "t": int(self.clock())})

    def _queue_journal(self, entry: Dict[str, Any]) -> None:
        if self.read_only:
            return
        self.journal_queue.append(entry)
        if len(self.journal_queue) > JOURNAL_QUEUED:
            del self.journal_queue[0]
            self.journal_dropped += 1

    async def _flush_journal(self, now: float) -> None:
        entries, self.journal_queue = self.journal_queue, []
        if self.read_only:
            self.journal_dropped = 0
            return
        if self.journal_dropped:
            entries.append({"kind": "erreur", "detail": "%d ligne(s) de journal perdues"
                            % self.journal_dropped, "t": int(now)})
            self.journal_dropped = 0
        await self._append(entries)

    async def _append(self, entries: List[Dict[str, Any]]) -> None:
        if entries:
            await self._run(self._append_now, entries)

    def _append_now(self, entries: List[Dict[str, Any]]) -> None:
        for entry in entries:
            try:
                self.store.append_journal(entry)
            except storage.StoreError:
                logging.exception("K1 Control spools: journal line not saved")

    # ------------------------------------------------------------ library
    async def _mutate(self, name: str, params: Dict[str, Any], internal: bool) -> Dict[str, Any]:
        """One action, saved; the caller holds the lock."""
        await self._save_unsaved()  # results of earlier writes go first
        return await self._apply(name, params, internal)

    async def _save_unsaved(self) -> None:
        for slot in sorted(self.unsaved):
            try:
                await self._apply("write_result", self.unsaved[slot], True)
            except spools.ModelError:
                logging.exception("K1 Control spools: write result refused, dropped")
            del self.unsaved[slot]

    async def _apply(self, name: str, params: Dict[str, Any], internal: bool) -> Dict[str, Any]:
        if self.read_only:
            raise storage.StoreError("bibliothèque en lecture seule : %s" % self.read_only)
        now = int(self.clock())
        work, events, result = spools.apply(self.library, name, params,
                                            spools.Context(now, self.materials, self.observations), internal)
        changed = work != self.library
        if changed:
            self.revision = await self._run(self.store.save_library, work)
            self.library = work
        await self._append(events)
        if changed:
            self._links()
        if changed or events:
            self._notify(name)
        return result

    async def _record_write(self, params: Dict[str, Any]) -> bool:
        """The result of a write, kept in memory while it cannot be saved."""
        try:
            await self._save_unsaved()
            await self._apply("write_result", params, True)
        except storage.StoreError:
            logging.exception("K1 Control spools: write result not saved")
            self.unsaved[params["slot"]] = params
            self.flush_after = self.clock() + FLUSH_RETRY_S
            return False
        return True

    async def _flush_reports(self, now: float) -> None:
        if not self.reports or self.read_only or now < self.flush_after:
            return
        while self.reports:
            report = self.reports[0]
            if report["job"].startswith("J") and report.get("file") and not report.get("planned"):
                planned, note = await self._run(self._planned, report["file"])
                report["planned"] = planned
                if not planned and note not in report["notes"] and len(report["notes"]) < NOTES_KEPT:
                    report["notes"].append(note)
            try:
                await self._mutate("print_end", report, True)
            except storage.StoreError:
                logging.exception("K1 Control spools: print report not saved, retried")
                self.flush_after = now + FLUSH_RETRY_S
                return
            except Exception as error:
                logging.exception("K1 Control spools: print report refused")
                self._queue_journal({"kind": "erreur", "job": report.get("job", ""),
                                     "detail": "rapport d'impression refusé : %s" % error, "t": int(now)})
            self.reports.pop(0)
        try:
            await self._run(self.store.save_checkpoint, self.counter.snapshot(now))
        except storage.StoreError:
            logging.exception("K1 Control spools: checkpoint not saved")
            self.counter.dirty = True

    def _planned(self, name: str) -> Tuple[List[Dict[str, float]], str]:
        root = os.path.realpath(self.gcodes_path)
        path = os.path.realpath(os.path.join(root, name))
        if not path.startswith(root + os.sep):
            return [], "fichier hors du dossier des impressions"
        return spools.read_planned(path)

    async def _flush_writes(self, now: float) -> None:
        """The writes queued during a print, once the K1 rests; never resent."""
        if self.read_only or now < self.flush_after:
            return
        if self.unsaved:
            try:
                await self._save_unsaved()
            except storage.StoreError:
                logging.exception("K1 Control spools: write result not saved")
                self.flush_after = now + FLUSH_RETRY_S
                return
        if (not self.connected or self._printing() or self._job_open() or self.reports
                or not self.library["pending_cfs"]):
            return
        for slot in sorted(self.library["pending_cfs"]):
            try:
                problem = rest_problem(await self._query_rest())
            except Exception:
                logging.exception("K1 Control spools: rest query failed")
                problem = "état de la K1 illisible"
            if problem:
                self.flush_after = now + FLUSH_RETRY_S
                return
            queued = self.library["pending_cfs"].get(slot)
            if queued is None:
                continue
            params = {"slot": slot, "spool": queued["spool"], "material": queued.get("material"),
                      "colour": queued.get("colour"), "result": "annulee", "detail": "", "read": None}
            plan, gcode = None, ""
            try:
                plan = spools.write_plan(self.library, slot, self.observations)
                if plan["spool"] != queued["spool"]:
                    raise spools.ModelError("%s n'est plus attendue en %s"
                                            % (spools.label(queued["spool"]), slot))
                if plan["material"] is None and plan["colour"] is None:
                    seen = self.observations.get(slot) or {}
                    params.update(result="ok", detail="le CFS montre déjà cette bobine",
                                  read={"material": seen.get("material"), "colour": seen.get("colour")})
                    plan = None
                else:
                    gcode = spools.gcode_of_plan(plan)
            except spools.ModelError as error:
                params["detail"] = str(error)
                plan = None
            try:
                if plan is None:
                    if not await self._record_write(params):
                        return
                    continue
                outcome = await self._write(plan, gcode)
            except spools.ModelError:
                logging.exception("K1 Control spools: write result refused")
                self.flush_after = now + FLUSH_RETRY_S
                return
            if slot in self.unsaved or outcome["result"] == "erreur":
                self.flush_after = now + FLUSH_RETRY_S
                return

    async def _save_checkpoint(self, now: float) -> None:
        # While a report waits the checkpoint keeps the closing period: a
        # restart counts it again, and print_end applies a job once.
        if self.read_only or self.reports or not self.counter.due(now):
            return
        try:
            await self._run(self.store.save_checkpoint, self.counter.snapshot(now))
        except storage.StoreError:
            logging.exception("K1 Control spools: checkpoint not saved")
            self.counter.dirty = True

    async def _reload_materials(self, now: float, force: bool = False) -> None:
        if not force and 0 <= now - self.materials_checked < MATERIALS_EVERY_S:
            return
        self.materials_checked = now
        stat = await self._run(_stat, self.material_database)
        if not force and stat is not None and stat == self.materials_stat:
            return
        materials, error = await self._run(spools.read_materials, self.material_database)
        if error:
            if error != self.materials_warned:
                logging.warning("K1 Control spools: material database: %s", error)
                self.materials_warned = error
            self.materials_stat = None
            if not self.materials:
                self.materials_error = error
            return  # the last good records stay in use
        self.materials = materials
        self.materials_error = self.materials_warned = ""
        self.materials_stat = stat
        self._notify("materials")

    # ------------------------------------------------------------ endpoints
    async def _status(self, web_request: WebRequest) -> Dict[str, Any]:
        return self._public()

    async def _materials(self, web_request: WebRequest) -> Dict[str, Any]:
        records = sorted(self.materials.values(), key=lambda record: (
            record["brand"].casefold(), record["name"].casefold(), record["id"]))
        return {"materials": copy.deepcopy(records), "error": self.materials_error}

    async def _action(self, web_request: WebRequest) -> Dict[str, Any]:
        args = dict(web_request.get_args())
        name = args.get("action")
        if not isinstance(name, str) or not name:
            raise self.server.error("action attendue", 400)
        params = args.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise self.server.error("paramètres attendus", 400)
        async with self.lock:
            self._check_writable()
            self._check_revision(args)
            result = await self._mutate(name, params, False)
        return {"result": result, "status": self._public()}

    def _check_writable(self) -> None:
        if self.read_only:
            raise self.server.error("bibliothèque en lecture seule : %s" % self.read_only, 503)

    def _check_revision(self, args: Dict[str, Any]) -> None:
        expected = args.get("revision")
        if expected is None:
            return
        if isinstance(expected, bool):
            raise self.server.error("révision mal formée", 400)
        try:
            expected = int(expected)
        except (TypeError, ValueError):
            raise self.server.error("révision mal formée", 400)
        if expected != self.revision:
            raise self.server.error("la bibliothèque a changé entre-temps : la fenêtre se met à jour, "
                                    "refais l'action", 409)

    async def _journal(self, web_request: WebRequest) -> Dict[str, Any]:
        try:
            limit = int(web_request.get_args().get("limit", JOURNAL_SHOWN))
        except (TypeError, ValueError):
            raise self.server.error("limite mal formée", 400)
        limit = max(1, min(JOURNAL_SHOWN, limit))
        return {"entries": await self._run(self.store.read_journal, limit)}

    async def _export(self, web_request: WebRequest) -> Dict[str, Any]:
        if self.store.locked:
            raise self.server.error("export impossible : %s" % self.store.locked, 409)
        journal = await self._run(self.store.read_journal, JOURNAL_EXPORTED)
        library = self.raw_library if self.raw_library is not None else self.library
        return spools.export_document(library, journal, int(self.clock()))

    async def _import(self, web_request: WebRequest) -> Dict[str, Any]:
        args = web_request.get_args()
        async with self.lock:
            if self._printing() or self._job_open():
                raise self.server.error("import refusé pendant une impression", 409)
            if self.store.locked:
                raise self.server.error("import refusé : %s" % self.store.locked, 409)
            self._check_revision(args)
            library = spools.import_document(args.get("document"))
            if not self.read_only:
                await self._save_unsaved()
            self.revision = await self._run(self.store.save_library, library)
            self.library = library
            self.read_only = ""
            self.raw_library = None
            self.unsaved = {}
            await self._append([{"kind": "import", "t": int(self.clock())}])
            self._links()
            self.sync_due = self.clock()
            self._notify("import")
        return {"result": {"revision": self.revision}, "status": self._public()}

    async def _cfs_write(self, web_request: WebRequest) -> Dict[str, Any]:
        args = web_request.get_args()
        slot = args.get("slot")
        if not isinstance(slot, str):
            raise self.server.error("emplacement attendu", 400)
        async with self.lock:
            self._check_writable()
            self._check_revision(args)
            if not self.connected:
                raise self.server.error("Klipper non connecté : écriture au CFS impossible", 503)
            await self._save_unsaved()
            plan = spools.write_plan(self.library, slot, self.observations)
            gcode = spools.gcode_of_plan(plan)
            if self._printing() or self._job_open():
                result = await self._queue(plan)
            else:
                try:
                    problem = rest_problem(await self._query_rest())
                except Exception as error:
                    raise self.server.error("état de la K1 illisible : écriture refusée", 503) from error
                if problem == PRINTING_NOW:
                    result = await self._queue(plan)
                elif problem:
                    raise self.server.error("écriture refusée : %s" % problem, 409)
                else:
                    result = await self._write(plan, gcode)
        return {"result": result, "status": self._public()}

    async def _queue(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        await self._mutate("queue_cfs", {"slot": plan["slot"], "spool": plan["spool"],
                                         "material": plan["material"], "colour": plan["colour"]}, True)
        return {"slot": plan["slot"], "queued": True, "written": False, "result": "en_attente",
                "detail": "sera envoyé au CFS à la fin de l'impression"}

    # ------------------------------------------------------------ CFS
    async def _write(self, plan: Dict[str, Any], gcode: str) -> Dict[str, Any]:
        """One KCTRL_FILAMENT, its read-back and its recorded result; no retry."""
        detail = ""
        try:
            await asyncio.wait_for(self.klippy_apis.run_gcode(gcode), WRITE_TIMEOUT_S)
        except asyncio.TimeoutError:
            detail = "pas de réponse de Klipper en %g s" % WRITE_TIMEOUT_S
        except Exception as error:
            detail = "refusé par Klipper : %s" % error
        seen = await self._readback(plan)
        if spools.readback_ok(plan, seen):
            result, detail = "ok", ""
        elif detail:
            result = "erreur"
        else:
            result, detail = "ecart", "le CFS montre autre chose après l'écriture"
        read = {"material": seen["material"], "colour": seen["colour"]} if seen else None
        await self._record_write({"slot": plan["slot"], "spool": plan["spool"], "material": plan["material"],
                                  "colour": plan["colour"], "result": result, "detail": detail, "read": read})
        return {"slot": plan["slot"], "queued": False, "written": result == "ok",
                "result": result, "detail": detail}

    async def _readback(self, plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        slot = plan["slot"]
        for _ in range(int(READBACK_S / READBACK_STEP_S)):
            if spools.readback_ok(plan, self.observations.get(slot)):
                return self.observations.get(slot)
            await asyncio.sleep(READBACK_STEP_S)
        try:
            result = await asyncio.wait_for(
                self.klippy_apis.query_objects({"box": list(OBJECTS["box"])}), QUERY_TIMEOUT_S)
            box = keep({"box": result.get("box")}).get("box") or {}
            return spools.observe_box(box).get(slot)
        except Exception:
            logging.exception("K1 Control spools: box read-back failed")
            return self.observations.get(slot)

    # ------------------------------------------------------------ helpers
    def _public(self) -> Dict[str, Any]:
        library = self.library
        try:
            views = spools.slot_views(library, self.observations, self.materials)
            attention = spools.attention(library, views)
            listed = [spools.spool_view(library, spool) for _, spool in sorted(library["spools"].items())]
            slots_error = ""
        except Exception as error:
            logging.exception("K1 Control spools: views failed")
            views, attention, listed = [], [], []
            slots_error = "emplacements illisibles : %s" % error
        return {
            "version": VERSION, "revision": self.revision, "read_only": self.read_only,
            "store": copy.deepcopy(self.store_report),
            "materials": {"count": len(self.materials), "error": self.materials_error},
            "klippy": {"connected": self.connected,
                       "cfs_ready": bool(self.projection and self.projection[0]),
                       "printing": self._printing() or self._job_open()},
            "counter": {"restored": self.counter.restored, "refused": self.counter.refused,
                        "live": self.counter.live()},
            "slots": views, "slots_error": slots_error, "attention": attention, "spools": listed,
            "empty_spools": copy.deepcopy(library["empty_spools"]),
            "filaments": copy.deepcopy(library["filaments"]),
            "unassigned": copy.deepcopy(library["unassigned"]),
            "prints": copy.deepcopy(library["prints"]),
            "settings": copy.deepcopy(library["settings"]),
            "pending_cfs": copy.deepcopy(library["pending_cfs"]),
            "counting_verified": spools.counting_verified(library),
            "unsaved_writes": sorted(self.unsaved),
            "reports_waiting": len(self.reports),
        }

    def _notify(self, reason: str) -> None:
        try:
            self.server.send_event(NOTIFICATION, {"revision": self.revision, "reason": reason})
        except Exception:
            logging.exception("K1 Control spools: notification failed")

    def _links(self) -> None:
        links = {spool["slot"]: ident for ident, spool in self.library["spools"].items()
                 if spool.get("state") == "cfs" and spool.get("slot")}
        try:
            self.counter.set_links(links, self.library["settings"].get("cut_loss_mm", 0.0))
        except Exception:
            logging.exception("K1 Control spools: counter links failed")

    def _printing(self) -> bool:
        return str(_field(self.merged, "print_stats", "state") or "") in counting.PRINTING

    def _job_open(self) -> bool:
        period = self.counter.state.get("period")
        return isinstance(period, dict) and period.get("kind") == "job"

    async def _query_rest(self) -> Dict[str, Any]:
        return await asyncio.wait_for(self.klippy_apis.query_objects(
            {name: list(fields) for name, fields in REST_QUERY.items()}), QUERY_TIMEOUT_S)

    async def _run(self, fn: Callable[..., Any], *args: Any) -> Any:
        return await self.server.get_event_loop().run_in_thread(fn, *args)


def load_component(config: ConfigHelper) -> KctrlSpools:
    return KctrlSpools(config)
