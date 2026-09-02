"""Le CFS choisit sa bobine, et la fin de bobine est rattrapée.

Trois choses sont épinglées ici, et les trois ont cassé pour de vrai.

L'emplacement ne peut plus être figé : le démarrage possédé appelle
BOX_EXTRUDE_MATERIAL sur un emplacement physique, ce qui contourne Tnn_map, et
tant que cet emplacement venait d'une constante tout partait sur T1A.

Le capteur de tête ne peut être armé que si la séquence qui doit le désarmer
est possédée. END_PRINT retire le filament par le cutter ; armé sans ce
désarmement, une fin d'impression normale devient une pause fantôme (ADR-051,
remplacé par l'ADR-055).

Et deux pièges de syntaxe Klipper, tous deux constatés en mettant la machine à
l'arrêt le 2 septembre : un `#` dans une chaîne coupe la ligne, et
`rename_existing` ne peut pas viser une section que ce fichier redéfinit.
"""

import os

import jinja2
import pytest

CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "packages", "k1-control-v1", "owned-start-print-v2",
    "k1-control-owned-start-print-v2.cfg")

# Klipper: jinja2.Environment('{%', '%}', '{', '}')
ENV = jinja2.Environment("{%", "%}", "{", "}", extensions=["jinja2.ext.do"])


def config_text():
    with open(CONFIG, encoding="utf-8") as handle:
        return handle.read()


def section(name):
    """Le corps gcode: d'une section, sans son indentation."""
    text = config_text()
    start = text.index("[gcode_macro %s]\n" % name)
    end = text.find("\n[", start + 1)
    block = text[start:end if end != -1 else len(text)]
    body = block.split("\ngcode:\n", 1)[1]
    return "\n".join(line[2:] if line.startswith("  ") else line
                     for line in body.splitlines())


def commands(name):
    """Le corps sans les commentaires : un commentaire n'est pas un appel."""
    kept = [line.strip() for line in section(name).splitlines()]
    return [line for line in kept if line and not line.startswith("#")]


def index_of(lines, needle):
    for position, line in enumerate(lines):
        if line.startswith(needle):
            return position
    raise AssertionError("%s absent de la sequence" % needle)


def gcode_blocks():
    """(nom de section, lignes du corps gcode:) pour toutes les sections."""
    blocks = []
    text = config_text()
    for chunk in text.split("\n[")[1:]:
        header = chunk.split("]", 1)[0]
        if "\ngcode:\n" not in chunk:
            continue
        body = chunk.split("\ngcode:\n", 1)[1]
        body = body.split("\n[", 1)[0]
        blocks.append((header, body.splitlines()))
    return blocks


# ------------------------------------------------------- pièges de syntaxe
def test_no_hash_survives_inside_a_gcode_body():
    # Klipper coupe la ligne au premier '#', y compris au milieu d'un litteral.
    # Un `couleur #%s` a laisse une chaine non fermee et mis la machine en
    # halted : EOL while scanning string literal.
    offenders = []
    for name, lines in gcode_blocks():
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            if "#" in stripped:
                offenders.append((name, stripped))
    assert offenders == []


def test_every_template_still_compiles():
    for name, lines in gcode_blocks():
        ENV.from_string("\n".join(lines))


def test_no_rename_existing_on_a_section_this_file_redefines():
    # Klipper fusionne les sections homonymes : le corps stock est ecrase avant
    # que le renommage cherche a l'attraper, et la machine refuse de demarrer
    # avec key169.
    text = config_text()
    declared = {chunk.split("]", 1)[0].replace("gcode_macro ", "")
                for chunk in text.split("\n[")[1:]
                if chunk.startswith("gcode_macro ")}
    for chunk in text.split("\n[")[1:]:
        name = chunk.split("]", 1)[0].replace("gcode_macro ", "")
        head = chunk.split("\ngcode:\n", 1)[0]
        if "rename_existing:" in head:
            target = head.split("rename_existing:", 1)[1].split("\n")[0].strip()
            assert target not in declared, name


# --------------------------------------------------------- choix de la bobine
def test_start_print_does_not_hardcode_the_slot():
    body = section("START_PRINT")
    assert 'printer.save_variables.variables.get("kctrl_slot")' in body
    assert "params.TOOL|default(saved_slot if saved_slot else c.default_tool)" in body


def test_start_print_refuses_an_empty_slot():
    body = section("START_PRINT")
    assert "material_type[slot_nums[tool[2]]]" in body
    assert "est vide" in body


def test_start_print_points_the_stock_table_at_the_slot_before_loading():
    # BOX_CHECK_MATERIAL_REFILL reecrit Tnn_map pour passer la main a la bobine
    # jumelle. Une route qui ignore la table ne peut pas suivre un rechargement.
    lines = commands("START_PRINT")
    assert index_of(lines, "BOX_MODIFY_TN T1A={tool}") < index_of(
        lines, "_KCTRL_CFS_LOAD TOOL={tool} ATTEMPT=1")


def test_kctrl_slot_writes_the_table_before_it_remembers_anything():
    # Si l'ecriture de la table echoue, la variable ne doit pas revendiquer une
    # route que le CFS ignore.
    lines = commands("KCTRL_SLOT")
    assert index_of(lines, "BOX_MODIFY_TN {logical}={slot}") < index_of(
        lines, "SAVE_VARIABLE VARIABLE=kctrl_slot")


def test_kctrl_slot_only_remembers_the_first_filament():
    # Seul le premier chargement se fait dans START_PRINT ; les suivants passent
    # par le cmd_T stock et n'ont besoin que de la table.
    body = section("KCTRL_SLOT")
    remember = body.index("SAVE_VARIABLE VARIABLE=kctrl_slot")
    guard = body.rindex('{% if logical == "T1A" %}', 0, remember)
    assert guard < remember


def test_kctrl_slot_validates_both_ends_of_the_mapping():
    body = section("KCTRL_SLOT")
    assert '("SLOT", slot), ("TOOL", logical)' in body


# ------------------------------------------------- rechargement automatique
def test_start_print_arms_the_head_sensor_after_the_material_step():
    lines = commands("START_PRINT")
    arm = index_of(lines, "SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=1")
    assert arm > index_of(lines, "BOX_MATERIAL_FLUSH")
    assert arm > index_of(lines, "CX_PRINT_DRAW_ONE_LINE")


@pytest.mark.parametrize("macro", ["END_PRINT", "CANCEL_PRINT"])
def test_the_end_disarms_the_sensor_before_the_stock_unload(macro):
    # BOX_END, la premiere chose que fait END_PRINT_NO_M84, tire le filament par
    # le cutter. Le capteur doit etre eteint avant, sinon une fin normale leve
    # un runout et la machine se met en pause sans rien a reprendre.
    lines = commands(macro)
    assert index_of(lines, "SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=0") < index_of(
        lines, "END_PRINT_NO_M84")


def test_the_stock_unload_body_is_left_alone():
    # Seuls les deux appelants sont redefinis ; le corps volumineux reste stock.
    assert "[gcode_macro END_PRINT_NO_M84]" not in config_text()


def test_cancel_print_still_reaches_the_renamed_stock_body():
    assert "CANCEL_PRINT_BASE" in commands("CANCEL_PRINT")
