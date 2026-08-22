# First calibration V1

Statut : exécuté KO le 2026-08-22 après exactement deux meshes. Le GO exact est
consommé ; aucun rerun n'est autorisé sans nouveau protocole revu et nouvelle
autorisation explicite.

Ce paquet n'installe aucun nouveau fichier sur la K1. Il orchestre, par étapes
séparées, les commandes déjà installées par le runtime Z/mesh et le chemin borné
du premier Z.

Le contrat figé est `first-calibration-contract.json`. Il choisit explicitement
la plaque `PEI_TEXTURED_A`, le plateau à `55 °C`, la buse à `140 °C`, `200 s`
de stabilisation, un nettoyage stock borné jusqu'à `180 °C`, puis un
homing. Deux meshes `6 × 6` Lagrange sont capturés sur `5–295 mm`. Le second
n'est qualifié que si chacun de ses 36 points reste à `0,025 mm` ou moins du
premier. Un échec arrête la mission sans troisième essai automatique.

Après qualification, le second mesh peut être enregistré sous
`k1_p001_t055_r001_n06x06`. La session Z utilise ensuite le chemin déjà installé
et sa descente `5 → 2 → 1 → 0,5 → 0,3 → 0,2 → 0,15 → 0,1 mm`. Le seed `0,0 mm`
est écrit dans le contrat : c'est le point neutre explicite de l'état vide, pas
une correction prétendument universelle. Chaque ajustement reste borné et
l'enregistrement exige confirmation humaine puis remontée de `5 mm`.

`compare_meshes.py` est local et sans réseau. Il refuse toute matrice autre que
`6 × 6`, toute valeur non finie et tout écart au-dessus du seuil revu.

Le pilote est `scripts/run-k1-control-first-calibration-v1.ps1`. Son action par
défaut `Plan` ne contacte pas la K1. Toutes les actions distantes exigent
`-Execute`, le nom de gate exact, un identifiant de capture conforme et un
dossier de preuve local sous le workspace. Les actions physiques sont séparées
pour laisser un checkpoint observable entre préparation, chaque mesh,
persistance, chaque hauteur Z et acceptation.

`Cancel` annule uniquement la session Z provisoire et conserve le mesh déjà
qualifié. `Rollback` restaure le `printer.cfg` exact et l'état Z vide sauvegardés
avant la première chauffe ; il conserve le runtime et le chemin de calibration
installés.
