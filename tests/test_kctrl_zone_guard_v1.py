"""Le garde qui empêche le plateau de remonter dans la tête, derrière le plateau.

Le 9 septembre 2026 la routine de rechargement du CFS a demandé
`Move out of range: 185.500 291.500 -18.951`. Klipper a refusé ce Z-là parce
qu'il passe sous `position_min: -10`, mais rien ne refuse un Z entre -10 et 0,
et un Z négatif derrière le plateau fait monter le plateau au-dessus du plan de
la buse. C'est le coincement de la tête dans la goulotte de purge.

Ce qui est épinglé ici : le garde s'installe avant que `gcode_move` ne capture
`toolhead.move`, il laisse passer tout ce qu'une impression fait, il refuse le
mouvement exact relevé pendant l'incident, et il ne ment pas sur son état.
"""

import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(ROOT, "packages", "k1-control-v1", "cfs-zone-z-guard-v1",
                      "kctrl_zone_guard.py")

# Relevé dans box.cfg le 2026-09-09.
EXTRUDE_POS_X = 185.5
SAFE_POS_Y = 291.5
EXTRUDE_POS_Y = 305.0
EXTRUDE_POS_Z = 30.0
# Relevé dans printer.cfg le 2026-09-09.
GCODE_POSITION_MAX_Y = 295.0
Z_POSITION_MIN = -10.0


def load_module():
    spec = importlib.util.spec_from_file_location("kctrl_zone_guard", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["kctrl_zone_guard"] = module
    spec.loader.exec_module(module)
    return module


MOD = load_module()


class CommandError(Exception):
    pass


class FakeGcode:
    def __init__(self):
        self.commands = {}
        self.said = []

    def register_command(self, name, callback, desc=None):
        self.commands[name] = callback

    def respond_info(self, message):
        self.said.append(message)


class FakeToolhead:
    def __init__(self):
        self.moves = []

    def move(self, newpos, speed):
        self.moves.append((list(newpos), speed))


class FakePrinter:
    def __init__(self):
        self.gcode = FakeGcode()
        self.toolhead = FakeToolhead()
        self.objects = {"gcode": self.gcode, "toolhead": self.toolhead}
        self.handlers = {}
        self.command_error = CommandError

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)

    def register_event_handler(self, name, callback):
        self.handlers.setdefault(name, []).append(callback)

    def fire(self, name):
        for callback in self.handlers.get(name, []):
            callback()


class FakeConfig:
    def __init__(self, printer, **values):
        self.printer = printer
        self.values = values

    def get_printer(self):
        return self.printer

    def getfloat(self, name, default=None, **kwargs):
        return float(self.values.get(name, default))

    def getboolean(self, name, default=None):
        return bool(self.values.get(name, default))

    def getchoice(self, name, choices, default=None):
        value = self.values.get(name, default)
        if value not in choices:
            raise ValueError(name)
        return choices[value]


class FakeGcodeCommand:
    def __init__(self, **params):
        self.params = params
        self.said = []

    def get_int(self, name, default=None):
        value = self.params.get(name, default)
        return None if value is None else int(value)

    def respond_info(self, message):
        self.said.append(message)


def armed(**values):
    printer = FakePrinter()
    guard = MOD.load_config(FakeConfig(printer, **values))
    printer.fire("klippy:connect")
    return printer, guard


def test_le_garde_remplace_bien_toolhead_move():
    printer, guard = armed()
    assert guard.installed is True
    assert printer.toolhead.move.__name__ == "guarded_move"


def test_gcode_move_capture_le_garde_et_non_l_original():
    # gcode_move fait `self.move_with_transform = toolhead.move` sur
    # klippy:ready, donc après klippy:connect. Ce que le G-code emprunte doit
    # être le garde.
    printer, _ = armed()
    capture = printer.lookup_object("toolhead").move
    with pytest.raises(CommandError):
        capture([EXTRUDE_POS_X, EXTRUDE_POS_Y, -1.0, 0.0], 100.0)


def test_le_mouvement_exact_de_l_incident_est_refuse():
    printer, guard = armed()
    with pytest.raises(CommandError) as refus:
        printer.toolhead.move([EXTRUDE_POS_X, SAFE_POS_Y, -18.951, 233.5], 50.0)
    assert "-18.951" in str(refus.value)
    assert printer.toolhead.moves == []
    assert guard.trips == 1
    assert guard.last_trip == "X185.500 Y291.500 Z-18.951"


def test_un_z_negatif_juste_au_dessus_de_position_min_est_refuse_aussi():
    # C'est celui-là que Klipper laisse passer tout seul, et c'est lui qui
    # coince la tête.
    printer, _ = armed()
    with pytest.raises(CommandError):
        printer.toolhead.move([EXTRUDE_POS_X, EXTRUDE_POS_Y,
                               Z_POSITION_MIN + 0.001, 0.0], 50.0)
    assert printer.toolhead.moves == []


def test_la_zone_de_service_laisse_passer_les_hauteurs_du_cfs():
    printer, guard = armed()
    for z in (0.0, EXTRUDE_POS_Z, 45.087):
        printer.toolhead.move([EXTRUDE_POS_X, EXTRUDE_POS_Y, z, 0.0], 50.0)
    assert len(printer.toolhead.moves) == 3
    assert guard.trips == 0


def test_une_impression_ne_peut_pas_atteindre_la_zone():
    # [stepper_y] déclare gcode_position_max: 295 : un fichier tranché ne va
    # jamais au-delà. Un Z négatif sur le plateau reste donc permis, la
    # palpation en a besoin.
    printer, guard = armed()
    printer.toolhead.move([150.0, GCODE_POSITION_MAX_Y, -2.0, 12.0], 300.0)
    printer.toolhead.move([150.0, 150.0, -5.0, 12.0], 300.0)
    assert len(printer.toolhead.moves) == 2
    assert guard.trips == 0


def test_le_mode_clamp_releve_le_z_au_lieu_de_refuser():
    printer, guard = armed(action="clamp")
    printer.toolhead.move([EXTRUDE_POS_X, EXTRUDE_POS_Y, -5.0, 0.0], 50.0)
    assert printer.toolhead.moves[0][0][2] == 0.0
    assert guard.trips == 1
    assert printer.gcode.said


def test_le_garde_desarme_ne_refuse_plus_rien():
    printer, guard = armed(enable=False)
    printer.toolhead.move([EXTRUDE_POS_X, EXTRUDE_POS_Y, -18.951, 0.0], 50.0)
    assert len(printer.toolhead.moves) == 1
    assert guard.trips == 0


def test_la_commande_dit_l_etat_et_le_dernier_refus():
    printer, guard = armed()
    with pytest.raises(CommandError):
        printer.toolhead.move([EXTRUDE_POS_X, SAFE_POS_Y, -18.951, 0.0], 50.0)
    command = printer.gcode.commands["KCTRL_ZONE_GUARD"]
    gcmd = FakeGcodeCommand()
    command(gcmd)
    assert "actif" in gcmd.said[0]
    assert "1 refus" in gcmd.said[0]
    assert "X185.500 Y291.500 Z-18.951" in gcmd.said[0]


def test_la_commande_peut_desarmer_et_rearmer():
    printer, guard = armed()
    command = printer.gcode.commands["KCTRL_ZONE_GUARD"]
    command(FakeGcodeCommand(ENABLE=0))
    assert guard.enabled is False
    printer.toolhead.move([EXTRUDE_POS_X, EXTRUDE_POS_Y, -18.951, 0.0], 50.0)
    command(FakeGcodeCommand(ENABLE=1))
    assert guard.enabled is True
    with pytest.raises(CommandError):
        printer.toolhead.move([EXTRUDE_POS_X, EXTRUDE_POS_Y, -18.951, 0.0], 50.0)


def test_l_etat_publie_ne_ment_pas():
    printer, guard = armed()
    status = guard.get_status()
    assert status["installed"] is True
    assert status["enabled"] is True
    assert status["zone_y_min"] == 296.0
    assert status["z_floor"] == 0.0
    assert status["action"] == "refuse"
    assert status["trips"] == 0
    assert status["last_trip"] == ""


def test_deux_connexions_ne_superposent_pas_deux_gardes():
    printer, guard = armed()
    printer.fire("klippy:connect")
    with pytest.raises(CommandError):
        printer.toolhead.move([EXTRUDE_POS_X, EXTRUDE_POS_Y, -1.0, 0.0], 50.0)
    assert guard.trips == 1
