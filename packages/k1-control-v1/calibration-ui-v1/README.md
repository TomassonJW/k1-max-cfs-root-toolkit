# CALIBRATION-UI-V1

Statut : candidat hors imprimante. Aucune pose n'est autorisée sans la gate
exacte `G4-K1-CONTROL-CALIBRATION-UI-V1`.

Ce paquet transforme le prototype en parcours réel sans console. La page
statique est servie sous `/k1-control/` par le nginx déjà installé. Elle ne peut
appeler que dix routes métier du composant Moonraker original. Elle n'expose
ni G-code arbitraire, ni impression, ni extrusion, ni action CFS.

Le lanceur poste ouvre cette route sous l'origine
`http://localhost:4409/k1-control/`, distincte de l'origine Mainsail
`127.0.0.1:4409` et de son service worker. Le déployeur fixe le dossier statique
en `0755` et le validateur exige ce mode exact avant d'accepter la pose.

Le composant exécute côté machine les six maillages fixes, conserve les
matrices dans un état JSON atomique, compare deux médianes indépendantes de
trois, charge le candidat robuste, le relit puis le persiste. Une fermeture du
navigateur n'interrompt donc pas la sécurité du protocole. Un échec ou une
annulation coupe les chauffes. La chauffe et les 200 secondes de stabilisation
sont découpées côté contrôleur pour accepter une annulation rapidement. Un
homing, nettoyage ou mesh physique déjà commencé va seulement jusqu'à la fin de
cette opération bornée avant l'arrêt. Un backup vérifié de `printer.cfg` et, s'il
existe, de l'état Z précède la première chauffe.

Au premier affichage, le formulaire reprend le Z accepté par le runtime comme
seed explicite. Après un rechargement du navigateur, il réaffiche aussi les
paramètres exacts de la campagne serveur. La confirmation physique « plateau
libre » reste volontairement à refaire et demeure accessible avant le début du
Z ; avec « buse propre », elle conditionne directement le bouton de descente.

Après le mesh, l'interface guide les huit paliers Z. Les ajustements ne sont
disponibles qu'à `0,1 mm`. L'enregistrement exige une confirmation explicite du
jeu observé et une remontée préalable. La restauration complète remet exactement
`printer.cfg` et l'état Z du backup de cette campagne, puis recharge Klipper.

La pose future ajoute deux composants Python, trois fichiers statiques et une
configuration Moonraker complète dérivée de la base PATHS-V1. Elle redémarre
Moonraker seulement ; elle ne chauffe, ne home et ne lance aucune calibration.
Son préflight accepte un chemin réellement fermé après une calibration réussie
(`committed`), après annulation (`cancelled`) ou avant toute session (`idle`) ;
tout état intermédiaire ou armé reste refusé.
Il compile et importe aussi les deux sources en mémoire avec le Python Moonraker
exact, par stdin et sans créer de fichier distant, avant toute mutation.

Les fichiers sont transférés avec `scp -O` : l'OpenSSH Windows récent utilise
sinon SFTP par défaut, alors que le Dropbear Creality exact ne fournit pas de
serveur SFTP. Le rollback retire également le staging exact avant de restaurer
et vérifier la base.
