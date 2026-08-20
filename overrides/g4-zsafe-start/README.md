# G4-ZSAFE-START-V1

Statut : **candidat préparé hors imprimante, non autorisé et non déployé**.

Ce paquet surcharge uniquement le corps de `START_PRINT` par un include chargé
après les fichiers stock. Il ajoute un point de fin `ZSAFE_END_PRINT`, appelé par
Orca, qui capture la correction finale avant d'appeler le `END_PRINT` stock.
Aucun fichier constructeur n'est copié ou modifié dans ce dépôt.

## Contrat borné

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
  une future revue.

Le post-traitement Orca existant reste configuré et inchangé. Le point d'entrée
s'appelle toujours `START_PRINT`, donc il réinsère ensuite `SET_GCODE_OFFSET
Z=0.27`. Cette écriture absolue est idempotente : elle confirme la même valeur
après la purge, elle ne l'ajoute pas une seconde fois.

## Fichiers

- `zsafe_g4.cfg` : overlay Klipper original ;
- `orca-machine-start.gcode` : départ Orca sans `G28` ni `T0` préalable ;
- `orca-machine-end.gcode` : capture avant la fin stock ;
- `sequence-contract.json` : modèle utilisé par la simulation hors ligne.

La procédure complète de sauvegarde, déploiement futur, validation et rollback
est dans `docs/09-g4-zsafe-start-package.md`.
