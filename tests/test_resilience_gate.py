"""resilience-v1 gate and Bobines page (ADR-080, document 109).

An end that failed and is over no longer closes the next start: the gate lets
it through, the page says what happened, START_PRINT clears the end. Still
refused, each with its own sentence: an end still running, an end that cannot
be read, heaters not confirmed off.

Every earlier gate test is rerun on this module. The page ships only the two
files it changes, so its node tests run in a folder put together here from the
installed page and those two files. Software validation only, no printer
transport.
"""

import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

import test_kctrl_end_no_stock_flush_v5 as end5
import test_kctrl_print_gate_v1 as base
from test_kctrl_print_gate_v1 import EndStatus, FakeGcmd, GcmdError, confirm, machine, start

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGES = os.path.join(ROOT, "packages", "k1-control-v1")
PACKAGE = os.path.join(PACKAGES, "resilience-v1")
INSTALLED = os.path.join(PACKAGES, "spool-choice-gate-v1")
MODULE = os.path.join(PACKAGE, "kctrl_print_gate.py")
PAGE_FILES = ["bobines.js", "logic.js"]
NODE = shutil.which("node")


def load_module():
    # The gate finds the slot map module under the name Klipper gives it.
    sys.modules["extras.kctrl_slot_map"] = base.SLOT_MAP_MOD
    spec = importlib.util.spec_from_file_location("kctrl_print_gate_resilience", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = load_module()
OLD = base.MOD

# Rewritten below: an end that failed and is over no longer refuses.
ADAPTED = ("test_unfinished_end_blocks_before_sd_or_mapping",)
RERUN = {name: value for name, value in vars(base).items()
         if name.startswith("test_") and name not in ADAPTED}
globals().update(RERUN)

# The real end module of the machine (end-no-stock-flush-v5) on its own harness.
successor = end5.successor


@pytest.fixture(autouse=True)
def new_module(monkeypatch):
    """Every gate built by the harness, the rerun tests included, is the new one."""
    monkeypatch.setattr(base, "MOD", MOD)


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


def end(phase, pending=False, **more):
    value = {"enabled": True, "pending": pending, "phase": phase}
    value.update(more)
    return value


RUNNING = "encore en cours"
UNREADABLE = "illisible"
HEATERS = "chauffes non confirme"
SENTENCES = (RUNNING, UNREADABLE, HEATERS)

# The same two tables as logic.test.mjs: what lets a start leave, what holds it.
RELEASED = [
    pytest.param(end("idle"), id="idle"),
    pytest.param(end("complete"), id="complete"),
    pytest.param(end("complete", reason="cancel"), id="complete-after-cancel"),
    pytest.param(end("failed"), id="failed"),
    pytest.param(end("failed", failure="auto_refill_not_disabled"), id="failed-with-reason"),
    pytest.param(end("idle", failure="left_from_before"), id="idle-with-old-reason"),
    pytest.param({"enabled": False, "pending": False, "phase": "disabled"}, id="owner-disabled"),
]
HELD = [
    pytest.param(end("rewinding", True), RUNNING, id="rewinding-pending"),
    pytest.param(end("failed", True), RUNNING, id="failed-pending"),
    pytest.param(end("failed", True, failure="end_timeout"), RUNNING,
                 id="failed-pending-with-reason"),
    pytest.param(end("waiting"), RUNNING, id="waiting"),
    pytest.param(end("heating"), RUNNING, id="heating"),
    pytest.param(end("cutting"), RUNNING, id="cutting"),
    pytest.param(end("rewinding"), RUNNING, id="rewinding"),
    pytest.param(end("finalizing"), RUNNING, id="finalizing"),
    pytest.param(end("idle", True), RUNNING, id="idle-pending"),
    pytest.param(end("complete", True), RUNNING, id="complete-pending"),
    pytest.param(end("shutdown"), UNREADABLE, id="shutdown"),
    pytest.param(end("shutdown", True, failure="printer_shutdown_or_disconnect"), UNREADABLE,
                 id="shutdown-pending"),
    pytest.param(end("future"), UNREADABLE, id="unknown-phase"),
    pytest.param(end("disabled"), UNREADABLE, id="enabled-yet-disabled"),
    pytest.param(end("idle", 1), UNREADABLE, id="pending-not-a-boolean"),
    pytest.param({"enabled": False, "pending": False, "phase": "complete"}, UNREADABLE,
                 id="disabled-yet-complete"),
    pytest.param({"enabled": False, "pending": True, "phase": "disabled"}, UNREADABLE,
                 id="disabled-yet-pending"),
    pytest.param({}, UNREADABLE, id="empty"),
    pytest.param(None, UNREADABLE, id="none"),
    pytest.param(RuntimeError("lost observation"), UNREADABLE, id="raises"),
    pytest.param(end("complete", thermal_failure="targets_not_zero"), HEATERS,
                 id="heaters-after-complete"),
    pytest.param(end("failed", thermal_failure="targets_not_zero"), HEATERS,
                 id="heaters-after-failed"),
    pytest.param(end("failed", True, thermal_failure="heater_error"), HEATERS,
                 id="heaters-failed-pending"),
    pytest.param(end("shutdown", thermal_failure="targets_not_zero"), HEATERS,
                 id="heaters-shutdown"),
]
ENTRIES = ("start", "resume", "confirm")


def enter(gate, entry):
    if entry == "confirm":
        return confirm(gate, MAP="T1A:T1B")
    return start(gate, **({"ISCONTINUEPRINT": "1"} if entry == "resume" else {}))


def stock_starts(gate):
    return [line for line in gate.gcode.scripts if line.startswith(MOD.STOCK)]


# --- the rerun ----------------------------------------------------------------

def test_every_earlier_gate_test_runs_on_this_module():
    earlier = {name for name in vars(base) if name.startswith("test_")}
    assert set(ADAPTED) <= earlier
    assert set(RERUN) == earlier - set(ADAPTED) and len(RERUN) == 41
    assert all(globals()[name] is value for name, value in RERUN.items())


def test_the_harness_builds_the_new_gate(tmp_path):
    gate = machine(tmp_path)
    assert type(gate).__module__ == "kctrl_print_gate_resilience"
    assert gate.get_status()["revision"] == MOD.REVISION == "resilience-v1"


# --- the rule -----------------------------------------------------------------

def test_the_rule_is_written_once():
    assert MOD.END_RELEASED == ("idle", "complete", "failed")
    assert MOD.END_UNREADABLE == ("unknown", "shutdown", "disabled")


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("value", RELEASED)
def test_an_end_that_is_over_lets_every_entry_through(tmp_path, value, entry):
    gate = machine(tmp_path, state="complete")
    gate.printer.objects["kctrl_end"] = EndStatus(value)
    if entry == "start":
        # Held for the choice of spools as usual, nothing started, nothing refused.
        start(gate)
        assert gate.pending is not None and gate.pending["name"] == "job.gcode"
        assert stock_starts(gate) == []
        return
    if entry == "confirm":
        start(gate)
    enter(gate, entry)
    assert len(stock_starts(gate)) == 1


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("value, sentence", HELD)
def test_an_end_that_holds_refuses_every_entry_in_its_own_words(tmp_path, value, sentence,
                                                                 entry):
    gate = machine(tmp_path, state="complete")
    if entry == "confirm":
        start(gate)
    before = list(gate.gcode.scripts)
    gate.printer.objects["kctrl_end"] = EndStatus(value)
    with pytest.raises(GcmdError) as caught:
        enter(gate, entry)
    message = str(caught.value)
    assert message.startswith("K1 Control: fin precedente")
    assert [text for text in SENTENCES if text in message] == [sentence]
    # Before the SD card, the mapping or any stock start.
    assert gate.gcode.scripts == before
    if entry == "confirm":
        assert gate.pending is not None
    else:
        assert gate.pending is None


def test_each_refusal_names_its_remedy():
    said = {}
    for value, sentence in ((end("cutting"), RUNNING), (end("shutdown"), UNREADABLE),
                            (end("complete", thermal_failure="x"), HEATERS)):
        owner = SimpleNamespace(end_status=lambda value=value: value)
        with pytest.raises(GcmdError) as caught:
            MOD.KctrlPrintGate.assert_end_released(owner, FakeGcmd())
        said[sentence] = str(caught.value)
    assert "attendez la fin du cycle" in said[RUNNING] and "Bobines" in said[RUNNING]
    assert "eteignez puis rallumez" in said[UNREADABLE]
    assert "verifiez l'imprimante" in said[HEATERS] and "rallumez" in said[HEATERS]
    assert len(set(said.values())) == 3
    for message in said.values():
        message.encode("ascii")
        assert len(message) < 140


def test_a_failed_end_is_published_as_it_is(tmp_path):
    gate = machine(tmp_path)
    assert gate.get_status()["end"] is None
    value = end("failed", failure="auto_refill_not_disabled", thermal_failure="")
    gate.printer.objects["kctrl_end"] = EndStatus(value)
    assert gate.get_status()["end"] == value
    gate.printer.objects["kctrl_end"] = EndStatus(RuntimeError("lost"))
    assert gate.get_status()["end"] == {"enabled": True, "pending": True, "phase": "unknown",
                                        "failure": "end_status_unavailable",
                                        "thermal_failure": ""}


# --- the real end module ------------------------------------------------------

def really_failed_end():
    """31 October: the stock auto refill would not switch off, the end stopped."""
    p, c = end5.refill_on()
    p.gcode.on_script[end5.REFILL % 0] = lambda: None
    end5.base.finish(p, c)
    return p, c


def test_a_really_failed_end_lets_the_next_print_leave_and_is_cleared_by_it(tmp_path):
    p, c = really_failed_end()
    status = c.get_status()
    assert (status["phase"], status["failure"]) == ("failed", "auto_refill_not_disabled")
    assert status["pending"] is False and not status["thermal_failure"]

    gate = machine(tmp_path, state="complete")
    gate.printer.objects["kctrl_end"] = c
    assert gate.get_status()["end"]["phase"] == "failed"
    start(gate)
    confirm(gate, MAP="T1A:T1B")
    assert len(stock_starts(gate)) == 1

    # The stock start reaches START_PRINT, where the end clears itself.
    p.gcode.handlers["START_PRINT"](end5.base.Cmd())
    cleared = c.get_status()
    assert (cleared["phase"], cleared["failure"], cleared["pending"]) == ("idle", "", False)
    gate.assert_end_released(FakeGcmd())


def test_the_installed_gate_refused_that_very_end_until_klipper_restarted():
    p, c = really_failed_end()
    owner = SimpleNamespace(end_status=lambda: c.get_status())
    with pytest.raises(GcmdError, match="fin precedente"):
        OLD.KctrlPrintGate.assert_end_released(owner, FakeGcmd())
    MOD.KctrlPrintGate.assert_end_released(owner, FakeGcmd())


def test_heaters_that_really_stay_on_still_close_the_start(tmp_path):
    p, c = end5.previous.setup()
    p.heaters.lie = True
    end5.v4.cancel(p)
    assert c.get_status()["thermal_failure"] == "targets_not_zero" and p.shutdowns
    gate = machine(tmp_path, state="complete")
    gate.printer.objects["kctrl_end"] = c
    with pytest.raises(GcmdError, match=HEATERS):
        start(gate)
    assert gate.gcode.scripts == [] and gate.pending is None


# --- nothing else moved -------------------------------------------------------

def shape(path):
    tree = ast.parse(read(path))
    functions, assigned, others = {}, {}, []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            functions[node.name] = ast.dump(node)
        elif isinstance(node, ast.ClassDef):
            for inner in node.body:
                if isinstance(inner, ast.FunctionDef):
                    functions["%s.%s" % (node.name, inner.name)] = ast.dump(inner)
                else:
                    others.append(ast.dump(inner))
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            assigned[node.targets[0].id] = ast.dump(node.value)
        else:
            others.append(ast.dump(node))
    return functions, assigned, others


def test_only_the_end_rule_and_the_published_revision_differ_from_the_installed_gate():
    old_functions, old_assigned, old_others = shape(os.path.join(INSTALLED,
                                                                 "kctrl_print_gate.py"))
    functions, assigned, others = shape(MODULE)
    assert sorted(functions) == sorted(old_functions)
    assert sorted(name for name in functions if functions[name] != old_functions[name]) == [
        "KctrlPrintGate.assert_end_released", "KctrlPrintGate.get_status"]
    assert sorted(set(assigned) - set(old_assigned)) == ["END_RELEASED", "END_UNREADABLE",
                                                         "REVISION"]
    assert all(assigned[name] == value for name, value in old_assigned.items())
    assert others == old_others


def test_the_status_gains_the_revision_and_nothing_else(tmp_path, monkeypatch):
    status = machine(tmp_path).get_status()
    monkeypatch.setattr(base, "MOD", OLD)
    installed = machine(tmp_path).get_status()
    assert sorted(set(status) - set(installed)) == ["revision"]
    assert {key: status[key] for key in installed} == installed


def test_python38_grammar_and_ascii_source():
    source = read(MODULE)
    source.encode("ascii")
    ast.parse(source, feature_version=(3, 8))


# --- the page -----------------------------------------------------------------

def test_the_package_ships_only_the_page_files_it_changes():
    shipped = os.path.join(PACKAGE, "www", "bobines")
    assert sorted(os.listdir(shipped)) == PAGE_FILES
    assert os.listdir(os.path.join(PACKAGE, "www")) == ["bobines"]
    for name in PAGE_FILES:
        assert read(shipped, name) != read(INSTALLED, "www", "bobines", name)


def test_what_the_page_gains_stays_local_and_plain():
    for name in PAGE_FILES:
        installed = set(read(INSTALLED, "www", "bobines", name).splitlines())
        gained = [line for line in read(PACKAGE, "www", "bobines", name).splitlines()
                  if line not in installed]
        assert gained
        for line in gained:
            assert "—" not in line and "–" not in line
            assert "http://" not in line and "https://" not in line and "//cdn" not in line


def test_the_window_is_only_asked_for_modes_it_knows():
    logic = read(PACKAGE, "www", "bobines", "logic.js")
    body = logic.split("export function overlayMode", 1)[1].split("\nexport ", 1)[0]
    modes = set(re.findall(r'(?:return|\?|:)\s*"([a-z]+)"', body))
    assert modes == {"hidden", "minimised", "choice", "launched", "ending"}
    # overlay.js is not shipped: the installed one opens on "ending" already.
    overlay = read(INSTALLED, "www", "bobines", "overlay.js")
    assert 'mode === "ending"' in overlay and 'mode !== "minimised"' in overlay


def test_the_page_reads_what_the_gate_publishes():
    module = read(MODULE)
    logic = read(PACKAGE, "www", "bobines", "logic.js")
    for key in ("end", "wrapped", "pending", "filaments", "slots", "units", "used_count",
                "declared_count", "confirmed_name", "confirmed_map", "since", "note"):
        assert '"%s"' % key in module
        assert key in logic
    for phase in MOD.END_RELEASED:
        assert '"%s"' % phase in logic


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    """The page as the machine will serve it: installed files, then the two new ones."""
    folder = tmp_path_factory.mktemp("page")
    shutil.copytree(os.path.join(INSTALLED, "www"), str(folder / "www"))
    for name in PAGE_FILES:
        shutil.copyfile(os.path.join(PACKAGE, "www", "bobines", name),
                        str(folder / "www" / "bobines" / name))
    shutil.copyfile(os.path.join(PACKAGE, "logic.test.mjs"), str(folder / "logic.test.mjs"))
    return folder


def node(page, *arguments):
    # Outside a terminal node --test writes TAP or spec depending on its version:
    # TAP forced, the texts of the window are French, read as UTF-8.
    result = subprocess.run([NODE] + list(arguments), cwd=str(page), capture_output=True,
                            text=True, encoding="utf-8", timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.mark.skipif(NODE is None, reason="node absent")
def test_the_page_tests_pass_under_node(page):
    report = node(page, "--test", "--test-reporter=tap", "logic.test.mjs")
    assert "# fail 0" in report
    passed = int(re.search(r"^# pass (\d+)$", report, re.M).group(1))
    assert passed >= 70


AGREE = """
import { readFileSync } from "node:fs";
import { endState } from "./www/bobines/logic.js";
const cases = JSON.parse(readFileSync("cases.json", "utf8"));
process.stdout.write(JSON.stringify(cases.map((value) => endState(value).blocked)));
"""


@pytest.mark.skipif(NODE is None, reason="node absent")
def test_the_page_locks_exactly_what_the_gate_refuses(tmp_path, page):
    """One rule on both sides: the page never shows a start the gate will refuse."""
    values = [None] + [param.values[0] for param in RELEASED + HELD]
    expected = [False] + [False] * len(RELEASED) + [True] * len(HELD)
    gate = machine(tmp_path, state="complete")
    published, refused = [], []
    for value in values:
        gate.printer.objects.pop("kctrl_end", None)
        if value is not None or len(published):
            gate.printer.objects["kctrl_end"] = EndStatus(value)
        published.append(gate.get_status()["end"])
        try:
            gate.assert_end_released(FakeGcmd())
            refused.append(False)
        except GcmdError:
            refused.append(True)
    assert published[0] is None and refused == expected
    (page / "cases.json").write_text(json.dumps(published), encoding="utf-8")
    (page / "agree.mjs").write_text(AGREE, encoding="utf-8")
    assert json.loads(node(page, "agree.mjs")) == refused
