"""Le changement d'outil appartient au démarrage, et la ligne d'amorce aussi.

Le 9 septembre 2026 à 23:42, une impression s'est figée pour de bon : file
d'attente G-code bloquée, annulation ignorée, sortie seulement par redémarrage
de Klipper. La trace du module CFS compilé dit la chaîne complète.

Un fichier tranché ne porte qu'une commande outil, et le trancheur la place
*après* le bloc de démarrage — ligne 275 du fichier, douze lignes sous son
START_PRINT. Quand elle s'exécute enfin, le CFS lit son propre état ainsi :

    cmd_T last_cmd=None, get_fialment_sensor_detect()=True
    cmd_T ret = self.box_action_move_to_cut

`last_cmd` est l'outil que le CFS croit chargé, et rien de ce que le démarrage
appelait avant ne le renseignait : BOX_EXTRUDE_MATERIAL ne l'écrit pas. Le
module voit donc du filament dans la tête sans pouvoir l'attribuer, en conclut
qu'une bobine étrangère doit sortir, et coupe. Puis il réinsère, repurge, et
restaure un Z relevé avant que notre purge ne le déplace :

    Move out of range: 185.500 291.500 -18.951

Ce refus n'est pas rattrapé dans le module compilé, et la file ne repart pas.

Émise pendant que la tête est encore vide, la même commande prend son autre
branche : pas de coupe, un chargement normal, `last_cmd` renseigné. Le T du
fichier retombe alors sur le même outil et ne fait plus rien.

Deuxième constat, corrigé le 10 septembre : CX_PRINT_DRAW_ONE_LINE trace ses
trois cordons lents à chaque démarrage normal, pas seulement sur rupture. Tout
ce qui dessine, dans custom_macro.py, est derrière
`if self.pheaters.can_break_flag == 3`, et heaters.py met ce drapeau à 3 à la
fin de chaque attente de température non interrompue — le M109 du démarrage
suffit. Vu sur le cube du 10 septembre à 11:19:50 : la ligne stock, lente,
puis la nôtre. L'appel stock n'est plus émis ; la ligne est tracée ici, une
fois, à nos chiffres.

Troisième constat, le même jour : le changement d'outil est à lui seul tout le
chargement — le CFS alimente, l'extrudeur tire jusqu'à la buse, la purge stock
tourne au-dessus du bac, à chaud. Ce que le démarrage poussait encore après
(BOX_EXTRUDER_EXTRUDE, 120 mm de complément, BOX_MATERIAL_FLUSH) faisait une
seconde boule : 254 mm à 190 °C après une purge complète à 200 °C, mesurés à
11:18. Le démarrage ne pousse plus de filament lui-même.
"""

import os

import jinja2
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "packages", "k1-control-v1", "owned-start-print-v2",
                      "k1-control-owned-start-print-v2.cfg")

# Klipper: jinja2.Environment('{%', '%}', '{', '}')
ENV = jinja2.Environment("{%", "%}", "{", "}", extensions=["jinja2.ext.do"])

# Relevé dans custom_macro.py et dans le fichier tranché du 2026-09-09.
STOCK_LINE_SPEED = 3000.0
STOCK_LINE_E = 10.0
STOCK_LINE_LENGTH = 160.0
# Section d'un filament de 1,75 mm.
FILAMENT_AREA = 2.40528


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


def variables(name):
    text = config_text()
    start = text.index("[gcode_macro %s]\n" % name)
    head = text[start:text.index("\ngcode:\n", start)]
    out = {}
    for line in head.splitlines():
        if line.startswith("variable_"):
            key, _, value = line.partition(":")
            out[key.strip()[len("variable_"):]] = float(value.strip())
    return out


def render_prime(**overrides):
    conf = variables("_KCTRL_PRIME_LINE")
    conf.update(overrides)

    class Bag(dict):
        def __getattr__(self, key):
            return self[key]

    said = []
    template = ENV.from_string(section("_KCTRL_PRIME_LINE"))
    text = template.render(
        printer={"gcode_macro _KCTRL_PRIME_LINE": Bag(
            line_speed=conf["line_speed"], line_z=conf["line_z"],
            volumetric=conf["volumetric"], passes=conf["passes"],
            y_start=conf["y_start"], y_end=conf["y_end"],
            x_first=conf["x_first"], x_step=conf["x_step"])},
        action_respond_info=said.append)
    return [line.strip() for line in text.splitlines() if line.strip()], said


# ---------------------------------------------------------------------------
# Le changement d'outil
# ---------------------------------------------------------------------------

def test_le_demarrage_emet_lui_meme_le_changement_d_outil():
    # Sans cette ligne, le seul T du travail est celui que le trancheur pose
    # apres le bloc de demarrage, et il arrive trop tard.
    lines = commands("START_PRINT")
    assert index_of(lines, "T{position - 1}") >= 0


def test_l_outil_est_emis_avant_que_du_filament_soit_charge():
    # C'est tout l'interet : la tete est encore vide, donc cmd_T ne coupe pas.
    lines = commands("START_PRINT")
    tool = index_of(lines, "T{position - 1}")
    assert tool < index_of(lines, "_KCTRL_CFS_LOAD TOOL={tool} ATTEMPT=1")
    assert tool < index_of(lines, "KCTRL_WAIT_FILAMENT SENSOR=filament_sensor_2")


def test_le_changement_d_outil_est_la_seule_purge_du_demarrage():
    # cmd_T charge, tire jusqu'a la buse et purge au-dessus du bac, a chaud.
    # Le 10 septembre a 11:18 le demarrage poussait encore 254 mm a 190 C
    # apres cette purge : deux boules dans le bac pour une impression.
    lines = commands("START_PRINT")
    for command in ("BOX_EXTRUDER_EXTRUDE", "BOX_MATERIAL_FLUSH", "_KCTRL_PURGE_BALL"):
        assert not any(line.startswith(command) for line in lines), command


def test_l_outil_est_emis_apres_que_la_table_ait_ete_ecrite():
    # cmd_T lit Tnn_map pour resoudre le logique vers le physique. Emis avant
    # BOX_MODIFY_TN, il partirait sur l'ancienne entree.
    lines = commands("START_PRINT")
    assert index_of(lines, "BOX_MODIFY_TN {logical}={tool}") < index_of(
        lines, "T{position - 1}")


def test_l_outil_n_est_emis_que_si_le_cfs_est_actif():
    # Sans CFS, la commande outil n'a pas de destinataire.
    body = section("START_PRINT")
    guard = body.index("T{position - 1}")
    assert "{% if printer.box.enable|int == 1 %}" in body[:guard]


def test_l_outil_emis_est_l_index_du_fichier_et_non_le_nom_logique():
    # Le fichier ecrit T1, pas T1B : le firmware decode positionnellement.
    # Emettre le nom logique passerait par une commande qui n'existe pas.
    lines = commands("START_PRINT")
    assert "T{logical}" not in lines
    position = [line for line in commands("START_PRINT")
                if line.startswith("T{position")]
    assert position == ["T{position - 1}"]


def test_le_changement_d_outil_est_suivi_d_une_barriere():
    # cmd_T bouge la tete et pousse de la matiere. Ce qui suit ne doit pas se
    # rendre pendant.
    lines = commands("START_PRINT")
    assert lines[index_of(lines, "T{position - 1}") + 1] == "M400"


# ---------------------------------------------------------------------------
# La ligne d'amorce
# ---------------------------------------------------------------------------

def test_l_appel_stock_n_est_plus_emis():
    # Il tracait ses trois cordons lents avant les notres a chaque demarrage :
    # le drapeau qu'il lit vaut 3 apres toute attente de temperature, et rien
    # d'autre que lui ne lit ce drapeau.
    lines = commands("START_PRINT")
    assert not any(line.startswith("CX_PRINT_DRAW_ONE_LINE") for line in lines)
    assert sum(1 for line in lines if line.startswith("_KCTRL_PRIME_LINE")) == 1


def test_la_ligne_d_amorce_precede_l_armement_du_capteur():
    # Le capteur de tete est arme une fois la premiere ligne posee, pas avant :
    # un contact marginal pendant l'amorce ne doit pas mettre en pause.
    lines = commands("START_PRINT")
    assert index_of(lines, "_KCTRL_PRIME_LINE") < index_of(
        lines, "SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=1")


def test_la_ligne_est_plus_haute_que_celle_qui_s_est_soudee():
    # Le stock trace a Z 0.30 et ca a colle au plateau le 2026-09-09.
    assert variables("_KCTRL_PRIME_LINE")["line_z"] > 0.30


def test_la_ligne_va_trois_fois_plus_vite_que_le_stock():
    assert variables("_KCTRL_PRIME_LINE")["line_speed"] == 3.0 * STOCK_LINE_SPEED


def test_la_ligne_depose_beaucoup_plus_de_matiere_dans_le_meme_temps():
    conf = variables("_KCTRL_PRIME_LINE")
    lines, _ = render_prime()
    extrusions = [line for line in lines if " E" in line and line.startswith("G1 X")]
    assert len(extrusions) == int(conf["passes"])

    total = sum(float(line.split(" E")[1].split()[0]) for line in extrusions)
    assert total > 2.5 * STOCK_LINE_E

    length = conf["y_end"] - conf["y_start"]
    duration = int(conf["passes"]) * length / (conf["line_speed"] / 60.0)
    stock_duration = STOCK_LINE_LENGTH / (STOCK_LINE_SPEED / 60.0)
    # Meme duree que l'amorce stock, a un dixieme de seconde pres.
    assert abs(duration - stock_duration) < 0.1


def test_le_debit_demande_est_bien_celui_qui_sort():
    conf = variables("_KCTRL_PRIME_LINE")
    lines, _ = render_prime()
    extrusion = next(line for line in lines if " E" in line and line.startswith("G1 X"))
    e = float(extrusion.split(" E")[1].split()[0])
    speed = float(extrusion.split(" F")[1].split()[0]) / 60.0
    length = conf["y_end"] - conf["y_start"]
    volumetric = e * FILAMENT_AREA / (length / speed)
    assert abs(volumetric - conf["volumetric"]) < 0.05


def test_les_passes_sont_paralleles_et_ne_se_recouvrent_pas():
    conf = variables("_KCTRL_PRIME_LINE")
    lines, _ = render_prime()
    xs = []
    for line in lines:
        if line.startswith("G1 X") and " E" in line:
            xs.append(float(line.split("X")[1].split()[0]))
    assert xs == sorted(xs)
    assert len(set(xs)) == int(conf["passes"])
    for previous, following in zip(xs, xs[1:]):
        assert abs(following - previous - conf["x_step"]) < 1e-6


def test_les_passes_font_un_serpentin_plutot_que_des_retours_a_vide():
    lines, _ = render_prime()
    extrusions = [line for line in lines if line.startswith("G1 X") and " E" in line]
    ends = [float(line.split("Y")[1].split()[0]) for line in extrusions]
    # Une passe finit ou la suivante commence : les Y d'arrivee alternent.
    for previous, following in zip(ends, ends[1:]):
        assert previous != following


def test_la_ligne_reste_sur_la_bande_d_amorce_et_pas_sur_la_piece():
    conf = variables("_KCTRL_PRIME_LINE")
    lines, _ = render_prime()
    for line in lines:
        if line.startswith("G1 X"):
            x = float(line.split("X")[1].split()[0])
            # [stepper_x] position_min: -2, et le plateau commence a 0.
            assert -2.0 <= x < 0.0
    assert conf["x_first"] < 0.0


def test_le_cordon_est_casse_avant_de_partir_sur_la_piece():
    lines, _ = render_prime()
    tail = lines[lines.index(next(l for l in reversed(lines)
                                  if l.startswith("G1 X") and " E" in l)):]
    assert any(line.startswith("G1 E-") for line in tail)
    assert any(line == "G92 E0" for line in tail)
    assert lines[-1] == "M400" or "M400" in lines


def test_la_ligne_remonte_avant_de_se_deplacer_a_sa_position():
    # Sinon la buse racle le plateau depuis la ou la purge l'a laissee.
    lines, _ = render_prime()
    first_travel = next(i for i, line in enumerate(lines)
                        if line.startswith("G1 X") and "F12000" in line)
    lifts = [line for line in lines[:first_travel] if line.startswith("G1 Z")]
    assert lifts
    conf = variables("_KCTRL_PRIME_LINE")
    assert float(lifts[0].split("Z")[1].split()[0]) > conf["line_z"]


def test_l_extrusion_est_relative_pendant_l_amorce():
    # La purge qui precede laisse l'axe E n'importe ou, et les box font des
    # G92 E0 par-dessus. Une amorce en absolu pousserait un nombre inconnu.
    lines, _ = render_prime()
    assert "M83" in lines
    assert lines.index("M83") < min(
        i for i, line in enumerate(lines) if line.startswith("G1 X") and " E" in line)


def test_le_compte_rendu_dit_ce_qui_a_ete_pousse():
    _, said = render_prime()
    assert said and "ligne d'amorce" in said[0]
    for token in ("passes", "Z", "mm/s", "mm3/s", "mm de filament"):
        assert token in said[0]


@pytest.mark.parametrize("volumetric,passes", [(14.0, 1), (20.0, 3), (25.0, 5)])
def test_les_reglages_restent_coherents_quand_l_operateur_les_change(
        volumetric, passes):
    conf = variables("_KCTRL_PRIME_LINE")
    lines, _ = render_prime(volumetric=volumetric, passes=passes)
    extrusions = [line for line in lines if line.startswith("G1 X") and " E" in line]
    assert len(extrusions) == passes
    e = float(extrusions[0].split(" E")[1].split()[0])
    length = conf["y_end"] - conf["y_start"]
    speed = conf["line_speed"] / 60.0
    assert abs(e * FILAMENT_AREA / (length / speed) - volumetric) < 0.05
