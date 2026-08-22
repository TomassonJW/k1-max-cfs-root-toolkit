# K1 Control calibration path V1

Statut : **candidat hors imprimante ; installation et calibration interdites**.

Ce paquet prépare le gate nommé
`G4-K1-CONTROL-CALIBRATION-PATH-V1`. Il corrige un manque découvert avant la
première calibration : le runtime Z/mesh sait enregistrer un Z provisoire, mais
ne fournit aucun chemin borné pour l'évaluer physiquement avant acceptation.

Le paquet ajoute une seule inclusion originale après le runtime déjà installé.
Il ne remplace ni ce runtime, ni `START_PRINT`, ni un fichier constructeur. Son
éventuelle pose recharge uniquement l'hôte Klipper et sa validation doit rester
sans chauffe et sans mouvement.

## Ce que le chemin ajoute

- sélection et relecture d'un mesh persistant déjà qualifié, avec identité
  plaque/plage thermique/révision capteur/matrice conservée jusqu'à la session
  Z ;
- vérification des températures demandées et réellement atteintes ;
- ouverture de la session Z existante seulement dans ce contexte ;
- approche centrale non extrusive avec départ à `5 mm` ;
- descente imposée `5 → 2 → 1 → 0,5 → 0,3 → 0,2 → 0,15 → 0,1 mm` ;
- réglages Z uniquement à la dernière hauteur, avec repositionnement physique
  borné à `0,1 mm` après chaque incrément ;
- confirmation humaine explicite du jeu de référence ;
- remontée obligatoire de `5 mm` avant acceptation ou annulation ;
- wrappers séparés pour accepter ou annuler la session Z ;
- garde fermée si la session, le mesh, le homing ou l'état machine changent.

Le chemin ne contient aucune extrusion, aucun appel CFS, aucune purge et aucune
commande de chauffe. La chauffe, le homing et la création des deux meshes
restent les opérations explicites du futur gate
`G4-K1-CONTROL-FIRST-CALIBRATION-V1`.

## Limite volontaire

Cette première méthode règle le Z avec une cale ou une feuille connue, sans
imprimer de motif. Elle permet d'établir un premier enregistrement cohérent sans
ouvrir prématurément le CFS, la purge ou `START_PRINT`. Une validation de
première couche restera obligatoire dans la future bascule atomique
interface/Orca ; le présent paquet ne prétend pas valider l'autonomie
production.

## Pose future, non autorisée

Source : `k1-control-calibration-path.cfg`.

Destination prévue :
`/usr/data/printer_data/config/k1-control-calibration-path.cfg`.

Modification prévue de `printer.cfg` : une seule ligne
`[include k1-control-calibration-path.cfg]` immédiatement après
`[include k1-control-z-mesh.cfg]`.

État initial exact : runtime Z/mesh installé et validé, état persistant vide,
axes non référencés, chauffes à zéro, deux CFS connectés, `printer.cfg` stabilisé
sur l'empreinte revue. Le déploiement ne doit appeler aucune macro de mouvement
du présent fichier.

## Rollback futur

Le déployeur `scripts/deploy-k1-control-calibration-path-v1.ps1` vérifie son
backup de `printer.cfg`, retire l'unique fichier et l'unique inclusion, recharge
Klipper, attend la reconnexion des deux CFS et les écritures différées Creality,
puis restaure une dernière fois le backup exact sans nouveau restart. Aucune
donnée Z ne doit exister ni être modifiée par la pose de ce seul chemin.

Son préflight futur parse aussi le candidat en mémoire avec le Python/Jinja
exact de la K1 avant la première écriture. Cette préparation hors imprimante
n'exécute pas ce préflight et ne contacte pas la machine.

## Autonomie

Ce paquet est un prérequis de sécurité, pas encore l'interface autonome. Le
contrat `calibration-path-contract.json` définit les étapes et boutons que la
future interface devra exposer sans console. La gate suivante réalisera la
première calibration ; une pose ultérieure raccordera réellement cette UX à
Moonraker.
