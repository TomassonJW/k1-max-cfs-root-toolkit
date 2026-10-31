"""Le modèle des bobines (document 102, lots B à G, côté sans socket).

Une pesée remplace toujours la tare du catalogue et une saisie ne peut pas se
faire passer pour lui ; chaque fiche pointe vers une fiche matériau qui existe
sur la K1 ; le calculateur donne les mêmes chiffres ici et dans Mainsail ;
aucune suite d'actions ne perd une bobine ni n'en met deux au même
emplacement ; la lecture du CFS ne touche jamais au numéro de série ;
l'écriture n'envoie que ce qui diffère et jamais vers un emplacement vide ;
une impression se compte une fois, et ce qui ne s'attribue pas avec
certitude attend Thomas.

Regénérer les vecteurs partagés avec Mainsail après un changement voulu du
calcul : python tests/test_kctrl_spools_model_v1.py
"""

import copy
import importlib.util
import json
import math
import random
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "spool-manager-v1"
OWNED = ROOT / "packages" / "k1-control-v1" / "owned-start-print-v2"
VECTORS = PACKAGE / "calculator-vectors.json"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


model = load(PACKAGE / "kctrl_spools_model.py", "kctrl_spools_model")
MATERIALS, MATERIALS_ERROR = model.read_materials(str(PACKAGE / "lab" / "material_database.synthetic.json"))
NOW = 1_790_000_000
PLA = model.grams_per_metre(1.24, 1.75)
PETG = model.grams_per_metre(1.27, 1.75)
RED_PLA = ("000001", "0ff1e1e")  # Generic PLA in F001's colour


def ctx(now=NOW, observations=None, materials=None):
    return model.Context(now, MATERIALS if materials is None else materials, observations or {})


def run(library, name, params=None, context=None, internal=False):
    return model.apply(library, name, {} if params is None else params, context or ctx(),
                       internal=internal)


def act(library, name, params=None, context=None, internal=False):
    return run(library, name, params, context, internal)[0]


def refused(library, name, params, fragment, context=None, internal=False):
    with pytest.raises(model.ModelError) as caught:
        run(library, name, params, context, internal)
    assert fragment in str(caught.value), str(caught.value)
    return str(caught.value)


def box(slots, connected=("1", "2")):
    """The box object's status; `slots` is {name: (material, colour[, vender, remain])}."""
    status = {}
    for number in model.BOXES:
        identity = {"sn": "SERIAL-T" + number, "uuid": "UUID-T" + number}
        if number not in connected:
            status["T" + number] = dict(identity, state="None", material_type=["None"] * 4,
                                        color_value=["None"] * 4, vender=["-1"] * 4,
                                        remain_len=["-1"] * 4)
            continue
        unit = dict(identity, state="connect", material_type=["-1"] * 4, color_value=["-1"] * 4,
                    vender=["none"] * 4, remain_len=["0"] * 4)
        for index, letter in enumerate(model.SLOTS):
            found = slots.get("T" + number + letter)
            if found:
                unit["material_type"][index] = found[0]
                unit["color_value"][index] = found[1]
                unit["vender"][index] = found[2] if len(found) > 2 else "unknown"
                unit["remain_len"][index] = found[3] if len(found) > 3 else "100"
        status["T" + number] = unit
    return status


def seen(slots=None, connected=("1", "2")):
    return model.observe_box(box(slots or {}, connected))


def base():
    """Two empty spools from the catalogue and three filament records."""
    library = model.empty_library()
    library = act(library, "create_empty_spool", {
        "manufacturer": "GEEETECH", "name": "Bobine plastique fine", "spool_material": "plastique",
        "tare_g": 180, "nominal_net_g": 1000, "source": "spoolmandb",
        "catalogue": "GEEETECH|1000|180|plastique"})
    library = act(library, "create_empty_spool", {
        "manufacturer": "eSun", "spool_material": "carton", "tare_g": 170, "nominal_net_g": 1000,
        "source": "spoolmandb", "catalogue": "eSun|1000|170|carton"})
    library = act(library, "create_filament", {
        "manufacturer": "Geeetech", "name": "PLA", "material": "PLA", "colour": "#FF1E1E"})
    library = act(library, "create_filament", {
        "manufacturer": "Creality", "name": "Hyper PLA", "material": "PLA", "colour": "FFFFFF"})
    library = act(library, "create_filament", {
        "manufacturer": "eSun", "name": "PETG", "material": "PETG", "colour": "000000"})
    return library


def with_spools():
    """B-001 new in stock, B-002 weighed at 650 g to put away, B-003 estimated at 300 g on a shelf."""
    library = act(base(), "create_spool", {"filament": "F001", "empty_spool": "V001"})
    library = act(library, "create_spool", {"filament": "F001", "empty_spool": "V001",
                                            "basis_kind": "pesee", "value_g": 650, "state": "a_ranger"})
    return act(library, "create_spool", {"filament": "F003", "empty_spool": "V002",
                                         "basis_kind": "estimation", "value_g": 300,
                                         "place": "Étagère 2"})


def in_cfs(library, spool, slot, observations=None):
    return act(library, "put_in_cfs", {"id": spool, "slot": slot}, ctx(observations=observations))


def observe(library, observations, now=NOW):
    work, events, _ = run(library, "observe", {}, ctx(now, observations), internal=True)
    return work, events


def left(library, spool):
    return model.remaining_of(library, library["spools"][spool])["net_g"]


def view_of(views, slot):
    return next(view for view in views if view["slot"] == slot)


# ---------------------------------------------------------------- shared vectors
ROUNDS = [[2.5, 0], [-2.5, 0], [0.5, 0], [1.5, 0], [1.005, 2], [2.675, 2], [157.58, 0],
          [9.95, 1], [-0.004, 2], [0.0, 0], [1234.5678, 1], [0.045, 2]]
GPMS = [[1.24, 1.75], [1.27, 1.75], [1.04, 1.75], [1.26, 1.75], [1.21, 1.75], [1.24, 2.85],
        [3.9, 1.75]]
SHOWN = [[470, 1000, 1.24, 1.75], [1000, 1000, 1.24, 1.75], [20, 1000, 1.24, 1.75],
         [29.5, 1000, 1.24, 1.75], [30, 1000, 1.24, 1.75], [0, 1000, 1.27, 1.75],
         [1003.4, 1000, 1.24, 1.75], [12.345, 250, 1.21, 1.75], [296.95, 1000, 1.27, 1.75],
         [50, 0, 1.24, 1.75], [50, 1000, 0, 1.75]]
GROSS = [[650, 180], [180, 180], [1180.25, 180], [474, 176]]
MILLIMETRES = [[6847.96, 1.24, 1.75], [1000, 1.27, 1.75], [0.4, 1.04, 1.75], [67056.7, 1.24, 1.75]]
PERCENTS = [[47, 1000], [12.5, 250], [100, 1000], [33, 750]]
LENGTHS = [[158, 1.24, 1.75], [10, 1.27, 1.75], [0.5, 1.04, 1.75]]
COLOURS = ["0ff1e1e", "#FF1E1E", "ff1e1e", " #00ff00 ", "-1", "None", "", "0FFF", "12345G",
           "0123456", "1123456", "#0ff1e1e", None, "FF1E1E\n"]
SUGGESTIONS = [
    ("Creality", "PLA", "Hyper PLA", "01001"),
    ("Creality", "PLA", "CR-PLA Blanc", "01002"),
    ("Creality", "PLA", "PLA", "00001"),
    ("creality", "petg", "", "01003"),
    ("Acme Filaments", "PLA", "", "02001"),
    ("Geeetech", "PLA", "PLA", "00001"),
    ("Geeetech", "PLA-SILK", "Silk", "00002"),
    ("Geeetech", "PA", "", ""),
    ("Nodensity", "PA", "", "03001"),
    ("Geeetech", "ASA", "", ""),
    ("", "", "", ""),
    ("Broken", "PLA", "Short id", "00001"),
]


def vectors():
    """What spools-logic.js must compute, from the Python model."""
    def gpm(density, diameter):
        return model.grams_per_metre(density, diameter)

    return {
        "format": "kctrl_spools.vectors",
        "note": "Generated by tests/test_kctrl_spools_model_v1.py from kctrl_spools_model.py; "
                "spools-logic.test.mjs checks the JavaScript side against it.",
        "round_half_away": [[value, digits, model.round_half_away(value, digits)]
                            for value, digits in ROUNDS],
        "grams_per_metre": [[density, diameter, gpm(density, diameter)] for density, diameter in GPMS],
        "shown": [{"net_g": net, "initial_g": initial, "density": density, "diameter": diameter,
                   "expected": model.shown(net, initial, gpm(density, diameter))}
                  for net, initial, density, diameter in SHOWN],
        "net_of_gross": [[gross, tare, model.net_of_gross(gross, tare)] for gross, tare in GROSS],
        "grams_of_mm": [[mm, density, diameter, model.grams_of_mm(mm, gpm(density, diameter))]
                        for mm, density, diameter in MILLIMETRES],
        "net_of_percent": [[percent, initial, model.net_of_percent(percent, initial)]
                           for percent, initial in PERCENTS],
        "net_of_length": [[metres, density, diameter,
                           model.net_of_length(metres, gpm(density, diameter))]
                          for metres, density, diameter in LENGTHS],
        "colour_key": [[text, model.colour_key(text)] for text in COLOURS],
        "materials": MATERIALS,
        "suggest_creality_id": [[manufacturer, material, name,
                                 model.suggest_creality_id(manufacturer, material, name, MATERIALS)]
                                for manufacturer, material, name, _ in SUGGESTIONS],
    }


def test_the_vectors_shared_with_mainsail_are_the_python_figures():
    assert json.loads(VECTORS.read_text(encoding="utf-8")) == vectors()
    assert b"\r" not in VECTORS.read_bytes()


# ---------------------------------------------------------------- calculator
def test_rounding_goes_half_away_from_zero_and_never_gives_minus_zero():
    assert model.round_half_away(2.5) == 3 and model.round_half_away(-2.5) == -3
    assert model.round_half_away(0.5) == 1 and model.round_half_away(1.5) == 2
    zero = model.round_half_away(-0.004, 2)
    assert zero == 0 and math.copysign(1, zero) == 1
    assert model.round_half_away(157.58) == 158


def test_the_example_of_document_102_reads_470_g_47_percent_158_m():
    assert abs(PLA - 2.98255) < 0.00001
    net = model.net_of_gross(650, 180)
    assert net == 470
    assert model.shown(net, 1000, PLA) == {"g": 470, "percent": 47, "m": 158}


def test_metres_keep_one_decimal_under_ten_metres():
    assert model.shown(20, 1000, PLA)["m"] == 6.7
    assert model.shown(29.5, 1000, PLA)["m"] == 9.9
    assert model.shown(30, 1000, PLA)["m"] == 10


def test_a_weighing_lighter_than_its_empty_spool_is_refused_with_both_figures():
    with pytest.raises(model.ModelError) as caught:
        model.net_of_gross(150, 180)
    assert "150 g" in str(caught.value) and "180 g" in str(caught.value)


# ---------------------------------------------------------------- library
def test_an_action_works_on_a_copy_and_stamps_its_events():
    library = model.empty_library()
    assert model.check(library) == []
    frozen = json.dumps(library, sort_keys=True)
    work, events, result = run(library, "create_empty_spool", {
        "manufacturer": "Sunlu", "spool_material": "plastique", "tare_g": 135, "nominal_net_g": 1000,
        "source": "manuel"})
    assert json.dumps(library, sort_keys=True) == frozen
    assert result == {"id": "V001"} and work["empty_spools"]["V001"]["tare_g"] == 135
    assert events[0]["kind"] == "bobine_vide" and events[0]["t"] == NOW


def test_unknown_actions_unknown_fields_and_internal_actions_are_refused():
    library = model.empty_library()
    refused(library, "drop_table", {}, "action inconnue")
    refused(library, "observe", {}, "action inconnue")
    refused(library, "print_end", {"job": "x"}, "action inconnue")
    refused(library, "create_empty_spool", {"manufacturer": "x", "colour": "red"}, "champ inconnu : colour")
    with pytest.raises(model.ModelError):
        model.apply(library, "settings", ["low_g"], ctx())


def test_check_finds_what_would_lose_or_duplicate_a_spool():
    library = with_spools()
    assert model.check(library) == []

    def broken(change):
        copied = copy.deepcopy(library)
        change(copied)
        return " | ".join(model.check(copied))

    def two_in_t1a(lib):
        for ident in ("B001", "B002"):
            lib["spools"][ident].update(state="cfs", slot="T1A")

    assert "même emplacement T1A" in broken(two_in_t1a)
    assert "hors CFS avec un emplacement" in broken(lambda lib: lib["spools"]["B001"].update(slot="T1A"))
    assert "au CFS sans emplacement" in broken(lambda lib: lib["spools"]["B001"].update(state="cfs"))
    assert "bobine B001 mal formée" in broken(lambda lib: lib["spools"]["B001"].update(filament="F099"))
    assert "au-delà du compteur" in broken(lambda lib: lib["counters"].update(spool=1))
    assert "prints absent" in broken(lambda lib: lib.pop("prints"))
    assert model.check([]) == ["bibliothèque : objet attendu"]


# ---------------------------------------------------------------- empty spools (B)
def test_a_catalogue_spool_is_imported_once_and_a_weighing_replaces_its_tare():
    library = base()
    empty = library["empty_spools"]["V001"]
    assert (empty["tare_g"], empty["source"], empty["weighed_on"]) == (180, "spoolmandb", 0)
    again = {"manufacturer": "GEEETECH", "spool_material": "plastique", "tare_g": 180,
             "nominal_net_g": 1000, "source": "spoolmandb", "catalogue": "GEEETECH|1000|180|plastique"}
    refused(library, "create_empty_spool", again, "déjà dans la bibliothèque : V001")
    library = act(library, "weigh_empty_spool", {"id": "V001", "tare_g": "176,5"}, ctx(NOW + 60))
    empty = library["empty_spools"]["V001"]
    assert (empty["tare_g"], empty["source"], empty["weighed_on"]) == (176.5, "pesee", NOW + 60)
    refused(library, "create_empty_spool", again, "déjà dans la bibliothèque : V001")
    assert library["empty_spools"]["V001"]["tare_g"] == 176.5


def test_a_typed_tare_is_marked_manual_and_nothing_can_pass_for_the_catalogue():
    library = act(base(), "weigh_empty_spool", {"id": "V001", "tare_g": 176})
    refused(library, "edit_empty_spool", {"id": "V001", "source": "spoolmandb"}, "champ inconnu : source")
    kept = act(library, "edit_empty_spool", {"id": "V001", "notes": "anneau fin"})
    assert kept["empty_spools"]["V001"]["source"] == "pesee"
    work, events, result = run(library, "edit_empty_spool", {"id": "V001", "tare_g": 176})
    assert events == [] and result["changed"] == []
    typed = act(library, "edit_empty_spool", {"id": "V001", "tare_g": 175})
    assert typed["empty_spools"]["V001"]["source"] == "manuel"
    assert typed["empty_spools"]["V001"]["weighed_on"] == 0


def test_tares_and_nets_are_bounded_and_accept_a_decimal_comma():
    library = model.empty_library()
    params = {"manufacturer": "X", "spool_material": "carton", "nominal_net_g": 1000, "source": "manuel"}
    refused(library, "create_empty_spool", dict(params, tare_g=0), "tare : entre 0 et 2000")
    refused(library, "create_empty_spool", dict(params, tare_g=2001), "tare : entre 0 et 2000")
    refused(library, "create_empty_spool", dict(params, tare_g="abc"), "tare : nombre attendu")
    refused(library, "create_empty_spool", dict(params, tare_g=True), "tare : nombre attendu")
    refused(library, "create_empty_spool", dict(params, tare_g=float("nan")), "tare : nombre attendu")
    refused(library, "create_empty_spool", dict(params, tare_g=100, nominal_net_g=0), "net nominal")
    refused(library, "create_empty_spool", dict(params, tare_g=100, spool_material="bois"),
            "matière de la bobine")
    refused(library, "create_empty_spool", dict(params, tare_g=100, source="spoolmandb"),
            "référence SpoolmanDB manquante")
    refused(library, "create_empty_spool", dict(params, tare_g=100, manufacturer="  "), "fabricant manquant")
    work = act(library, "create_empty_spool", dict(params, tare_g="180,456"))
    assert work["empty_spools"]["V001"]["tare_g"] == 180.46


def test_a_new_tare_recalculates_every_weighed_spool_on_it():
    library = with_spools()
    assert left(library, "B002") == 470 and left(library, "B001") == 1000
    work, events, _ = run(library, "weigh_empty_spool", {"id": "V001", "tare_g": 176})
    assert left(work, "B002") == 474 and left(work, "B001") == 1000
    assert events[0]["recalculated"] == ["B002"]


def test_an_empty_spool_in_use_stays_and_numbers_are_never_reused():
    refused(with_spools(), "delete_empty_spool", {"id": "V001"}, "utilisée par B-001, B-002")
    library = act(base(), "delete_empty_spool", {"id": "V002"})
    assert "V002" not in library["empty_spools"]
    library = act(library, "create_empty_spool", {"manufacturer": "eSun", "spool_material": "carton",
                                                  "tare_g": 170, "nominal_net_g": 1000, "source": "manuel"})
    assert sorted(library["empty_spools"]) == ["V001", "V003"]


# ---------------------------------------------------------------- filament records (C)
def test_the_synthetic_database_is_read_like_the_firmware_s(tmp_path):
    assert MATERIALS_ERROR == ""
    assert sorted(MATERIALS) == ["00001", "00002", "00003", "00004", "00005", "01001", "01002",
                                 "01003", "02001", "03001"]
    assert MATERIALS["00001"] == {"id": "00001", "brand": "Generic", "name": "Generic PLA",
                                  "type": "PLA", "density": 1.24, "diameter": 1.75}
    assert MATERIALS["03001"]["density"] is None
    assert model.read_materials(str(tmp_path / "absent.json"))[1].startswith(
        "base matériau de la K1 illisible")
    (tmp_path / "nolist.json").write_text('{"result": {}}', encoding="utf-8")
    assert model.read_materials(str(tmp_path / "nolist.json")) == ({}, "base matériau de la K1 sans liste de fiches")
    (tmp_path / "empty.json").write_text('{"result": {"list": [{"base": {"id": "1"}}]}}', encoding="utf-8")
    assert model.read_materials(str(tmp_path / "empty.json"))[1] == "base matériau de la K1 sans fiche exploitable"


@pytest.mark.parametrize("manufacturer, material, name, expected", SUGGESTIONS)
def test_the_suggested_material_record(manufacturer, material, name, expected):
    assert model.suggest_creality_id(manufacturer, material, name, MATERIALS) == expected


def test_every_filament_record_points_at_a_record_of_that_type_on_the_k1():
    library = base()
    for fiche in library["filaments"].values():
        assert fiche["creality_id"] in MATERIALS
        assert MATERIALS[fiche["creality_id"]]["type"] == fiche["material"]
    assert [library["filaments"][ident]["creality_id"] for ident in ("F001", "F002", "F003")] == \
        ["00001", "01001", "00003"]
    assert [library["filaments"][ident]["density"] for ident in ("F001", "F002", "F003")] == [1.24, 1.26, 1.27]
    assert library["filaments"]["F001"]["colour"] == "FF1E1E"


def test_a_filament_record_needs_a_material_record_that_fits():
    library = base()
    fiche = {"manufacturer": "Geeetech", "colour": "112233"}
    refused(library, "create_filament", dict(fiche, material="ASA"), "choisir la fiche matériau Creality")
    refused(library, "create_filament", fiche, "choisir la fiche matériau Creality")
    refused(library, "create_filament", dict(fiche, creality_id="09999"), "09999 inconnue de la K1")
    refused(library, "create_filament", dict(fiche, material="PETG", creality_id="00001"),
            "est du PLA, pas du PETG")
    refused(library, "create_filament", dict(fiche, material="PLA"), "base matériau de la K1 illisible",
            context=ctx(materials={}))
    refused(library, "create_filament", dict(fiche, manufacturer="Nodensity", material="PA"),
            "densité inconnue pour PA")
    work = act(library, "create_filament", dict(fiche, manufacturer="Nodensity", material="PA", density="1,14"))
    assert (work["filaments"]["F004"]["density"], work["filaments"]["F004"]["creality_id"]) == (1.14, "03001")
    refused(library, "create_filament", dict(fiche, material="PLA", colour="rouge"), "couleur : six chiffres")
    refused(library, "create_filament", {"manufacturer": "Geeetech", "material": "PLA"}, "couleur manquante")
    refused(library, "create_filament", {"manufacturer": "Geeetech", "name": "PLA", "material": "PLA",
                                         "colour": "0ff1e1e"}, "fiche identique déjà présente : F001")


def test_an_edit_keeps_a_chosen_material_record_until_the_material_changes():
    library = act(base(), "edit_filament", {"id": "F001", "creality_id": "02001"})
    assert (library["filaments"]["F001"]["creality_id"], library["filaments"]["F001"]["density"]) == ("02001", 1.24)
    # The form sends the whole record back, without the id: the choice stays.
    library = act(library, "edit_filament", {"id": "F001", "manufacturer": "Geeetech", "name": "PLA",
                                             "material": "PLA", "colour": "FF1E1E", "notes": "mat"})
    assert library["filaments"]["F001"]["creality_id"] == "02001"
    work, events, result = run(library, "edit_filament", {"id": "F001", "material": "PETG"})
    fiche = work["filaments"]["F001"]
    assert (fiche["material"], fiche["creality_id"], fiche["density"]) == ("PETG", "00003", 1.27)
    assert {"material", "creality_id", "density"} <= set(result["changed"])


def test_a_record_in_use_stays_and_its_edit_names_its_spools():
    library = with_spools()
    refused(library, "delete_filament", {"id": "F001"}, "fiche utilisée par B-001, B-002")
    work, events, _ = run(library, "edit_filament", {"id": "F001", "colour": "00FF00"})
    assert events[0]["spools"] == ["B001", "B002"] and events[0]["fields"] == ["colour"]
    assert "F003" not in act(base(), "delete_filament", {"id": "F003"})["filaments"]


def test_colour_and_material_keys_are_the_slot_map_s():
    slot_map = load(OWNED / "kctrl_slot_map.py", "kctrl_slot_map_for_spools")
    for text in COLOURS:
        assert model.colour_key(text) == slot_map.colour_key(text), text
    for text in ("000001", "001001", "00001", "123456", "-1", "None", "", 1):
        assert model.material_key(text) == slot_map.material_key(text), text


# ---------------------------------------------------------------- spools and states (E)
def test_a_new_spool_starts_from_its_empty_spool_s_nominal_net():
    library = with_spools()
    spool = library["spools"]["B001"]
    assert spool["initial_net_g"] == 1000 and spool["basis"] == {"kind": "neuve", "value_g": 1000, "on": NOW}
    view = model.spool_view(library, spool)
    assert view["label"] == "B-001" and not view["low"]
    assert view["remaining"]["shown"] == {"g": 1000, "percent": 100, "m": 335}
    assert view["remaining"]["gross_g"] == 1180
    weighed = model.spool_view(library, library["spools"]["B002"])
    assert weighed["remaining"]["shown"] == {"g": 470, "percent": 47, "m": 158}
    assert weighed["remaining"]["gross_g"] == 650
    assert library["spools"]["B003"]["place"] == "Étagère 2"


def test_a_spool_is_refused_when_its_remaining_cannot_be_computed():
    library = base()
    refused(library, "create_spool", {"filament": "F001"}, "net initial manquant")
    refused(library, "create_spool", {"filament": "F001", "initial_net_g": 1000, "basis_kind": "pesee",
                                      "value_g": 900}, "poids brut sans bobine vide")
    refused(library, "create_spool", {"filament": "F001", "empty_spool": "V001", "basis_kind": "pesee",
                                      "value_g": 150}, "inférieur à la tare")
    refused(library, "create_spool", {"filament": "F001", "empty_spool": "V001",
                                      "basis_kind": "estimation", "value_g": 1200}, "au-delà du net initial")
    refused(library, "create_spool", {"filament": "F001", "empty_spool": "V001",
                                      "basis_kind": "estimation"}, "valeur manquante")
    refused(library, "create_spool", {"filament": "F009"}, "fiche filament introuvable")
    refused(library, "create_spool", {"filament": "F001", "empty_spool": "V009"}, "bobine vide introuvable")
    refused(library, "create_spool", {"filament": "F001", "empty_spool": "V001", "state": "terminee"}, "état")
    refused(library, "create_spool", {"filament": "F001", "empty_spool": "V001", "slot": "T1A"},
            "emplacement donné pour une bobine hors du CFS")
    refused(library, "create_spool", {"filament": "F001", "empty_spool": "V001", "state": "cfs",
                                      "slot": "T5A"}, "emplacement : T1A à T4D")
    work = act(library, "create_spool", {"filament": "F001", "initial_net_g": 750,
                                         "basis_kind": "estimation", "value_g": "300"})
    remaining = model.remaining_of(work, work["spools"]["B001"])
    assert remaining["net_g"] == 300 and remaining["gross_g"] is None
    assert remaining["shown"]["percent"] == 40


def test_a_weighing_keeps_its_gap_to_the_count_and_restarts_the_count():
    library = in_cfs(with_spools(), "B001", "T1A", seen({"T1A": RED_PLA}))
    library = act(library, "print_end", {"job": "j1", "segments": [{"slot": "T1A", "mm": 67056.7}],
                                         "spools": {"T1A": "B001"}}, internal=True)
    counted = library["spools"]["B001"]["counted_g"]
    assert 199 < counted < 201 and not model.counting_verified(library)
    work, events, _ = run(library, "set_remaining", {"id": "B001", "kind": "pesee", "value_g": 950})
    spool = work["spools"]["B001"]
    gap = model.round_half_away(770 - (1000 - counted), 2)
    assert spool["counted_g"] == 0 and spool["basis"]["kind"] == "pesee" and left(work, "B001") == 770
    assert spool["last_gap"] == {"g": gap, "counted_g": counted, "previous": "neuve", "on": NOW}
    assert events[0]["kind"] == "reste" and events[0]["gap_g"] == gap
    assert model.counting_verified(work)
    estimated = act(library, "set_remaining", {"id": "B001", "kind": "estimation", "value_g": 500})
    assert estimated["spools"]["B001"]["last_gap"] is None and left(estimated, "B001") == 500


def in_state(state):
    library = with_spools()
    if state == "a_ranger":
        library = act(in_cfs(library, "B001", "T1A"), "remove_from_cfs", {"id": "B001"})
    elif state == "cfs":
        library = in_cfs(library, "B001", "T1A")
    elif state in ("terminee", "jetee"):
        library = act(library, "finish" if state == "terminee" else "discard", {"id": "B001"})
    assert library["spools"]["B001"]["state"] == state
    return library


TRANSITIONS = [
    ("stock", "put_in_cfs", {"slot": "T1B"}, "cfs"),
    ("a_ranger", "put_in_cfs", {"slot": "T1B"}, "cfs"),
    ("cfs", "put_in_cfs", {"slot": "T1B"}, "déjà au CFS en T1A"),
    ("terminee", "put_in_cfs", {"slot": "T1B"}, "archivée"),
    ("jetee", "put_in_cfs", {"slot": "T1B"}, "archivée"),
    ("cfs", "remove_from_cfs", {}, "a_ranger"),
    ("stock", "remove_from_cfs", {}, "n'est pas au CFS"),
    ("a_ranger", "remove_from_cfs", {}, "n'est pas au CFS"),
    ("terminee", "remove_from_cfs", {}, "n'est pas au CFS"),
    ("a_ranger", "store", {"place": "Boîte 3"}, "stock"),
    ("stock", "store", {"place": "Boîte 4"}, "stock"),
    ("cfs", "store", {"place": "Boîte 4"}, "retirer du CFS"),
    ("jetee", "store", {"place": "Boîte 4"}, "retirer du CFS"),
    ("cfs", "finish", {}, "terminee"),
    ("a_ranger", "finish", {}, "terminee"),
    ("stock", "finish", {}, "terminee"),
    ("terminee", "finish", {}, "déjà archivée"),
    ("jetee", "finish", {}, "déjà archivée"),
    ("cfs", "discard", {}, "jetee"),
    ("a_ranger", "discard", {}, "jetee"),
    ("stock", "discard", {}, "jetee"),
    ("terminee", "discard", {}, "déjà archivée"),
    ("terminee", "restore", {}, "stock"),
    ("jetee", "restore", {}, "stock"),
    ("stock", "restore", {}, "n'est pas archivée"),
    ("cfs", "restore", {}, "n'est pas archivée"),
    ("a_ranger", "restore", {}, "n'est pas archivée"),
]


@pytest.mark.parametrize("state, action, extra, outcome", TRANSITIONS,
                         ids=["%s-%s" % (item[0], item[1]) for item in TRANSITIONS])
def test_each_state_transition(state, action, extra, outcome):
    library = in_state(state)
    params = dict(extra, id="B001")
    if outcome in model.STATES:
        work = act(library, action, params)
        spool = work["spools"]["B001"]
        assert spool["state"] == outcome
        assert bool(spool["slot"]) == (outcome == "cfs")
        assert sorted(work["spools"]) == sorted(library["spools"]) and model.check(work) == []
        if action == "store":
            assert spool["place"] == extra["place"]
    else:
        refused(library, action, params, outcome)


def test_no_sequence_of_actions_loses_a_spool_or_shares_a_slot():
    rng = random.Random(102)
    library = act(with_spools(), "create_spool", {"filament": "F002", "empty_spool": "V001", "state": "a_ranger"})
    spools = sorted(library["spools"])
    slots = ["T1A", "T1B", "T2A"]
    makers = [
        ("put_in_cfs", lambda: {"id": rng.choice(spools), "slot": rng.choice(slots)}),
        ("remove_from_cfs", lambda: {"id": rng.choice(spools)}),
        ("store", lambda: {"id": rng.choice(spools), "place": rng.choice(["", "Boîte", "Étagère"])}),
        ("finish", lambda: {"id": rng.choice(spools)}),
        ("discard", lambda: {"id": rng.choice(spools)}),
        ("restore", lambda: {"id": rng.choice(spools)}),
        ("set_remaining", lambda: {"id": rng.choice(spools), "kind": "estimation",
                                   "value_g": rng.choice([0, 10, 500])}),
        ("observe", None),
    ]
    refusals = 0
    for step in range(800):
        name, make = rng.choice(makers)
        observations = seen({slot: RED_PLA for slot in slots if rng.random() < 0.5})
        try:
            library = act(library, name, {} if make is None else make(), ctx(NOW + step, observations),
                          internal=make is None)
        except model.ModelError:
            refusals += 1
        assert sorted(library["spools"]) == spools and model.check(library) == []
        held = [spool["slot"] for spool in library["spools"].values() if spool["state"] == "cfs"]
        assert len(held) == len(set(held))
    assert 0 < refusals < 800


def test_putting_a_spool_where_another_was_sends_the_other_to_be_put_away():
    library = in_cfs(with_spools(), "B001", "T1A")
    work, events, _ = run(library, "put_in_cfs", {"id": "B002", "slot": "T1A"})
    assert (work["spools"]["B001"]["state"], work["spools"]["B001"]["slot"]) == ("a_ranger", "")
    assert (work["spools"]["B002"]["state"], work["spools"]["B002"]["slot"]) == ("cfs", "T1A")
    assert events[0]["detail"] == "remplacée par B-002"


def test_an_archived_spool_keeps_its_place_and_comes_back_to_stock():
    library = act(with_spools(), "store", {"id": "B002", "place": "Boîte à chaussures"})
    library = act(library, "finish", {"id": "B002"})
    assert (library["spools"]["B002"]["state"], library["spools"]["B002"]["place"]) == \
        ("terminee", "Boîte à chaussures")
    library = act(library, "restore", {"id": "B002"})
    assert (library["spools"]["B002"]["state"], library["spools"]["B002"]["place"]) == \
        ("stock", "Boîte à chaussures")


# ---------------------------------------------------------------- the CFS, without a socket (F)
class Sealed(dict):
    """A unit whose serial number and uuid must never be read."""

    def __getitem__(self, key):
        assert key not in ("sn", "uuid"), key
        return dict.__getitem__(self, key)

    def get(self, key, default=None):
        assert key not in ("sn", "uuid"), key
        return dict.get(self, key, default)


def test_the_box_is_read_without_its_serial_number_or_uuid():
    status = box({"T1A": RED_PLA, "T2C": ("001001", "0ffffff", "Creality", "73")})
    found = model.observe_box({name: Sealed(unit) for name, unit in status.items()})
    assert "SERIAL" not in json.dumps(found) and "UUID" not in json.dumps(found)
    assert sorted(found) == sorted(model.SLOT_NAMES)
    assert found["T1A"] == {"connected": True, "present": True, "material": "000001",
                            "colour": "FF1E1E", "chip": None}
    assert found["T2C"]["chip"] == 73
    assert found["T1B"] == {"connected": True, "present": False, "material": "", "colour": "", "chip": None}
    assert not found["T3A"]["connected"] and not found["T3A"]["present"]
    assert not any(slot["connected"] for slot in model.observe_box({"T1": "x"}).values())


def test_each_slot_shows_what_the_cfs_holds_against_what_thomas_expects():
    library = with_spools()
    library = act(library, "create_spool", {"filament": "F002", "empty_spool": "V001"})                       # B004
    library = act(library, "create_spool", {"filament": "F003", "empty_spool": "V002"})                       # B005
    library = act(library, "create_spool", {"filament": "F001", "empty_spool": "V001", "state": "a_ranger"})  # B006
    observations = seen({"T1A": RED_PLA, "T1C": ("000001", "0ffffff"), "T1D": RED_PLA,
                         "T2B": ("000003", "0000000")})
    library = in_cfs(library, "B001", "T1A", observations)
    library = in_cfs(library, "B003", "T1C", observations)
    library = in_cfs(library, "B004", "T2A", observations)
    library = in_cfs(library, "B005", "T2B", observations)
    library = act(library, "queue_cfs", {"slot": "T2B", "spool": "B005", "material": None, "colour": None},
                  internal=True)
    library = in_cfs(library, "B002", "T3B", observations)
    views = model.slot_views(library, observations, MATERIALS)
    assert {view["slot"]: view["status"] for view in views} == {
        "T1A": "ok", "T1B": "vide", "T1C": "a_verifier", "T1D": "inconnue", "T2A": "attendue",
        "T2B": "en_attente_cfs", "T2C": "vide", "T2D": "vide", "T3B": "hors_ligne"}
    assert view_of(views, "T1D")["candidates"] == ["B006"]
    plan = view_of(views, "T1C")["plan"]
    assert (plan["spool"], plan["material"], plan["colour"]) == ("B003", "000003", "0000000")
    assert view_of(views, "T1A")["observed"]["type"] == "PLA" and view_of(views, "T1A")["spool"] == "B001"


def test_candidates_put_the_exact_spools_just_taken_out_first_and_stop_at_eight():
    library = act(base(), "create_filament", {"manufacturer": "Creality", "name": "CR-PLA",
                                              "material": "PLA", "colour": "FF1E1E"})            # F004
    made = []
    for index, (fiche, state) in enumerate([("F001", "stock")] * 3 + [("F001", "a_ranger")] * 3
                                           + [("F004", "a_ranger")] * 3 + [("F002", "a_ranger")]):
        library, _, result = run(library, "create_spool", {"filament": fiche, "empty_spool": "V001",
                                                           "state": state}, ctx(NOW + index))
        made.append(result["id"])
    found = model.candidates(library, seen({"T1A": RED_PLA})["T1A"], MATERIALS)
    assert found == ["B006", "B005", "B004", "B003", "B002", "B001", "B009", "B008"]


def test_a_write_sends_only_what_differs_and_never_to_an_empty_slot():
    library = in_cfs(with_spools(), "B001", "T1A", seen({"T1A": RED_PLA}))
    plan = model.write_plan(library, "T1A", seen({"T1A": ("000001", "0ffffff")}))
    assert (plan["material"], plan["colour"]) == (None, "0ff1e1e")
    assert model.gcode_of_plan(plan) == "KCTRL_FILAMENT SLOT=T1A COLOR=0ff1e1e"
    plan = model.write_plan(library, "T1A", seen({"T1A": ("000003", "0ffffff")}))
    assert model.gcode_of_plan(plan) == "KCTRL_FILAMENT SLOT=T1A MATERIAL=000001 COLOR=0ff1e1e"
    plan = model.write_plan(library, "T1A", seen({"T1A": ("000003", "0ff1e1e")}))
    assert model.gcode_of_plan(plan) == "KCTRL_FILAMENT SLOT=T1A MATERIAL=000001"
    with pytest.raises(model.ModelError, match="rien à écrire"):
        model.gcode_of_plan(model.write_plan(library, "T1A", seen({"T1A": RED_PLA})))
    with pytest.raises(model.ModelError, match="vide au CFS"):
        model.write_plan(library, "T1A", seen({}))
    with pytest.raises(model.ModelError, match="non connectée"):
        model.write_plan(library, "T1A", seen({"T1A": RED_PLA}, connected=("2",)))
    with pytest.raises(model.ModelError, match="aucune bobine attendue en T1B"):
        model.write_plan(library, "T1B", seen({"T1B": RED_PLA}))
    with pytest.raises(model.ModelError, match="emplacement inconnu"):
        model.write_plan(library, "T9Z", seen({}))


@pytest.mark.parametrize("plan, fragment", [
    ({"slot": "T1A\nG28", "material": "000001", "colour": None}, "emplacement inconnu"),
    ({"slot": "T1A", "material": "000001 G28", "colour": None}, "matériau mal formé"),
    ({"slot": "T1A", "material": "000001\n", "colour": None}, "matériau mal formé"),
    ({"slot": "T1A", "material": "00001", "colour": None}, "matériau mal formé"),
    ({"slot": "T1A", "material": None, "colour": "0ff1e1e\nM104 S300"}, "couleur mal formée"),
    ({"slot": "T1A", "material": None, "colour": "0FF1E1E"}, "couleur mal formée"),
    ({"slot": "T1A", "material": None, "colour": None}, "rien à écrire"),
])
def test_the_command_refuses_anything_but_its_exact_values(plan, fragment):
    with pytest.raises(model.ModelError, match=fragment):
        model.gcode_of_plan(plan)


def test_a_readback_confirms_only_what_was_written():
    plan = {"slot": "T1A", "material": "000001", "colour": "0ff1e1e"}
    assert model.readback_ok(plan, seen({"T1A": RED_PLA})["T1A"])
    assert not model.readback_ok(plan, seen({"T1A": ("000001", "0ffffff")})["T1A"])
    assert not model.readback_ok(plan, seen({})["T1A"])
    assert model.readback_ok({"slot": "T1A", "material": None, "colour": "0ff1e1e"},
                             seen({"T1A": ("000003", "0ff1e1e")})["T1A"])


def test_the_refill_partners_gained_and_lost_are_named_before_a_write():
    observations = seen({"T1A": RED_PLA, "T1B": RED_PLA, "T2A": ("000003", "0000000"),
                         "T2B": ("000003", "0000000")})
    assert model.refill_impact(observations, "T1A", "000003", "000000") == {
        "gained": ["T2A", "T2B"], "lost": ["T1B"], "partners": ["T2A", "T2B"]}


def test_adopting_the_cfs_identity_never_edits_a_shared_record():
    black_petg = ("000003", "0000000")
    observations = seen({"T1A": black_petg, "T1B": black_petg})
    library = in_cfs(with_spools(), "B001", "T1A", observations)
    work, events, result = run(library, "adopt_cfs", {"slot": "T1A"}, ctx(observations=observations))
    assert work["filaments"]["F001"] == library["filaments"]["F001"]
    fiche = work["filaments"][result["filament"]]
    assert result["filament"] == "F004" and work["spools"]["B001"]["filament"] == "F004"
    assert (fiche["manufacturer"], fiche["material"], fiche["creality_id"], fiche["colour"], fiche["density"]) == \
        ("Geeetech", "PETG", "00003", "000000", 1.27)
    work = in_cfs(work, "B002", "T1B", observations)
    again, _, result = run(work, "adopt_cfs", {"slot": "T1B"}, ctx(observations=observations))
    assert result["filament"] == "F004" and len(again["filaments"]) == 4
    unchanged, events, _ = run(again, "adopt_cfs", {"slot": "T1B"}, ctx(observations=observations))
    assert events == []
    refused(library, "adopt_cfs", {"slot": "T1A"}, "inconnu de la base",
            context=ctx(observations=seen({"T1A": ("009999", "0000000")})))
    refused(library, "adopt_cfs", {"slot": "T1A"}, "vide au CFS", context=ctx(observations=seen({})))
    refused(library, "adopt_cfs", {"slot": "T1B"}, "aucune bobine attendue", context=ctx(observations=observations))


def test_the_first_reading_is_a_reference_and_a_removal_sends_the_spool_to_be_put_away():
    present = seen({"T1A": RED_PLA, "T2D": ("000003", "0000000")})
    library = in_cfs(with_spools(), "B001", "T1A", present)
    library, events = observe(library, present)
    assert events == []
    library, events = observe(library, seen({"T2D": ("000003", "0000000")}), NOW + 10)
    assert (library["spools"]["B001"]["state"], library["spools"]["B001"]["slot"]) == ("a_ranger", "")
    assert [event["detail"] for event in events] == ["retirée du CFS"]


def test_a_spool_linked_to_an_empty_slot_waits_for_it_then_can_leave():
    library, _ = observe(with_spools(), seen({}))
    library = in_cfs(library, "B001", "T1A", seen({}))
    assert view_of(model.slot_views(library, seen({}), MATERIALS), "T1A")["status"] == "attendue"
    library, events = observe(library, seen({}))
    assert events == [] and library["spools"]["B001"]["state"] == "cfs"
    library, events = observe(library, seen({"T1A": RED_PLA}))
    assert (events[0]["detail"], events[0]["spool"]) == ("bobine arrivée", "B001")
    library, events = observe(library, seen({}))
    assert library["spools"]["B001"]["state"] == "a_ranger"


def test_a_unit_that_drops_off_says_nothing_about_its_spools():
    present = seen({"T2A": RED_PLA})
    library, _ = observe(in_cfs(with_spools(), "B001", "T2A", present), present)
    library, events = observe(library, seen({}, connected=("1",)))
    assert events == [] and library["spools"]["B001"]["state"] == "cfs"
    views = model.slot_views(library, seen({}, connected=("1",)), MATERIALS)
    assert view_of(views, "T2A")["status"] == "hors_ligne"


def test_a_changed_colour_at_the_cfs_is_journaled_and_shown_to_check():
    present = seen({"T1A": RED_PLA})
    library, _ = observe(in_cfs(with_spools(), "B001", "T1A", present), present)
    white = seen({"T1A": ("000001", "0ffffff")})
    library, events = observe(library, white)
    assert events[0]["detail"] == "matière ou couleur changée au CFS"
    assert library["spools"]["B001"]["state"] == "cfs"
    view = view_of(model.slot_views(library, white, MATERIALS), "T1A")
    assert view["status"] == "a_verifier" and view["plan"]["colour"] == "0ff1e1e"


def test_a_queued_write_ends_with_its_result_or_when_its_spool_leaves():
    library = in_cfs(with_spools(), "B001", "T1A", seen({"T1A": RED_PLA}))
    queued = act(library, "queue_cfs", {"slot": "T1A", "spool": "B001", "material": None,
                                        "colour": "0ff1e1e"}, internal=True)
    assert queued["pending_cfs"]["T1A"]["spool"] == "B001"
    done = act(queued, "write_result", {"slot": "T1A", "spool": "B001", "material": None,
                                        "colour": "0ff1e1e", "result": "ok",
                                        "read": {"material": "000001", "colour": "FF1E1E"}}, internal=True)
    assert done["pending_cfs"] == {} and done["slots"]["T1A"]["last_write"]["result"] == "ok"
    for name, params in (("remove_from_cfs", {"id": "B001"}), ("finish", {"id": "B001"}),
                         ("put_in_cfs", {"id": "B002", "slot": "T1A"})):
        work, events, _ = run(queued, name, params)
        assert work["pending_cfs"] == {}, name
        assert any(event["kind"] == "ecriture_cfs" and event["result"] == "annulée" for event in events)
    refused(library, "queue_cfs", {"slot": "T1B", "spool": "B001"}, "n'est plus attendue en T1B", internal=True)


def test_the_badge_lists_what_waits_for_thomas():
    library = act(with_spools(), "create_spool", {"filament": "F001", "initial_net_g": 1000,
                                                  "basis_kind": "estimation", "value_g": 50})  # B004
    observations = seen({"T1A": ("000001", "0ffffff"), "T1B": RED_PLA, "T1D": RED_PLA})
    library = in_cfs(library, "B001", "T1A", observations)
    library = in_cfs(library, "B004", "T1B", observations)
    library = act(library, "write_result", {"slot": "T1A", "spool": "B001", "material": None,
                                            "colour": "0ff1e1e", "result": "ecart", "detail": "relu 0ffffff",
                                            "read": {"material": "000001", "colour": "FFFFFF"}}, internal=True)
    library = act(library, "print_end", {"job": "j1", "segments": [
        {"slot": "", "mm": 120.0, "reason": "emplacement non prouvé"}]}, internal=True)
    views = model.slot_views(library, observations, MATERIALS)
    assert model.attention(library, views) == [
        "T1A à vérifier", "T1A : écriture au CFS non confirmée", "T1B : B-004 basse (50 g)",
        "T1D : bobine inconnue", "1 consommation à attribuer"]
    library = act(library, "print_end", {"job": "j2", "segments": [
        {"slot": "", "mm": 80.0, "reason": "emplacement non prouvé"}]}, internal=True)
    assert model.attention(library, views)[-1] == "2 consommations à attribuer"


# ---------------------------------------------------------------- counting (G, model side)
def test_a_print_is_counted_on_the_spools_that_were_in_their_slots_and_only_once():
    observations = seen({"T1A": RED_PLA, "T1C": ("000003", "0000000")})
    library = in_cfs(in_cfs(with_spools(), "B001", "T1A", observations), "B003", "T1C", observations)
    params = {"job": "job-7", "file": "benchy.gcode", "start": NOW - 3600, "end": NOW, "outcome": "complete",
              "segments": [{"slot": "T1A", "mm": 6000.0}, {"slot": "T1C", "mm": 1000.0},
                           {"slot": "T1A", "mm": 847.96}, {"slot": "T1A", "mm": 0.0}],
              "spools": {"T1A": "B001", "T1C": "B003"}, "planned": [{"mm": 6847.96, "g": 20.59}]}
    work, events, result = run(library, "print_end", params, internal=True)
    assert result == {"job": "job-7", "applied": True}
    counted = model.round_half_away(model.grams_of_mm(6000.0, PLA) + model.grams_of_mm(847.96, PLA), 2)
    petg = model.round_half_away(model.grams_of_mm(1000.0, PETG), 2)
    assert work["spools"]["B001"]["counted_g"] == counted == 20.42
    assert left(work, "B001") == model.round_half_away(1000 - counted, 2)
    assert left(work, "B003") == model.round_half_away(300 - petg, 2)
    record = work["prints"][-1]
    assert record["per_spool"] == [{"spool": "B001", "slot": "T1A", "mm": 6848.0, "g": counted, "m": 6.85},
                                   {"spool": "B003", "slot": "T1C", "mm": 1000.0, "g": petg, "m": 1.0}]
    assert record["planned"] == [{"mm": 6847.96, "g": 20.59}] and work["unassigned"] == []
    again, events, result = run(work, "print_end", params, internal=True)
    assert result == {"job": "job-7", "applied": False} and events == [] and again == work


def test_a_segment_without_a_proved_slot_or_spool_waits_for_one_click():
    library = in_cfs(with_spools(), "B001", "T1A", seen({"T1A": RED_PLA}))
    work = act(library, "print_end", {"job": "job-8", "spools": {"T1A": "B001"}, "segments": [
        {"slot": "", "mm": 500.0, "reason": "emplacement non prouvé après un rechargement"},
        {"slot": "T1B", "mm": 300.0},
        {"slot": "T1A", "mm": 200.0, "reason": "recharge automatique"}]}, internal=True)
    assert [segment["id"] for segment in work["unassigned"]] == ["S001", "S002", "S003"]
    assert work["unassigned"][1]["reason"] == "aucune bobine liée à T1B"
    assert work["spools"]["B001"]["counted_g"] == 0
    grams = model.round_half_away(model.grams_of_mm(500.0, PLA), 2)
    assigned, events, result = run(work, "assign_segment", {"segment": "S001", "spool": "B002"})
    assert assigned["spools"]["B002"]["counted_g"] == grams == result["g"]
    assert [segment["id"] for segment in assigned["unassigned"]] == ["S002", "S003"]
    assert assigned["prints"][-1]["assigned"] == [{"segment": "S001", "spool": "B002", "mm": 500.0, "g": grams}]
    dismissed = act(assigned, "dismiss_segment", {"segment": "S002"})
    refused(dismissed, "assign_segment", {"segment": "S002", "spool": "B002"}, "segment introuvable")


def test_a_segment_names_its_spool_when_the_counter_knew_it():
    library = in_cfs(with_spools(), "B001", "T1A", seen({"T1A": RED_PLA}))
    work = act(library, "print_end", {"job": "job-9", "spools": {"T1A": "B001"}, "segments": [
        {"slot": "T1A", "spool": "B002", "mm": 1000.0},
        {"slot": "T1A", "mm": 500.0},
        {"slot": "T1A", "spool": "B099", "mm": 200.0}]}, internal=True)
    assert work["spools"]["B002"]["counted_g"] == model.round_half_away(model.grams_of_mm(1000.0, PLA), 2)
    assert work["spools"]["B001"]["counted_g"] == model.round_half_away(model.grams_of_mm(500.0, PLA), 2)
    assert [(item["slot"], item["mm"], item["reason"]) for item in work["unassigned"]] == [
        ("T1A", 200.0, "bobine B-099 introuvable")]


def test_the_history_and_the_list_to_attribute_stay_bounded():
    library = with_spools()
    for index in range(25):
        library = act(library, "print_end", {"job": "j%d" % index, "segments": [
            {"slot": "", "mm": 10.0, "reason": reason} for reason in ("x", "y", "z")]}, internal=True)
    assert len(library["prints"]) == 20 and library["prints"][0]["job"] == "j5"
    assert len(library["unassigned"]) == 50
    assert (library["unassigned"][0]["id"], library["unassigned"][-1]["id"]) == ("S026", "S075")
    assert model.check(library) == []


def test_the_planned_consumption_is_read_from_the_end_of_the_sliced_file(tmp_path):
    footer = ("; filament used [mm] = 6847.96, 0.00\n; filament used [cm3] = 16.47, 0.00\n"
              "; filament used [g] = 20.59, 0.00\n; total filament used [g] = 20.59\n"
              "; CONFIG_BLOCK_START\n; nozzle_diameter = 0.4\n")
    job = tmp_path / "job.gcode"
    job.write_text("G1 X10 E0.4\n" * 1000 + footer, encoding="ascii")
    planned, note = model.read_planned(str(job))
    assert planned == [{"mm": 6847.96, "g": 20.59}, {"mm": 0.0, "g": 0.0}] and note == "2 filament(s) prévu(s)"
    early = tmp_path / "early.gcode"
    early.write_text(footer + "G1 X10 E0.4\n" * 50, encoding="ascii")
    assert model.read_planned(str(early), limit=100) == ([], "pas de consommation prévue en fin de fichier")
    assert model.read_planned(str(tmp_path / "absent.gcode"))[1].startswith("fichier illisible")


# ---------------------------------------------------------------- export, settings, size
def test_an_export_comes_back_whole_without_its_queued_writes():
    library = in_cfs(with_spools(), "B001", "T1A", seen({"T1A": RED_PLA}))
    library = act(library, "queue_cfs", {"slot": "T1A", "spool": "B001", "material": None,
                                         "colour": "0ff1e1e"}, internal=True)
    document = json.loads(json.dumps(model.export_document(library, [{"kind": "etat", "t": NOW}], NOW)))
    back = model.import_document(document)
    assert back["pending_cfs"] == {} and document["journal"] == [{"kind": "etat", "t": NOW}]
    assert back["spools"] == library["spools"] and back["filaments"] == library["filaments"]
    with pytest.raises(model.ModelError, match="fichier d'export"):
        model.import_document({"format": "kctrl_spools.library"})
    with pytest.raises(model.ModelError, match="version plus récente"):
        model.import_document(dict(document, schema=model.SCHEMA + 1))
    broken = copy.deepcopy(document)
    broken["library"]["spools"]["B001"]["filament"] = "F099"
    with pytest.raises(model.ModelError, match="export incohérent"):
        model.import_document(broken)
    partial = copy.deepcopy(document)
    del partial["library"]["settings"]
    assert model.import_document(partial)["settings"] == {"cut_loss_mm": 0.0, "low_g": 100.0}


def test_settings_are_bounded_and_journaled():
    library = model.empty_library()
    work, events, result = run(library, "settings", {"low_g": "150"})
    assert work["settings"]["low_g"] == 150 and events[0]["kind"] == "reglages" and events[0]["low_g"] == 150
    refused(library, "settings", {"cut_loss_mm": 500}, "perte de coupe : entre 0 et 200")
    assert run(library, "settings", {"low_g": 100})[1] == []


def test_two_hundred_spools_stay_small_and_quick():
    library = base()
    for index in range(200):
        library = act(library, "create_spool", {"filament": "F00%d" % (1 + index % 3), "empty_spool": "V001",
                                                "place": "Étagère %d" % (index % 7)})
    size = len(json.dumps(library, ensure_ascii=False).encode("utf-8"))
    assert size < 160000, size
    start = time.perf_counter()
    act(library, "store", {"id": "B150", "place": "Boîte"})
    views = [model.spool_view(library, spool) for spool in library["spools"].values()]
    assert time.perf_counter() - start < 1.0 and len(views) == 200


if __name__ == "__main__":
    with open(str(VECTORS), "w", encoding="utf-8", newline="\n") as stream:
        json.dump(vectors(), stream, ensure_ascii=False, sort_keys=True, indent=1)
        stream.write("\n")
    print("écrit :", VECTORS)
