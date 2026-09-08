# Analyse une campagne de résonance : les cinq filtres sur chaque axe, la
# comparaison des deux courroies, et l'écart avec la série du 2 septembre.
#
# Rien n'est mesuré ici et rien n'est appliqué. Le script relit les CSV produits
# par campagne-resonance.py, avec l'analyseur non bridé préparé par
# prepare-analyseur.py.
#
# Deux natures de données, qui ne se comparent pas entre elles :
#   - les axes viennent de SHAPER_CALIBRATE, normalisés aux fréquences
#     d'entrée : le pourcentage de vibrations restantes y a un sens ;
#   - les courroies viennent de TEST_RESONANCES, non normalisées : on y compare
#     la courroie A à la courroie B, mesurées de la même façon, et rien d'autre.
import importlib
import pathlib
import sys

sys.path.insert(0, "/tmp/sc")
import numpy as np

sc = importlib.import_module("extras.shaper_calibrate")

# Série du 2 septembre après resserrage, document 61. Point de comparaison, pas
# une cible : la tête a changé depuis.
REFERENCE = {
    "resonance-x": ("ei", 40.2, 24.7, 3000),
    "resonance-y": ("mzv", 39.0, 0.0, 4500),
}
# Largeurs recalculees ici sur les CSV du 2 septembre : le document 61 donnait
# 10,7 Hz, mesure autrement. Ce sont ces valeurs-la qui sont comparables.
REFERENCE_COURROIES = {"courroie-a": (39.8, 7.9, 1.5), "courroie-b": (40.1, 8.0, 1.3)}


def charge(chemin):
    d = np.loadtxt(chemin, skiprows=1, comments="#", delimiter=",")
    data = sc.CalibrationData(freq_bins=d[:, 0], psd_sum=d[:, 4],
                              psd_x=d[:, 1], psd_y=d[:, 2], psd_z=d[:, 3])
    data.set_numpy(np)
    return data


def axe(nom, chemin):
    entete = pathlib.Path(chemin).read_text().splitlines()[0]
    if "(" not in entete:
        raise SystemExit(
            "%s n'est pas normalise (entete : %s). Un pourcentage de vibrations "
            "calcule sur cette sortie ne veut rien dire." % (chemin, entete))
    lignes = []
    meilleur, tous = sc.ShaperCalibrate(printer=None).find_best_shaper(
        charge(chemin), max_smoothing=None, logger=lignes.append)
    print("\n=== %s" % nom)
    print("    %-9s %9s %14s %12s" % ("filtre", "frequence", "vibrations", "accel max"))
    for r in tous:
        marque = "->" if r.name == meilleur.name else "  "
        print("    %s %-7s %7.1f Hz %11.1f %% %9d" %
              (marque, r.name, r.freq, r.vibrs * 100.0, r.max_accel))
    if nom in REFERENCE:
        t, f, v, a = REFERENCE[nom]
        print("    2 septembre : %s a %.1f Hz, %.1f %% de vibrations, accel %d" % (t, f, v, a))
        print("    ecart       : %+.1f Hz, %+.1f point(s) de vibrations"
              % (meilleur.freq - f, meilleur.vibrs * 100.0 - v))
    return meilleur


def courroie(nom, chemin):
    """Pic principal, largeur à mi-hauteur, et répartition de l'énergie."""
    d = np.loadtxt(chemin, skiprows=1, comments="#", delimiter=",")
    freq, psd = d[:, 0], d[:, 4]
    total = psd.sum()
    sommet = int(np.argmax(psd))
    moitie = psd[sommet] / 2.0
    au_dessus = freq[psd >= moitie]
    largeur = float(au_dessus.max() - au_dessus.min()) if au_dessus.size else 0.0
    bas = float(psd[freq < 30.0].sum() / total * 100.0)
    bande = float(psd[(freq >= 30.0) & (freq <= 45.0)].sum() / total * 100.0)
    print("\n=== %s" % nom)
    print("    pic principal %.1f Hz | largeur a mi-hauteur %.1f Hz"
          % (freq[sommet], largeur))
    print("    energie 30-45 Hz %.1f %% | energie sous 30 Hz %.1f %%" % (bande, bas))
    if nom in REFERENCE_COURROIES:
        f, l, b = REFERENCE_COURROIES[nom]
        print("    2 septembre : pic %.1f Hz, largeur %.1f Hz, sous 30 Hz %.1f %%" % (f, l, b))
    return {"pic": float(freq[sommet]), "largeur": largeur, "sous_30": bas}


def main():
    dossier = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                           else "/tmp/campagne-resonance")
    retenus = {}
    for nom in ("resonance-x", "resonance-y"):
        chemin = dossier / (nom + ".csv")
        if chemin.exists():
            retenus[nom] = axe(nom, chemin)
    courroies = {}
    for nom in ("courroie-a", "courroie-b"):
        chemin = dossier / (nom + ".csv")
        if chemin.exists():
            courroies[nom] = courroie(nom, chemin)

    if len(courroies) == 2:
        a, b = courroies["courroie-a"], courroies["courroie-b"]
        ecart = abs(a["pic"] - b["pic"])
        print("\n=== courroies")
        print("    ecart entre les deux pics : %.1f Hz" % ecart)
        # Le 2 septembre, 0,3 Hz d'ecart valait "tendues pareil, ne pas y
        # toucher". Un ecart franc est le signal inverse.
        print("    %s" % ("tension comparable, rien a reprendre" if ecart <= 2.0
                          else "ECART NET : une courroie est plus lache que l'autre"))

    if retenus:
        print("\n=== a appliquer si ces mesures sont retenues")
        parties = []
        for nom, cle in (("resonance-x", "X"), ("resonance-y", "Y")):
            if nom in retenus:
                r = retenus[nom]
                parties.append("SHAPER_TYPE_%s=%s SHAPER_FREQ_%s=%.1f" % (cle, r.name, cle, r.freq))
        print("    SET_INPUT_SHAPER " + " ".join(parties))
        accels = [r.max_accel for r in retenus.values()]
        print("    plafond d'acceleration conseille : %d mm/s2 (le plus bas des deux axes)"
              % min(accels))


if __name__ == "__main__":
    main()
