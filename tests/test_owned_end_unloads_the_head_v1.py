"""La fin d'impression vide la tete elle-meme : coupe, puis rembobinage du
filament courant, nomme (ADR-067).

Le 15 septembre 2026 a 12:03, la fin stock (`END_PRINT_NO_M84`, donc `BOX_END`)
prend dans le module CFS compile la branche « extrude all material, last_cmd:
T1A » : 80 mm pousses toutes les 40 s, 25 tours, deux metres, jusqu'a l'arret
de Klipper a 12:20. Le 14 a 22:53, la meme fin avait coupe, rembobine et rendu
la main en 49 s. Ce qui choisit la branche est dans le module ; rien ne le
change de l'exterieur.

Ce que nous savons faire, nous : couper puis rembobiner, avec les deux
commandes stock que le retrait de l'ecran utilise, en nommant l'emplacement.
`BOX_RETRUDE_MATERIAL` sans `TNN` ne fait rien apres un redemarrage
(`last_tnn: None`, 13:02) ; `BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1A` a rembobine
T1A en 20 s a 13:23. L'emplacement vient du dernier changement d'outil de
notre enveloppe, sinon du depart de l'impression.

Deux contraintes du rendu Jinja (ADR-066) : le capteur de tete est lu au rendu
de `_KCTRL_UNLOAD`, c'est l'etat d'avant la coupe, le bon ; l'etat d'apres le
rembobinage est lu par `_KCTRL_UNLOAD_CHECK`, macro a part. Aucune des deux ne
leve d'erreur : `END_PRINT` doit atteindre `TURN_OFF_HEATERS` (idle_timeout
vaut 99999999 s sur cette machine).
"""

import os
import re

import jinja2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "packages", "k1-control-v1", "owned-start-print-v2",
                      "k1-control-owned-start-print-v2.cfg")

# Klipper: jinja2.Environment('{%', '%}', '{', '}')
ENV = jinja2.Environment("{%", "%}", "{", "}", extensions=["jinja2.ext.do"])

UNLOAD = "_KCTRL_UNLOAD"
CHECK = "_KCTRL_UNLOAD_CHECK"
STOCK_END = "END_PRINT_NO_M84"


def config_text():
    with open(CONFIG, encoding="utf-8") as handle:
        return handle.read()


def section(name):
    text = config_text()
    start = text.index("[gcode_macro %s]\n" % name)
    end = text.find("\n[", start + 1)
    block = text[start:end if end != -1 else len(text)]
    body = block.split("\ngcode:\n", 1)[1]
    # Klipper coupe tout ce qui suit un # avant de lire la valeur (configfile.py).
    body = chr(10).join(line.split(chr(35), 1)[0].rstrip() for line in body.splitlines())
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


def printer_state(head=True, enable=1, last=None, active_tool="T1A", target=215.0, homed="xyz"):
    state = {
        "box": {"enable": enable},
        "filament_switch_sensor filament_sensor_2": {"filament_detected": head},
        "gcode_macro START_PRINT": {"active_tool": active_tool},
        "extruder": {"target": target},
        "toolhead": {"homed_axes": homed},
    }
    if last is not None:
        state["kctrl_tool_change"] = {"last": last}
    return state


def render(name, params=None, **state):
    said = []
    text = ENV.from_string(section(name)).render(
        params=params or {}, printer=printer_state(**state),
        action_respond_info=lambda message: said.append(message) or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines, said


def unload_lines(tool, reason="fin", temp=215):
    return [
        "SET_GCODE_VARIABLE MACRO=_KCTRL_UNLOAD VARIABLE=last VALUE='\"%s\"'" % tool,
        "M109 S%d" % temp,
        "BOX_ERROR_CLEAR",
        "BOX_CUT_MATERIAL",
        "M400",
        "BOX_RETRUDE_MATERIAL_WITH_TNN TNN=%s" % tool,
        "M400",
        "_KCTRL_UNLOAD_CHECK TOOL=%s REASON=%s" % (tool, reason),
    ]


# ---------------------------------------------------------------------------
# Sa place dans la fin et l'annulation
# ---------------------------------------------------------------------------

def test_la_fin_vide_la_tete_avant_la_fin_stock():
    assert commands("END_PRINT") == [
        "SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=0",
        "_KCTRL_LOAD_GUARD_OFF",
        "_KCTRL_UNLOAD REASON=fin",
        STOCK_END,
        "M84",
    ]


def test_l_annulation_aussi():
    assert commands("CANCEL_PRINT") == [
        "SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=0",
        "_KCTRL_LOAD_GUARD_OFF",
        "_KCTRL_UNLOAD REASON=annulation",
        STOCK_END,
        "CANCEL_PRINT_BASE",
    ]


def test_l_alarme_du_capteur_est_coupee_avant_le_retrait():
    for name in ("END_PRINT", "CANCEL_PRINT"):
        lines = commands(name)
        assert index_of(lines, "SET_FILAMENT_SENSOR") < index_of(lines, UNLOAD) < index_of(lines, STOCK_END)


# ---------------------------------------------------------------------------
# Le retrait
# ---------------------------------------------------------------------------

def test_le_retrait_nomme_le_dernier_changement_d_outil():
    lines, said = render(UNLOAD, params={"REASON": "fin"},
                         last={"tool": "T3", "outcome": "done", "slot": "T2C", "temp": 215})
    assert lines == unload_lines("T2C")
    assert said == ["K1 Control: retrait (fin) de T2C (dernier changement d'outil) : coupe, puis rembobinage"]


def test_sans_changement_d_outil_le_depart_donne_le_filament():
    lines, said = render(UNLOAD, active_tool="T1A")
    assert lines == unload_lines("T1A")
    assert "T1A (depart de l'impression)" in said[0]


def test_un_changement_refuse_ou_hors_travail_ne_compte_pas():
    for outcome in ("refuse", "stock"):
        lines, _ = render(UNLOAD, last={"tool": "T2", "outcome": outcome, "detail": "x"})
        assert "BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1A" in lines


def test_un_changement_fini_sans_filament_ou_en_pause_garde_son_emplacement():
    for outcome in ("empty", "paused_by_firmware", "start"):
        lines, _ = render(UNLOAD, last={"tool": "T1", "outcome": outcome, "slot": "T1D", "temp": 200})
        assert "BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1D" in lines


def test_tool_impose_gagne():
    lines, said = render(UNLOAD, params={"TOOL": "t1b"},
                         last={"tool": "T3", "outcome": "done", "slot": "T2C"})
    assert "BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1B" in lines
    assert "(TOOL= impose)" in said[0]


def test_le_rembobinage_est_toujours_nomme():
    # BOX_RETRUDE_MATERIAL sans TNN : rien apres un redemarrage (15 septembre, 13:02).
    assert not re.search(r"^\s*BOX_RETRUDE_MATERIAL\s*$", section(UNLOAD), re.MULTILINE)
    assert "BOX_QUIT_MATERIAL" not in section(UNLOAD)


def test_filament_inconnu_laisse_la_fin_stock():
    lines, said = render(UNLOAD, active_tool="")
    assert not any(line.startswith("BOX_") for line in lines)
    assert "M109" not in " ".join(lines)
    assert "filament courant inconnu (aucune source)" in said[0]


def test_emplacement_mal_forme_laisse_la_fin_stock():
    lines, said = render(UNLOAD, active_tool="T5A")
    assert not any(line.startswith("BOX_") for line in lines)
    assert "inconnu (T5A)" in said[0]


def test_tete_vide_rien_a_couper():
    lines, said = render(UNLOAD, head=False)
    assert lines == ["SET_GCODE_VARIABLE MACRO=_KCTRL_UNLOAD VARIABLE=last VALUE='\"vide\"'"]
    assert "deja vide" in said[0]


def test_sans_cfs_rien_a_vider():
    lines, said = render(UNLOAD, enable=0)
    assert not any(line.startswith("BOX_") for line in lines)
    assert "sans CFS actif" in said[0]


def test_axes_non_references_rien_ne_bouge():
    # Une annulation avant le G28 du depart : la coupe ferait une erreur de
    # Klipper, et CANCEL_PRINT_BASE ne tournerait jamais.
    lines, said = render(UNLOAD, homed="")
    assert not any(line.startswith("BOX_") for line in lines)
    assert "axes non references" in said[0]


def test_la_buse_est_a_sa_temperature_d_impression_ou_a_200():
    lines, _ = render(UNLOAD, target=230.0)
    assert "M109 S230" in lines
    lines, _ = render(UNLOAD, target=0.0)
    assert "M109 S200" in lines
    lines, _ = render(UNLOAD, params={"TEMP": "210"}, target=0.0)
    assert "M109 S210" in lines
    lines, _ = render(UNLOAD, params={"TEMP": "210"}, target=230.0)
    assert "M109 S230" in lines


def test_la_chauffe_precede_la_coupe_et_le_rembobinage_suit_la_coupe():
    lines, _ = render(UNLOAD)
    assert index_of(lines, "M109") < index_of(lines, "BOX_CUT_MATERIAL") \
        < index_of(lines, "BOX_RETRUDE_MATERIAL_WITH_TNN") < index_of(lines, CHECK)


def test_la_raison_est_dite():
    _, said = render(UNLOAD, params={"REASON": "annulation"})
    assert said[0].startswith("K1 Control: retrait (annulation) de T1A")


# ---------------------------------------------------------------------------
# Le controle d'apres, et ce qu'aucune des deux macros ne fait
# ---------------------------------------------------------------------------

def test_l_etat_d_apres_est_lu_par_une_macro_a_part():
    assert CHECK + " TOOL=" in " ".join(commands(UNLOAD))
    lines, said = render(CHECK, params={"TOOL": "T2C", "REASON": "fin"}, head=True)
    assert lines == []
    assert said == ["K1 Control: retrait (fin) de T2C incomplet, le capteur de tete voit encore du "
                    "filament, la fin stock (BOX_END) reessaie, surveiller la boucle extrude all material"]
    _, said = render(CHECK, params={"TOOL": "T2C", "REASON": "fin"}, head=False)
    assert said == ["K1 Control: retrait (fin) de T2C fait, tete vide"]


def test_aucune_des_deux_macros_ne_leve():
    # Une erreur ici finirait END_PRINT avant TURN_OFF_HEATERS.
    assert "action_raise_error" not in section(UNLOAD)
    assert "action_raise_error" not in section(CHECK)


# ---------------------------------------------------------------------------
# Le depart retient son filament
# ---------------------------------------------------------------------------

def test_start_print_retient_le_filament_de_depart_avant_son_changement_d_outil():
    assert re.search(r"^variable_active_tool: \"\"$", config_text(), re.MULTILINE)
    lines = commands("START_PRINT")
    kept = index_of(lines, "SET_GCODE_VARIABLE MACRO=START_PRINT VARIABLE=active_tool VALUE='\"{tool}\"'")
    assert kept < index_of(lines, "T{position - 1}")


# ---------------------------------------------------------------------------
# Ce que Klipper coupe en lisant le fichier
# ---------------------------------------------------------------------------

def test_aucun_message_ne_contient_de_commentaire_en_ligne():
    # Klipper lit le fichier avec inline_comment_prefixes=(';', '#') et coupe
    # lui-meme tout ce qui suit un '#'. Un " ;" dans une chaine tronque la
    # ligne, le modele Jinja ne se charge plus et Klipper reste en erreur au
    # redemarrage (15 septembre 2026 a 14:00, premiere pose d'ADR-067).
    for number, line in enumerate(config_text().splitlines(), 1):
        if "action_respond_info(" in line or "action_raise_error(" in line:
            assert " ;" not in line, "ligne %d : point-virgule en ligne dans un message" % number
            assert "#" not in line, "ligne %d : diese dans un message" % number
