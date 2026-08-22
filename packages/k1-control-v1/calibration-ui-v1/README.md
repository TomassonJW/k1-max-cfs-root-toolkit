# CALIBRATION-UI-V1

Statut : candidat hors imprimante. Aucune pose n'est autorisée sans la gate
exacte `G4-K1-CONTROL-CALIBRATION-UI-V1`.

Ce paquet transforme le prototype en parcours réel sans console. La page
statique est servie sous `/k1-control/` par le nginx déjà installé. Elle ne peut
appeler que dix routes métier du composant Moonraker original. Elle n'expose
ni G-code arbitraire, ni impression, ni extrusion, ni action CFS.

Le composant exécute côté machine les six maillages fixes, conserve les
matrices dans un état JSON atomique, compare deux médianes indépendantes de
trois, charge le candidat robuste, le relit puis le persiste. Une fermeture du
navigateur n'interrompt donc pas la sécurité du protocole. Un échec ou une
annulation coupe les chauffes. La chauffe et les 200 secondes de stabilisation
sont découpées côté contrôleur pour accepter une annulation rapidement. Un
homing, nettoyage ou mesh physique déjà commencé va seulement jusqu'à la fin de
cette opération bornée avant l'arrêt. Un backup vérifié de `printer.cfg` et, s'il
existe, de l'état Z précède la première chauffe.

Après le mesh, l'interface guide les huit paliers Z. Les ajustements ne sont
disponibles qu'à `0,1 mm`. L'enregistrement exige une confirmation explicite du
jeu observé et une remontée préalable. La restauration complète remet exactement
`printer.cfg` et l'état Z du backup de cette campagne, puis recharge Klipper.

La pose future ajoute deux composants Python, trois fichiers statiques et une
configuration Moonraker complète dérivée de la base PATHS-V1. Elle redémarre
Moonraker seulement ; elle ne chauffe, ne home et ne lance aucune calibration.
