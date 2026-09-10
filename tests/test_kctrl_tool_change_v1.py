"""L'enveloppe des changements d'outil T0..T15 (kctrl_tool_change.py).

Ce qui est épinglé : la prise en main des seize commandes au chargement sans
faire échouer Klipper quand le CFS n'en a pas enregistré une ; l'alignement de
la fiche matière de l'emplacement visé sur la température du fichier tranché
(première couche ou courante) avant l'appel de la commande stock ; le refus
net quand le filament ne pointe nulle part, sur une unité absente ou un
emplacement vide ; hors démarrage, la pause quand le changement finit sans
filament à la tête, et la cible remise à la valeur du fichier sinon ; dans
START_PRINT, rien de plus que l'alignement, le démarrage garde ses contrôles.
"""

import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "packages", "k1-control-v1", "owned-start-print-v2")


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PACKAGE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SLOT_MAP = load("kctrl_slot_map")
TOOL_CHANGE = load("kctrl_tool_change")


class CommandError(Exception):
    pass


class FakeGcode:
    """register_command au sens de Klipper : None retire et rend l'ancien."""

    def __init__(self):
        self.handlers = {}
        self.scripts = []

    def register_command(self, name, func, when_not_ready=False, desc=None):
        if func is None:
            return self.handlers.pop(name, None)
        if name in self.handlers:
            raise AssertionError("gcode command %s already registered" % name)
        self.handlers[name] = func

    def run_script_from_command(self, script):
        self.scripts.append(script)


class FakeCommand:
    error = CommandError

    def __init__(self, params=None):
        self.params = params or {}
        self.said = []

    def get(self, key, default=None):
        return self.params.get(key, default)

    def respond_info(self, message):
        self.said.append(message)


class FakeObject:
    def __init__(self, status):
        self.status = status

    def get_status(self, eventtime=None):
        return self.status


class FakeReactor:
    def monotonic(self):
        return 1.0


class FakePrinter:
    def __init__(self):
        self.gcode = FakeGcode()
        self.objects = {"gcode": self.gcode}
        self.reactor = FakeReactor()

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)

    def get_reactor(self):
        return self.reactor


class FakeConfig:
    def __init__(self, printer, values=None):
        self.printer = printer
        self.values = values or {}

    def get_printer(self):
        return self.printer

    def get(self, key, default=None):
        return self.values.get(key, default)

    def getint(self, key, default=None, minval=None, maxval=None):
        return int(self.values.get(key, default))


LIVE_MAP = {"T%d%s" % (b, s): "T%d%s" % (b, s)
            for b in (1, 2, 3, 4) for s in "ABCD"}

# Relevé sur la machine le 10 septembre 2026 : deux unités, T1B et T2D en PLA
# (000001), T2C en PETG (000003), T1A et T1C vides.
UNIT_1 = {"state": "connect",
          "material_type": ["-1", "000001", "-1", "000001"],
          "color_value": ["-1", "0000000", "-1", "0ffffff"]}
UNIT_2 = {"state": "connect",
          "material_type": ["000001", "000001", "000003", "000001"],
          "color_value": ["0ff1e1e", "000a3ff", "0ffffff", "0b2a1e1"]}
UNIT_OFF = {"state": "None", "material_type": ["-1"] * 4, "color_value": ["-1"] * 4}


def material_db(tmp_path, pla=220, petg=240):
    path = tmp_path / "material_database.json"
    payload = {"result": {"list": [
        {"base": {"id": "00001", "name": "PLA"},
         "kvParam": {"nozzle_temperature": str(pla),
                     "nozzle_temperature_initial_layer": str(pla)}},
        {"base": {"id": "00003", "name": "PETG"},
         "kvParam": {"nozzle_temperature": str(petg),
                     "nozzle_temperature_initial_layer": str(petg)}},
    ]}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# Fin de fichier telle qu'Orca 2.4.2 l'écrit (cube du 10 septembre 2026) :
# le bloc de configuration est en queue, les températures en listes.
def gcode_file(tmp_path, temps="195,220", initial="190,220", types="PLA;PLA",
               colours="#000000;#8080FF", body="T0\nG1 X10\n", block=True):
    path = tmp_path / "job.gcode"
    text = "; HEADER_BLOCK_START\n; filament: 2\n; HEADER_BLOCK_END\n" + body
    if block:
        text += "\n".join([
            "; CONFIG_BLOCK_START",
            "; change_filament_gcode = ",
            "; filament_colour = " + colours,
            '; filament_settings_id = "PLA Geeetech";"eSUN PLA+ @System - Copie"',
            "; filament_type = " + types,
            "; initial_layer_print_height = 0.2",
            "; layer_height = 0.2",
            "; nozzle_temperature = " + temps,
            "; nozzle_temperature_initial_layer = " + initial,
            "; CONFIG_BLOCK_END",
            "",
        ])
    path.write_text(text, encoding="utf-8")
    return str(path)


class Bench:
    """Une machine factice : box, capteur, pause, position, fichier en cours."""

    def __init__(self, tmp_path, tn_map=None, units=None, printing=True,
                 z=0.2, filament=True, paused=False, start_running=0,
                 registered=16, **file_kw):
        self.printer = FakePrinter()
        gcode = self.printer.gcode
        self.stock_calls = []
        for index in range(registered):
            name = "T%d" % index
            gcode.handlers[name] = self.stock_for(name)
        tn = tmp_path / "tn_data.json"
        tn.write_text(json.dumps({"tnn_map": tn_map or dict(LIVE_MAP)}),
                      encoding="utf-8")
        self.db = material_db(tmp_path)
        self.file = gcode_file(tmp_path, **file_kw)
        units = units or {"T1": UNIT_1, "T2": UNIT_2, "T3": UNIT_OFF, "T4": UNIT_OFF}
        self.box = FakeObject(dict({"enable": 1}, **units))
        self.sensor = FakeObject({"filament_detected": filament})
        self.pause = FakeObject({"is_paused": paused})
        self.move = FakeObject({"gcode_position": [0.0, 0.0, z, 0.0]})
        self.start = FakeObject({"start_running": start_running})
        self.sdcard = FakeObject({"file_path": self.file if printing else ""})
        objects = self.printer.objects
        objects["box"] = self.box
        objects["filament_switch_sensor filament_sensor_2"] = self.sensor
        objects["pause_resume"] = self.pause
        objects["gcode_move"] = self.move
        objects["gcode_macro START_PRINT"] = self.start
        objects["virtual_sdcard"] = self.sdcard
        objects["print_stats"] = FakeObject({"filename": os.path.basename(self.file)})

        class MapConfig:
            def __init__(inner):
                inner.printer = self.printer

            def get_printer(inner):
                return inner.printer

            def get(inner, key, default=None):
                if key == "path":
                    return str(tn)
                if key == "material_db":
                    return str(self.db)
                return default

        self.slot_map = SLOT_MAP.load_config(MapConfig())
        objects["kctrl_slot_map"] = self.slot_map
        self.obj = TOOL_CHANGE.load_config(FakeConfig(self.printer))

    def stock_for(self, name):
        def stock(gcmd):
            self.stock_calls.append(name)
        return stock

    def rewrap(self, name=None, handler=None, values=None):
        """Rebuild the wrapper, optionally with another stock handler."""
        handlers = self.printer.gcode.handlers
        handlers.pop("KCTRL_TOOLS", None)
        for index in range(16):
            tool = "T%d" % index
            if tool in handlers:
                handlers[tool] = self.stock_for(tool)
        if name is not None:
            handlers[name] = handler
        self.obj = TOOL_CHANGE.load_config(FakeConfig(self.printer, values))

    def run(self, name, **params):
        cmd = FakeCommand(params)
        self.printer.gcode.handlers[name](cmd)
        return cmd

    def record_temp(self, ident):
        data = json.loads(self.db.read_text(encoding="utf-8"))
        for record in data["result"]["list"]:
            if record["base"]["id"] == ident:
                return (record["kvParam"]["nozzle_temperature"],
                        record["kvParam"]["nozzle_temperature_initial_layer"])
        return None


# ------------------------------------------------------------ prise en main

def test_les_seize_commandes_sont_reprises_et_kctrl_tools_existe(tmp_path):
    bench = Bench(tmp_path)
    handlers = bench.printer.gcode.handlers
    assert bench.obj.wrapped == ["T%d" % i for i in range(16)]
    assert bench.obj.missing == []
    for index in range(16):
        assert handlers["T%d" % index] is not bench.stock_for("x")
    assert "KCTRL_TOOLS" in handlers


def test_une_commande_absente_est_laissee_sans_faire_echouer_le_chargement(tmp_path):
    # Le module compilé n'enregistre pas forcément les seize noms : un nom
    # absent est listé, les autres sont repris, Klipper démarre.
    bench = Bench(tmp_path, registered=8)
    assert bench.obj.wrapped == ["T%d" % i for i in range(8)]
    assert bench.obj.missing == ["T%d" % i for i in range(8, 16)]
    assert "T9" not in bench.printer.gcode.handlers


def test_les_noms_logiques_suivent_la_meme_convention_que_la_table(tmp_path):
    assert TOOL_CHANGE.NAMES == SLOT_MAP.NAMES
    assert TOOL_CHANGE.material_key("000001") == SLOT_MAP.material_key("000001")


# ------------------------------------------------------------ l'alignement

def test_un_changement_en_cours_d_impression_aligne_la_fiche_sur_le_fichier(tmp_path):
    # Fichier 195/220, fiche PLA du cloud a 220 : le T1 mid-print vise T1B
    # (PLA) et doit ecrire 220 (deja bon) ; le T0 vise T1A, vide -> refus
    # teste plus bas. Ici T1 -> T1B en couche 5 : temperature courante 220.
    bench = Bench(tmp_path, z=1.0)
    cmd = bench.run("T1")
    assert bench.stock_calls == ["T1"]
    assert bench.record_temp("00001") == ("220", "220")
    assert any("deja a 220 C" in line for line in cmd.said)
    # Hors demarrage : file d'attente vidée, capteur vu, cible remise.
    assert bench.printer.gcode.scripts == ["M400", "M104 S220"]
    assert bench.obj.last["outcome"] == "done"


def test_la_temperature_courante_est_ecrite_dans_la_fiche_avant_la_commande_stock(tmp_path):
    # Filament 2 a 200 C dans le fichier, fiche PLA a 220 : la fiche passe a
    # 200 AVANT l'appel stock, puisque c'est lui qui la lit.
    seen = {}
    bench = Bench(tmp_path, z=1.0, temps="195,200", initial="190,205")

    def stock(gcmd):
        seen["record"] = bench.record_temp("00001")
        bench.stock_calls.append("T1")
    bench.rewrap("T1", stock)
    cmd = bench.run("T1")
    assert seen["record"] == ("200", "200")
    assert any("alignee 220/220 -> 200 C" in line for line in cmd.said)
    assert bench.printer.gcode.scripts[-1] == "M104 S200"


def test_en_premiere_couche_c_est_la_temperature_de_premiere_couche(tmp_path):
    bench = Bench(tmp_path, z=0.2, temps="195,200", initial="190,205")
    cmd = bench.run("T1")
    assert bench.record_temp("00001") == ("205", "205")
    assert any("premiere couche" in line for line in cmd.said)
    assert bench.printer.gcode.scripts[-1] == "M104 S205"


def test_dans_start_print_l_enveloppe_aligne_et_ne_fait_rien_d_autre(tmp_path):
    # Le demarrage attend le capteur lui-meme (KCTRL_WAIT_FILAMENT, 15 s de
    # grace) et remet la temperature du fichier apres le chargeur : ici, ni
    # M400, ni pause, ni M104, mais la fiche est bien alignee, sur la
    # premiere couche, quel que soit le Z du moment.
    bench = Bench(tmp_path, z=10.0, start_running=1, filament=False,
                  temps="195,200", initial="190,205")
    bench.run("T1")
    assert bench.stock_calls == ["T1"]
    assert bench.record_temp("00001") == ("205", "205")
    assert bench.printer.gcode.scripts == []
    assert bench.obj.last["outcome"] == "start"


def test_le_t_du_demarrage_ne_reecrit_pas_une_fiche_deja_alignee(tmp_path):
    # START_PRINT a deja aligne la fiche (KCTRL_MATERIAL_ALIGN) : le passage
    # par l'enveloppe ne doit rien ecrire de plus.
    bench = Bench(tmp_path, start_running=1, temps="195,220", initial="220,220")
    before = bench.db.read_bytes()
    cmd = bench.run("T1")
    assert bench.db.read_bytes() == before
    assert any("deja a 220 C" in line for line in cmd.said)


# ------------------------------------------------------------ les refus

def test_un_filament_vers_un_emplacement_vide_est_refuse_avant_la_commande_stock(tmp_path):
    bench = Bench(tmp_path, z=1.0)
    with pytest.raises(CommandError) as caught:
        bench.run("T0")  # T1A est vide sur la machine du 10 septembre
    assert "T1A" in str(caught.value) and "vide" in str(caught.value)
    assert bench.stock_calls == []
    assert bench.obj.last["outcome"] == "refuse"


def test_un_filament_vers_une_unite_absente_est_refuse(tmp_path):
    nine = ",".join(["200"] * 9)
    bench = Bench(tmp_path, z=1.0, temps=nine, initial=nine,
                  types=";".join(["PLA"] * 9), colours=";".join(["#000000"] * 9))
    with pytest.raises(CommandError) as caught:
        bench.run("T8")  # T3A, unite 3 non connectee
    assert "unite CFS 3" in str(caught.value)
    assert bench.stock_calls == []


def test_un_filament_que_le_fichier_ne_declare_pas_est_refuse(tmp_path):
    bench = Bench(tmp_path, z=1.0)
    with pytest.raises(CommandError) as caught:
        bench.run("T5")
    assert "ne declare que 2 filament(s)" in str(caught.value)
    assert bench.stock_calls == []


def test_un_filament_sans_entree_dans_la_table_est_refuse(tmp_path):
    table = dict(LIVE_MAP)
    del table["T1B"]
    bench = Bench(tmp_path, z=1.0, tn_map=table)
    with pytest.raises(CommandError) as caught:
        bench.run("T1")
    assert "ne pointe sur aucun emplacement" in str(caught.value)
    assert bench.stock_calls == []


def test_un_fichier_sans_temperatures_est_refuse(tmp_path):
    bench = Bench(tmp_path, z=1.0, block=False)
    with pytest.raises(CommandError) as caught:
        bench.run("T1")
    assert "ne dit pas ses temperatures" in str(caught.value)
    assert bench.stock_calls == []


def test_une_fiche_non_alignable_est_un_refus(tmp_path):
    bench = Bench(tmp_path, z=1.0)
    bench.db.write_text("{", encoding="utf-8")
    with pytest.raises(CommandError) as caught:
        bench.run("T1")
    assert "non alignee" in str(caught.value)
    assert bench.stock_calls == []


# ------------------------------------------------------------ hors travail

def test_sans_fichier_en_cours_la_commande_stock_tourne_seule(tmp_path):
    # Un T tape a la console : rien a aligner, rien a verifier, le CFS fait
    # ce qu'il faisait avant.
    bench = Bench(tmp_path, printing=False)
    cmd = bench.run("T1")
    assert bench.stock_calls == ["T1"]
    assert cmd.said == []
    assert bench.printer.gcode.scripts == []
    assert bench.obj.last["outcome"] == "stock"


def test_cfs_desactive_la_commande_stock_tourne_seule(tmp_path):
    bench = Bench(tmp_path)
    bench.box.status["enable"] = 0
    bench.run("T1")
    assert bench.stock_calls == ["T1"]
    assert bench.printer.gcode.scripts == []


# ------------------------------------------------------------ apres la commande

def test_un_changement_fini_sans_filament_met_en_pause(tmp_path):
    bench = Bench(tmp_path, z=1.0, filament=False)
    cmd = bench.run("T1")
    assert bench.stock_calls == ["T1"]
    assert bench.printer.gcode.scripts == ["M400", "PAUSE"]
    assert any("mise en pause" in line for line in cmd.said)
    assert bench.obj.last["outcome"] == "empty"


def test_sans_pause_demandee_le_vide_est_seulement_dit(tmp_path):
    bench = Bench(tmp_path, z=1.0, filament=False)
    bench.rewrap(values={"pause_on_empty": 0})
    cmd = bench.run("T1")
    assert bench.printer.gcode.scripts == ["M400"]
    assert any("continue a vide" in line for line in cmd.said)


def test_une_pause_posee_par_le_firmware_n_est_pas_doublee(tmp_path):
    # Erreur cutter (key841) : le firmware met lui-meme en pause pendant le
    # changement ; l'enveloppe ne pose ni seconde pause ni cible.
    bench = Bench(tmp_path, z=1.0, filament=False, paused=True)
    cmd = bench.run("T1")
    assert bench.printer.gcode.scripts == ["M400"]
    assert any("pause pendant T1" in line for line in cmd.said)
    assert bench.obj.last["outcome"] == "paused_by_firmware"


def test_une_erreur_de_la_commande_stock_remonte_telle_quelle(tmp_path):
    bench = Bench(tmp_path, z=1.0)

    def broken(gcmd):
        raise CommandError("Move out of range")
    bench.rewrap("T1", broken)
    with pytest.raises(CommandError):
        bench.run("T1")
    assert bench.printer.gcode.scripts == []


# ------------------------------------------------------------ KCTRL_TOOLS

def test_kctrl_tools_montre_chaque_filament_et_son_emplacement(tmp_path):
    bench = Bench(tmp_path, temps="195,220", initial="190,220")
    cmd = bench.run("KCTRL_TOOLS")
    text = "\n".join(cmd.said)
    assert "enveloppees: T0, T1" in text
    assert "filament 1 (T1A) PLA #000000, 195 C (1re couche 190 C) -> T1A, emplacement vide" in text
    assert "filament 2 (T1B) PLA #8080FF, 220 C (1re couche 220 C) -> T1B, fiche 00001 a 220 C" in text


def test_kctrl_tools_annonce_l_alignement_a_venir(tmp_path):
    bench = Bench(tmp_path, temps="195,200", initial="190,205")
    cmd = bench.run("KCTRL_TOOLS")
    assert "fiche 00001 a 220 C (sera alignee au changement)" in "\n".join(cmd.said)


def test_kctrl_tools_sans_fichier_dit_comment_en_donner_un(tmp_path):
    bench = Bench(tmp_path, printing=False)
    cmd = bench.run("KCTRL_TOOLS")
    assert "KCTRL_TOOLS FILE=" in "\n".join(cmd.said)
    cmd = bench.run("KCTRL_TOOLS", FILE=bench.file)
    assert "filament 2 (T1B)" in "\n".join(cmd.said)


def test_le_statut_publie_les_commandes_reprises_et_le_dernier_changement(tmp_path):
    bench = Bench(tmp_path, z=1.0)
    bench.run("T1")
    status = bench.obj.get_status()
    assert len(status["wrapped"]) == 16
    assert status["last"]["outcome"] == "done"
    assert status["last"]["slot"] == "T1B"
