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
def test_start_print_reads_the_slot_from_the_cfs_table():
    # Une seule source de verite : Tnn_map, ecrite par le popup de l'ecran, par
    # un rechargement automatique, ou par KCTRL_SLOT. Rien n'est stocke a cote.
    body = section("START_PRINT")
    assert 'printer["kctrl_slot_map"]' in body
    assert 'slot_map.map.get("T1A")' in body
    assert "VARIABLE=kctrl_slot" not in config_text()
    assert 'get("kctrl_slot")' not in config_text()


def test_start_print_refuses_to_guess_when_the_table_is_unreadable():
    # Repartir sur T1A en silence est exactement la panne que tout ceci corrige.
    body = section("START_PRINT")
    guard = body.index("{% if not tool %}")
    assert "action_raise_error" in body[guard:guard + 400]
    assert body.index("{% if not tool %}") < body.index("BOX_MODIFY_TN T1A={tool}")


def test_the_slot_map_object_is_declared():
    assert '[kctrl_slot_map]' in config_text()


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


def test_kctrl_slot_writes_the_table_first_then_remembers_the_choice():
    # La table reste l'ecrivain unique et la premiere ecriture. Ce qui est
    # garde a cote n'est pas une seconde verite : c'est la memoire du dernier
    # choix de l'operateur, relue seulement quand la machine a efface la table,
    # et immediatement reecrite dedans par START_PRINT.
    lines = commands("KCTRL_SLOT")
    table = index_of(lines, "BOX_MODIFY_TN {logical}={slot}")
    saves = [line for line in lines if line.startswith("SAVE_VARIABLE")]
    assert saves == ["SAVE_VARIABLE VARIABLE=slot_last_choice VALUE='\"{slot}\"'"]
    assert index_of(lines, "SAVE_VARIABLE") > table


def test_the_remembered_slot_is_only_the_first_filament():
    # T1B, T1C... sont les autres couleurs du meme travail. Les retenir comme
    # "le" choix ferait repartir une impression suivante sur la mauvaise bobine.
    body = section("KCTRL_SLOT")
    guard = body.index("SAVE_VARIABLE VARIABLE=slot_last_choice")
    assert '{% if logical == "T1A" %}' in body[:guard]


def test_start_print_falls_back_on_the_remembered_slot_when_the_table_is_gone():
    # Un arret d'urgence, une coupure ou un FIRMWARE_RESTART rendent un
    # tn_data.json sans tnn_map, et l'ecran est le seul a le remplir : sans
    # repli, toute reprise depuis Mainsail est refusee. Le repli n'est pas une
    # devinette, il rejoue un choix explicite et le dit.
    body = section("START_PRINT")
    assert 'get("slot_last_choice")' in body
    assert body.index('slot_map.map.get("T1A")') < body.index('get("slot_last_choice")')
    assert "dernier choix retenu" in body
    assert "%s (%s)" in body  # l'emplacement et sa provenance, sur la ligne de depart


def test_kctrl_slots_reads_the_selection_from_the_same_table():
    assert 'printer["kctrl_slot_map"].map.get("T1A"' in section("KCTRL_SLOTS")


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


def test_kctrl_slots_resolves_exactly_like_start_print():
    # Deux resolutions qui divergent, c'est un ecran qui annonce une bobine et
    # une impression qui en charge une autre.
    listing = section("KCTRL_SLOTS")
    start = section("START_PRINT")
    for source in ['.map.get("T1A")', 'get("slot_last_choice")']:
        assert source in listing
        assert source in start
    assert listing.index('.map.get("T1A")') < listing.index('get("slot_last_choice")')
