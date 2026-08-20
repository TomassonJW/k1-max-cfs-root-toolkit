# G4-ZSAFE-START-V1

Statut : **REJETÉ, jamais déployé, ne jamais charger ni importer**.

Ce dossier est conservé uniquement comme preuve historique et comme fixture de
tests. Il ne constitue plus un candidat G4. Le corps de `START_PRINT` échoue
volontairement s'il est chargé par erreur et les extraits Orca sont marqués
`NEVER IMPORT`.

L'ancien paquet surchargeait uniquement le corps de `START_PRINT` par un include chargé
après les fichiers stock. Il ajoute un point de fin `ZSAFE_END_PRINT`, appelé par
Orca, qui capture la correction finale avant d'appeler le `END_PRINT` stock.
Aucun fichier constructeur n'est copié ou modifié dans ce dépôt.

## Ancien contrat refusé

- cible : K1 Max S12 structure 0, firmware `2.3.5.34` ;
- outils initiaux : `T0` à `T7` ;
- mesh : chargement explicite du profil stock `default`, sans contrôle aléatoire,
  génération ni sauvegarde automatique ;
- correction autorisée : `+0,27 mm` seulement pour ce premier paquet ;
- nettoyage : manuel, confirmé une fois par `ZSAFE_CONFIRM_NOZZLE_CLEAN` ;
- purge et mouvements bas : refusés tant que référence finale, mesh et
  correction effective ne sont pas vérifiés ;
- fin : la correction finale devient un candidat conservé dans
  `zsafe_g4_variables.cfg`. Elle n'est jamais réappliquée automatiquement sans
  une revue qui n'est plus autorisée pour ce paquet.

Le post-traitement Orca existant reste configuré et inchangé sur la machine. L'ancien point d'entrée
s'appelle toujours `START_PRINT`, donc il réinsère ensuite `SET_GCODE_OFFSET
Z=0.27`. Cette écriture absolue est idempotente : elle confirme la même valeur
après la purge, elle ne l'ajoute pas une seconde fois.

## Fichiers

- `zsafe_g4.cfg` : overlay Klipper original ;
- `orca-machine-start.gcode` : départ Orca sans `G28` ni `T0` préalable ;
- `orca-machine-end.gcode` : capture avant la fin stock ;
- `sequence-contract.json` : modèle utilisé par la simulation hors ligne.

La raison du rejet et la cible qui le remplace sont dans
`docs/09-g4-zsafe-start-package.md` et
`docs/10-systeme-pilotage-perenne.md`. Il n'existe plus de procédure de
déploiement pour ce dossier.
