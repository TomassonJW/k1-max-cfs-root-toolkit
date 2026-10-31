"""Le décompte des bobines (document 102, lot G).

Ce que l'extrudeur pousse va à l'emplacement que le CFS dit engagé et à la
bobine que la bibliothèque y met ; ce qui bouge sans emplacement prouvé attend
une annonce ou une confirmation de kctrl_tool_change, sinon Thomas ; le capteur
de tête vide avant et après, c'est de l'air ; un redémarrage de K1 Control
reprend du point de reprise sans compter deux fois ni perdre ce qui est sûr ;
le point de reprise tient toujours dans sa taille fixe ; le numéro de série du
CFS n'entre jamais dans l'état.
"""

import ast
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "spool-manager-v1"
TOOL_CHANGE = ROOT / "packages" / "k1-control-v1" / "owned-start-print-v2" / "kctrl_tool_change.py"
FIXTURE = (ROOT / "packages" / "k1-control-v1" / "cfs-stock-unload-guard-adapter-offline-v1"
           / "fixtures" / "unique-route.json")


def load(name):
    spec = importlib.util.spec_from_file_location(name, str(PACKAGE / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


counter = load("kctrl_spools_counter")
model = load("kctrl_spools_model")
store = load("kctrl_spools_store")
MATERIALS, _ = model.read_materials(str(PACKAGE / "lab" / "material_database.synthetic.json"))
BOX = json.loads(FIXTURE.read_text(encoding="utf-8"))["result"]["status"]["box"]
T0 = 1_790_000_000
LINKS = {"T1A": "B001", "T1B": "B002"}
SLOTS = ["T%d%s" % (unit, letter) for unit in range(1, 5) for letter in "ABCD"]

# kctrl_tool_change's own messages, checked against its source below.
ANNOUNCED = "K1 Control: %s -> filament %d (%s) sur %s, %s %s, fiche %s (%s) %s %d C%s"
CHANGED, SAME, FIRST = "alignee %s ->", "deja a", ", premiere couche"
REFUSED = "K1 Control: changement d'outil %s refuse, %s"
VACANT = ("le filament %d (%s) veut l'emplacement %s, qui est vide; "
          "KCTRL_SLOTS pour voir les bobines")
PAUSED = ("K1 Control: le firmware a mis l'impression en pause pendant "
          "%s -> %s; voir l'ecran, puis RESUME")
EMPTY = "K1 Control: %s -> %s termine sans filament a la tete; %s"
DONE = "K1 Control: %s fait, filament a la tete, cible %d C"
TOOLS = "K1 Control: commandes T enveloppees: %s; laissees au CFS: %s"
RELOADS = "  rechargements de reprise proteges: %s"
TOOL_LINE = "  filament %d (%s) %s %s, %s"
TOOL_SLOT = " -> %s, fiche %s a %s C%s"
UNMAPPED = " -> non associe"
TOOL_LAST = "  dernier changement: %s"


def info(text):
    """What Klipper sends for respond_info: each line stripped and marked."""
    return "\n".join("// " + line.strip() for line in text.strip().split("\n"))


def announcement(slot, logical="T1C", changed=False, first_layer=False):
    """kctrl_tool_change's line before it loads filament 2 from `slot`."""
    return info(ANNOUNCED % ("T2", 2, logical, slot, "PLA", "FFFFFF", "000001", "Generic PLA",
                             CHANGED % "210/220" if changed else SAME, 220,
                             FIRST if first_layer else ""))


def box_status(route="T1A", **changes):
    """The box object as Moonraker sends it, serial numbers included."""
    box = copy.deepcopy(BOX)
    box["enable"] = 1
    for number in (1, 2):
        box["T%d" % number].update(filament="None", sn="SERIAL-T%d" % number,
                                   uuid="UUID-T%d" % number)
    if route:
        box[route[:2]]["filament"] = route[2]
    box.update(changes)
    return box


def library():
    """B001 Geeetech PLA and B002 Creality Hyper PLA, both on a thin Geeetech spool."""
    context = model.Context(T0, MATERIALS, {})
    work = model.empty_library()
    for name, params in (
            ("create_empty_spool", {
                "manufacturer": "GEEETECH", "name": "Bobine plastique fine",
                "spool_material": "plastique", "tare_g": 180, "nominal_net_g": 1000,
                "source": "spoolmandb", "catalogue": "GEEETECH|1000|180|plastique"}),
            ("create_filament", {"manufacturer": "Geeetech", "name": "PLA", "material": "PLA",
                                 "colour": "#FF1E1E"}),
            ("create_filament", {"manufacturer": "Creality", "name": "Hyper PLA",
                                 "material": "PLA", "colour": "FFFFFF"}),
            ("create_spool", {"filament": "F001", "empty_spool": "V001"}),
            ("create_spool", {"filament": "F002", "empty_spool": "V001"})):
        work = model.apply(work, name, params, context)[0]
    return work


def counted(work, spool, mm):
    """The grams print_end adds to a fresh spool for `mm` millimetres."""
    fiche = work["filaments"][work["spools"][spool]["filament"]]
    return model.round_half_away(model.grams_of_mm(mm, model.fiche_gpm(fiche)), 2)


def ended(report, now):
    return model.apply(library(), "print_end", report, model.Context(now, MATERIALS, {}),
                       internal=True)


class Rig(object):
    """The printer as the counter sees it: one status a second unless told otherwise."""

    def __init__(self, checkpoint=None, links=LINKS, cut_loss=0.0, **values):
        self.links, self.cut_loss, self.now = dict(links), cut_loss, T0
        self.counter = counter.Counter(checkpoint)
        self.counter.set_links(self.links, cut_loss)
        self.route, self.e, self.sensor = "T1A", 0.0, True
        self.state, self.file, self.phase, self.epoch = "standby", "", "idle", 0
        self.last, self.reload, self.box, self.omit, self.reports = {}, {}, None, (), []
        for name, value in values.items():
            setattr(self, name, value)

    @property
    def s(self):
        return self.counter.state

    def status(self):
        status = {
            "box": box_status(self.route) if self.box is None else self.box,
            "toolhead": {"position": [10.0, 20.0, 0.3, self.e]},
            counter.SENSOR: {"filament_detected": self.sensor, "enabled": True},
            "print_stats": {"state": self.state, "filename": self.file},
            "kctrl_end": {"phase": self.phase, "job_epoch": self.epoch},
            "kctrl_tool_change": {"last": self.last, "last_reload": self.reload},
        }
        for name in self.omit:
            del status[name]
        return status

    def observe(self, seconds=1.0, **changes):
        for name, value in changes.items():
            setattr(self, name, value)
        self.now += seconds
        reports = self.counter.observe(self.now, self.status())
        self.reports += reports
        return reports

    def push(self, mm, seconds=1.0, **changes):
        self.e += mm
        return self.observe(seconds, **changes)

    def tick(self, seconds):
        self.now += seconds
        reports = self.counter.tick(self.now)
        self.reports += reports
        return reports

    def say(self, line):
        self.counter.gcode_response(self.now, line)

    def start(self, file="cube.gcode", reset=True):
        """print_stats starts, then START_PRINT counts its job and empties `last`."""
        self.observe(state="printing", file=file)
        self.observe(epoch=self.epoch + 1, **({"last": {}} if reset else {}))

    def end(self):
        """kctrl_end's withdrawal: cut, rewind past the head sensor, route released."""
        self.observe(phase="waiting")
        self.observe(state="complete")
        self.observe(phase="heating")
        self.observe(phase="cutting")
        self.push(-20, phase="rewinding")
        self.push(-15)
        self.observe(sensor=False)
        self.observe(route="", phase="finalizing")
        self.observe(phase="complete")
        self.observe(seconds=counter.SETTLE_S)

    def finish(self, state="complete"):
        """An end that keeps the filament engaged."""
        self.observe(state=state)
        self.observe(seconds=counter.SETTLE_S)

    def report(self):
        assert len(self.reports) == 1, self.reports
        return self.reports.pop()

    def save(self):
        """The checkpoint as the store gives it back."""
        return json.loads(counter.encode(self.counter.snapshot(self.now)).decode("utf-8"))

    def restart(self, checkpoint, seconds=1.0):
        """K1 Control starts again from a checkpoint; the printer carries on."""
        self.now += seconds
        self.counter = counter.Counter(checkpoint)
        self.counter.set_links(self.links, self.cut_loss)


def announced(rig):
    """A planned change from T1A to T1B: announced, then T1A withdrawn."""
    rig.observe()
    rig.start()
    rig.push(500)
    rig.say(announcement("T1B"))
    rig.push(-10)
    rig.observe(sensor=False)
    rig.observe(route="")


def unannounced(rig):
    """T1A runs out and the CFS loads T1B on its own: nothing announced it."""
    rig.observe()
    rig.start()
    rig.push(800)
    rig.counter.set_links({"T1B": "B002"})  # the empty spool leaves its slot in the library
    rig.push(50)
    rig.observe(sensor=False)
    rig.push(30)  # the extruder runs on air
    rig.observe(route="")
    rig.observe(sensor=True)
    rig.push(5)
    rig.push(140)  # the new filament arrives before its route is engaged


def blip(rig):
    """The CFS stops answering for a while during a job."""
    rig.observe()
    rig.start()
    rig.push(100)
    rig.box = box_status("T1A", state="disconnect")
    rig.push(50)  # moved before the status that says so: still T1A's
    rig.push(30)
    rig.push(20)


def printed(rig, mm=300):
    """A job that pushed `mm` on T1A, and its checkpoint."""
    rig.observe()
    rig.start()
    rig.push(mm)
    return rig.save()


def retried(rig):
    """T2B to T1A announced with a 40 mm cut piece, of which T1A pushed 5 mm."""
    rig.observe()
    rig.start()
    rig.push(500)
    rig.say(announcement("T1A"))
    rig.observe(route="")
    rig.observe(route="T1A")
    assert rig.s["debt"] == {"from": "T1A|B001", "to": "T2B|B002", "mm": 40.0}
    rig.push(5)
    assert rig.s["debt"]["mm"] == 35.0


# ---------------------------------------------------------------- a job
def test_a_job_counts_what_the_extruder_pushed_on_the_engaged_spool():
    rig = Rig()
    rig.observe()
    rig.start()
    for mm in (400, -2, 2, 600):
        rig.push(mm)
    job = "J%d" % (T0 + 2)
    assert rig.counter.live() == {
        "period": {"kind": "job", "id": job, "file": "cube.gcode", "start": T0 + 2, "notes": []},
        "route": "T1A", "spools": [{"slot": "T1A", "spool": "B001", "mm": 1000.0}],
        "waiting_mm": 0.0}
    rig.end()
    report = rig.report()
    assert report == {
        "job": job, "file": "cube.gcode", "start": T0 + 2, "end": int(rig.now),
        "outcome": "complete", "segments": [{"slot": "T1A", "spool": "B001", "mm": 965.0}],
        "spools": LINKS, "planned": [], "notes": []}
    work, _, result = ended(report, rig.now)
    assert result == {"job": job, "applied": True}
    assert work["spools"]["B001"]["counted_g"] == counted(work, "B001", 965.0)
    assert work["spools"]["B002"]["counted_g"] == 0.0
    assert work["unassigned"] == []
    again = model.apply(work, "print_end", report, model.Context(rig.now, MATERIALS, {}),
                        internal=True)
    assert again[2] == {"job": job, "applied": False} and again[0] == work


def test_the_live_figure_never_goes_back_with_a_retraction():
    rig = Rig()
    rig.observe()
    rig.start()
    rig.push(1000)
    rig.push(-35)
    assert rig.counter.live()["spools"] == [{"slot": "T1A", "spool": "B001", "mm": 1000.0}]
    assert rig.s["nets"] == {"T1A|B001": 965.0}


def test_the_extruder_on_air_counts_nothing():
    rig = Rig()
    rig.observe()
    rig.start()
    rig.observe(sensor=False)
    rig.push(30)
    rig.push(10, sensor=True)
    rig.push(20, sensor=None)
    rig.push(5)
    rig.push(7, sensor=False)
    rig.push(9)
    assert rig.counter.live()["spools"] == [{"slot": "T1A", "spool": "B001", "mm": 42.0}]


def test_a_cancel_that_keeps_the_filament_stays_a_cancel():
    rig = Rig()
    rig.observe()
    rig.start()
    rig.push(500)
    rig.observe(state="cancelled", phase="finalizing")
    rig.observe(state="standby", phase="complete")
    rig.observe(seconds=counter.SETTLE_S)
    report = rig.report()
    assert report["outcome"] == "cancelled"
    assert report["segments"] == [{"slot": "T1A", "spool": "B001", "mm": 500.0}]


def test_a_job_whose_end_never_settles_closes_after_end_wait():
    rig = Rig()
    rig.observe()
    rig.start()
    rig.push(1000)
    rig.observe(phase="waiting")
    rig.observe(state="complete")
    rig.observe(phase="finalizing")
    counts = [len(rig.push(80, seconds=40)) for _ in range(25)]
    assert counts == [0] * 22 + [1, 0, 0]
    report = rig.report()
    assert report["outcome"] == "complete"
    assert report["segments"] == [{"slot": "T1A", "spool": "B001", "mm": 2840.0}]
    assert report["notes"] == ["fin de K1 Control encore en cours (finalizing), bilan fait sans elle"]
    assert rig.s["period"]["kind"] == "rest"
    [rest] = rig.tick(counter.REST_FOLD_S)
    assert rest["job"].startswith("R") and rest["outcome"] == "rest"
    assert rest["segments"] == [{"slot": "T1A", "spool": "B001", "mm": 160.0}]


def test_a_second_start_print_in_the_same_job_is_noted():
    rig = Rig()
    rig.observe()
    rig.start()
    rig.observe(epoch=2)
    assert rig.counter.live()["period"]["notes"] == ["nouveau départ K1 Control pendant l'impression"]


def test_another_file_without_an_end_closes_the_job_before():
    rig = Rig()
    rig.observe()
    rig.start()
    rig.push(100)
    [report] = rig.observe(file="other.gcode")
    assert report["outcome"] == "interrupted"
    assert report["segments"] == [{"slot": "T1A", "spool": "B001", "mm": 100.0}]
    assert report["notes"] == ["autre fichier lancé sans fin observée"]
    assert rig.counter.live()["period"]["file"] == "other.gcode"


def test_a_new_print_before_the_end_settles_keeps_the_outcome_seen():
    rig = Rig()
    rig.observe()
    rig.start()
    rig.push(100)
    rig.observe(state="complete")
    [report] = rig.observe(state="printing")
    assert report["outcome"] == "complete" and report["notes"] == []


# ---------------------------------------------------------------- changes
@pytest.mark.parametrize("route_first", [True, False])
def test_an_announced_change_goes_to_the_new_spool_after_the_cut_piece(route_first):
    rig = Rig(cut_loss=40.0)
    announced(rig)
    if route_first:
        rig.observe(route="T1B")
    rig.observe(sensor=True)
    rig.push(5)
    rig.push(140)
    if not route_first:
        rig.observe(route="T1B")
    assert rig.s["debt"] is None and rig.s["held"] is None
    rig.push(300)
    rig.end()
    assert rig.report()["segments"] == [
        {"slot": "T1A", "spool": "B001", "mm": 530.0},
        {"slot": "T1B", "spool": "B002", "mm": 370.0}]


def test_an_unannounced_change_waits_then_goes_to_thomas():
    rig = Rig()
    unannounced(rig)
    rig.observe(route="T1B")
    held = rig.s["held"]
    assert (held["slot"], held["key"], held["mm"]) == ("T1B", "T1B|B002", 145.0)
    rig.push(400)
    assert rig.tick(counter.CONFIRM_S + 1) == []
    assert rig.s["held"] is None
    assert rig.s["todo"] == [{"slot": "T1B", "mm": 145.0, "reason": counter.UNANNOUNCED}]
    rig.end()
    report = rig.report()
    assert report["spools"] == {"T1B": "B002"}
    assert report["segments"] == [
        {"slot": "T1A", "spool": "B001", "mm": 850.0},
        {"slot": "T1B", "spool": "B002", "mm": 365.0},
        {"slot": "T1B", "mm": 145.0, "reason": counter.UNANNOUNCED}]
    work = ended(report, rig.now)[0]
    assert work["spools"]["B001"]["counted_g"] == counted(work, "B001", 850.0)
    assert work["spools"]["B002"]["counted_g"] == counted(work, "B002", 365.0)
    [waiting] = work["unassigned"]
    assert (waiting["slot"], waiting["mm"], waiting["reason"]) == ("T1B", 145.0, counter.UNANNOUNCED)


CONFIRMATIONS = {
    "done": {"last": {"tool": "T2", "outcome": "done", "slot": "T1B", "temp": 220}},
    "start": {"last": {"tool": "T2", "outcome": "start", "slot": "T1B", "temp": 220}},
    "reload": {"reload": {"tool": "T1B", "error": False, "head": True, "paused": True}},
}


@pytest.mark.parametrize("route_first", [True, False])
@pytest.mark.parametrize("name", sorted(CONFIRMATIONS))
def test_a_confirmation_from_kctrl_tool_change_releases_what_waited(name, route_first):
    rig = Rig()
    unannounced(rig)
    steps = [{"route": "T1B"}, copy.deepcopy(CONFIRMATIONS[name])]
    for changes in steps if route_first else steps[::-1]:
        rig.observe(**changes)
    assert rig.s["held"] is None and rig.s["todo"] == []
    rig.push(400)
    rig.end()
    assert rig.report()["segments"] == [
        {"slot": "T1A", "spool": "B001", "mm": 850.0},
        {"slot": "T1B", "spool": "B002", "mm": 510.0}]


NOT_CONFIRMATIONS = {
    "refuse": {"last": {"tool": "T2", "outcome": "refuse", "detail": "x"}},
    "stock": {"last": {"tool": "T2", "outcome": "stock", "detail": "hors travail"}},
    "empty": {"last": {"tool": "T2", "outcome": "empty", "slot": "T1B", "temp": 220}},
    "paused": {"last": {"tool": "T2", "outcome": "paused_by_firmware", "slot": "T1B",
                        "temp": 220}},
    "reload_error": {"reload": {"tool": "T1B", "error": True, "head": True, "paused": True}},
    "reload_empty": {"reload": {"tool": "T1B", "error": False, "head": False, "paused": True}},
}


@pytest.mark.parametrize("name", sorted(NOT_CONFIRMATIONS))
def test_a_change_that_did_not_load_confirms_nothing(name):
    rig = Rig()
    unannounced(rig)
    rig.observe(route="T1B")
    rig.observe(**copy.deepcopy(NOT_CONFIRMATIONS[name]))
    assert rig.s["held"]["mm"] == 145.0
    assert "T1B|B002" not in rig.s["nets"]


def test_the_same_result_in_a_new_job_is_news():
    rig = Rig()
    rig.observe()
    rig.start()
    rig.observe(last={"tool": "T1", "outcome": "start", "slot": "T1A", "temp": 220})
    assert rig.s["expect"] is None  # already on T1A
    rig.push(100)
    rig.end()
    rig.report()
    rig.start(reset=False)  # the status where START_PRINT emptied `last` was missed
    assert rig.s["expect"]["slot"] == "T1A"
    rig.observe(sensor=True)
    rig.push(5)
    rig.push(140)
    rig.observe(route="T1A")
    assert rig.s["held"] is None and rig.s["todo"] == []
    rig.finish()
    assert rig.report()["segments"] == [{"slot": "T1A", "spool": "B001", "mm": 145.0}]


def test_a_status_without_kctrl_tool_change_replays_nothing():
    rig = Rig()
    rig.observe()
    rig.start()
    rig.observe(last={"tool": "T2", "outcome": "done", "slot": "T1B", "temp": 220})
    assert rig.s["expect"]["slot"] == "T1B"
    rig.tick(counter.EXPECT_S + 1)
    assert rig.s["expect"] is None
    seen = rig.s["seen_last"]
    rig.observe(omit=("kctrl_tool_change",))
    assert rig.s["seen_last"] == seen
    rig.observe(omit=())
    assert rig.s["expect"] is None


def test_an_announcement_older_than_expect_s_confirms_nothing():
    rig = Rig()
    announced(rig)
    rig.observe(sensor=True)
    rig.push(5)
    rig.push(140)
    rig.observe(seconds=counter.EXPECT_S, route="T1B")
    assert rig.s["held"]["mm"] == 145.0 and rig.s["expect"] is None


def test_a_clock_that_goes_back_makes_an_expectation_old():
    rig = Rig()
    rig.observe()
    rig.start()
    rig.counter.announce(rig.now, "T1B")
    assert rig.s["expect"]["slot"] == "T1B"
    rig.tick(-10)
    assert rig.s["expect"] is None


# ---------------------------------------------------------------- the CFS
def test_a_cfs_blip_gives_its_millimetres_to_the_route_that_comes_back():
    rig = Rig()
    blip(rig)
    assert rig.s["gap"] == {"mm": 50.0, "kind": "unknown", "before": "T1A"}
    assert rig.counter.live()["route"] is None
    rig.push(10, box=None)
    assert rig.s["gap"] is None
    assert rig.counter.live()["spools"] == [{"slot": "T1A", "spool": "B001", "mm": 210.0}]


def test_a_cfs_blip_ending_on_another_route_waits_for_a_confirmation():
    rig = Rig()
    blip(rig)
    rig.push(10, box=None, route="T1B")
    assert rig.s["held"]["mm"] == 60.0
    rig.finish()
    assert rig.report()["segments"] == [
        {"slot": "T1A", "spool": "B001", "mm": 150.0},
        {"slot": "T1B", "mm": 60.0, "reason": counter.UNANNOUNCED}]


def test_a_cfs_that_never_answers_again_leaves_its_millimetres_to_thomas():
    rig = Rig()
    blip(rig)
    rig.finish()
    assert rig.report()["segments"] == [
        {"slot": "T1A", "spool": "B001", "mm": 150.0},
        {"slot": "T1A", "mm": 50.0, "reason": "CFS illisible"}]


def two_routes():
    box = box_status("T1A")
    box["T2"]["filament"] = "B"
    return box


def route_of_a_unit_gone():
    box = box_status("")
    box["T3"]["filament"] = "A"
    return box


def unreadable_route():
    box = box_status("")
    box["T1"]["filament"] = "E"
    return box


ROUTES = {
    "absent": (lambda: None, ("", "CFS absent")),
    "not_enabled": (lambda: box_status(enable=0), ("", "CFS non prêt")),
    "not_connected": (lambda: box_status(state="disconnect"), ("", "CFS non prêt")),
    "two_routes": (two_routes, ("", "plusieurs routes CFS")),
    "unit_gone": (route_of_a_unit_gone, ("", "route d'un CFS déconnecté")),
    "unreadable": (unreadable_route, ("", "route CFS illisible")),
    "none": (lambda: box_status(""), ("", "")),
    "second_unit": (lambda: box_status("T2C"), ("T2C", "")),
}


@pytest.mark.parametrize("name", sorted(ROUTES))
def test_the_route_is_read_only_when_the_box_is_unambiguous(name):
    build, expected = ROUTES[name]
    assert counter.route_of(build()) == expected


def test_the_cfs_serial_numbers_never_reach_the_state():
    rig = Rig(cut_loss=40.0)
    announced(rig)
    rig.observe(route="T1B")
    rig.push(300)
    texts = [json.dumps(rig.save()), json.dumps(rig.counter.live())]
    rig.end()
    texts.append(json.dumps(rig.reports))
    for text in texts:
        assert "SERIAL" not in text and "UUID" not in text


# ---------------------------------------------------------------- Klipper and E
def test_losing_klipper_before_the_first_status_keeps_the_checkpoint():
    fresh = counter.Counter()
    fresh.lost(T0, "Klipper arrêté")
    assert fresh.state == counter.fresh_state() and not fresh.dirty
    saved = printed(Rig())
    restored = counter.Counter(saved)
    restored.lost(T0 + 5, "Klipper arrêté")
    assert restored.state == saved


def test_a_klipper_restart_ends_the_job_without_losing_its_count():
    rig = Rig()
    rig.observe()
    rig.start()
    rig.push(300)
    rig.counter.lost(rig.now, "Klipper arrêté")
    rig.observe(e=0.0, state="standby", file="")
    rig.observe(seconds=counter.SETTLE_S)
    report = rig.report()
    assert report["outcome"] == "interrupted"
    assert report["segments"] == [{"slot": "T1A", "spool": "B001", "mm": 300.0}]
    assert report["notes"] == ["Klipper arrêté : décompte à vérifier"]


def test_a_jump_of_e_is_a_lost_origin_not_filament():
    rig = Rig()
    rig.observe()
    rig.start()
    for mm in (100, -1500, 25000, 50):
        rig.push(mm)
    live = rig.counter.live()
    assert live["spools"] == [{"slot": "T1A", "spool": "B001", "mm": 150.0}]
    assert live["period"]["notes"] == [counter.LOST_ORIGIN]


def test_an_unreadable_e_starts_a_new_origin():
    rig = Rig()
    rig.observe()
    rig.start()
    rig.push(100)
    rig.observe(e=None)
    rig.observe(e=500.0)
    rig.push(50)
    live = rig.counter.live()
    assert live["spools"] == [{"slot": "T1A", "spool": "B001", "mm": 150.0}]
    assert live["period"]["notes"] == ["position de l'extrudeur illisible : décompte à vérifier"]


# ---------------------------------------------------------------- restarts
def test_a_restart_of_k1_control_resumes_the_job_it_vouches_for():
    rig = Rig()
    saved = printed(rig)
    assert saved["saved"] == T0 + 4
    rig.restart(saved)
    rig.push(250)
    live = rig.counter.live()
    assert live["spools"] == [{"slot": "T1A", "spool": "B001", "mm": 550.0}]
    assert live["period"]["notes"] == ["reprise après redémarrage de K1 Control"]
    rig.end()
    report = rig.report()
    assert report["job"] == "J%d" % (T0 + 2)
    assert report["segments"] == [{"slot": "T1A", "spool": "B001", "mm": 515.0}]


def test_a_file_name_cut_by_the_checkpoint_still_resumes_its_job():
    name = "x" * 150 + ".gcode"
    rig = Rig()
    rig.observe()
    rig.start(file=name)
    rig.push(300)
    saved = rig.save()
    saved["period"]["file"] = name[:counter.FILE_CUT]
    rig.restart(saved)
    rig.push(50)
    live = rig.counter.live()
    assert live["period"]["file"] == name
    assert live["period"]["notes"] == ["reprise après redémarrage de K1 Control"]
    assert live["spools"] == [{"slot": "T1A", "spool": "B001", "mm": 350.0}]


def test_a_restart_that_finds_another_route_leaves_the_movement_to_thomas():
    rig = Rig()
    rig.restart(printed(rig))
    rig.push(250, route="T1B")
    assert rig.s["todo"] == [{"slot": "", "mm": 250.0, "reason": counter.INTERRUPTED}]


def test_a_late_restart_cannot_vouch_for_the_route():
    rig = Rig()
    saved = printed(rig)
    rig.restart(saved, seconds=counter.RESUME_S + 1)
    rig.push(250)
    assert rig.s["todo"] == [{"slot": "T1A", "mm": 250.0, "reason": counter.INTERRUPTED}]


def test_a_job_that_ended_while_k1_control_was_down():
    rig = Rig()
    saved = printed(rig)
    rig.e += 165
    rig.restart(saved)
    rig.observe(state="complete", route="", sensor=False)
    rig.observe(seconds=counter.SETTLE_S)
    report = rig.report()
    assert report["outcome"] == "complete"
    assert report["segments"] == [
        {"slot": "T1A", "spool": "B001", "mm": 300.0},
        {"slot": "T1A", "mm": 165.0, "reason": counter.INTERRUPTED}]
    assert report["notes"] == ["fin pendant l'arrêt de K1 Control"]


def test_a_new_job_started_while_k1_control_was_down():
    rig = Rig()
    saved = printed(rig)
    rig.e += 165
    rig.restart(saved)
    [old] = rig.observe(file="other.gcode", epoch=2)
    assert old["end"] == int(saved["saved"]) and old["outcome"] == "interrupted"
    assert old["segments"] == [
        {"slot": "T1A", "spool": "B001", "mm": 300.0},
        {"slot": "T1A", "mm": 165.0, "reason": counter.INTERRUPTED}]
    assert old["notes"] == ["fin et nouvelle impression pendant l'arrêt de K1 Control"]
    live = rig.counter.live()
    assert live["period"]["file"] == "other.gcode"
    assert live["period"]["notes"] == [counter.MIDWAY]
    assert live["spools"] == []


def test_a_print_started_while_k1_control_was_down_ends_the_stretch_at_rest():
    rig = Rig()
    rig.observe()
    rig.push(20)
    saved = rig.save()
    rig.e += 60
    rig.restart(saved)
    [rest] = rig.observe(state="printing", file="cube.gcode", epoch=1)
    assert rest["outcome"] == "rest"
    assert rest["segments"] == [{"slot": "T1A", "spool": "B001", "mm": 20.0}]
    live = rig.counter.live()
    assert live["period"]["notes"] == [counter.MIDWAY]
    assert live["spools"] == [{"slot": "T1A", "spool": "B001", "mm": 60.0}]


def test_klipper_restarted_while_k1_control_was_down():
    rig = Rig()
    saved = printed(rig)
    rig.restart(saved)
    [report] = rig.observe(e=0.0, state="standby", file="")
    assert report["end"] == int(saved["saved"]) and report["outcome"] == "interrupted"
    assert report["segments"] == [{"slot": "T1A", "spool": "B001", "mm": 300.0}]
    assert report["notes"] == ["Klipper redémarré pendant l'arrêt de K1 Control : "
                               "décompte arrêté au dernier point de reprise"]


def test_the_checkpoint_waits_for_klipper_to_give_e():
    rig = Rig()
    saved = printed(rig)
    rig.restart(saved)
    assert rig.observe(e=None) == [] and rig.counter.values is None
    rig.counter.lost(rig.now, "Klipper arrêté")  # still before the first status
    rig.observe(e=550.0)
    live = rig.counter.live()
    assert live["spools"] == [{"slot": "T1A", "spool": "B001", "mm": 550.0}]
    assert live["period"]["notes"] == ["reprise après redémarrage de K1 Control"]


def test_a_first_start_in_the_middle_of_a_print_says_so():
    rig = Rig(state="printing", file="cube.gcode", epoch=1)
    rig.observe()
    assert rig.counter.live()["period"]["notes"] == [counter.MIDWAY]


def test_a_checkpoint_of_another_version_is_refused():
    saved = printed(Rig())
    saved["v"] = 2
    refused = counter.Counter(saved)
    assert refused.refused and not refused.restored
    assert refused.state == counter.fresh_state()


BREAKS = {
    "e": lambda state: state.update(e=True),
    "key": lambda state: state.update(key="T5A|B001"),
    "extra": lambda state: state.update(extra=1),
    "route": lambda state: state.update(route="T1B"),
    "version": lambda state: state.update(v=2),
    "todo": lambda state: state.update(todo=[
        {"slot": "T1A", "mm": 2.0, "reason": counter.UNANNOUNCED} for _ in range(13)]),
    "cut_loss": lambda state: state.update(cut_loss=-1.0),
    "links": lambda state: state["links"].update(T1A="X001"),
}


@pytest.mark.parametrize("name", sorted(BREAKS))
def test_a_checkpoint_this_version_did_not_write_is_refused(name):
    state = printed(Rig())
    assert counter.usable(state)
    BREAKS[name](state)
    assert not counter.usable(state)
    assert counter.Counter(state).refused


# ---------------------------------------------------------------- at rest
def test_a_load_at_rest_goes_to_thomas_when_its_stretch_ends():
    rig = Rig(route="", sensor=False)
    rig.observe()
    rig.observe(sensor=True)
    rig.push(5)
    rig.push(140)
    rig.observe(route="T1B")
    [rest] = rig.tick(counter.CONFIRM_S + 1)
    assert rest["outcome"] == "rest"
    assert rest["segments"] == [{"slot": "T1B", "mm": 145.0, "reason": counter.AT_REST}]
    rig.push(0.5)
    assert rig.tick(counter.REST_FOLD_S) == []
    assert rig.s["period"] is None


def test_a_print_start_ends_the_stretch_at_rest_before_it():
    rig = Rig()
    rig.observe()
    rig.push(20)
    rig.start()
    rest = rig.report()
    assert rest["job"].startswith("R") and rest["outcome"] == "rest"
    assert rest["segments"] == [{"slot": "T1A", "spool": "B001", "mm": 20.0}]


# ---------------------------------------------------------------- links and cut pieces
def test_a_link_made_during_a_route_takes_what_the_route_counted():
    rig = Rig(links={})
    rig.observe()
    rig.push(100)
    assert rig.s["nets"] == {"T1A|": 100.0}
    assert rig.counter.live()["spools"] == [{"slot": "T1A", "spool": "", "mm": 100.0}]
    rig.counter.set_links(LINKS)
    assert rig.s["nets"] == {"T1A|B001": 100.0}
    rig.counter.set_links({"T1A": "B003", "T1B": "B002"})
    rig.push(50)
    assert rig.s["nets"] == {"T1A|B001": 100.0, "T1A|B003": 50.0}


def test_the_cut_piece_follows_its_route_when_the_library_relinks_it():
    rig = Rig(cut_loss=40.0)
    rig.observe()
    rig.start()
    rig.push(500)
    rig.counter.announce(rig.now, "T1B")
    rig.observe(route="")
    rig.observe(route="T1B")
    assert rig.s["debt"] == {"from": "T1B|B002", "to": "T1A|B001", "mm": 40.0}
    rig.counter.set_links({"T1A": "B001", "T1B": "B003"}, 40.0)
    assert rig.s["debt"]["from"] == "T1B|B003"
    rig.push(100)
    assert rig.s["nets"] == {"T1A|B001": 540.0, "T1B|B003": 60.0}


def test_a_piece_owed_to_the_spool_now_on_its_route_is_dropped():
    rig = Rig(cut_loss=40.0)
    rig.observe()
    rig.start()
    rig.push(500)
    rig.observe(route="")
    rig.counter.set_links({"T1A": "B004", "T1B": "B002"}, 40.0)
    rig.observe(route="T1A")
    assert rig.s["debt"] == {"from": "T1A|B004", "to": "T1A|B001", "mm": 40.0}
    rig.counter.set_links(LINKS, 40.0)
    assert rig.s["debt"] is None and rig.s["key"] == "T1A|B001"


def test_a_retry_of_the_same_route_keeps_what_it_still_owes():
    rig = Rig(route="T2B", links={"T1A": "B001", "T2B": "B002"}, cut_loss=40.0)
    retried(rig)
    rig.observe(route="")
    rig.observe(route="T1A")
    assert rig.s["debt"] == {"from": "T1A|B001", "to": "T2B|B002", "mm": 35.0}
    rig.push(140)
    assert rig.s["nets"] == {"T1A|B001": 105.0, "T2B|B002": 540.0}


def test_a_chain_of_cut_pieces_is_not_followed():
    rig = Rig(route="T2B", links={"T1A": "B001", "T2B": "B002"}, cut_loss=40.0)
    retried(rig)
    rig.observe(route="")
    rig.observe(route="T1C")
    assert rig.s["debt"] == {"from": "T1C|", "to": "T1A|B001", "mm": 40.0}


def test_a_wrong_cut_length_setting_counts_no_piece():
    rig = Rig(cut_loss=40.0)
    rig.observe()
    for wrong in (-5.0, float("nan"), "40", None):
        rig.counter.set_links(LINKS, wrong)
        assert rig.s["cut_loss"] == 0.0 and counter.usable(rig.save())


# ---------------------------------------------------------------- the checkpoint
def test_the_checkpoint_is_written_every_minute_and_soon_after_a_change_of_route():
    rig = Rig()
    assert rig.counter.due(rig.now)
    rig.counter.snapshot(rig.now)
    assert not rig.counter.due(rig.now)
    rig.observe()
    rig.start()
    saved_at = rig.now
    rig.counter.snapshot(saved_at)
    rig.push(10)
    assert not rig.counter.due(rig.now)
    assert rig.counter.due(saved_at + counter.SAVE_EVERY_S)
    saved_at = rig.now
    rig.counter.snapshot(saved_at)
    rig.observe(route="")
    assert not rig.counter.due(rig.now)
    assert rig.counter.due(saved_at + counter.URGENT_EVERY_S)


def test_the_list_to_attribute_groups_what_overflows():
    rig = Rig()
    saved = printed(rig)
    saved["todo"] = [{"slot": "T1B", "mm": 10.0, "reason": counter.UNANNOUNCED}
                     for _ in range(counter.TODO_KEPT)]
    rig.restart(saved, seconds=counter.RESUME_S + 1)
    rig.push(250)
    todo = rig.s["todo"]
    assert len(todo) == counter.TODO_KEPT
    assert todo[-2] == {"slot": "T1B", "mm": 10.0, "reason": counter.UNANNOUNCED}
    assert todo[-1] == {"slot": "", "mm": 260.0, "reason": counter.GROUPED}


def worst_state():
    """Every field at its largest: the longest file, notes and list to attribute."""
    moment = T0 + 1000.5
    state = counter.fresh_state()
    state.update({
        "period": {"kind": "job", "id": "J%d" % T0, "file": "é" * counter.FILE_LIMIT,
                   "start": T0, "epoch": 123456, "adopted": True,
                   "notes": ["%d" % i + "é" * (counter.NOTE_LIMIT - 1)
                             for i in range(counter.NOTES_KEPT)],
                   "ended": moment, "calm": moment, "outcome": "interrupted"},
        "e": 123456.789, "route": "T2D", "key": "T2D|B991", "route_known": True, "sensor": True,
        "nets": {"%s|B%03d" % (slot, 990 + i): 123456.789 for i, slot in enumerate(SLOTS)},
        "gap": {"mm": 123456.789, "kind": "unknown", "before": "T2D"},
        "held": {"slot": "T2D", "key": "T2D|B991", "mm": 123456.789, "t": moment},
        "expect": {"slot": "T1A", "t": moment},
        "orphan": "T2C|B990", "debt": {"from": "T2D|B991", "to": "T2C|B990", "mm": 40.0},
        "todo": [{"slot": SLOTS[i], "mm": 12345.6, "reason": counter.UNANNOUNCED}
                 for i in range(counter.TODO_KEPT)],
        "links": {slot: "B%03d" % (980 + i) for i, slot in enumerate(SLOTS[:8])},
        "cut_loss": 40.0, "seen_last": "0123456789abcdef:123456",
        "seen_reload": "0123456789abcdef", "last_move": moment, "saved": moment,
    })
    state["highs"] = dict(state["nets"])
    return state


def test_the_checkpoint_always_fits_its_fixed_size(tmp_path):
    raw = worst_state()
    assert counter.usable(raw) and len(counter.encode(raw)) > counter.STATE_LIMIT
    total = counter._round(sum(item["mm"] for item in raw["todo"]), 1)
    fitted = counter.fit(raw)
    assert len(counter.encode(fitted)) <= counter.STATE_LIMIT and counter.usable(fitted)
    assert counter._round(sum(item["mm"] for item in fitted["todo"]), 1) == total
    snap = counter.Counter(raw).snapshot(T0 + 2000)
    assert len(counter.encode(snap)) <= counter.STATE_LIMIT and counter.usable(snap)
    # Short of room, the list to attribute goes last, grouped, its total kept.
    trimmed = copy.deepcopy(raw)
    trimmed["period"]["notes"], trimmed["highs"] = [], {}
    trimmed["period"]["file"] = trimmed["period"]["file"][:counter.FILE_CUT]
    limit = len(counter.encode(trimmed)) - 1
    tight = counter.fit(raw, limit)
    assert tight["todo"] == [{"slot": "", "mm": total, "reason": counter.GROUPED}]
    assert tight["period"]["notes"] == [] and tight["highs"] == {}
    assert tight["period"]["file"] == "é" * counter.FILE_CUT
    assert len(counter.encode(tight)) <= limit and counter.usable(tight)
    store.SpoolStore(str(tmp_path)).save_checkpoint(snap)
    loaded, _ = store.SpoolStore(str(tmp_path)).load_checkpoint()
    assert loaded == snap and counter.Counter(loaded).restored


# ---------------------------------------------------------------- the messages read
def literals(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)}


def test_the_messages_read_here_are_kctrl_tool_change_s_own():
    found = literals(TOOL_CHANGE)
    for text in (ANNOUNCED, CHANGED, SAME, FIRST, REFUSED, VACANT, PAUSED, EMPTY, DONE, TOOLS,
                 RELOADS, TOOL_LINE, TOOL_SLOT, UNMAPPED, TOOL_LAST):
        assert text in found, text
    for options in ({}, {"changed": True}, {"first_layer": True}):
        assert counter.ANNOUNCE.search(announcement("T2B", **options)).group(1) == "T2B"


def tools_listing():
    """KCTRL_TOOLS during a job: it names slots too, but announces nothing."""
    return info("\n".join([
        TOOLS % ("T0, T1, T2", "aucune"),
        RELOADS % "aucun",
        TOOL_LINE % (1, "T1A", "PLA", "FF0000", "220 C (1re couche 225 C)")
        + TOOL_SLOT % ("T1B", "000001", "220", ""),
        TOOL_LINE % (2, "T1C", "PLA", "FFFFFF", "220 C (1re couche 225 C)") + UNMAPPED,
        TOOL_LAST % "outcome=done, slot=T1B, temp=220, tool=T2"]))


NOT_ANNOUNCEMENTS = {
    "empty": info(EMPTY % ("T2", "T1B", "l'impression continue a vide")),
    "done": info(DONE % ("T2", 220)),
    "paused": info(PAUSED % ("T2", "T1B")),
    "refused": "!! " + REFUSED % ("T2", VACANT % (2, "T1C", "T1B")),
    "listing": tools_listing(),
}


@pytest.mark.parametrize("name", sorted(NOT_ANNOUNCEMENTS))
def test_the_other_messages_of_kctrl_tool_change_announce_nothing(name):
    assert counter.ANNOUNCE.search(NOT_ANNOUNCEMENTS[name]) is None
    rig = Rig()
    rig.observe()
    rig.say(NOT_ANNOUNCEMENTS[name])
    assert rig.s["expect"] is None
