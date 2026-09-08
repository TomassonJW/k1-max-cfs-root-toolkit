# Campagne de résonance complète, exécutée sur la K1 elle-même.
#
# Quatre mesures : les deux axes, puis chaque courroie CoreXY excitée seule.
# Rien n'est appliqué ici. Le script mesure, contrôle, range et rend un rapport ;
# le choix des filtres et leur écriture sont une décision séparée.
#
# Trois pièges de cette machine sont traités explicitement, tous les trois
# rencontrés le 2 et le 8 septembre :
#
#   1. SHAPER_CALIBRATE écrit dans printer.cfg tout seul, sans qu'aucun
#      SAVE_CONFIG ait été demandé. Le fichier est empreint avant et après, et
#      l'écriture est signalée pour être reprise ensuite.
#   2. Le code Creality mesure un seul axe et recopie le résultat sur l'autre
#      (`copy_TestAxis_y_to_x`). Deux fichiers identiques valent donc une mesure
#      manquante, pas deux mesures : c'est un échec, pas un détail.
#   3. Le calibrage embarqué n'a le droit d'évaluer qu'un seul filtre, imposé
#      par `variable_autotune_shapers` dans gcode_macro.cfg. Les cinq sont
#      rejoués hors ligne par prepare-analyseur.py, sur ces mêmes données.
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request

MOONRAKER = "http://127.0.0.1:7125"
CONFIG = pathlib.Path("/usr/data/printer_data/config/printer.cfg")
CAPTEURS = ["filament_sensor", "filament_sensor_2"]
POINT = (150.0, 150.0, 10.0)

# Les deux axes viennent de SHAPER_CALIBRATE, dont le CSV est normalisé aux
# fréquences d'entrée - c'est la seule sortie sur laquelle un pourcentage de
# vibrations veut dire quelque chose. Les deux courroies viennent de
# TEST_RESONANCES, qui n'écrit pas dans printer.cfg et dont la sortie n'est pas
# normalisée : elles se comparent l'une à l'autre, jamais aux axes.
MESURES = [
    ("resonance-x", "SHAPER_CALIBRATE AXIS=x", "calibration_data_x_*.csv", True),
    ("resonance-y", "SHAPER_CALIBRATE AXIS=y", "calibration_data_y_*.csv", True),
    ("courroie-a", "TEST_RESONANCES AXIS=1,1 OUTPUT=resonances", "resonances_*.csv", False),
    ("courroie-b", "TEST_RESONANCES AXIS=1,-1 OUTPUT=resonances", "resonances_*.csv", False),
]


def requete(chemin, corps=None, timeout=30):
    url = MOONRAKER + chemin
    if corps is None:
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(
            url, data=json.dumps(corps).encode(),
            headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as reponse:
        return json.loads(reponse.read().decode())


def etat(objets):
    chemin = "/printer/objects/query?" + "&".join(
        o.replace(" ", "%20") for o in objets)
    return requete(chemin)["result"]["status"]


def gcode(script, timeout=600):
    return requete("/printer/gcode/script", {"script": script}, timeout=timeout)


def empreinte(chemin):
    return hashlib.sha256(pathlib.Path(chemin).read_bytes()).hexdigest()


def prefligt():
    """Refuse de bouger si la machine n'est pas libre, froide et vide."""
    d = etat(["webhooks", "print_stats", "idle_timeout", "extruder",
              "heater_bed", "filament_switch_sensor filament_sensor_2",
              "configfile"])
    refus = []
    if d["webhooks"]["state"] != "ready":
        refus.append("Klipper n'est pas pret : %s" % d["webhooks"]["state"])
    if d["print_stats"]["state"] in ("printing", "paused"):
        refus.append("une impression est en cours (%s)" % d["print_stats"]["state"])
    # Une buse chaude coule sur le plateau pendant vingt minutes de balayage, et
    # une machine chaude ne donne pas les memes frequences qu'une machine froide :
    # la serie du 2 septembre au soir differait de la precedente pour cette
    # seule raison. Les mesures se font a froid, pour rester comparables.
    if d["extruder"]["temperature"] > 40.0:
        refus.append("buse a %.0f C, attendre moins de 40" % d["extruder"]["temperature"])
    if d["heater_bed"]["temperature"] > 40.0:
        refus.append("plateau a %.0f C, attendre moins de 40" % d["heater_bed"]["temperature"])
    if d["filament_switch_sensor filament_sensor_2"]["filament_detected"]:
        refus.append("du filament est engage dans la tete, le desengager d'abord")
    if refus:
        raise SystemExit("PREFLIGHT REFUSE :\n  - " + "\n  - ".join(refus))
    return d


def csv_recent(motif, depuis):
    """Le fichier produit par la mesure qui vient de tourner, et lui seul."""
    trouves = [p for p in pathlib.Path("/tmp").glob(motif)
               if p.stat().st_mtime >= depuis - 1.0]
    if not trouves:
        raise SystemExit("aucun fichier %s produit apres la mesure" % motif)
    return max(trouves, key=lambda p: p.stat().st_mtime)


def main():
    sortie = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                          else "/tmp/campagne-resonance")
    sortie.mkdir(parents=True, exist_ok=True)
    journal = {"debut": time.strftime("%Y-%m-%d %H:%M:%S"), "mesures": []}

    avant = prefligt()
    journal["input_shaper_avant"] = avant["configfile"]["settings"].get("input_shaper")
    journal["printer_cfg_avant"] = empreinte(CONFIG)

    sauvegarde = CONFIG.with_suffix(
        ".cfg.bak-avant-resonance-" + time.strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(CONFIG, sauvegarde)
    journal["sauvegarde"] = str(sauvegarde)
    print("sauvegarde de printer.cfg :", sauvegarde, flush=True)

    # Un capteur de filament qui declenche au milieu d'un balayage met la
    # machine en pause et perd les vingt minutes.
    for capteur in CAPTEURS:
        gcode("SET_FILAMENT_SENSOR SENSOR=%s ENABLE=0" % capteur)
    try:
        gcode("G28", timeout=300)
        gcode("G90")
        gcode("G1 X%.1f Y%.1f Z%.1f F3000" % POINT, timeout=120)
        gcode("M400", timeout=300)

        empreintes = {}
        for nom, commande, motif, normalise in MESURES:
            print("\n=== %s : %s" % (nom, commande), flush=True)
            depart = time.time()
            gcode(commande, timeout=900)
            source = csv_recent(motif, depart)
            cible = sortie / (nom + ".csv")
            shutil.copy2(source, cible)
            empreintes[nom] = empreinte(cible)
            journal["mesures"].append({
                "nom": nom, "commande": commande, "source": str(source),
                "fichier": str(cible), "sha256": empreintes[nom],
                "normalise": normalise,
                "duree_s": round(time.time() - depart, 1),
                "entete": cible.read_text().splitlines()[0],
            })
            print("   -> %s (%.0f s)" % (cible, time.time() - depart), flush=True)
            # Rapatrie avant la mesure suivante : la commande suivante ecrase
            # ces fichiers dans /tmp, et sur cette machine elle en ecrit meme
            # une copie sous le nom de l'autre axe.
            source.unlink(missing_ok=True)
    finally:
        for capteur in CAPTEURS:
            try:
                gcode("SET_FILAMENT_SENSOR SENSOR=%s ENABLE=1" % capteur)
            except Exception as err:  # la reactivation prime sur le rapport
                print("ATTENTION : capteur %s non reactive (%s)" % (capteur, err))

    # Deux axes identiques ne sont pas deux mesures : c'est la recopie Creality,
    # et la campagne ne vaut rien sans l'axe manquant.
    if empreintes.get("resonance-x") == empreintes.get("resonance-y"):
        journal["echec"] = "les deux axes ont rendu le meme fichier : un seul a ete mesure"
    if empreintes.get("courroie-a") == empreintes.get("courroie-b"):
        journal["echec"] = "les deux courroies ont rendu le meme fichier"

    journal["printer_cfg_apres"] = empreinte(CONFIG)
    journal["printer_cfg_modifie"] = journal["printer_cfg_apres"] != journal["printer_cfg_avant"]
    journal["input_shaper_apres"] = etat(["configfile"])["configfile"]["settings"].get("input_shaper")
    journal["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (sortie / "campagne.json").write_text(json.dumps(journal, indent=2))

    print("\n=== resume")
    if journal["printer_cfg_modifie"]:
        print("   printer.cfg A ETE MODIFIE par la machine pendant la campagne.")
        print("   sauvegarde :", sauvegarde)
    else:
        print("   printer.cfg inchange")
    if "echec" in journal:
        print("   ECHEC :", journal["echec"])
        raise SystemExit(2)
    print("   quatre mesures dans", sortie)


if __name__ == "__main__":
    main()
