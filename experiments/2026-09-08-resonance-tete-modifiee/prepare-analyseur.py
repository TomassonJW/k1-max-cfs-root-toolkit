# Prépare une copie non bridée de l'analyseur de Klipper, dans /tmp.
#
# Deux bridages vivent dans le module d'origine, et aucun des deux n'a sa place
# dans une relecture hors ligne :
#
#   - le constructeur relit `gcode_macro.cfg` pour restreindre les filtres
#     candidats à ce que porte `variable_autotune_shapers`, c'est-à-dire `ei`
#     seul sur cette machine ;
#   - il le fait à travers l'objet `configfile` de Klipper, qui n'existe pas
#     hors d'une instance en marche.
#
# On retire donc exactement ce bloc, du `configfile = ...` au `logging.error`
# qui ferme son `except`. La liste par défaut des cinq filtres, posée juste
# avant, reprend alors ses droits. Rien n'est touché dans /usr/share.
import pathlib
import sys

SOURCE = pathlib.Path("/usr/share/klipper/klippy/extras/shaper_calibrate.py")
CIBLE = pathlib.Path("/tmp/sc/extras")

DEBUT = "configfile = self.printer.lookup_object('configfile')"
FIN = 'logging.error("gcode_macro_path:'


def deplomber(texte):
    lignes = texte.splitlines(keepends=True)
    debuts = [i for i, l in enumerate(lignes) if DEBUT in l]
    fins = [i for i, l in enumerate(lignes) if FIN in l]
    if len(debuts) != 1 or len(fins) != 1 or fins[0] < debuts[0]:
        raise SystemExit(
            "shaper_calibrate.py n'a pas la forme attendue : %d debut(s), %d fin(s). "
            "Le module a change, la decoupe doit etre revue avant toute analyse."
            % (len(debuts), len(fins)))
    retire = lignes[debuts[0]:fins[0] + 1]
    if not any("autotune_shapers" in l for l in retire):
        raise SystemExit("le bloc retire ne contient pas le bridage attendu")
    return "".join(lignes[:debuts[0]] + lignes[fins[0] + 1:]), len(retire)


def main():
    CIBLE.mkdir(parents=True, exist_ok=True)
    (CIBLE / "__init__.py").write_text("")
    (CIBLE / "shaper_defs.py").write_text(
        (SOURCE.parent / "shaper_defs.py").read_text())
    texte, retire = deplomber(SOURCE.read_text())
    (CIBLE / "shaper_calibrate.py").write_text(texte)

    sys.path.insert(0, "/tmp/sc")
    import importlib
    sc = importlib.import_module("extras.shaper_calibrate")
    filtres = sc.ShaperCalibrate(printer=None).autotune_shapers
    attendu = ['zv', 'mzv', 'ei', '2hump_ei', '3hump_ei']
    if list(filtres) != attendu:
        raise SystemExit("filtres candidats %s, attendu %s" % (filtres, attendu))
    print("analyseur pret dans /tmp/sc : %d lignes retirees, filtres %s"
          % (retire, ", ".join(filtres)))


if __name__ == "__main__":
    main()
