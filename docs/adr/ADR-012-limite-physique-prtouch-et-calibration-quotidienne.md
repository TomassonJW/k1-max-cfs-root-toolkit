# ADR-012 — Limite physique PRTouch et calibration quotidienne à un passage

Date : 2026-08-23

Statut : accepté hors imprimante ; remplace les grandes matrices de l'ADR-010
et complète l'ADR-011

## Contexte

La campagne réelle `20260823-021858-540-calibration-ui-v1` a chargé une matrice
`9 × 9` bicubique et commencé le premier mesh. Le journal Klipper exact atteint
`g29_cnt=36`, puis `prtouch_v2_wrapper.py` lève `IndexError: list index out of
range` au passage vers le trente-septième point physique. Le contrôleur ne reçoit
donc aucune matrice complète et s'arrête à `mesh_index=1`.

La configuration usine K1 Max contient exactement trente-six paires de tables
de compensation `tri_min_hold_1..36` et `tri_max_hold_1..36`. La limite n'est
pas un défaut de l'agrégateur K1 Control : elle appartient au chemin PRTouch
Creality exact de cette machine.

Une discussion communautaire propose de passer `pr_version: 1` et de retirer
les tables par point. Ce contournement change le mode propriétaire du capteur,
supprime ses compensations calibrées et comporte au moins un retour de démarrage
bloqué après coupure électrique. Il n'est pas acceptable sur cette imprimante
de production.

La même campagne révélait un second problème de produit : l'interface annonçait
six meshes successifs pour une calibration quotidienne. Ces six passages
étaient justifiés pour la qualification scientifique initiale
FIRST-CALIBRATION-V2, pas pour l'usage courant une fois le capteur qualifié.

## Options examinées

1. Conserver `9/11/15` et modifier `pr_version` ou retirer les tables PRTouch.
   Refusé : risque matériel et de démarrage disproportionné, sans preuve sur la
   révision exacte.
2. Simuler une grande matrice par interpolation ou duplication de points.
   Refusé : l'interface présenterait de fausses mesures comme des points
   physiques.
3. Garder six meshes `6 × 6` à chaque usage. Refusé : durée et usure inutiles ;
   le protocole robuste à six passages a déjà rempli son rôle de qualification.
4. Fixer la calibration quotidienne à un mesh physique `6 × 6` Lagrange, puis
   conserver le chemin Z borné. Retenu.

## Décision

- La matrice physique exposée et acceptée par K1 Control est uniquement
  `6 × 6` avec interpolation `lagrange`.
- Le contrôleur exécute exactement un mesh complet par calibration quotidienne.
- Le compteur UI et l'API annoncent explicitement `1/1`.
- Toute autre taille est refusée avant chauffe avec un message mentionnant la
  limite PRTouch de trente-six points.
- L'adaptateur `probe_count + algorithm` reste installé comme garde, mais
  n'autorise plus que `6,6 + lagrange`.
- FIRST-CALIBRATION-V2 et ses six mesures restent une preuve historique valide ;
  elles ne deviennent pas le comportement quotidien.
- La campagne d'acceptation UI doit prouver un mesh `6 × 6`, le chemin Z complet,
  l'enregistrement, l'annulation et la restauration depuis l'écran. Elle ne
  relance pas une qualification statistique de six meshes.

## Conséquences

- les niveaux `9 × 9`, `11 × 11` et `15 × 15` sont retirés de l'interface et
  refusés côté serveur ;
- le package de presets est aligné sur le seul niveau matériel réel pour éviter
  qu'une ancienne surcouche réintroduise les choix invalides ;
- la durée normale tombe de six meshes à un seul, sans réduire la preuve déjà
  acquise sur la répétabilité du capteur ;
- aucun contournement `pr_version`, aucune suppression des tables usine et aucun
  changement de firmware n'est autorisé ;
- les corrections restent hors imprimante tant que les gates exactes révisées
  n'ont pas reçu leurs nouveaux GO.

## Sources externes vérifiées

- configuration usine K1 Max publiée par Creality :
  [factory_printer.cfg](https://github.com/CrealityOfficial/K1_Series_Klipper/blob/main/config/K1_MAX_CR4CU220812S12_1/factory_printer.cfg) ;
- discussion communautaire décrivant le contournement `pr_version: 1` et ses
  retours contradictoires :
  [Creality Helper Script Wiki — discussion 434](https://github.com/Guilouz/Creality-Helper-Script-Wiki/discussions/434).

Ces sources complètent la preuve principale issue du journal de la machine
exacte ; elles ne la remplacent pas.
