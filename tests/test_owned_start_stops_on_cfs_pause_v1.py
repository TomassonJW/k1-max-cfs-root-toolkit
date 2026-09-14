"""Le départ s'arrête net sur une pause, et ne pousse plus que deux fois.

Le module CFS compilé ne publie aucune erreur : l'objet `box` porte filament,
state, auto_refill, enable, filament_useup, same_material, T1 à T4, cut_pos,
t_command et custom_command_result, relevés sur la machine le 14 septembre 2026
vers 21:45, et rien d'autre. Quand il abandonne un chargement, il écrit
« error: printing to pause » dans le journal et met l'impression en pause. Cette
pause est sa seule trace lisible depuis une macro.

Le départ, lui, continuait comme si de rien n'était. Le 14 septembre :

- 18:18:56, le changement d'outil abandonne (key836) ; quatre poussées de notre
  code suivent, chacune finit sur une nouvelle pause, jusqu'à 18:24:25, et
  l'annulation demandée à 18:23:58 n'aboutit qu'à 18:24:57 ;
- 18:36:22, nouvel abandon (key845, buse bouchée pendant la purge) ; une
  poussée de plus (key840 à 18:36:52, key836 à 18:38:52), puis la ligne
  d'amorce est tracée à 18:39:33 quand même.

Trois contrôles lisent désormais la pause : juste après le changement d'outil,
après les tentatives, et après la dernière attente de chauffe. Sur pause, le
départ coupe la buse et le plateau (idle_timeout vaut 99999999 s sur cette
machine, rien ne les couperait), ferme ses fenêtres, efface la pause et lève
une erreur. Une pause demandée depuis l'interface pendant le départ l'arrête de
la même façon : rien n'est encore sur le plateau.

Deux pièges du rendu Jinja fixent la forme :

- START_PRINT est rendu en entier avant sa première commande : une lecture de
  la pause écrite dans son corps verrait l'état du lancement, jamais celui
  d'après le changement d'outil. La lecture vit dans sa propre macro ;
- action_raise_error lève au rendu : écrite dans la macro des commandes
  d'arrêt, aucune d'elles ne s'exécuterait. L'erreur vient d'une seconde macro.

Les tentatives passent de quatre à deux (ADR-066) : elles ne tournent plus
qu'après un changement d'outil qui laisse la tête vide sans pause, ce que les
journaux du 9 au 14 septembre ne montrent jamais.
"""

import os
import re

import jinja2
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "packages", "k1-control-v1", "owned-start-print-v2",
                      "k1-control-owned-start-print-v2.cfg")

# Klipper: jinja2.Environment('{%', '%}', '{', '}')
ENV = jinja2.Environment("{%", "%}", "{", "}", extensions=["jinja2.ext.do"])

TOOL = "T{position - 1}"
CHECK = "_KCTRL_ASSERT_CFS_OK"
LOAD = "_KCTRL_CFS_LOAD"
WAIT = "KCTRL_WAIT_FILAMENT SENSOR=filament_sensor_2"


class Raised(Exception):
    pass


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


def raise_error(message):
    raise Raised(message)


def render_check(paused, stage="after_tool_change"):
    text = ENV.from_string(section(CHECK)).render(
        params={"STAGE": stage},
        printer={"pause_resume": {"is_paused": paused}},
        action_raise_error=raise_error)
    return [line.strip() for line in text.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Le contrôle
# ---------------------------------------------------------------------------

def test_sans_pause_le_controle_ne_fait_rien():
    # Le départ normal ne doit rien voir passer : pas une commande.
    assert render_check(paused=False) == []


def test_sur_pause_le_depart_coupe_tout_puis_leve_l_erreur():
    assert render_check(paused=True, stage="after_tool_change") == [
        "_KCTRL_LOAD_GUARD_OFF",
        "M104 S0",
        "M140 S0",
        "SET_GCODE_VARIABLE MACRO=START_PRINT VARIABLE=start_running VALUE=0",
        "CLEAR_PAUSE",
        "_KCTRL_START_STOPPED STAGE=after_tool_change",
    ]


def test_les_chauffes_sont_coupees_avant_l_erreur():
    # idle_timeout vaut 99999999 s : un départ mort chaud resterait chaud.
    lines = render_check(paused=True)
    stop = index_of(lines, "_KCTRL_START_STOPPED")
    assert index_of(lines, "M104 S0") < stop
    assert index_of(lines, "M140 S0") < stop
    assert stop == len(lines) - 1


def test_l_erreur_ne_vient_pas_de_la_macro_du_controle():
    # Levée au rendu, elle empêcherait toutes les commandes d'arrêt.
    assert "action_raise_error" not in section(CHECK)
    assert "action_raise_error" in section("_KCTRL_START_STOPPED")


def test_l_erreur_nomme_l_etape_et_dit_quoi_faire():
    template = ENV.from_string(section("_KCTRL_START_STOPPED"))
    with pytest.raises(Raised) as raised:
        template.render(params={"STAGE": "before_prime"},
                        action_raise_error=raise_error)
    message = str(raised.value)
    assert message.startswith("K1 Control [before_prime]:")
    assert "buse et plateau coupes" in message
    assert "relancer l'impression" in message


def test_la_variable_remise_a_zero_existe_dans_start_print():
    # Sinon SET_GCODE_VARIABLE échoue et l'arrêt s'interrompt avant l'erreur.
    assert re.search(r"^variable_start_running:", config_text(), re.MULTILINE)


# ---------------------------------------------------------------------------
# Sa place dans START_PRINT
# ---------------------------------------------------------------------------

def test_start_print_ne_lit_pas_la_pause_dans_son_propre_corps():
    # Rendu en entier au lancement, il n'y verrait jamais la pause d'après le T.
    assert not any("pause_resume" in line for line in commands("START_PRINT"))


def test_trois_controles_un_par_etape():
    lines = commands("START_PRINT")
    stages = [line.split("STAGE=", 1)[1] for line in lines if line.startswith(CHECK)]
    assert stages == ["after_tool_change", "after_cfs_load", "before_prime"]


def test_rien_ne_s_intercale_entre_le_changement_d_outil_et_le_premier_controle():
    lines = commands("START_PRINT")
    tool = index_of(lines, TOOL)
    assert lines[tool + 1:tool + 4] == [
        "M400",
        "{% endif %}",
        "_KCTRL_ASSERT_CFS_OK STAGE=after_tool_change",
    ]


def test_deux_tentatives_de_chargement_pas_quatre():
    lines = commands("START_PRINT")
    assert [line for line in lines if line.startswith(LOAD)] == [
        "_KCTRL_CFS_LOAD TOOL={tool} ATTEMPT=1",
        "_KCTRL_CFS_LOAD TOOL={tool} ATTEMPT=2",
    ]


def test_les_tentatives_sont_encadrees_par_deux_controles():
    # Aucune poussée après un abandon, et l'attente du capteur ne démarre pas
    # sur un CFS qui vient d'abandonner.
    lines = commands("START_PRINT")
    attempts = [n for n, line in enumerate(lines) if line.startswith(LOAD)]
    before = index_of(lines, CHECK + " STAGE=after_tool_change")
    after = index_of(lines, CHECK + " STAGE=after_cfs_load")
    assert before < min(attempts)
    assert max(attempts) < after < index_of(lines, WAIT)


def test_le_dernier_controle_suit_la_chauffe_et_precede_la_ligne_d_amorce():
    lines = commands("START_PRINT")
    heat = index_of(lines, "M109 S{nozzle}")
    last = index_of(lines, CHECK + " STAGE=before_prime")
    assert heat < last < index_of(lines, "_KCTRL_PRIME_LINE")
    # Avant les contrôles de filament, qui lèvent sans couper les chauffes.
    # Égalité stricte : STAGE=after_cfs est aussi le début de after_cfs_load.
    assert last < lines.index("_KCTRL_ASSERT_FILAMENT_ENGAGED STAGE=after_cfs")
    assert last < lines.index("_KCTRL_ASSERT_FILAMENT_ENGAGED STAGE=before_prime")
    # Et plus rien n'attend entre lui et la ligne.
    between = lines[last + 1:index_of(lines, "_KCTRL_PRIME_LINE")]
    for command in ("M109", "M190", "M400", "G4", "KCTRL_WAIT", "TEMPERATURE_WAIT", "T{"):
        assert not any(line.startswith(command) for line in between), command
