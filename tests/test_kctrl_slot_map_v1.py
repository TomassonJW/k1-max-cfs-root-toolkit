"""La table de correspondance du CFS, lue telle que le firmware l'écrit.

`tnn_map` vit dans `tn_data.json` et nulle part ailleurs : l'objet `box` de
Klipper ne l'expose pas. Le popup de l'écran l'écrit, un rechargement
automatique la réécrit, `KCTRL_SLOT` aussi. `START_PRINT` la lit pour savoir
sur quelle bobine partir, donc une lecture qui ment fait imprimer la mauvaise
couleur sans rien dire.

Ce qui est épinglé ici : le contenu réel relevé sur la machine le 2 septembre,
le rafraîchissement quand le fichier change, et le refus de fabriquer une
réponse quand le fichier est absent, illisible ou abîmé.
"""

import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(ROOT, "packages", "k1-control-v1", "owned-start-print-v2",
                      "kctrl_slot_map.py")

# Relevé sur la machine, `cat tn_data.json`, 2026-09-02.
LIVE_MAP = {"T%d%s" % (b, s): "T%d%s" % (b, s)
            for b in (1, 2, 3, 4) for s in "ABCD"}


def load_module():
    spec = importlib.util.spec_from_file_location("kctrl_slot_map", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["kctrl_slot_map"] = module
    spec.loader.exec_module(module)
    return module


MOD = load_module()


class FakeGcode:
    def __init__(self):
        self.commands = {}

    def register_command(self, name, callback, desc=None):
        self.commands[name] = callback


class FakePrinter:
    def __init__(self):
        self.gcode = FakeGcode()
        self.objects = {"gcode": self.gcode}

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)

    def get_reactor(self):
        raise AssertionError("le rafraichissement ne doit pas toucher au reacteur")


class FakeConfig:
    def __init__(self, path):
        self.path = path
        self.printer = FakePrinter()

    def get_printer(self):
        return self.printer

    def get(self, key, default=None):
        return self.path if key == "path" else default


def build(tmp_path, payload, name="tn_data.json"):
    target = tmp_path / name
    if payload is not None:
        target.write_text(json.dumps(payload), encoding="utf-8")
    return MOD.load_config(FakeConfig(str(target))), target


@pytest.fixture
def live(tmp_path):
    obj, target = build(tmp_path, {"base_data": {}, "tnn_map": dict(LIVE_MAP)})
    return obj, target


def test_the_machine_table_reads_back_exactly(live):
    obj, _ = live
    status = obj.get_status()
    assert status["map"] == LIVE_MAP
    assert status["loaded"] == 1
    assert status["error"] == ""


def test_a_remapped_entry_survives_the_read(tmp_path):
    table = dict(LIVE_MAP)
    table["T1A"] = "T2C"
    obj, _ = build(tmp_path, {"tnn_map": table})
    assert obj.get_status()["map"]["T1A"] == "T2C"


def test_a_rewritten_file_is_picked_up(live):
    obj, target = live
    assert obj.get_status()["map"]["T1A"] == "T1A"
    table = dict(LIVE_MAP)
    table["T1A"] = "T2B"
    target.write_text(json.dumps({"tnn_map": table}), encoding="utf-8")
    # Le cache est indexe sur (mtime, taille) et la taille ne bouge pas ici.
    # L'horodatage est avance a la main pour ne pas faire dependre le test de
    # la resolution du systeme de fichiers.
    stamp = os.stat(str(target))
    os.utime(str(target), (stamp.st_atime + 5, stamp.st_mtime + 5))
    assert obj.get_status()["map"]["T1A"] == "T2B"


def test_a_missing_file_reports_instead_of_guessing(tmp_path):
    obj, _ = build(tmp_path, None)
    status = obj.get_status()
    assert status["map"] == {}
    assert status["loaded"] == 0
    assert "absent" in status["error"]


def test_a_truncated_file_reports_instead_of_guessing(tmp_path):
    obj, target = build(tmp_path, {"tnn_map": dict(LIVE_MAP)})
    target.write_text('{"tnn_map": {"T1A": "T1', encoding="utf-8")
    status = obj.get_status()
    assert status["map"] == {}
    assert "lecture impossible" in status["error"]


def test_a_file_without_the_key_reports_instead_of_guessing(tmp_path):
    obj, _ = build(tmp_path, {"base_data": {}})
    status = obj.get_status()
    assert status["map"] == {}
    assert status["error"] == "tnn_map vide"


@pytest.mark.parametrize("entry", [
    {"T1A": "T5A"},      # boitier hors plage
    {"T1A": "T1E"},      # position hors plage
    {"T1A": "T1"},       # tronque
    {"T1A": 3},          # pas une chaine
    {"X1A": "T1A"},      # cle qui n'est pas un emplacement
])
def test_a_damaged_entry_is_dropped_not_propagated(tmp_path, entry):
    table = dict(LIVE_MAP)
    table.update(entry)
    obj, _ = build(tmp_path, {"tnn_map": table})
    values = obj.get_status()["map"]
    (key, value), = entry.items()
    # L'entree abimee disparait, les autres restent lisibles.
    assert values.get(key) != value
    assert all(k in MOD.NAMES and v in MOD.NAMES for k, v in values.items())
    assert len(values) >= 15


def test_nothing_here_writes(live):
    obj, target = live
    before = target.read_bytes()
    obj.get_status()
    obj.get_status()
    assert target.read_bytes() == before


# ------------------------------------------- le filament sur lequel on demarre
#
# Un fichier peut declarer seize filaments et n'en imprimer qu'un. Celui du
# 9 septembre en declarait deux et n'emettait qu'un seul `T1`, son second. Le
# demarrage chargeait le premier : le Geeetech noir de T1B a ete charge et purge
# pour un travail qui voulait l'eSUN de T2D, et le `T1` qui suivait est devenu un
# changement d'outil en plein demarrage, fini en `macro_box_extrude_err`.

ENTETE = "\n".join([
    "; nozzle_temperature_initial_layer = 190,220",
    "; filament: 2",
    "; EXECUTABLE_BLOCK_START",
    "START_PRINT EXTRUDER_TEMP=220 BED_TEMP=55",
    "M104 S220",
    "M83 ; use relative distances for extrusion",
])


def gcode(tmp_path, corps, name="job.gcode"):
    target = tmp_path / name
    target.write_text(ENTETE + "\n" + corps + "\n", encoding="utf-8")
    return str(target)


@pytest.mark.parametrize("ligne,attendu", [
    ("T0", 0),
    ("T1", 1),
    ("T15", 15),
    ("T1 ; set nozzle temperature", 1),
    ("  T3  ", 3),
])
def test_the_initial_tool_is_read_from_the_file(tmp_path, ligne, attendu):
    index, note = MOD.scan_initial_tool(gcode(tmp_path, ligne))
    assert index == attendu
    assert note == "premier T du fichier"


def test_only_the_first_tool_command_counts(tmp_path):
    # Les suivants sont les changements de couleur du travail, pas son depart.
    index, _ = MOD.scan_initial_tool(gcode(tmp_path, "T5\nG1 X1\nT2\nT9"))
    assert index == 5


def test_a_file_without_a_tool_command_starts_on_the_first_filament(tmp_path):
    index, note = MOD.scan_initial_tool(gcode(tmp_path, "G1 X1 Y1"))
    assert index == 0
    assert "mono-filament" in note


@pytest.mark.parametrize("ligne", [
    "; T1",                       # en commentaire
    "TEMPERATURE_WAIT SENSOR=extruder MAXIMUM=45",
    "M104 T1 S200",               # pas en debut de ligne
    "T",                          # pas de numero
])
def test_what_is_not_a_tool_command_is_not_read_as_one(tmp_path, ligne):
    index, note = MOD.scan_initial_tool(gcode(tmp_path, ligne))
    assert index == 0
    assert "mono-filament" in note


def test_a_tool_beyond_the_cfs_is_refused_not_wrapped(tmp_path):
    # Seize emplacements, T0 a T15. T16 n'existe pas : repondre 0 ferait
    # charger la premiere bobine pour un travail qui en demande une autre.
    index, note = MOD.scan_initial_tool(gcode(tmp_path, "T16"))
    assert index == -1
    assert "16" in note


def test_an_unreadable_file_reports_instead_of_guessing(tmp_path):
    index, note = MOD.scan_initial_tool(str(tmp_path / "absent.gcode"))
    assert index == -1
    assert "illisible" in note


def test_the_tool_command_is_found_past_the_first_chunk(tmp_path):
    # Le fichier est lu par blocs : un `T` a cheval sur deux blocs, ou tres
    # loin dans l'entete, doit sortir pareil.
    corps = "\n".join(["G1 X%d" % i for i in range(20000)] + ["T7"])
    index, _ = MOD.scan_initial_tool(gcode(tmp_path, corps))
    assert index == 7


@pytest.mark.parametrize("index,logical", [
    (0, "T1A"), (1, "T1B"), (3, "T1D"), (4, "T2A"), (15, "T4D"),
])
def test_the_sixteen_filaments_map_onto_the_sixteen_slots(index, logical):
    assert MOD.logical_of_index(index) == logical


@pytest.mark.parametrize("index", [-1, 16, 99, None, "1"])
def test_a_filament_number_outside_the_cfs_has_no_logical_name(index):
    assert MOD.logical_of_index(index) == ""


class FakeSdcard:
    def __init__(self, path):
        self.path = path

    def get_status(self, eventtime=None):
        return {"file_path": self.path}


def test_the_status_names_the_slot_the_job_starts_on(tmp_path):
    table = dict(LIVE_MAP)
    table["T1A"] = "T1B"
    table["T1B"] = "T2D"
    obj, _ = build(tmp_path, {"tnn_map": table})
    obj.printer.objects["virtual_sdcard"] = FakeSdcard(gcode(tmp_path, "T1"))
    status = obj.get_status()
    assert status["initial_index"] == 1
    assert status["initial_logical"] == "T1B"
    # L'emplacement reellement charge : celui du 9 septembre, T2D et pas T1B.
    assert status["initial_slot"] == "T2D"


def test_the_file_is_scanned_once_and_re_read_when_it_changes(tmp_path):
    obj, _ = build(tmp_path, {"tnn_map": dict(LIVE_MAP)})
    path = gcode(tmp_path, "T2")
    obj.printer.objects["virtual_sdcard"] = FakeSdcard(path)
    assert obj.get_status()["initial_index"] == 2

    calls = []
    reel = MOD.scan_initial_tool
    MOD.scan_initial_tool = lambda p, **kw: (calls.append(p), reel(p, **kw))[1]
    try:
        obj.get_status()
        obj.get_status()
        assert calls == [], "un fichier inchange ne doit pas etre relu"
        gcode(tmp_path, "T4")
        stamp = os.stat(path)
        os.utime(path, (stamp.st_atime + 5, stamp.st_mtime + 5))
        assert obj.get_status()["initial_index"] == 4
        assert len(calls) == 1
    finally:
        MOD.scan_initial_tool = reel


def test_no_file_running_means_the_first_filament(tmp_path):
    obj, _ = build(tmp_path, {"tnn_map": dict(LIVE_MAP)})
    status = obj.get_status()
    assert status["initial_logical"] == "T1A"
    assert status["initial_file"] == ""
    assert "aucun fichier" in status["initial_note"]
