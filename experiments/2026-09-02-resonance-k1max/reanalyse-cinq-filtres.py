# Reevalue les cinq filtres sur des donnees deja enregistrees.
# Rien n est mesure ici : on relit le CSV du balayage et on refait le choix
# que la machine n a pas eu le droit de faire, elle qui ne teste que ei.
#
# On ne renormalise pas : l entete porte deja une colonne de filtre, donc la
# reponse est deja ramenee aux frequences d entree. Le controle est le filtre
# ei, qui doit retomber exactement sur ce que la machine a annonce.
import sys, importlib
sys.path.insert(0, "/tmp/sc")
import numpy as np
sc = importlib.import_module("extras.shaper_calibrate")

def charge(chemin):
    with open(chemin) as f:
        entete = f.readline()
    assert "ei(" in entete or "mzv" in entete, "reponse non normalisee"
    d = np.loadtxt(chemin, skiprows=1, comments="#", delimiter=",")
    data = sc.CalibrationData(freq_bins=d[:,0], psd_sum=d[:,4],
                              psd_x=d[:,1], psd_y=d[:,2], psd_z=d[:,3])
    data.set_numpy(np)
    return data

for axe, chemin in (("X", sys.argv[1]), ("Y", sys.argv[2])):
    calib = sc.ShaperCalibrate(printer=None)
    lignes = []
    meilleur, tous = calib.find_best_shaper(charge(chemin), max_smoothing=None,
                                            logger=lignes.append)
    print("")
    print("=== axe %s" % axe)
    for l in lignes:
        print("   ", l)
    print("    -> retenu : %s a %.1f Hz, vibrations %.1f%%, accel max %d"
          % (meilleur.name, meilleur.freq, meilleur.vibrs*100.,
             meilleur.max_accel))
