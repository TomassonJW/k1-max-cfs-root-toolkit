"""What each spool gives, counted from the extruder while it runs.

Document 102, lot G. The Moonraker component hands this counter the status it
subscribes to: the box (which slot the CFS says is engaged), the extruder's
commanded position, the head sensor, print_stats, kctrl_end and
kctrl_tool_change. The counter turns the movement of E into millimetres per
slot and spool, and at the end of a job, or of a stretch at rest, returns the
parameters of the model's print_end action.

E is toolhead.position[3]: what the extruder was told to push, the extrusion
factor included, purges and the purge tower too. G92 does not move it; a
Klipper restart sets it back to zero. Retractions cancel out within a
segment. The CFS motor alone pushes nothing E can see.

The route is the box module's memory, not a sensor (document 96): it can lag a
load, and once stayed engaged with an empty head. So nothing is guessed. E
that moves while no route is proved waits for the next engaged slot, and goes
to it only when kctrl_tool_change announced or confirmed that slot. Otherwise
it goes to the list Thomas attributes with one click, the slot as a hint. E
that moves while the head sensor reads empty before and after is air.

A change cuts the old filament above the extruder. The piece between the
blade and the gears has left its spool, but E counts it only when the new
filament pushes it through. Its length is a setting, zero until qualification
measures it: the first millimetres a new route pushes, up to that length, go
to the spool the piece came from.

Pure: no socket, no file, no clock. Time comes in as an argument. The state is
a small JSON dictionary the component writes to the store's fixed-size
checkpoint, and a restart of K1 Control in the middle of a print resumes from
it.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

VERSION = 1
SENSOR = "filament_switch_sensor filament_sensor_2"
SLOT = re.compile(r"T[1-4][A-D]")
SPOOL = re.compile(r"B[0-9]{3,}")
KEY = re.compile(r"T[1-4][A-D]\|(?:B[0-9]{3,})?")  # "slot|spool", the spool unknown or not
# kctrl_tool_change, before each planned change of a print:
# "K1 Control: T2 -> filament 3 (T1C) sur T2B, PLA FF0000, fiche ...".
ANNOUNCE = re.compile(r"K1 Control: \S+ -> filament \d+ \(\S*\) sur (T[1-4][A-D])\b")
LETTERS = ("A", "B", "C", "D")
PRINTING = ("printing", "paused")
TERMINAL = ("complete", "cancelled", "error", "standby")
OUTCOMES = ("complete", "cancelled", "error", "interrupted")
# kctrl_end's phases that end a job; any other one, known or new, is waited for.
END_IDLE = ("disabled", "idle", "complete", "failed", "shutdown")
SETTLE_S = 5  # terminal and kctrl_end idle that long: the job is over
END_WAIT_S = 900  # a job closes anyway this long after its terminal state
EXPECT_S = 900  # an announced slot stays expected that long
CONFIRM_S = 300  # a confirmation releases held millimetres that long after
REST_FOLD_S = 300  # a stretch at rest ends that long after its last movement
# A restart later than this after the checkpoint cannot vouch for the route:
# two changes, there and back, take more than twice as long (document 79).
RESUME_S = 300
SAVE_EVERY_S = 60
URGENT_EVERY_S = 2  # even a flapping route writes the checkpoint no faster
GAP_MIN_MM = 1.5
REST_MIN_MM = 1.0
LOST_MM = -1000.0  # a single drop of E larger than this is a lost origin
JUMP_MM = 20000.0  # and so is a single rise larger than this
RESUME_SLACK_MM = 50.0
FILE_LIMIT = 200
FILE_CUT = 40  # what a checkpoint short of room keeps of the file name
TODO_KEPT = 12
NOTES_KEPT = 10
NOTE_LIMIT = 120
STATE_LIMIT = 3600  # bytes of canonical JSON; the checkpoint holds 4096

UNANNOUNCED = "changement non annoncé (relève automatique ?), bobine à confirmer"
AT_REST = "chargement hors impression, bobine à confirmer"
INTERRUPTED = "décompte interrompu, emplacement à confirmer"
GROUPED = "plusieurs consommations regroupées"
GAP_REASONS = {"none": "filament sans emplacement prouvé", "unknown": "CFS illisible"}
MIDWAY = "décompte commencé en cours d'impression"
LOST_ORIGIN = "repère de l'extrudeur perdu : décompte à vérifier"


def _round(value: float, digits: int = 1) -> float:
    """Half away from zero, never -0.0: kctrl_spools_model.round_half_away."""
    scale = 10 ** digits
    result = math.floor(abs(value) * scale + 0.5) / scale
    if result == 0:
        return 0.0
    return -result if value < 0 else result


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _age(now: float, then: float) -> float:
    """Seconds since `then`; a clock that went back makes everything old."""
    return now - then if now >= then else math.inf


def _signature(value: Any) -> str:
    """A short fingerprint of one of kctrl_tool_change's results, "" when absent."""
    if not isinstance(value, dict):
        return ""
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _same_file(kept: str, file: str) -> bool:
    """Whether a job's file name, maybe cut by fit(), is this one."""
    file = file[:FILE_LIMIT]
    return file == kept or (len(kept) == FILE_CUT and file.startswith(kept))


def encode(state: Dict[str, Any]) -> bytes:
    """The checkpoint body, canonical JSON as kctrl_spools_store writes it."""
    return json.dumps(state, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


# ---------------------------------------------------------------- status
def route_of(box: Any) -> Tuple[str, str]:
    """(route, problem): the slot the box module says is engaged.

    The reading of kctrl_end.live_route without its requirement of two units:
    a disconnected unit says nothing unless it still names a slot. The route
    is "" when no slot is engaged; a problem means it is not known.
    """
    if not isinstance(box, dict):
        return "", "CFS absent"
    if box.get("enable") != 1 or box.get("state") != "connect":
        return "", "CFS non prêt"
    routes = []
    for number in range(1, 5):
        unit = box.get("T%d" % number)
        if not isinstance(unit, dict):
            continue
        slot = unit.get("filament")
        if unit.get("state") != "connect":
            if slot in (None, "None"):
                continue
            return "", "route d'un CFS déconnecté"
        if slot == "None":
            continue
        if slot not in LETTERS:
            return "", "route CFS illisible"
        routes.append("T%d%s" % (number, slot))
    if len(routes) > 1:
        return "", "plusieurs routes CFS"
    return (routes[0] if routes else ""), ""


def read_status(status: Dict[str, Any]) -> Dict[str, Any]:
    """The few values the counter uses, from Moonraker's merged status."""
    route, problem = route_of(status.get("box"))
    toolhead = status.get("toolhead")
    position = toolhead.get("position") if isinstance(toolhead, dict) else None
    e = _number(position[3]) if isinstance(position, (list, tuple)) and len(position) > 3 else None
    sensor = status.get(SENSOR)
    detected = sensor.get("filament_detected") if isinstance(sensor, dict) else None
    stats = status.get("print_stats")
    stats = stats if isinstance(stats, dict) else {}
    end = status.get("kctrl_end")
    phase = end.get("phase") if isinstance(end, dict) else None
    epoch = end.get("job_epoch") if isinstance(end, dict) else None
    change = status.get("kctrl_tool_change")
    change = change if isinstance(change, dict) else {}
    return {
        "route": route, "problem": problem, "e": e,
        "sensor": detected if isinstance(detected, bool) else None,
        "state": str(stats.get("state") or ""), "file": str(stats.get("filename") or ""),
        "phase": str(phase) if phase is not None else None,
        "epoch": epoch if isinstance(epoch, int) and not isinstance(epoch, bool) else None,
        "last": change.get("last"), "reload": change.get("last_reload"),
    }


# ---------------------------------------------------------------- state
def fresh_state() -> Dict[str, Any]:
    return {
        "v": VERSION,
        "period": None,  # the job or the stretch at rest being counted
        "e": None,  # the last position of E, None until the next reading
        "route": "",  # the last known route
        "route_known": False,  # whether the latest reading proved it
        "key": "",  # "slot|spool" of the route, "" while none is engaged
        "sensor": None,
        "nets": {},  # key -> millimetres, retractions included
        "highs": {},  # key -> highest net reached, for the live display
        "gap": None,  # millimetres pushed while no route was proved
        "held": None,  # a gap that waits for its slot to be confirmed
        "expect": None,  # a slot announced or confirmed by kctrl_tool_change
        "orphan": "",  # key of the last route left: its cut piece is in the head
        "debt": None,  # what the route after it owes that piece's spool
        "todo": [],  # millimetres for Thomas to attribute
        "links": {},  # slot -> spool, from the library
        "cut_loss": 0.0,
        "seen_last": None,  # fingerprints of kctrl_tool_change's results
        "seen_reload": None,
        "last_move": None,
        "saved": None,
    }


def _optional(check: Callable[[Any], bool]) -> Callable[[Any], bool]:
    return lambda value: value is None or check(value)


def _matching(pattern: Any, empty: bool = False) -> Callable[[Any], bool]:
    return lambda value: isinstance(value, str) and (
        (empty and value == "") or pattern.fullmatch(value) is not None)


def _among(choices: Tuple[str, ...]) -> Callable[[Any], bool]:
    return lambda value: isinstance(value, str) and value in choices


def _fields(checks: Dict[str, Callable[[Any], bool]]) -> Callable[[Any], bool]:
    """A dictionary with exactly these fields, each passing its check."""
    return lambda value: (isinstance(value, dict) and set(value) == set(checks)
                          and all(check(value[name]) for name, check in checks.items()))


def _listing(check: Callable[[Any], bool], most: int) -> Callable[[Any], bool]:
    return lambda value: isinstance(value, list) and len(value) <= most and all(map(check, value))


def _table(key: Callable[[Any], bool], value: Callable[[Any], bool]) -> Callable[[Any], bool]:
    return lambda table: isinstance(table, dict) and all(
        key(name) and value(item) for name, item in table.items())


def _text(value: Any) -> bool:
    return isinstance(value, str)


def _flag(value: Any) -> bool:
    return isinstance(value, bool)


def _whole(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _amount(value: Any) -> bool:
    return _number(value) is not None


SHAPE = {
    "v": lambda value: _whole(value) and value == VERSION,
    "period": _optional(_fields({
        "kind": _among(("job", "rest")), "id": _text, "file": _text, "start": _amount,
        "epoch": _optional(_whole), "adopted": _flag, "notes": _listing(_text, NOTES_KEPT),
        "ended": _optional(_amount), "calm": _optional(_amount),
        "outcome": _optional(_among(OUTCOMES))})),
    "e": _optional(_amount),
    "route": _matching(SLOT, True),
    "route_known": _flag,
    "key": _matching(KEY, True),
    "sensor": _optional(_flag),
    "nets": _table(_matching(KEY), _amount),
    "highs": _table(_matching(KEY), _amount),
    "gap": _optional(_fields({"mm": _amount, "kind": _among(("none", "unknown")),
                              "before": _matching(SLOT, True)})),
    "held": _optional(_fields({"slot": _matching(SLOT), "key": _matching(KEY), "mm": _amount,
                               "t": _amount})),
    "expect": _optional(_fields({"slot": _matching(SLOT), "t": _amount})),
    "orphan": _matching(KEY, True),
    "debt": _optional(_fields({"from": _matching(KEY), "to": _matching(KEY), "mm": _amount})),
    "todo": _listing(_fields({"slot": _matching(SLOT, True), "mm": _amount, "reason": _text}),
                     TODO_KEPT),
    "links": _table(_matching(SLOT), _matching(SPOOL)),
    "cut_loss": lambda value: _amount(value) and value >= 0,
    "seen_last": _optional(_text),
    "seen_reload": _optional(_text),
    "last_move": _optional(_amount),
    "saved": _optional(_amount),
}


def usable(state: Any) -> bool:
    """Whether a checkpoint's state is one this version wrote, whole."""
    if not isinstance(state, dict) or set(state) != set(SHAPE):
        return False
    if not all(check(state[name]) for name, check in SHAPE.items()):
        return False
    route, key = state["route"], state["key"]
    return key.split("|", 1)[0] == route if route else key == ""


def _compact(state: Dict[str, Any]) -> Dict[str, Any]:
    """Millimetres to the micrometre: what a restart needs, in fewer bytes."""
    if state["e"] is not None:
        state["e"] = round(state["e"], 3)
    for name in ("nets", "highs"):
        state[name] = {key: round(mm, 3) for key, mm in state[name].items()}
    for name in ("gap", "held", "debt"):
        if state[name] is not None:
            state[name]["mm"] = round(state[name]["mm"], 3)
    return state


def fit(state: Dict[str, Any], limit: int = STATE_LIMIT) -> Dict[str, Any]:
    """The state cut down to the checkpoint's size, what counts kept last.

    The notes go first, then the end of the file name, then the live display's
    highs; the list to attribute is grouped last, its total kept.
    """
    if len(encode(state)) <= limit:
        return state
    state = copy.deepcopy(state)
    period = state["period"]
    cuts = []  # type: List[Tuple[Dict[str, Any], str, Any]]
    if period is not None:
        cuts += [(period, "notes", period["notes"][-2:]), (period, "file", period["file"][:FILE_CUT]),
                 (period, "notes", [])]
    cuts.append((state, "highs", {}))
    if state["todo"]:
        total = _round(sum(item["mm"] for item in state["todo"]), 1)
        cuts.append((state, "todo", [{"slot": "", "mm": total, "reason": GROUPED}]))
    for where, name, value in cuts:
        where[name] = value
        if len(encode(state)) <= limit:
            break
    return state


# ---------------------------------------------------------------- counter
class Counter(object):
    """One counter per Moonraker process, fed in the order things happened."""

    def __init__(self, state: Optional[Dict[str, Any]] = None) -> None:
        self.restored = usable(state)
        self.state = copy.deepcopy(state) if self.restored else fresh_state()  # type: Dict[str, Any]
        self.refused = state is not None and not self.restored
        self.values = None  # type: Optional[Dict[str, Any]]
        self.dirty = False
        self.urgent = False
        self.last_save = None  # type: Optional[float]

    # ------------------------------------------------------------ inputs
    def set_links(self, links: Dict[str, str], cut_loss_mm: float = 0.0) -> None:
        """Which spool the library puts in each slot, and the cut piece's length.

        The engaged route takes a spool linked to it from now on; a route that
        had none takes it for what it already counted too. A link that
        disappears is ignored until the route changes: a spool that runs out
        leaves the CFS before its tail reaches the nozzle.
        """
        s = self.state
        clean = {slot: spool for slot, spool in sorted(links.items())
                 if isinstance(slot, str) and SLOT.fullmatch(slot)
                 and isinstance(spool, str) and SPOOL.fullmatch(spool)}
        cut = _number(cut_loss_mm)
        cut = max(0.0, cut) if cut is not None else 0.0
        if clean == s["links"] and cut == s["cut_loss"]:
            return
        s["links"], s["cut_loss"] = clean, cut
        self.dirty = True
        if not s["route"]:
            return
        slot, spool = s["key"].split("|", 1)
        fresh = clean.get(slot, "")
        if fresh and fresh != spool:
            key = slot + "|" + fresh
            self._rename(s["key"], key, counted=not spool)
            s["key"] = key

    def announce(self, now: float, slot: str) -> None:
        """kctrl_tool_change named the slot it is about to load."""
        if SLOT.fullmatch(slot):
            self._confirm(now, slot)

    def gcode_response(self, now: float, line: str) -> None:
        found = ANNOUNCE.search(line)
        if found:
            self.announce(now, found.group(1))

    def lost(self, now: float, why: str) -> None:
        """Klipper went away: its next position of E starts a new origin.

        Before the first status of this process the checkpoint stays the
        reference: the first position of E decides whether it still holds.
        """
        s = self.state
        if self.values is None or (s["e"] is None and not s["route_known"]):
            return
        s["e"] = None
        s["route_known"] = False
        self._note("%s : décompte à vérifier" % why)
        self.dirty = self.urgent = True

    def observe(self, now: float, status: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fold one status in; returns the reports of the periods it closed."""
        values = read_status(status)
        if self.values is None and self.restored and values["e"] is None:
            return []  # Klipper is not ready yet: the checkpoint waits for E
        reports = []  # type: List[Dict[str, Any]]
        self._results(now, values)
        if self.values is None:
            reports += self._begin(now, values)
        else:
            reports += self._periods(now, values)
        self.values = values
        self._move(now, values)
        self._route(now, values)
        if values["sensor"] is not self.state["sensor"]:
            self.state["sensor"] = values["sensor"]
            self.dirty = True
        reports += self._timeouts(now)
        reports += self._closing(now, values)
        return reports

    def tick(self, now: float) -> List[Dict[str, Any]]:
        """Time passing without a status: settles, holds and stretches at rest."""
        if self.values is None:
            return []
        return self._timeouts(now) + self._closing(now, self.values)

    # ------------------------------------------------------------ outputs
    def live(self) -> Dict[str, Any]:
        """What the window shows during a period; never goes backwards."""
        s = self.state
        period = s["period"]
        spools = []
        for key in sorted(set(s["nets"]) | set(s["highs"])):
            mm = max(s["highs"].get(key, 0.0), s["nets"].get(key, 0.0))
            if mm > 0:
                slot, spool = key.split("|", 1)
                spools.append({"slot": slot, "spool": spool or s["links"].get(slot, ""),
                               "mm": _round(mm, 1)})
        waiting = sum(item["mm"] for item in s["todo"])
        for name in ("held", "gap"):
            if s[name] is not None and s[name]["mm"] > 0:
                waiting += s[name]["mm"]
        return {
            "period": None if period is None else {
                "kind": period["kind"], "id": period["id"], "file": period["file"],
                "start": period["start"], "notes": list(period["notes"])},
            "route": s["route"] if s["route_known"] else None,
            "spools": spools, "waiting_mm": _round(waiting, 1),
        }

    def due(self, now: float) -> bool:
        """Whether the checkpoint should be written now."""
        if not self.dirty:
            return False
        if self.last_save is None:
            return True
        age = _age(now, self.last_save)
        return age >= SAVE_EVERY_S or (self.urgent and age >= URGENT_EVERY_S)

    def snapshot(self, now: float) -> Dict[str, Any]:
        """The state to write, cut to the checkpoint's size; marks it saved."""
        self.state["saved"] = now
        self.dirty = self.urgent = False
        self.last_save = now
        return fit(_compact(copy.deepcopy(self.state)))

    # ------------------------------------------------------------ periods
    def _note(self, text: str) -> None:
        period = self.state["period"]
        if period is None:
            return
        text = text[:NOTE_LIMIT]
        if text not in period["notes"] and len(period["notes"]) < NOTES_KEPT:
            period["notes"].append(text)
            self.dirty = True

    def _open(self, now: float, kind: str, values: Optional[Dict[str, Any]] = None) -> None:
        self.state["period"] = {
            "kind": kind, "id": ("J%d" if kind == "job" else "R%d") % int(now),
            "file": values["file"][:FILE_LIMIT] if values else "", "start": int(now),
            "epoch": values["epoch"] if values else None, "adopted": values is None,
            "notes": [], "ended": None, "calm": None, "outcome": None,
        }
        self.dirty = self.urgent = True

    def _begin(self, now: float, values: Dict[str, Any]) -> List[Dict[str, Any]]:
        """The first status after a start of K1 Control."""
        s = self.state
        printing = values["state"] in PRINTING and bool(values["file"])
        reports = []  # type: List[Dict[str, Any]]
        if not self.restored:
            if printing:
                self._open(now, "job", values)
                self._note(MIDWAY)
            return reports
        period = s["period"]
        previous, e = s["e"], values["e"]
        if e is None or previous is None or e < previous - RESUME_SLACK_MM:
            # Klipper restarted too: what it pushed since the checkpoint is lost.
            s["e"] = None
            if period is not None:
                if period["kind"] == "job":
                    self._note("Klipper redémarré pendant l'arrêt de K1 Control : "
                               "décompte arrêté au dernier point de reprise")
                    reports += self._close(s["saved"] or now, period["outcome"] or "interrupted")
                else:
                    reports += self._close(s["saved"] or now, "rest")
            if printing:
                self._open(now, "job", values)
                self._note(MIDWAY)
            return reports
        delta, s["e"] = e - previous, e
        wet = delta > 0 and not (s["sensor"] is False and values["sensor"] is False)
        vouched = (not values["problem"] and s["route_known"] and bool(s["route"])
                   and values["route"] == s["route"] and s["saved"] is not None
                   and _age(now, s["saved"]) <= RESUME_S)
        hint = s["route"] if not values["problem"] and values["route"] in ("", s["route"]) else ""
        job = period is not None and period["kind"] == "job"
        if job:
            epoch = values["epoch"]
            same_job = printing and _same_file(period["file"], values["file"]) and (
                epoch == period["epoch"] or (not period["adopted"] and epoch is not None
                                             and period["epoch"] is not None
                                             and epoch == period["epoch"] + 1))
            if same_job:
                period["file"] = values["file"][:FILE_LIMIT]
                self._note("reprise après redémarrage de K1 Control")
            elif printing:
                self._note("fin et nouvelle impression pendant l'arrêt de K1 Control")
                if wet:
                    self._todo(delta, hint, INTERRUPTED)
                reports += self._close(s["saved"] or now, period["outcome"] or "interrupted")
                self._open(now, "job", values)
                self._note(MIDWAY)
                return reports
            elif values["state"] in TERMINAL:
                self._note("fin pendant l'arrêt de K1 Control")
        elif printing:
            # A print started while K1 Control was down: what moved is most
            # likely its start, the load and the purge.
            reports += self._close(s["saved"] or now, "rest")
            self._open(now, "job", values)
            self._note(MIDWAY)
        elif wet and period is None:
            self._open(s["saved"] or now, "rest")
        if wet:
            s["last_move"] = now
            if vouched:
                self._add(s["key"], delta)
            else:
                self._todo(delta, hint, INTERRUPTED)
        return reports

    def _periods(self, now: float, values: Dict[str, Any]) -> List[Dict[str, Any]]:
        """A job starts when print_stats starts printing a file."""
        period = self.state["period"]
        if values["state"] not in PRINTING or not values["file"]:
            return []
        reports = []  # type: List[Dict[str, Any]]
        if period is not None and period["kind"] == "job":
            if period["ended"] is None and _same_file(period["file"], values["file"]):
                epoch = values["epoch"]
                if epoch is not None and epoch != period["epoch"]:
                    # START_PRINT counts its job right after print_stats starts.
                    if period["adopted"]:
                        self._note("nouveau départ K1 Control pendant l'impression")
                    period["epoch"], period["adopted"] = epoch, True
                    self.dirty = self.urgent = True
                return reports
            if period["ended"] is None:
                self._note("autre fichier lancé sans fin observée")
            reports += self._close(now, period["outcome"] or "interrupted")
        else:
            reports += self._close(now, "rest")
        self._open(now, "job", values)
        return reports

    @staticmethod
    def _outcome(values: Dict[str, Any]) -> str:
        state = values["state"]
        return state if state in OUTCOMES else "interrupted"

    def _closing(self, now: float, values: Dict[str, Any]) -> List[Dict[str, Any]]:
        """A job ends once print_stats and kctrl_end both rest for SETTLE_S.

        Its outcome is print_stats' first terminal state: a cancel that
        settles to standby stays a cancel.
        """
        period = self.state["period"]
        if period is None or period["kind"] != "job":
            return []
        if values["state"] not in TERMINAL:
            if (period["ended"], period["calm"], period["outcome"]) != (None, None, None):
                period["ended"] = period["calm"] = period["outcome"] = None
                self.dirty = True
            return []
        if period["ended"] is None:
            period["ended"], period["outcome"] = now, self._outcome(values)
            self.dirty = True
        busy = values["phase"] is not None and values["phase"] not in END_IDLE
        calm = None if busy else (now if period["calm"] is None else period["calm"])
        if calm != period["calm"]:
            period["calm"] = calm
            self.dirty = True
        if calm is not None and _age(now, calm) >= SETTLE_S:
            return self._close(now, period["outcome"])
        if _age(now, period["ended"]) >= END_WAIT_S:
            self._note("fin de K1 Control encore en cours (%s), bilan fait sans elle"
                       % values["phase"])
            return self._close(now, period["outcome"])
        return []

    def _unannounced(self) -> str:
        period = self.state["period"]
        return AT_REST if period is not None and period["kind"] == "rest" else UNANNOUNCED

    def _timeouts(self, now: float) -> List[Dict[str, Any]]:
        s = self.state
        held = s["held"]
        if held is not None and _age(now, held["t"]) > CONFIRM_S:
            self._todo(held["mm"], held["slot"], self._unannounced())
            s["held"] = None
            self.dirty = True
        expect = s["expect"]
        if expect is not None and _age(now, expect["t"]) > EXPECT_S:
            s["expect"] = None
            self.dirty = True
        period = s["period"]
        if period is not None and period["kind"] == "rest" and _age(
                now, s["last_move"] if s["last_move"] is not None else period["start"]) >= REST_FOLD_S:
            return self._close(now, "rest")
        return []

    def _close(self, now: float, outcome: str) -> List[Dict[str, Any]]:
        s = self.state
        period = s["period"]
        if period is None:
            return []
        held = s["held"]
        if held is not None:
            self._todo(held["mm"], held["slot"], self._unannounced())
            s["held"] = None
        gap = s["gap"]
        if gap is not None:
            self._todo(gap["mm"], gap["before"] if gap["kind"] == "unknown" else "",
                       GAP_REASONS[gap["kind"]])
            s["gap"] = None
        segments = self._segments()
        report = {
            "job": period["id"], "file": period["file"], "start": period["start"],
            "end": int(now), "outcome": outcome, "segments": segments,
            "spools": dict(s["links"]), "planned": [], "notes": list(period["notes"]),
        }
        s["period"] = None
        s["nets"], s["highs"], s["todo"] = {}, {}, []
        self.dirty = self.urgent = True
        if period["kind"] == "rest" and not any(item["mm"] >= REST_MIN_MM for item in segments):
            return []
        return [report]

    def _segments(self) -> List[Dict[str, Any]]:
        s = self.state
        segments = []  # type: List[Dict[str, Any]]
        for key in sorted(s["nets"]):
            mm = _round(s["nets"][key], 1)
            if mm > 0:
                slot, spool = key.split("|", 1)
                segments.append({"slot": slot, "spool": spool, "mm": mm})
        for item in s["todo"]:
            segments.append({"slot": item["slot"], "mm": item["mm"], "reason": item["reason"]})
        return segments

    # ------------------------------------------------------------ movement
    def _move(self, now: float, values: Dict[str, Any]) -> None:
        """The movement of E since the last status, on the route before it."""
        s = self.state
        e = values["e"]
        if e is None:
            if s["e"] is not None:
                s["e"] = None
                self._note("position de l'extrudeur illisible : décompte à vérifier")
                self.dirty = True
            return
        previous, s["e"] = s["e"], e
        if previous is None or e == previous:
            return
        self.dirty = True
        delta = e - previous
        if delta < LOST_MM or delta > JUMP_MM:
            self._note(LOST_ORIGIN)
            return
        if s["sensor"] is False and values["sensor"] is False:
            return
        s["last_move"] = now
        if s["period"] is None:
            self._open(now, "rest")
        if s["route_known"] and s["route"]:
            self._add(s["key"], delta)
            return
        kind = "none" if s["route_known"] else "unknown"
        gap = s["gap"]
        if gap is None:
            s["gap"] = {"mm": delta, "kind": kind, "before": s["route"]}
        else:
            gap["mm"] += delta
            if kind == "none":
                gap["kind"] = "none"

    def _add(self, key: str, mm: float) -> None:
        """Millimetres pushed on `key`, the cut piece of the route before first."""
        s = self.state
        debt = s["debt"]
        if debt is not None and key == debt["from"] and mm > 0:
            paid = min(mm, debt["mm"])
            self._put(debt["to"], paid)
            mm -= paid
            if paid >= debt["mm"]:
                s["debt"] = None
            else:
                debt["mm"] -= paid
        if mm != 0:
            self._put(key, mm)

    def _put(self, key: str, mm: float) -> None:
        s = self.state
        s["nets"][key] = s["nets"].get(key, 0.0) + mm
        s["highs"][key] = max(s["highs"].get(key, 0.0), s["nets"][key])
        self.dirty = True

    def _rename(self, old: str, new: str, counted: bool) -> None:
        """The route's key becomes `new`; with `counted`, what it counted too.

        A debt follows the route, whatever spool pushes the piece out.
        """
        s = self.state
        if counted:
            for name in ("nets", "highs"):
                if old in s[name]:
                    s[name][new] = s[name].get(new, 0.0) + s[name].pop(old)
            held = s["held"]
            if held is not None and held["key"] == old:
                held["key"] = new
        debt = s["debt"]
        if debt is not None and debt["from"] == old:
            debt["from"] = new
            if new == debt["to"]:
                s["debt"] = None

    def _todo(self, mm: float, slot: str, reason: str) -> None:
        if mm < GAP_MIN_MM:
            return
        todo = self.state["todo"]
        if len(todo) >= TODO_KEPT:
            last = todo[-1]
            last.update({"mm": _round(last["mm"] + mm, 1), "slot": "", "reason": GROUPED})
        else:
            todo.append({"slot": slot, "mm": _round(mm, 1), "reason": reason})
        self.dirty = self.urgent = True

    # ------------------------------------------------------------ route
    def _route(self, now: float, values: Dict[str, Any]) -> None:
        s = self.state
        if values["problem"]:
            if s["route_known"]:
                s["route_known"] = False
                self.dirty = True
            return
        route = values["route"]
        if s["route_known"] and route == s["route"]:
            return
        before = s["route"]
        s["route_known"] = True
        self.dirty = True
        gap = s["gap"]
        if route == before:
            # The CFS came back on the route it had: what moved meanwhile is its
            # own. No change runs while the CFS cannot be read.
            if route and gap is not None and gap["kind"] == "unknown" and gap["before"] == route:
                s["gap"] = None
                self._add(s["key"], gap["mm"])
            return
        self.urgent = True
        held = s["held"]
        if held is not None:
            self._todo(held["mm"], held["slot"], self._unannounced())
            s["held"] = None
        if before:
            s["orphan"] = s["key"]
        s["route"], s["key"] = route, ""
        if route:
            self._engage(now, route)

    def _engage(self, now: float, route: str) -> None:
        s = self.state
        links = s["links"]
        key = route + "|" + links.get(route, "")
        s["key"] = key
        orphan, s["orphan"] = s["orphan"], ""
        if s["debt"] is not None and s["debt"]["from"] != key:
            # A retry reloads the same route and keeps what it still owes; a
            # chain of pieces from several changes is not followed.
            s["debt"] = None
        if orphan and orphan != key and s["cut_loss"] > 0:
            # The piece belongs to the spool it was cut from, known then or now.
            slot, spool = orphan.split("|", 1)
            owner = slot + "|" + (spool or links.get(slot, ""))
            if owner != key and owner.split("|", 1)[1]:
                s["debt"] = {"from": key, "to": owner, "mm": s["cut_loss"]}
        expect = s["expect"]
        expected = (expect is not None and expect["slot"] == route
                    and _age(now, expect["t"]) <= EXPECT_S)
        if expect is not None and expect["slot"] == route:
            s["expect"] = None
        gap, s["gap"] = s["gap"], None
        if gap is None or gap["mm"] < GAP_MIN_MM:
            return  # a net pull while no route was proved went back where it came from
        if expected:
            self._add(key, gap["mm"])
        else:
            s["held"] = {"slot": route, "key": key, "mm": gap["mm"], "t": now}

    def _confirm(self, now: float, slot: str) -> None:
        s = self.state
        held = s["held"]
        if held is not None and held["slot"] == slot and _age(now, held["t"]) <= CONFIRM_S:
            self._add(held["key"], held["mm"])
            s["held"] = None
            self.urgent = True
            return
        if s["route_known"] and s["route"] == slot:
            return
        s["expect"] = {"slot": slot, "t": now}
        self.dirty = True

    def _results(self, now: float, values: Dict[str, Any]) -> None:
        """kctrl_tool_change's results, each counted once as it changes.

        An absent result is not news: the one seen before stays the reference,
        so a status without the object does not replay the last result.
        START_PRINT empties `last` for its job, so the same result in a new
        job is news even when the empty one was never seen.
        """
        s = self.state
        for name, field in (("seen_last", "last"), ("seen_reload", "reload")):
            value = values[field]
            signature = _signature(value)
            if signature and field == "last":
                signature += ":%s" % values["epoch"]
            if not signature or signature == s[name]:
                continue
            first, s[name] = s[name] is None, signature
            self.dirty = True
            if first:
                continue
            if field == "last":
                slot = value.get("slot")
                if value.get("outcome") in ("done", "start") and isinstance(slot, str) \
                        and SLOT.fullmatch(slot):
                    self._confirm(now, slot)
            else:
                tool = value.get("tool")
                if value.get("error") is False and value.get("head") is not False \
                        and isinstance(tool, str) and SLOT.fullmatch(tool):
                    self._confirm(now, tool)
