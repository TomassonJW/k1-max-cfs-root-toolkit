#!/usr/bin/env python3
# Corrige la temperature que le CFS impose a la buse quand il charge, change ou
# purge un filament.
#
# Le chargeur d'origine ne lit pas la temperature du fichier tranche. Il lit le
# type de matiere de l'emplacement qu'il va tirer, cherche cet identifiant dans
# material_database.json, et chauffe au nozzle_temperature de cette fiche. La
# fiche Generic PLA porte 220 C : c'est la raison pour laquelle tous les PLA
# chargeaient a 220 C, quelle que soit la temperature demandee par le G-code.
#
# Preuve du 9 septembre 2026 : le meme chargement journalise
# max_volumetric_speed: 14, qui est le filament_max_volumetric_speed de cette
# meme fiche, alors que le fichier tranche portait 23,24. La base est donc bien
# lue, et c'est elle qui donne le 220.
#
# Le script tourne sur la machine. Il sauvegarde avant d'ecrire, ne touche que
# les deux cles de temperature de buse des fiches nommees, puis relit le fichier
# et verifie ce qui s'y trouve. Sans --appliquer il ne fait que rendre compte.

import argparse
import json
import os
import shutil
import sys
import time

BASE = "/usr/data/creality/userdata/box/material_database.json"
ROUTES = "/usr/data/creality/userdata/box/tn_data.json"
CLES = ("nozzle_temperature", "nozzle_temperature_initial_layer")

# Les emplacements stockent le type de matiere sur six caracteres, la base sur
# cinq. Un chargement en 000001 ressort a 220 C, la valeur de la fiche 00001, ce
# qui donne la correspondance : le zero de tete en trop est retire.
def cle_base(type_matiere):
    t = str(type_matiere)
    if len(t) == 6 and t.startswith("0"):
        return t[1:]
    return t


def charger(chemin):
    with open(chemin) as f:
        return json.load(f)


def fiches(base):
    for fiche in base["result"]["list"]:
        socle = fiche.get("base") or {}
        if socle.get("id"):
            yield socle["id"], socle, fiche.setdefault("kvParam", {})


def matieres_chargees():
    """Types de matiere presents dans les emplacements du CFS."""
    try:
        routes = charger(ROUTES)
    except (OSError, ValueError) as err:
        return {}, "table des emplacements illisible : %s" % err
    presents = {}
    for boite, contenu in sorted(routes.get("base_data", {}).items()):
        for rang, type_matiere in enumerate(contenu.get("material_type", [])):
            if str(type_matiere) in ("-1", "None", ""):
                continue
            emplacement = "%s%s" % (boite, "ABCD"[rang])
            presents.setdefault(cle_base(type_matiere), []).append(emplacement)
    return presents, None


def rendre_compte(base, presents, note):
    if note:
        print("emplacements : %s" % note)
    else:
        print("matieres actuellement dans le CFS :")
        for identifiant, emplacements in sorted(presents.items()):
            print("    %s  %s" % (identifiant, " ".join(emplacements)))
    print("temperatures de chargement en vigueur :")
    for identifiant, socle, kv in fiches(base):
        if identifiant not in presents:
            continue
        print("    %s  %-18s %s / %s C" % (
            identifiant,
            socle.get("name", "?"),
            kv.get("nozzle_temperature", "?"),
            kv.get("nozzle_temperature_initial_layer", "?"),
        ))


def appliquer(base, voulu):
    """Ecrit les temperatures voulues et renvoie ce qui a change."""
    connus = {identifiant for identifiant, _, _ in fiches(base)}
    inconnus = sorted(set(voulu) - connus)
    if inconnus:
        raise SystemExit("fiche inconnue dans la base : %s" % ", ".join(inconnus))
    touchees = []
    for identifiant, socle, kv in fiches(base):
        if identifiant not in voulu:
            continue
        cible = str(int(voulu[identifiant]))
        avant = [kv.get(cle) for cle in CLES]
        for cle in CLES:
            kv[cle] = cible
        touchees.append((identifiant, socle.get("name", "?"), avant, cible))
    return touchees


def ecrire(chemin, base):
    sauvegarde = "%s.kctrl-bak-%s" % (chemin, time.strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(chemin, sauvegarde)
    provisoire = chemin + ".kctrl-tmp"
    with open(provisoire, "w") as f:
        json.dump(base, f, ensure_ascii=False, separators=(",", ":"))
    os.rename(provisoire, chemin)
    return sauvegarde


def relire_et_verifier(chemin, voulu):
    relu = charger(chemin)
    ecarts = []
    for identifiant, _, kv in fiches(relu):
        if identifiant not in voulu:
            continue
        cible = str(int(voulu[identifiant]))
        for cle in CLES:
            if kv.get(cle) != cible:
                ecarts.append("%s.%s = %r au lieu de %r"
                              % (identifiant, cle, kv.get(cle), cible))
    return ecarts


def paire(texte):
    if "=" not in texte:
        raise argparse.ArgumentTypeError("attendu fiche=temperature, recu %r" % texte)
    identifiant, valeur = texte.split("=", 1)
    return identifiant.strip(), float(valeur)


def main():
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--temp", type=paire, action="append", default=[],
                         metavar="FICHE=CELSIUS",
                         help="temperature de chargement voulue, par exemple 00001=200")
    parseur.add_argument("--appliquer", action="store_true",
                         help="ecrire; sans cette option le script ne fait que lire")
    parseur.add_argument("--base", default=BASE)
    args = parseur.parse_args()

    base = charger(args.base)
    presents, note = matieres_chargees()
    rendre_compte(base, presents, note)

    voulu = dict(args.temp)
    if not voulu:
        return 0

    for identifiant, celsius in sorted(voulu.items()):
        if celsius < 150.0 or celsius > 320.0:
            raise SystemExit("temperature hors limites pour %s : %s" % (identifiant, celsius))

    touchees = appliquer(base, voulu)
    print("")
    for identifiant, nom, avant, cible in touchees:
        print("%s %-18s %s -> %s C" % (identifiant, nom, " / ".join(map(str, avant)), cible))

    if not args.appliquer:
        print("\nrien ecrit ; relancer avec --appliquer")
        return 0

    sauvegarde = ecrire(args.base, base)
    print("\nsauvegarde : %s" % sauvegarde)
    ecarts = relire_et_verifier(args.base, voulu)
    if ecarts:
        print("RELECTURE EN ECHEC :")
        for ecart in ecarts:
            print("    %s" % ecart)
        return 1
    print("relecture conforme")
    return 0


if __name__ == "__main__":
    sys.exit(main())
