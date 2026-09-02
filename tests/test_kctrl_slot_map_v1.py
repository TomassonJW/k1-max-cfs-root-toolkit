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
