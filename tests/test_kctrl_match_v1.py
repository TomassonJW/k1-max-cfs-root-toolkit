"""L'appariement automatique des filaments du fichier sur les bobines (point 2).

Mainsail et Fluidd n'ont pas le popup de l'écran : la table CFS garde ce que
le travail précédent ou le dernier `KCTRL_SLOT` y a laissé, et un fichier
bleu part en noir sans un mot. `kctrl_slot_map` publie maintenant `match` -
pour chaque filament déclaré par le fichier, la bobine chargée de même
type et même couleur - et `KCTRL_MATCH` l'écrit dans la table avant de
chauffer, ou refuse en nommant la bobine la plus proche. `START_PRINT` lit
`match` au rendu et émet `KCTRL_MATCH STARTING=1`.

Formes réelles : couleurs CFS `0ff1e1e` (sept caractères), fichier `#8080FF`,
fiches `#ffffff` ; groupes `same_material` `[id, couleur, [emplacements],
type]` relevés le 10 septembre ; fiche `base.meterialType` (orthographe du
firmware).
"""

import json
import os
import re

import jinja2
import pytest

from test_kctrl_slot_map_v1 import (FakeConfig, FakeReactor, GcmdError, MOD,
                                    gcode)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "packages", "k1-control-v1", "owned-start-print-v2",
                      "k1-control-owned-start-print-v2.cfg")
FIXTURE_TAIL = os.path.join(ROOT, "tests", "fixtures", "k1-control-v1",
                            "orca-2.4.2-cube-2026-09-10-tail.gcode")

NAMES = ["T%d%s" % (b, s) for b in (1, 2, 3, 4) for s in "ABCD"]
IDENTITY = {name: name for name in NAMES}

# Fiches relevées sur la machine le 10 septembre (extrait).
DB = {"result": {"list": [
    {"base": {"id": "00001", "name": "Hyper PLA", "meterialType": "PLA"},
     "kvParam": {"nozzle_temperature": 220}},
    {"base": {"id": "00003", "name": "Generic PETG", "meterialType": "PETG"},
     "kvParam": {"nozzle_temperature": 240}},
    {"base": {"id": "00007", "name": "Hyper PLA-CF", "meterialType": "PLA-CF"},
     "kvParam": {"nozzle_temperature": 230}},
]}}


def box_state(slots, same_material=None):
    """`slots` : {nom: (id matiere, couleur CFS)} ; les autres sont vides."""
    state = {"same_material": same_material or []}
    for unit in "1234":
        present = any(name[1] == unit for name in slots)
        materials = ["-1"] * 4
        colours = ["-1"] * 4
        for index, letter in enumerate("ABCD"):
            name = "T" + unit + letter
            if name in slots:
                materials[index], colours[index] = slots[name]
        state["T" + unit] = {"state": "connect" if present else "None",
                             "material_type": materials, "color_value": colours}
    return state


class FakeBox:
    def __init__(self, state):
        self.state = state

    def get_status(self, eventtime=None):
        return self.state


class FakeStats:
    def __init__(self, state="standby"):
        self.state = state

    def get_status(self, eventtime=None):
        return {"state": self.state, "filename": ""}


class FakeSdcard:
    def __init__(self, path):
        self.path = path

    def get_status(self, eventtime=None):
        return {"file_path": self.path, "is_active": True}


class FakeGcmd:
    def __init__(self, **params):
        self.params = params
        self.said = []
        self.error = GcmdError

    def get(self, name, default=None):
        return self.params.get(name, default)

    def get_int(self, name, default=None):
        return int(self.params.get(name, default))

    def respond_info(self, message):
        self.said.append(message)


def tail(colours="#000000;#8080FF", types="PLA;PLA", temps="195,220"):
    return "\n".join([
        "; CONFIG_BLOCK_START",
        "; filament_colour = %s" % colours,
        "; filament_type = %s" % types,
        "; nozzle_temperature = %s" % temps,
        "; nozzle_temperature_initial_layer = %s" % temps,
        "; initial_layer_print_height = 0.2",
        "; layer_height = 0.2",
        '; filament_settings_id = "a";"b"',
        "; CONFIG_BLOCK_END",
    ])


def machine(tmp_path, table, slots, same_material=None, body="T0\nG1 X1\nT1",
            file_tail=None, printing="standby", db=DB):
    """Un kctrl_slot_map avec sa table, sa base, sa box et un fichier."""
    table_path = tmp_path / "tn_data.json"
    table_path.write_text(json.dumps({"tnn_map": table}), encoding="utf-8")
    db_path = tmp_path / "material_database.json"
    db_path.write_text(json.dumps(db), encoding="utf-8")
    obj = MOD.load_config(FakeConfig(str(table_path), str(db_path)))
    obj.printer.objects["box"] = FakeBox(box_state(slots, same_material))
    obj.printer.objects["print_stats"] = FakeStats(printing)
    obj.printer.get_reactor = lambda: FakeReactor()
    path = gcode(tmp_path, body + "\n" + (tail() if file_tail is None else file_tail))
    obj.printer.objects["virtual_sdcard"] = FakeSdcard(path)
    obj.printer.gcode.scripts = []
    obj.printer.gcode.run_script_from_command = obj.printer.gcode.scripts.append
    return obj


# --- couleurs ---------------------------------------------------------------


@pytest.mark.parametrize("raw,attendu", [
    ("#8080FF", "8080FF"), ("#ffffff", "FFFFFF"), ("0ff1e1e", "FF1E1E"),
    ("0000000", "000000"), ("000000", "000000"), ("-1", ""), ("None", ""),
    ("", ""), (None, ""), ("#GGGGGG", ""), ("0b2a1e1", "B2A1E1"),
])
def test_every_colour_form_of_the_machine_reads_as_six_hex(raw, attendu):
    assert MOD.colour_key(raw) == attendu


# --- fiches et identites ----------------------------------------------------


def test_material_records_give_a_type_name_by_id(tmp_path):
    db = tmp_path / "db.json"
    db.write_text(json.dumps(DB), encoding="utf-8")
    temps, types, error = MOD.read_material_records(str(db))
    assert error == ""
    assert temps["00001"] == 220.0
    assert types == {"00001": "PLA", "00003": "PETG", "00007": "PLA-CF"}


def test_slot_identities_read_type_from_refill_groups_then_from_the_database():
    state = box_state({"T1B": ("000001", "0000000"), "T2C": ("000003", "0ffffff"),
                       "T2D": ("000009", "0b2a1e1")},
                      same_material=[["000001", "0000000", ["T1B"], "PLA"]])
    found = MOD.slot_identities(state, {"00001": "PLA", "00003": "PETG"})
    assert found == {
        "T1B": {"material": "000001", "type": "PLA", "colour": "000000"},
        "T2C": {"material": "000003", "type": "PETG", "colour": "FFFFFF"},
        # Fiche inconnue, groupe absent : type vide, n'apparie rien.
        "T2D": {"material": "000009", "type": "", "colour": "B2A1E1"},
    }


def test_an_unplugged_unit_has_no_identities_even_with_data():
    state = box_state({"T1A": ("000001", "0ffffff")})
    state["T3"] = {"state": "None", "material_type": ["000001"] * 4,
                   "color_value": ["0ffffff"] * 4}
    found = MOD.slot_identities(state, {"00001": "PLA"})
    assert list(found) == ["T1A"]


# --- match_job, pur ---------------------------------------------------------

LOADED = {
    "T1B": {"material": "000001", "type": "PLA", "colour": "000000"},
    "T1D": {"material": "000001", "type": "PLA", "colour": "FFFFFF"},
    "T2A": {"material": "000001", "type": "PLA", "colour": "FF1E1E"},
    "T2C": {"material": "000003", "type": "PETG", "colour": "FFFFFF"},
    "T2D": {"material": "000001", "type": "PLA", "colour": "B2A1E1"},
}


def job(colours, types):
    return {"count": len(colours), "colours": colours, "types": types}


def test_type_and_colour_both_have_to_agree():
    got = MOD.match_job(job(["#ffffff", "#FFFFFF"], ["PLA", "PETG"]), LOADED, {})
    assert [e["slot"] for e in got] == ["T1D", "T2C"]
    assert "filament 1 (T1A) PLA FFFFFF -> T1D" in got[0]["note"]


def test_a_filament_already_on_a_fitting_spool_keeps_it():
    got = MOD.match_job(job(["#000000"], ["PLA"]), LOADED, {"T1A": "T1B"})
    assert got[0]["slot"] == "T1B"
    assert "deja en table" in got[0]["note"]


def test_a_filament_on_the_wrong_spool_moves_and_says_where_it_was():
    got = MOD.match_job(job(["#ff1e1e"], ["PLA"]), LOADED, {"T1A": "T1B"})
    assert got[0]["slot"] == "T2A"
    assert "etait T1B, PLA 000000" in got[0]["note"]


def test_two_identical_spools_are_interchangeable_and_the_current_one_wins():
    loaded = dict(LOADED, T3A={"material": "000001", "type": "PLA",
                               "colour": "FFFFFF"})
    got = MOD.match_job(job(["#ffffff"], ["PLA"]), loaded, {"T1A": "T3A"})
    assert got[0]["slot"] == "T3A"
    got = MOD.match_job(job(["#ffffff"], ["PLA"]), loaded, {"T1A": "T1B"})
    assert got[0]["slot"] == "T1D"
    assert "aussi T3A, identique" in got[0]["note"]


def test_no_spool_of_that_colour_names_the_nearest_one():
    got = MOD.match_job(job(["#8080FF"], ["PLA"]), LOADED, {"T1A": "T1B"})
    assert got[0]["slot"] == ""
    note = got[0]["note"]
    assert "aucune bobine PLA de cette couleur" in note
    assert "la plus proche est T2D (B2A1E1)" in note
    assert "KCTRL_SLOT SLOT=T2D TOOL=T1A" in note


def test_no_spool_of_that_type_lists_what_is_loaded():
    got = MOD.match_job(job(["#ffffff"], ["ABS"]), LOADED, {})
    assert got[0]["slot"] == ""
    assert "aucune bobine ABS chargee" in got[0]["note"]
    assert "T2C PETG FFFFFF" in got[0]["note"]


def test_a_filament_without_colour_takes_the_only_spool_of_its_type():
    got = MOD.match_job(job(["", ""], ["PETG", "PLA"]), LOADED, {})
    assert got[0]["slot"] == "T2C"
    assert got[1]["slot"] == ""
    assert "couleur non declaree et 4 bobines PLA" in got[1]["note"]


def test_a_filament_without_type_matches_nothing():
    got = MOD.match_job(job(["#ffffff"], [""]), LOADED, {"T1A": "T1D"})
    assert got[0]["slot"] == ""
    assert "matiere non declaree" in got[0]["note"]


def test_nothing_loaded_at_all_is_said_as_such():
    got = MOD.match_job(job(["#ffffff"], ["PLA"]), {}, {})
    assert "chargees: aucune" in got[0]["note"]


# --- statut publie ----------------------------------------------------------

SLOTS = {"T1B": ("000001", "0000000"), "T1D": ("000001", "0ffffff"),
         "T2A": ("000001", "0ff1e1e"), "T2C": ("000003", "0ffffff"),
         "T2D": ("000001", "0b2a1e1")}
GROUPS = [["000001", "0000000", ["T1B"], "PLA"], ["000001", "0ffffff", ["T1D"], "PLA"],
          ["000001", "0ff1e1e", ["T2A"], "PLA"], ["000003", "0ffffff", ["T2C"], "PETG"],
          ["000001", "0b2a1e1", ["T2D"], "PLA"]]


def test_the_status_publishes_the_match_of_the_running_file(tmp_path):
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS,
                  file_tail=tail("#000000;#ff1e1e"))
    status = obj.get_status(0.0)
    assert status["match"] == {"T1A": "T1B", "T1B": "T2A"}
    assert status["match_ok"] == 1
    assert len(status["match_notes"]) == 2


def test_the_status_says_when_a_filament_has_no_spool(tmp_path):
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS,
                  file_tail=tail("#000000;#8080FF"))
    status = obj.get_status(0.0)
    assert status["match"] == {"T1A": "T1B"}
    assert status["match_ok"] == 0
    assert "la plus proche est T2D" in status["match_notes"][1]


def test_no_file_means_no_match_and_no_reactor(tmp_path):
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS)
    obj.printer.objects.pop("virtual_sdcard")
    status = obj.get_status()
    assert status["match"] == {}
    assert status["match_ok"] == 0
    assert status["match_notes"] == []


def test_the_real_cube_tail_matches_black_and_refuses_the_blue(tmp_path):
    with open(FIXTURE_TAIL, "rb") as handle:
        real = handle.read().decode("utf-8", "replace")
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS, body="", file_tail=real)
    status = obj.get_status(0.0)
    assert status["job_colours"] == ["#000000", "#8080FF"]
    assert status["match"] == {"T1A": "T1B"}
    assert status["match_ok"] == 0


# --- KCTRL_MATCH ------------------------------------------------------------


def run_match(obj, **params):
    gcmd = FakeGcmd(**params)
    obj.printer.gcode.commands["KCTRL_MATCH"](gcmd)
    return gcmd


def test_the_used_filaments_are_written_with_the_two_commands_of_kctrl_slot(tmp_path):
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS,
                  file_tail=tail("#ff1e1e;#ffffff", "PLA;PETG"))
    gcmd = run_match(obj)
    assert obj.printer.gcode.scripts == [
        "BOX_MODIFY_TN T1A=T2A",
        "SAVE_VARIABLE VARIABLE=slot_choice_t1a VALUE='\"T2A\"'",
        "SAVE_VARIABLE VARIABLE=slot_last_choice VALUE='\"T2A\"'",
        "BOX_MODIFY_TN T1B=T2C",
        "SAVE_VARIABLE VARIABLE=slot_choice_t1b VALUE='\"T2C\"'",
    ]
    report = "\n".join(gcmd.said)
    assert "2 entree(s) ecrite(s)" in report
    assert "T1A=T2A, T1B=T2C" in report
    # La table sur disque a change sous le cache : relue au prochain appel.
    assert obj.stamp is None


def test_a_declared_but_unused_filament_is_reported_not_written(tmp_path):
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS, body="T1\nG1 X1",
                  file_tail=tail("#8080FF;#ffffff", "PLA;PLA"))
    gcmd = run_match(obj)
    assert obj.printer.gcode.scripts == [
        "BOX_MODIFY_TN T1B=T1D",
        "SAVE_VARIABLE VARIABLE=slot_choice_t1b VALUE='\"T1D\"'",
    ]
    assert "declare mais non utilise" in "\n".join(gcmd.said)


def test_a_used_filament_without_spool_refuses_before_any_write(tmp_path):
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS,
                  file_tail=tail("#ff1e1e;#8080FF", "PLA;PLA"))
    with pytest.raises(GcmdError) as failure:
        run_match(obj)
    assert "1 filament(s) sans bobine" in str(failure.value)
    assert "MATCH=0" in str(failure.value)
    assert obj.printer.gcode.scripts == []


def test_a_table_already_right_writes_nothing(tmp_path):
    obj = machine(tmp_path, dict(IDENTITY, T1A="T1B", T1B="T2A"), SLOTS, GROUPS,
                  file_tail=tail("#000000;#ff1e1e"))
    gcmd = run_match(obj)
    assert obj.printer.gcode.scripts == []
    assert "deja conforme" in "\n".join(gcmd.said)


def test_check_writes_nothing_and_counts_what_it_would(tmp_path):
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS,
                  file_tail=tail("#000000;#ff1e1e"))
    gcmd = run_match(obj, CHECK=1)
    assert obj.printer.gcode.scripts == []
    assert "2 ecriture(s) en attente" in "\n".join(gcmd.said)


def test_skip_leaves_a_filament_as_it_is(tmp_path):
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS,
                  file_tail=tail("#000000;#8080FF"))
    gcmd = run_match(obj, SKIP="T1B")
    assert obj.printer.gcode.scripts[0] == "BOX_MODIFY_TN T1A=T1B"
    assert "laisse tel quel (SKIP)" in "\n".join(gcmd.said)


def test_a_used_filament_the_file_does_not_declare_is_a_refusal(tmp_path):
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS, body="T0\nT2",
                  file_tail=tail("#000000;#ff1e1e"))
    with pytest.raises(GcmdError):
        run_match(obj)
    assert obj.printer.gcode.scripts == []


def test_a_file_without_config_block_is_a_refusal_naming_kctrl_slot(tmp_path):
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS, file_tail="; rien")
    with pytest.raises(GcmdError) as failure:
        run_match(obj)
    assert "KCTRL_SLOT" in str(failure.value)


def test_no_file_and_no_file_parameter_is_a_refusal(tmp_path):
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS)
    obj.printer.objects.pop("virtual_sdcard")
    with pytest.raises(GcmdError) as failure:
        run_match(obj)
    assert "FILE=" in str(failure.value)


def test_file_parameter_reads_another_file(tmp_path):
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS)
    other = gcode(tmp_path, "T1\n" + tail("#000000;#ffffff"), name="other.gcode")
    gcmd = run_match(obj, FILE=other)
    assert obj.printer.gcode.scripts[0] == "BOX_MODIFY_TN T1B=T1D"
    assert other in "\n".join(gcmd.said)


@pytest.mark.parametrize("state", ["printing", "paused"])
def test_a_running_print_refuses_a_manual_rewrite_but_not_the_start(tmp_path, state):
    obj = machine(tmp_path, dict(IDENTITY), SLOTS, GROUPS, printing=state,
                  file_tail=tail("#000000;#ff1e1e"))
    with pytest.raises(GcmdError) as failure:
        run_match(obj)
    assert "impression en cours" in str(failure.value)
    assert obj.printer.gcode.scripts == []
    run_match(obj, CHECK=1)
    assert obj.printer.gcode.scripts == []
    run_match(obj, STARTING=1)
    assert obj.printer.gcode.scripts[0] == "BOX_MODIFY_TN T1A=T1B"


# --- START_PRINT ------------------------------------------------------------


def config_text():
    with open(CONFIG, encoding="utf-8") as handle:
        return handle.read()


def section(name):
    text = config_text()
    start = text.index("[gcode_macro %s]\n" % name)
    end = text.find("\n[", start + 1)
    block = text[start:end if end != -1 else len(text)]
    body = block.split("\ngcode:\n", 1)[1]
    return "\n".join(line[2:] if line.startswith("  ") else line
                     for line in body.splitlines())


def commands(name):
    kept = [line.strip() for line in section(name).splitlines()]
    return [line for line in kept if line and not line.startswith("#")]


def index_of(lines, needle):
    for position, line in enumerate(lines):
        if line.startswith(needle):
            return position
    raise AssertionError("%s absent de la sequence" % needle)


def test_start_print_reads_the_match_at_render_time():
    body = section("START_PRINT")
    assert "slot_map.match.get(logical)" in body
    # Since the Bobines page (ADR-063) the default is 0 when the gate confirmed
    # this very file, 1 otherwise; either way it is read at render time.
    assert "params.MATCH|default(0 if chosen else 1)|int != 0" in body
    assert "params.TOOL is not defined" in body
    assert "slot_map.job_count" in body
    assert "appariement sur le fichier" in body


def test_start_print_matches_after_the_alignment_and_before_anything_heats():
    lines = commands("START_PRINT")
    align = index_of(lines, "KCTRL_MATERIAL_ALIGN MATERIAL={material} TEMP={nozzle|int}")
    match = index_of(lines, "KCTRL_MATCH STARTING=1")
    assert align < match
    for needle in ("SET_GCODE_VARIABLE MACRO=START_PRINT", "M140", "M190", "M104",
                   "M109", "BOX_START_PRINT", "BOX_MODIFY_TN {logical}={tool}",
                   "_KCTRL_CFS_LOAD TOOL={tool} ATTEMPT=1"):
        assert match < index_of(lines, needle), needle


def test_start_print_refuses_at_render_time_with_the_note_when_nothing_fits():
    body = section("START_PRINT")
    at = body.index("{% if match and not matched %}")
    block = body[at:at + 700]
    assert "action_raise_error" in block
    assert "match_notes" in block
    assert "MATCH=0" in block
    assert "KCTRL_SLOT SLOT=... TOOL=%s" in block
    # Un `#` dans une chaine de macro arrete Klipper (document 54).
    assert "#" not in re.sub(r"^\s*#.*$", "", block, flags=re.M)


# Rendu du choix de la bobine, pour les trois cas : appariee, MATCH=0, TOOL=.

ENV = jinja2.Environment("{%", "%}", "{", "}", extensions=["jinja2.ext.do"])


def head_of_start_print():
    body = section("START_PRINT")
    stop = body.index("{% set profile =")
    kept = [line for line in body[:stop].splitlines() if not line.strip().startswith("#")]
    return "\n".join(kept) + '\n{ "%s|%s|%s" % (logical, tool, slot_source) }'


def render_choice(params, slot_map, variables=None):
    raised = {}

    def action_raise_error(message):
        raised["message"] = message
        raise jinja2.TemplateError(message)

    template = ENV.from_string(head_of_start_print())
    printer = {"gcode_macro _KCTRL_START_CONF": {},
               "kctrl_slot_map": slot_map,
               "save_variables": {"variables": variables or {}}}
    try:
        text = template.render(params=params, printer=printer,
                               action_raise_error=action_raise_error,
                               action_respond_info=lambda m: "")
    except jinja2.TemplateError:
        return None, raised["message"]
    return text.strip().splitlines()[-1], ""


SLOT_MAP = {"initial_logical": "T1B", "initial_note": "", "job_count": 2,
            "map": {"T1A": "T1A", "T1B": "T1B"},
            "match": {"T1A": "T1B", "T1B": "T2A"},
            "match_notes": ["filament 1 (T1A) PLA 000000 -> T1B",
                            "filament 2 (T1B) PLA FF1E1E -> T2A"]}


def test_rendered_start_takes_the_matched_slot_over_the_table():
    line, error = render_choice({"BED_TEMP": "60", "EXTRUDER_TEMP": "220"}, SLOT_MAP)
    assert error == ""
    assert line == "T1B|T2A|appariement sur le fichier, type et couleur"


def test_rendered_start_with_match_zero_takes_the_table():
    line, _ = render_choice({"BED_TEMP": "60", "EXTRUDER_TEMP": "220", "MATCH": "0"},
                            SLOT_MAP)
    assert line == "T1B|T1B|table CFS"


def test_rendered_start_with_tool_takes_tool():
    line, _ = render_choice({"BED_TEMP": "60", "EXTRUDER_TEMP": "220", "TOOL": "t2c"},
                            SLOT_MAP)
    assert line == "T1B|T2C|TOOL= impose"


def test_rendered_start_refuses_with_the_filament_note_when_nothing_fits():
    slot_map = dict(SLOT_MAP, match={"T1A": "T1B"},
                    match_notes=["filament 1 (T1A) PLA 000000 -> T1B",
                                 "filament 2 (T1B) PLA 8080FF: aucune bobine PLA de "
                                 "cette couleur; la plus proche est T2D"])
    line, error = render_choice({"BED_TEMP": "60", "EXTRUDER_TEMP": "220"}, slot_map)
    assert line is None
    assert error.startswith("K1 Control: filament 2 (T1B) PLA 8080FF: aucune bobine")
    assert "KCTRL_SLOT SLOT=... TOOL=T1B" in error
    assert "MATCH=0" in error


def test_rendered_start_without_declared_filaments_keeps_the_old_way():
    slot_map = dict(SLOT_MAP, job_count=0, match={}, match_notes=[])
    line, error = render_choice({"BED_TEMP": "60", "EXTRUDER_TEMP": "220"}, slot_map)
    assert error == ""
    assert line == "T1B|T1B|table CFS"
