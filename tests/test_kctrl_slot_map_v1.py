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
    def __init__(self, path, material_db=None):
        self.path = path
        self.material_db = material_db
        self.printer = FakePrinter()

    def get_printer(self):
        return self.printer

    def get(self, key, default=None):
        if key == "path":
            return self.path
        if key == "material_db":
            return self.material_db if self.material_db is not None else default
        return default


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


# --- Le contrôle avant impression -------------------------------------------
#
# START_PRINT ne charge que le filament de départ. Tout ce qui suit passe par le
# `cmd_T` d'origine, qui échoue en plein milieu — quatre heures plus tard — si
# un filament pointe sur un emplacement vide ou sur une unité absente. Ce
# contrôle pose la question avant, et ne coûte qu'une lecture du fichier.


class FakeReactor:
    def monotonic(self):
        return 0.0


class FakeBox:
    """L'objet `box` publie toujours T1 à T4, connectés ou non.

    Relevé sur la machine le 9 septembre : les unités absentes rendent
    `state: "None"` et `material_type: ["-1", ...]`.
    """

    def __init__(self, connected=("1", "2")):
        self.connected = connected

    def get_status(self, eventtime=None):
        state = {}
        for unit in ("1", "2", "3", "4"):
            present = unit in self.connected
            state["T" + unit] = {
                "state": "connect" if present else "None",
                "material_type": (["00001"] * 4 if present else ["-1"] * 4),
                "color_value": (["0ffffff"] * 4 if present else ["-1"] * 4),
            }
        return state


class GcmdError(Exception):
    pass


class FakeGcmd:
    def __init__(self, **params):
        self.params = params
        self.said = []
        self.error = GcmdError

    def get(self, name, default=None):
        return self.params.get(name, default)

    def respond_info(self, message):
        self.said.append(message)


def checker(tmp_path, table, connected=("1", "2")):
    obj, _ = build(tmp_path, {"base_data": {}, "tnn_map": table})
    obj.printer.objects["box"] = FakeBox(connected)
    obj.printer.get_reactor = lambda: FakeReactor()
    return obj


def test_every_tool_of_the_file_is_collected_in_order_of_first_use(tmp_path):
    path = gcode(tmp_path, "\n".join(["T0", "G1 X1", "T3", "T0", "T1"]))
    used, note = MOD.scan_all_tools(path)
    assert used == [0, 3, 1]
    assert "3 filament" in note


def test_a_colour_change_on_the_last_line_is_still_seen(tmp_path):
    """Le dernier bloc n'est pas terminé par une fin de ligne dans tous les
    fichiers ; le reste du tampon doit être examiné lui aussi."""
    target = tmp_path / "fin.gcode"
    target.write_text(ENTETE + "\nT0\nG1 X1\nT2", encoding="utf-8")
    used, _ = MOD.scan_all_tools(str(target))
    assert used == [0, 2]


def test_a_file_without_a_tool_command_uses_the_first_filament(tmp_path):
    used, note = MOD.scan_all_tools(gcode(tmp_path, "G1 X1"))
    assert used == [0]
    assert "mono-filament" in note


def test_an_unreadable_file_is_reported_not_guessed(tmp_path):
    used, note = MOD.scan_all_tools(str(tmp_path / "absent.gcode"))
    assert used is None
    assert "illisible" in note


def test_eighteen_filaments_are_seen_as_eighteen_not_wrapped(tmp_path):
    """Un fichier tranché pour dix-huit bobines existe ; le CFS s'arrête à
    seize. T16 et T17 doivent être lus comme tels pour être refusés, pas
    ramenés dans l'intervalle."""
    path = gcode(tmp_path, "\n".join("T%d" % i for i in range(18)))
    used, _ = MOD.scan_all_tools(path)
    assert used == list(range(18))


def test_the_check_passes_when_every_filament_points_at_a_loaded_spool(tmp_path):
    obj = checker(tmp_path, {"T1A": "T1B", "T1B": "T2D"})
    obj.printer.objects["virtual_sdcard"] = FakeSdcard(
        gcode(tmp_path, "\n".join(["T0", "T1"])))
    gcmd = FakeGcmd()
    obj.cmd_KCTRL_CHECK(gcmd)
    report = gcmd.said[0]
    assert "tout est en place" in report
    assert "filament 1 (T1A) -> T1B" in report
    assert "filament 2 (T1B) -> T2D" in report
    assert "<== charge au depart" in report


def test_the_check_names_the_unit_that_is_not_plugged_in(tmp_path):
    """Deux CFS branchés, un travail qui veut T3C : l'impression partirait et
    mourrait au premier changement de couleur."""
    obj = checker(tmp_path, {"T1A": "T1B", "T1B": "T3C"})
    gcmd = FakeGcmd(FILE=gcode(tmp_path, "\n".join(["T0", "T1"])))
    obj.cmd_KCTRL_CHECK(gcmd)
    report = gcmd.said[0]
    assert "unite 3 non connectee" in report
    assert "1 probleme" in report
    assert "s'arreterait en cours" in report


def test_the_check_refuses_a_filament_beyond_the_sixteen(tmp_path):
    obj = checker(tmp_path, {"T1A": "T1B"})
    gcmd = FakeGcmd(FILE=gcode(tmp_path, "\n".join(["T0", "T17"])))
    obj.cmd_KCTRL_CHECK(gcmd)
    report = gcmd.said[0]
    assert "filament 18" in report
    assert "16 emplacements" in report


def test_the_check_names_a_filament_that_points_nowhere(tmp_path):
    obj = checker(tmp_path, {"T1A": "T1B"})
    gcmd = FakeGcmd(FILE=gcode(tmp_path, "\n".join(["T0", "T5"])))
    obj.cmd_KCTRL_CHECK(gcmd)
    assert "non associe" in gcmd.said[0]


def test_the_check_refuses_to_answer_without_a_file(tmp_path):
    obj = checker(tmp_path, {"T1A": "T1B"})
    with pytest.raises(GcmdError):
        obj.cmd_KCTRL_CHECK(FakeGcmd())


def test_the_check_is_registered_as_a_command(tmp_path):
    obj = checker(tmp_path, {"T1A": "T1B"})
    assert "KCTRL_CHECK" in obj.printer.gcode.commands


# ------------------------------------------ la temperature que le chargeur lit
#
# Le chargeur d'origine chauffe au nozzle_temperature de la fiche matiere de
# l'emplacement, et attend cette temperature. Le 10 septembre a 10:06 la fiche
# Generic PLA, corrigee a 200 la veille, etait revenue a 220 apres le
# redemarrage du matin : le plafond de chargement l'a ramenee a 205 et le
# chargeur a attendu 220 pendant cinq minutes, annulation bloquee derriere.
# START_PRINT lit donc la fiche avant de chauffer. Ce qui est epingle ici : la
# forme reelle de la base relevee sur la machine, la correspondance six
# caracteres -> cinq, et le refus d'inventer une temperature.

def base_matiere(fiches):
    return {"code": 0, "msg": "", "reqId": "", "result": {"list": [
        {"engineVersion": "1", "base": {"id": ident, "name": name},
         "kvParam": {"nozzle_temperature": str(temp),
                     "nozzle_temperature_initial_layer": str(temp)}}
        for ident, name, temp in fiches]}}


# Releve sur la machine le 10 septembre a 10:19, apres correction.
FICHES = [("00001", "Generic PLA", 200), ("00003", "Generic PETG", 250),
          ("10001", "HP-TPU", 230)]


def build_temps(tmp_path, payload):
    db = tmp_path / "material_database.json"
    if payload is not None:
        db.write_text(json.dumps(payload) if not isinstance(payload, str)
                      else payload, encoding="utf-8")
    table = tmp_path / "tn_data.json"
    table.write_text(json.dumps({"tnn_map": LIVE_MAP}), encoding="utf-8")
    return MOD.load_config(FakeConfig(str(table), str(db))), db


@pytest.mark.parametrize("slot_type,attendu", [
    ("000001", "00001"), ("000003", "00003"), ("10001", "10001"),
    ("110001", "110001"), ("-1", "-1"),
])
def test_a_slot_type_maps_onto_its_record(slot_type, attendu):
    assert MOD.material_key(slot_type) == attendu


def test_the_loading_temperatures_read_back_by_record(tmp_path):
    obj, _ = build_temps(tmp_path, base_matiere(FICHES))
    status = obj.get_status()
    assert status["material_temp"] == {"00001": 200.0, "00003": 250.0,
                                       "10001": 230.0}
    assert status["material_temp_error"] == ""
    assert status["material_temp"][MOD.material_key("000001")] == 200.0


def test_a_corrected_record_is_picked_up_without_a_restart(tmp_path):
    obj, db = build_temps(tmp_path, base_matiere(FICHES))
    assert obj.get_status()["material_temp"]["00001"] == 200.0
    os.utime(db, (1, 1))
    db.write_text(json.dumps(base_matiere([("00001", "Generic PLA", 220)])),
                  encoding="utf-8")
    assert obj.get_status()["material_temp"]["00001"] == 220.0


def test_a_missing_database_reports_instead_of_guessing(tmp_path):
    obj, _ = build_temps(tmp_path, None)
    status = obj.get_status()
    assert status["material_temp"] == {}
    assert "absente" in status["material_temp_error"]


def test_a_damaged_database_reports_instead_of_guessing(tmp_path):
    obj, _ = build_temps(tmp_path, "{ pas du json")
    status = obj.get_status()
    assert status["material_temp"] == {}
    assert "illisible" in status["material_temp_error"]


def test_a_database_without_records_reports_instead_of_guessing(tmp_path):
    obj, _ = build_temps(tmp_path, {"result": {}})
    status = obj.get_status()
    assert status["material_temp"] == {}
    assert status["material_temp_error"]


def test_a_record_without_a_number_is_skipped_not_invented(tmp_path):
    payload = base_matiere(FICHES)
    payload["result"]["list"][0]["kvParam"]["nozzle_temperature"] = "chaud"
    payload["result"]["list"].append({"base": {"id": "00099"}})
    payload["result"]["list"].append("pas une fiche")
    obj, _ = build_temps(tmp_path, payload)
    temps = obj.get_status()["material_temp"]
    assert "00001" not in temps and "00099" not in temps
    assert temps["00003"] == 250.0


def test_reading_the_database_never_writes_it(tmp_path):
    obj, db = build_temps(tmp_path, base_matiere(FICHES))
    before = db.read_bytes()
    obj.get_status()
    obj.get_status()
    assert db.read_bytes() == before


# --- KCTRL_MATERIAL_ALIGN --------------------------------------------------
#
# Le firmware reecrit la base a chaque allumage (deux retours a 220 C, les 9
# et 10 septembre, pile sur les deux allumages), et le chargeur la relit a
# chaque chargement (fiche corrigee a 00:32 le 9, 27 chargements a 200 C des
# 13:17 sans redemarrage). START_PRINT ecrit donc la temperature du fichier
# dans la fiche juste avant de charger. Ce qui est epingle ici : les deux
# cles ecrites et rien d'autre, l'ecriture atomique, la relecture, le refus
# d'ecrire n'importe quoi, et le rafraichissement immediat du statut.

def align(obj, **params):
    gcmd = FakeGcmd(**params)
    obj.printer.gcode.commands["KCTRL_MATERIAL_ALIGN"](gcmd)
    return gcmd


def test_the_align_command_is_registered(tmp_path):
    obj, _ = build_temps(tmp_path, base_matiere(FICHES))
    assert "KCTRL_MATERIAL_ALIGN" in obj.printer.gcode.commands


def test_align_writes_both_loading_keys_of_that_record_and_nothing_else(tmp_path):
    payload = base_matiere(FICHES)
    payload["result"]["list"][0]["kvParam"]["filament_max_volumetric_speed"] = "14"
    obj, db = build_temps(tmp_path, payload)
    before = json.loads(db.read_text(encoding="utf-8"))
    gcmd = align(obj, MATERIAL="00001", TEMP="190")
    after = json.loads(db.read_text(encoding="utf-8"))
    pla = after["result"]["list"][0]["kvParam"]
    # Les temperatures sont des chaines dans la base du firmware, "220".
    assert pla["nozzle_temperature"] == "190"
    assert pla["nozzle_temperature_initial_layer"] == "190"
    assert pla["filament_max_volumetric_speed"] == "14"
    for key in ("nozzle_temperature", "nozzle_temperature_initial_layer"):
        before["result"]["list"][0]["kvParam"][key] = "190"
    assert after == before, "seules les deux cles de temperature ont bouge"
    assert "200/200 -> 190 C" in gcmd.said[0]
    assert "Generic PLA" in gcmd.said[0]


def test_align_accepts_the_six_character_slot_type(tmp_path):
    obj, db = build_temps(tmp_path, base_matiere(FICHES))
    align(obj, MATERIAL="000003", TEMP="235")
    petg = json.loads(db.read_text(encoding="utf-8"))["result"]["list"][1]
    assert petg["kvParam"]["nozzle_temperature"] == "235"


def test_align_writes_nothing_when_the_record_already_agrees(tmp_path):
    obj, db = build_temps(tmp_path, base_matiere(FICHES))
    os.utime(db, (1, 1))
    gcmd = align(obj, MATERIAL="00001", TEMP="200")
    assert os.stat(db).st_mtime == 1, "un fichier deja juste n'est pas reecrit"
    assert "rien ecrit" in gcmd.said[0]


def test_align_is_seen_by_the_status_at_once(tmp_path):
    obj, db = build_temps(tmp_path, base_matiere(FICHES))
    assert obj.get_status()["material_temp"]["00001"] == 200.0
    align(obj, MATERIAL="00001", TEMP="190")
    assert obj.get_status()["material_temp"]["00001"] == 190.0


def test_align_rounds_to_the_degree_the_loader_reads(tmp_path):
    obj, db = build_temps(tmp_path, base_matiere(FICHES))
    align(obj, MATERIAL="00001", TEMP="189.6")
    pla = json.loads(db.read_text(encoding="utf-8"))["result"]["list"][0]
    assert pla["kvParam"]["nozzle_temperature"] == "190"


def test_align_leaves_no_temporary_file_behind(tmp_path):
    obj, db = build_temps(tmp_path, base_matiere(FICHES))
    align(obj, MATERIAL="00001", TEMP="190")
    assert sorted(f.name for f in tmp_path.iterdir()) == [
        "material_database.json", "tn_data.json"]


def test_align_refuses_a_record_the_base_does_not_have(tmp_path):
    obj, db = build_temps(tmp_path, base_matiere(FICHES))
    before = db.read_bytes()
    with pytest.raises(GcmdError) as failure:
        align(obj, MATERIAL="00042", TEMP="190")
    assert "00042" in str(failure.value) and "absente" in str(failure.value)
    assert db.read_bytes() == before


@pytest.mark.parametrize("temp", ["40", "400", "chaud", "-190"])
def test_align_refuses_a_temperature_that_is_not_a_filament(tmp_path, temp):
    obj, db = build_temps(tmp_path, base_matiere(FICHES))
    before = db.read_bytes()
    with pytest.raises(GcmdError):
        align(obj, MATERIAL="00001", TEMP=temp)
    assert db.read_bytes() == before


@pytest.mark.parametrize("params", [{}, {"MATERIAL": "00001"}, {"TEMP": "190"}])
def test_align_refuses_to_guess_a_missing_parameter(tmp_path, params):
    obj, db = build_temps(tmp_path, base_matiere(FICHES))
    before = db.read_bytes()
    with pytest.raises(GcmdError):
        align(obj, **params)
    assert db.read_bytes() == before


def test_align_does_not_rewrite_a_damaged_base(tmp_path):
    obj, db = build_temps(tmp_path, "{ pas du json")
    with pytest.raises(GcmdError) as failure:
        align(obj, MATERIAL="00001", TEMP="190")
    assert "illisible" in str(failure.value)
    assert db.read_text(encoding="utf-8") == "{ pas du json"
    assert not (tmp_path / "material_database.json.kctrl-tmp").exists()


def test_align_refuses_when_the_base_is_absent(tmp_path):
    obj, db = build_temps(tmp_path, None)
    with pytest.raises(GcmdError):
        align(obj, MATERIAL="00001", TEMP="190")
    assert not db.exists(), "une base absente n'est pas inventee"


def test_a_failed_write_leaves_the_original_intact(tmp_path, monkeypatch):
    obj, db = build_temps(tmp_path, base_matiere(FICHES))
    before = db.read_bytes()

    def broken(*args, **kwargs):
        raise OSError("disque plein")

    monkeypatch.setattr(MOD.json, "dump", broken)
    with pytest.raises(GcmdError) as failure:
        align(obj, MATERIAL="00001", TEMP="190")
    assert "disque plein" in str(failure.value)
    assert db.read_bytes() == before
    assert not (tmp_path / "material_database.json.kctrl-tmp").exists()


def test_align_reads_back_what_it_wrote_and_refuses_a_mismatch(tmp_path, monkeypatch):
    """Si la base relue ne porte pas la valeur ecrite, le chargeur chaufferait
    a autre chose que le fichier : c'est un refus, pas un message."""
    obj, db = build_temps(tmp_path, base_matiere(FICHES))

    def swallowed(src, dst):
        os.unlink(src)

    monkeypatch.setattr(MOD.os, "replace", swallowed)
    with pytest.raises(GcmdError) as failure:
        align(obj, MATERIAL="00001", TEMP="190")
    assert "relecture" in str(failure.value)
    assert json.loads(db.read_text(encoding="utf-8"))["result"]["list"][0][
        "kvParam"]["nozzle_temperature"] == "200"
