# ADR-043 — Jamais de garde d'exclusion sans son remplaçant fonctionnel

Date : 2026-09-01

Statut : **acceptée**.

## Contexte

Le 1er septembre, la machine est arrivée dans un état où **aucun retrait de
filament n'était possible**, ni par Codex, ni par Thomas depuis l'écran.

Trois chemins, tous fermés :

1. `BOX_CUT_MATERIAL` et `BOX_RETRUDE_MATERIAL` — refusés par
   `k1_control_cfs_direct_owner` avec `stock_effect_command_blocked` ;
2. `KCTRL_CYCLE_UNLOAD_BEFORE_CLEAN_V1` — bouchon qui lève une erreur par
   construction : « stock cut and retract primitives are not physically
   qualified » ;
3. `remote_cutter_reach_recovery.py` — ne coupe jamais et dépend de
   `box.cut_pos`, champ qui ne reflète pas le capteur (ADR-041).

Onze refus consécutifs ont été capturés pendant les tentatives manuelles de
Thomas. Le filament est resté physiquement engagé, tube PTFE bloqué côté tête,
sans accès manuel simple.

Aggravant : le propriétaire direct se croyait `phase: idle`,
`active_route: None`, `unload_count: 0`, alors que les deux capteurs filament
étaient à `True`. L'état logique et l'état physique avaient divergé après un
redémarrage de Klipper, sans que rien ne le détecte.

## Décision

Un composant qui **retire** une capacité existante doit livrer son remplaçant
fonctionnel **dans la même tranche**, prouvé physiquement, avant d'être posé
avec `enabled: true`.

Concrètement, il est interdit de poser un garde d'exclusion `BOX_*` actif tant
que le propriétaire n'a pas, qualifié physiquement :

- un retrait complet ;
- un rembobinage vers le boîtier CFS ;
- une resynchronisation de son état logique sur les capteurs physiques au
  démarrage.

Tant que ces trois points ne sont pas verts, le composant se pose
`enabled: false`.

## Conséquences

- Toute pose future ajoute une question de revue obligatoire : « qu'est-ce que
  ce composant empêche, et par quoi je le remplace, aujourd'hui, prouvé ? »
- Un état logique de propriétaire doit se réconcilier sur les capteurs au
  démarrage, ou refuser de prendre la propriété.
- La sortie de secours doit rester documentée et testée : remettre les trois
  `include` en `-active-` / `-disabled-` est le retour arrière officiel, et il
  doit figurer dans le handoff, pas seulement dans un paquet.
- Le registre du Goal 3 est optimiste : il comptait `2/7` alors que l'étape de
  retrait n'a jamais été écrite. Le compte doit refléter les bouchons, pas
  seulement les gates fermées.
