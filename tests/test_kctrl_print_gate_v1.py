"""La porte de départ : aucune impression ne part sans le choix des bobines.

`kctrl_print_gate` prend la main sur `SDCARD_PRINT_FILE` à la connexion de
Klipper, retient le fichier sans rien chauffer, publie ses filaments et les
bobines du CFS, et ne rejoue le démarrage stock que depuis
`KCTRL_GATE_CONFIRM MAP=T1A:T2D,...` une fois chaque filament utilisé raccordé
à une bobine chargée (ADR-063, document 78).

Formes réelles : couleurs CFS `0ff1e1e` (sept caractères), fichier
`#8080FF` ; bobines du 10 septembre (T1B noir, T1D blanc, T2A rouge, T2B
bleu, T2C blanc PETG, T2D lilas) ; T1A et T1C vides.
"""

import importlib.util
import os
import sys

import jinja2
import pytest

from test_kctrl_slot_map_v1 import MOD as SLOT_MAP_MOD
from test_kctrl_slot_map_v1 import GcmdError, gcode
from test_kctrl_match_v1 import ENV, FakeBox, box_state, head_of_start_print, tail

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(ROOT, "packages", "k1-control-v1", "spool-choice-gate-v1",
                      "kctrl_print_gate.py")


def load_module():
    # The gate finds the slot map module under the name Klipper gives it.
    sys.modules["extras.kctrl_slot_map"] = SLOT_MAP_MOD
    spec = importlib.util.spec_from_file_location("kctrl_print_gate", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = load_module()

# Bobines chargées le 10 septembre : (fiche, couleur CFS).
LOADED = {"T1B": ("000001", "0000000"), "T1D": ("000001", "0ffffff"),
          "T2A": ("000001", "0ff1e1e"), "T2B": ("000001", "000a3ff"),
          "T2C": ("000003", "0ffffff"), "T2D": ("000001", "0b2a1e1")}
GROUPS = [["000001", "0000000", ["T1B"], "PLA"], ["000001", "0ffffff", ["T1D"], "PLA"],
          ["000001", "0ff1e1e", ["T2A"], "PLA"], ["000001", "000a3ff", ["T2B"], "PLA"],
          ["000003", "0ffffff", ["T2C"], "PETG"], ["000001", "0b2a1e1", ["T2D"], "PLA"]]


class FakeGcode:
    """Le registre de commandes de Klipper, avec le retour de l'ancien handler."""

    def __init__(self):
        self.commands = {}
        self.raw = []
        self.scripts = []
        self.fail_prefix = None

    def register_command(self, name, func, when_not_ready=False, desc=None):
        if func is None:
            return self.commands.pop(name, None)
        self.commands[name] = func

    def respond_raw(self, message):
        self.raw.append(message)

    def respond_info(self, message):
        self.raw.append("// " + message)

    def run_script_from_command(self, script):
        if self.fail_prefix and script.startswith(self.fail_prefix):
            raise RuntimeError("refuse: %s" % script)
        self.scripts.append(script)


class FakeReactor:
    def __init__(self):
        self.pauses = 0

    def monotonic(self):
        return 0.0

    def pause(self, until):
        self.pauses += 1


class FakePrinter:
    def __init__(self):
        self.gcode = FakeGcode()
        self.reactor = FakeReactor()
        self.objects = {"gcode": self.gcode}
        self.handlers = {}

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)

    def get_reactor(self):
        return self.reactor

    def register_event_handler(self, name, func):
        self.handlers.setdefault(name, []).append(func)

    def fire(self, name):
        for func in self.handlers.get(name, []):
            func()


class FakeConfig:
    def __init__(self, page=None):
        self.printer = FakePrinter()
        self.page = page

    def get_printer(self):
        return self.printer

    def get(self, key, default=None):
        if key == "page" and self.page is not None:
            return self.page
        return default


class FakeStats:
    def __init__(self, state="standby", filename=""):
        self.state = state
        self.filename = filename

    def get_status(self, eventtime=None):
        return {"state": self.state, "filename": self.filename}


class FakeSdcard:
    def __init__(self, folder, active=False):
        self.sdcard_dirname = folder
        self.active = active

    def is_active(self):
        return self.active


class FakeSlotMap:
    def __init__(self, table=None):
        self.types = {"000001": "PLA", "000003": "PETG"}
        self.map = dict(table or {"T1A": "T1A", "T1B": "T1B"})
        self.stamp = "old"
        self.refreshed = 0

    def refresh(self):
        self.refreshed += 1

    def refresh_temps(self):
        pass


class FakeGcmd:
    def __init__(self, line="", **params):
        self.line = line
        self.params = params
        self.said = []
        self.error = GcmdError

    def get_commandline(self):
        return self.line

    def get_command_parameters(self):
        return dict(self.params)

    def get(self, name, default=None):
        return self.params.get(name, default)

    def respond_info(self, message):
        self.said.append(message)


def stock_handler(gcmd):
    stock_handler.calls.append(gcmd)


stock_handler.calls = []


def machine(tmp_path, body="T0\nG1 X1\n", file_tail=None, state="standby",
            loaded=LOADED, groups=GROUPS, sd_active=False, connect=True, page=None):
    """Une porte connectée sur une machine avec un fichier, une box, une table."""
    config = FakeConfig(page)
    printer = config.printer
    printer.gcode.commands["SDCARD_PRINT_FILE"] = stock_handler
    gate = MOD.load_config(config)
    printer.objects["print_stats"] = FakeStats(state)
    printer.objects["virtual_sdcard"] = FakeSdcard(str(tmp_path), sd_active)
    printer.objects["box"] = FakeBox(box_state(loaded, groups))
    printer.objects["kctrl_slot_map"] = FakeSlotMap()
    gcode(tmp_path, body + (tail() if file_tail is None else file_tail))
    if connect:
        printer.fire("klippy:connect")
    return gate


def start(gate, filename="job.gcode", extra="", **params):
    line = 'SDCARD_PRINT_FILE FILENAME="%s"%s' % (filename, extra)
    gcmd = FakeGcmd(line, FILENAME=filename, **params)
    gate.printer.gcode.commands["SDCARD_PRINT_FILE"](gcmd)
    return gcmd


def confirm(gate, **params):
    gcmd = FakeGcmd("KCTRL_GATE_CONFIRM", **params)
    gate.cmd_KCTRL_GATE_CONFIRM(gcmd)
    return gcmd


# --- parse_map ----------------------------------------------------------------


def test_parse_map_reads_pairs_in_any_case_with_spaces():
    assert MOD.parse_map("T1A:T2D,T1B:T1B") == {"T1A": "T2D", "T1B": "T1B"}
    assert MOD.parse_map(" t1a:t2d , t1b : t1b ".replace(" : ", ":")) == {"T1A": "T2D", "T1B": "T1B"}


@pytest.mark.parametrize("text,fragment", [
    ("T1A-T2D", "illisible"),
    ("T1A:T5A", "illisible"),
    ("T1A:T2D,T1A:T1B", "deux fois"),
    ("", "MAP vide"),
    (None, "MAP vide"),
])
def test_parse_map_refuses_with_a_reason(text, fragment):
    with pytest.raises(ValueError) as caught:
        MOD.parse_map(text)
    assert fragment in str(caught.value)


# --- scan_used_tools ------------------------------------------------------------


def test_scan_finds_tools_in_order_of_first_use_and_ignores_lookalikes(tmp_path):
    path = gcode(tmp_path, "T1 ; first\nG1 X1\nT0\nM104 T3 S200\n; T5 in a comment\nT1\n  T2  \n")
    assert MOD.scan_used_tools(path) == ([1, 0, 2], "3 filament(s) utilise(s)")


def test_scan_without_tool_is_mono_filament_on_the_first(tmp_path):
    path = gcode(tmp_path, "G1 X1\nG1 X2\n")
    assert MOD.scan_used_tools(path) == ([0], "aucun T dans le fichier, mono-filament")


def test_scan_of_a_missing_file_says_so():
    used, note = MOD.scan_used_tools("/nulle/part.gcode")
    assert used is None
    assert "illisible" in note


def test_scan_reads_across_chunk_boundaries_and_breathes(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "CHUNK", 8)
    path = gcode(tmp_path, "G1 X1 Y1\nT7\nG1 X2\nT12\n")
    breaths = []
    used, _ = MOD.scan_used_tools(path, lambda: breaths.append(1))
    assert used == [7, 12]
    assert len(breaths) > 4


def test_scan_handles_crlf_and_a_last_line_without_newline(tmp_path):
    path = tmp_path / "crlf.gcode"
    path.write_bytes(b"G1 X1\r\nT4\r\nG1 X2\r\nT2")
    assert MOD.scan_used_tools(str(path))[0] == [4, 2]


# --- prise de la commande -------------------------------------------------------


def test_the_takeover_waits_for_connect_and_keeps_the_stock_handler(tmp_path):
    gate = machine(tmp_path, connect=False)
    commands = gate.printer.gcode.commands
    assert commands["SDCARD_PRINT_FILE"] is stock_handler
    assert gate.get_status()["wrapped"] == 0
    gate.printer.fire("klippy:connect")
    assert commands["SDCARD_PRINT_FILE"] == gate.cmd_SDCARD_PRINT_FILE
    assert commands[MOD.STOCK] is stock_handler
    assert gate.get_status()["wrapped"] == 1
    for name in ("KCTRL_GATE_CONFIRM", "KCTRL_GATE_CANCEL", "KCTRL_GATE"):
        assert name in commands


def test_no_stock_handler_means_no_gate_and_no_crash(tmp_path):
    gate = machine(tmp_path, connect=False)
    del gate.printer.gcode.commands["SDCARD_PRINT_FILE"]
    gate.printer.fire("klippy:connect")
    assert gate.get_status()["wrapped"] == 0
    assert "SDCARD_PRINT_FILE" not in gate.printer.gcode.commands


def test_the_page_address_comes_from_the_config(tmp_path):
    gate = machine(tmp_path, page="http://192.168.1.64:4409/bobines/")
    assert gate.get_status()["page"] == "http://192.168.1.64:4409/bobines/"
    assert machine(tmp_path).get_status()["page"] == "/bobines/"


# --- un depart attend ----------------------------------------------------------------


def test_a_start_is_held_nothing_runs_and_mainsail_is_told(tmp_path):
    gate = machine(tmp_path)
    gcmd = start(gate)
    assert gate.printer.gcode.scripts == []
    assert stock_handler.calls == []
    status = gate.get_status()
    assert status["pending"] == 1
    assert status["name"] == "job.gcode"
    assert status["file"] == os.path.join(str(tmp_path), "job.gcode")
    assert status["used_count"] == 1
    assert status["declared_count"] == 2
    assert "attend le choix des bobines" in gcmd.said[0]
    assert "Rien ne chauffe" in gcmd.said[0]
    raw = gate.printer.gcode.raw
    assert raw[0] == "// action:prompt_begin Choix des bobines"
    assert any("KCTRL_GATE_CANCEL" in line for line in raw)
    assert raw[-1] == "// action:prompt_show"


def test_the_status_lists_filaments_with_their_exact_and_same_type_spools(tmp_path):
    gate = machine(tmp_path)
    start(gate)
    filaments = gate.get_status()["filaments"]
    assert [f["logical"] for f in filaments] == ["T1A", "T1B"]
    black, blue = filaments
    assert (black["type"], black["colour"], black["used"], black["declared"]) == ("PLA", "000000", 1, 1)
    assert black["exact"] == ["T1B"]
    assert black["same_type"] == ["T1B", "T1D", "T2A", "T2B", "T2D"]
    assert (blue["colour"], blue["used"], blue["exact"]) == ("8080FF", 0, [])


def test_the_status_lists_every_slot_of_every_connected_unit(tmp_path):
    gate = machine(tmp_path)
    status = gate.get_status()
    assert status["units"] == ["T1", "T2"]
    assert sorted(status["slots"]) == ["T1A", "T1B", "T1C", "T1D", "T2A", "T2B", "T2C", "T2D"]
    assert status["slots"]["T1A"] == {"loaded": 0, "type": "", "colour": "", "material": "", "remain": -1}
    assert status["slots"]["T2C"]["type"] == "PETG"
    assert status["slots"]["T2C"]["colour"] == "FFFFFF"
    assert status["slots"]["T2D"]["colour"] == "B2A1E1"
    assert status["table"] == {"T1A": "T1A", "T1B": "T1B"}


def test_a_used_filament_the_file_does_not_declare_is_listed_as_used_only(tmp_path):
    gate = machine(tmp_path, body="T0\nT2\n")
    start(gate)
    filaments = gate.get_status()["filaments"]
    assert [(f["logical"], f["declared"], f["used"]) for f in filaments] == [
        ("T1A", 1, 1), ("T1B", 1, 0), ("T1C", 0, 1)]


def test_a_file_without_config_block_still_waits_on_its_used_tools(tmp_path):
    gate = machine(tmp_path, body="T1\nG1 X1\n", file_tail="")
    gcmd = start(gate)
    status = gate.get_status()
    assert status["pending"] == 1
    assert [(f["logical"], f["type"], f["colour"]) for f in status["filaments"]] == [("T1B", "", "")]
    assert "pas de bloc de configuration" in gcmd.said[0]


def test_a_second_start_replaces_the_first_and_forgets_any_confirmation(tmp_path):
    gate = machine(tmp_path)
    start(gate)
    confirm(gate, MAP="T1A:T1B")
    assert gate.get_status()["confirmed_name"] == "job.gcode"
    gcode(tmp_path, "T1\n" + tail(), name="other.gcode")
    start(gate, "other.gcode")
    status = gate.get_status()
    assert status["name"] == "other.gcode"
    assert status["confirmed_file"] == ""


# --- ce qui passe sans attendre ----------------------------------------------------


def test_a_power_loss_resume_goes_straight_to_the_stock_start(tmp_path):
    gate = machine(tmp_path)
    start(gate, extra=" ISCONTINUEPRINT=1", ISCONTINUEPRINT="1")
    assert gate.printer.gcode.scripts == [MOD.STOCK + ' FILENAME="job.gcode" ISCONTINUEPRINT=1']
    assert gate.get_status()["pending"] == 0
    assert "reprise apres coupure" in gate.get_status()["last"]


@pytest.mark.parametrize("state", ["printing", "paused"])
def test_a_start_during_a_print_is_left_to_the_stock_refusal(tmp_path, state):
    gate = machine(tmp_path, state=state)
    start(gate)
    assert gate.printer.gcode.scripts == [MOD.STOCK + ' FILENAME="job.gcode"']
    assert gate.get_status()["pending"] == 0


def test_a_busy_sd_card_is_left_to_the_stock_refusal(tmp_path):
    gate = machine(tmp_path, sd_active=True)
    start(gate)
    assert gate.printer.gcode.scripts == [MOD.STOCK + ' FILENAME="job.gcode"']


def test_a_missing_file_is_left_to_the_stock_refusal(tmp_path):
    gate = machine(tmp_path)
    start(gate, "absent.gcode")
    assert gate.printer.gcode.scripts == [MOD.STOCK + ' FILENAME="absent.gcode"']
    assert gate.get_status()["pending"] == 0


def test_the_command_line_is_replayed_as_is_with_its_quotes_and_flags(tmp_path):
    gate = machine(tmp_path, state="printing")
    line = 'SDCARD_PRINT_FILE FILENAME="a b/c.gcode" FIRST_FLOOR_PRINT=1'
    gcmd = FakeGcmd(line, FILENAME="a b/c.gcode", FIRST_FLOOR_PRINT="1")
    gate.cmd_SDCARD_PRINT_FILE(gcmd)
    assert gate.printer.gcode.scripts == [MOD.STOCK + ' FILENAME="a b/c.gcode" FIRST_FLOOR_PRINT=1']


def test_a_leading_slash_resolves_like_the_stock_handler(tmp_path):
    gate = machine(tmp_path)
    start(gate, "/job.gcode")
    assert gate.get_status()["file"] == os.path.join(str(tmp_path), "job.gcode")


# --- confirmer --------------------------------------------------------------------


def test_confirm_writes_the_choice_with_the_two_commands_then_starts(tmp_path):
    gate = machine(tmp_path)
    start(gate)
    gcmd = confirm(gate, MAP="T1A:T2D", FILE="job.gcode")
    assert gate.printer.gcode.scripts == [
        "BOX_MODIFY_TN T1A=T2D",
        "SAVE_VARIABLE VARIABLE=slot_choice_t1a VALUE='\"T2D\"'",
        "SAVE_VARIABLE VARIABLE=slot_last_choice VALUE='\"T2D\"'",
        MOD.STOCK + ' FILENAME="job.gcode"',
    ]
    status = gate.get_status()
    assert status["pending"] == 0
    assert status["confirmed_file"] == os.path.join(str(tmp_path), "job.gcode")
    assert status["confirmed_name"] == "job.gcode"
    assert status["confirmed_map"] == {"T1A": "T2D"}
    assert gate.printer.gcode.raw[-1] == "// action:prompt_end"
    assert "T2D" in gcmd.said[0] and "impression lancee" in gcmd.said[0]
    assert gate.printer.objects["kctrl_slot_map"].stamp is None


def test_confirm_writes_every_filament_in_slot_order_a_declared_one_included(tmp_path):
    gate = machine(tmp_path)
    start(gate)
    gcmd = confirm(gate, MAP="T1B:T2A,T1A:T1B")
    scripts = gate.printer.gcode.scripts
    assert scripts[0] == "BOX_MODIFY_TN T1A=T1B"
    assert scripts[3] == "BOX_MODIFY_TN T1B=T2A"
    assert scripts[4] == "SAVE_VARIABLE VARIABLE=slot_choice_t1b VALUE='\"T2A\"'"
    assert scripts[-1].startswith(MOD.STOCK)
    assert "declare mais non utilise" in gcmd.said[0]


def test_confirm_accepts_the_full_path_as_file_and_any_case_in_map(tmp_path):
    gate = machine(tmp_path)
    start(gate)
    confirm(gate, MAP="t1a:t1b", FILE=os.path.join(str(tmp_path), "job.gcode"))
    assert gate.printer.gcode.scripts[0] == "BOX_MODIFY_TN T1A=T1B"


@pytest.mark.parametrize("params,fragment", [
    ({"MAP": "T1A:T1B", "FILE": "autre.gcode"}, "rechargez la page"),
    ({"MAP": "n'importe quoi"}, "illisible"),
    ({"MAP": "T1B:T2D"}, "sans bobine: T1A"),
    ({"MAP": "T1A:T1B,T1C:T2D"}, "pas de filament T1C"),
    ({"MAP": "T1A:T1A"}, "vide"),
    ({"MAP": "T1A:T3A"}, "vide"),
])
def test_confirm_refuses_before_any_write(tmp_path, params, fragment):
    gate = machine(tmp_path)
    start(gate)
    with pytest.raises(GcmdError) as caught:
        confirm(gate, **params)
    assert fragment in str(caught.value)
    assert gate.printer.gcode.scripts == []
    assert gate.get_status()["pending"] == 1


def test_confirm_with_nothing_pending_is_a_refusal(tmp_path):
    gate = machine(tmp_path)
    with pytest.raises(GcmdError) as caught:
        confirm(gate, MAP="T1A:T1B")
    assert "aucune impression n'attend" in str(caught.value)


@pytest.mark.parametrize("state", ["printing", "paused"])
def test_confirm_during_a_print_refuses_and_keeps_the_choice_pending(tmp_path, state):
    gate = machine(tmp_path)
    start(gate)
    gate.printer.objects["print_stats"].state = state
    with pytest.raises(GcmdError) as caught:
        confirm(gate, MAP="T1A:T1B")
    assert "impression en cours" in str(caught.value)
    assert gate.printer.gcode.scripts == []


def test_a_stock_start_that_fails_forgets_the_confirmation(tmp_path):
    gate = machine(tmp_path)
    start(gate)
    gate.printer.gcode.fail_prefix = MOD.STOCK
    with pytest.raises(RuntimeError):
        confirm(gate, MAP="T1A:T1B")
    status = gate.get_status()
    assert status["confirmed_file"] == ""
    assert status["pending"] == 0
    assert "echoue" in status["last"]


def test_a_table_write_that_fails_keeps_the_file_waiting_and_nothing_confirmed(tmp_path):
    gate = machine(tmp_path)
    start(gate)
    gate.printer.gcode.fail_prefix = "BOX_MODIFY_TN"
    with pytest.raises(RuntimeError):
        confirm(gate, MAP="T1A:T1B")
    status = gate.get_status()
    assert status["pending"] == 1
    assert status["confirmed_file"] == ""
    assert not any(script.startswith(MOD.STOCK) for script in gate.printer.gcode.scripts)


# --- abandonner ----------------------------------------------------------------------


def test_cancel_forgets_the_file_and_closes_the_prompt(tmp_path):
    gate = machine(tmp_path)
    start(gate)
    gcmd = FakeGcmd()
    gate.cmd_KCTRL_GATE_CANCEL(gcmd)
    assert gate.get_status()["pending"] == 0
    assert gate.printer.gcode.raw[-1] == "// action:prompt_end"
    assert "abandonnee" in gcmd.said[0]
    assert gate.printer.gcode.scripts == []


def test_cancel_with_nothing_pending_just_says_so(tmp_path):
    gate = machine(tmp_path)
    gcmd = FakeGcmd()
    gate.cmd_KCTRL_GATE_CANCEL(gcmd)
    assert gcmd.said == ["K1 Control: aucune impression en attente"]


def test_the_console_report_names_the_file_its_filaments_and_the_slots(tmp_path):
    gate = machine(tmp_path)
    start(gate)
    gcmd = FakeGcmd()
    gate.cmd_KCTRL_GATE(gcmd)
    text = gcmd.said[0]
    assert "porte de depart active" in text
    assert "en attente: job.gcode" in text
    assert "filament 1 (T1A) PLA 000000, identiques: T1B" in text
    assert "T1A vide" in text
    assert "T2C PETG FFFFFF" in text


# --- START_PRINT lit la confirmation ---------------------------------------------------


def render_with_gate(params, slot_map, gate):
    raised = {}

    def action_raise_error(message):
        raised["message"] = message
        raise jinja2.TemplateError(message)

    template = ENV.from_string(head_of_start_print())
    printer = {"gcode_macro _KCTRL_START_CONF": {},
               "kctrl_slot_map": slot_map,
               "kctrl_print_gate": gate,
               "save_variables": {"variables": {}}}
    try:
        text = template.render(params={"BED_TEMP": "60", "EXTRUDER_TEMP": "220", **params},
                               printer=printer, action_raise_error=action_raise_error,
                               action_respond_info=lambda m: "")
    except jinja2.TemplateError:
        return None, raised["message"]
    return text.strip().splitlines()[-1], ""


SLOT_MAP = {"initial_logical": "T1A", "initial_note": "", "job_count": 2,
            "job_file": "/usr/data/printer_data/gcodes/job.gcode",
            "map": {"T1A": "T2D", "T1B": "T1B"},
            "match": {"T1A": "T1B"},
            "match_notes": ["filament 1 (T1A) PLA 000000 -> T1B",
                            "filament 2 (T1B) PLA 8080FF: aucune bobine"]}


def test_start_print_takes_the_table_as_written_when_the_gate_confirmed_this_file():
    gate = {"confirmed_file": SLOT_MAP["job_file"], "pending": 0}
    line, error = render_with_gate({}, SLOT_MAP, gate)
    assert error == ""
    assert line == "T1A|T2D|raccorde sur la page Bobines"


def test_start_print_matches_by_colour_when_the_gate_confirmed_another_file():
    gate = {"confirmed_file": "/usr/data/printer_data/gcodes/autre.gcode"}
    line, _ = render_with_gate({}, SLOT_MAP, gate)
    assert line == "T1A|T1B|appariement sur le fichier, type et couleur"


def test_start_print_matches_by_colour_without_any_gate():
    template = ENV.from_string(head_of_start_print())
    printer = {"gcode_macro _KCTRL_START_CONF": {}, "kctrl_slot_map": SLOT_MAP,
               "save_variables": {"variables": {}}}
    text = template.render(params={"BED_TEMP": "60", "EXTRUDER_TEMP": "220"},
                           printer=printer, action_raise_error=lambda m: "",
                           action_respond_info=lambda m: "")
    assert text.strip().splitlines()[-1] == "T1A|T1B|appariement sur le fichier, type et couleur"


def test_match_one_forces_the_colour_match_even_after_the_page():
    gate = {"confirmed_file": SLOT_MAP["job_file"]}
    line, _ = render_with_gate({"MATCH": "1"}, SLOT_MAP, gate)
    assert line == "T1A|T1B|appariement sur le fichier, type et couleur"


def test_the_section_is_declared_after_the_tool_change_wrapper():
    with open(os.path.join(ROOT, "packages", "k1-control-v1", "owned-start-print-v2",
                           "k1-control-owned-start-print-v2.cfg"), encoding="utf-8") as handle:
        text = handle.read()
    assert text.index("[kctrl_tool_change]") < text.index("[kctrl_print_gate]")
    section = text[text.index("[kctrl_print_gate]"):].split("\n\n", 1)[0]
    assert "page: http://192.168.1.64:4409/bobines/" in section
