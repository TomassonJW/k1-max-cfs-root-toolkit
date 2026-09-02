# ADR-055 — Sélection d'emplacement CFS et rechargement automatique repris

Date : 2026-09-02

Statut : **accepté**. Remplace l'ADR-051.

## Contexte

Trois fonctions du CFS d'origine avaient disparu de la voie possédée : choisir
la bobine d'un travail, recharger sur une bobine déclarée identique en fin de
bobine, et imprimer aux températures du G-code.

L'ADR-051 avait laissé le capteur de tête éteint, en identifiant correctement
sa dépendance — posséder `END_PRINT` — et en la jugeant trop coûteuse : « en
prendre le contrôle signifierait recopier tout son corps ». Cette évaluation
était fausse. `END_PRINT` fait deux lignes et `CANCEL_PRINT` trois ; le corps
volumineux est `END_PRINT_NO_M84`, qui n'a pas besoin d'être touché.

## Décision

**Le CFS n'est ni contourné ni repris à cent pour cent. Ses propres données
sont écrites par ses propres commandes.**

1. `KCTRL_SLOT` écrit `Tnn_map` par `BOX_MODIFY_TN` **et** mémorise
   l'emplacement pour l'appel direct du démarrage. Les deux routes disent la
   même chose, donc un rechargement automatique qui réécrit `Tnn_map` reste
   cohérent avec nous.
2. `filament_sensor_2` est armé en fin de `START_PRINT` et désarmé par
   `END_PRINT` et `CANCEL_PRINT`, redéfinis, `END_PRINT_NO_M84` laissé stock.
3. `Tn_extrude_temp` descend à `200` dans `box.cfg`. La clé n'est pas acceptée
   par `MODIFY_BOX_CFG` : c'est le fichier plus un redémarrage, ou rien.
4. Le composant `k1_control_cfs_direct_owner` reste désactivé. C'était le verrou
   sans clé de l'ADR-032 ; rien ici n'en a besoin.

## Conséquences

- Le point 4 du cahier des charges — rechargement automatique — cesse d'être
  bloqué. Il reste à prouver par une bobine réellement épuisée.
- La règle de l'ADR-051 tient toujours : **armer une protection sans posséder la
  séquence qui doit la désarmer transforme une fin normale en incident.** Elle
  est respectée, pas contournée : la séquence de désarmement est possédée avant
  l'armement.
- Le champ température de la fiche écran reste décoratif et le restera : le
  module ne lit pas le fichier que l'écran écrit. Le seul réglage réel est le
  repli global.
- Une session PETG demande de remonter `Tn_extrude_temp` et de redémarrer.
- La sélection ne passe pas par l'écran de la machine : l'écran écrit `Tnn_map`
  par son propre chemin, que `START_PRINT` ne relit pas. `KCTRL_SLOT` est le
  point d'entrée unique tant que l'interface K1 Control ne l'expose pas.

## Voir aussi

- ADR-051 — remplacé
- ADR-032 — propriétaire direct, resté désactivé
- doc 54 — preuves, commandes et pièges
