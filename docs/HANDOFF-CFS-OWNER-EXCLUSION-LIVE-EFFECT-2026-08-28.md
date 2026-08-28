# Passation — observabilité V2 et exclusion propriétaire CFS réelle

Date : 2026-08-28

État : **mission close OK ; captures consommées ; production fermée**.

## Résultat à reprendre

Les trois objectifs de la session sont atteints :

1. l'observation hors imprimante distingue la connexion Moonraker persistante,
   les transitions CFS rapportées et le vrai Z accepté `−0,04 mm` ;
2. une nouvelle lecture live strictement passive qualifie cette projection ;
3. l'auto-remplacement stock est désactivé une fois, prouvé à `0`, restauré une
   fois et prouvé à sa valeur exacte précédente `1`.

La gate finale est close avec
`CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED`. Le même observateur est resté
ouvert, aucune transition CFS n'a été rapportée, aucun filament n'a bougé, les
chauffes sont restées à zéro, le mesh `11 × 11`, le Z accepté et les trois
configurations sont inchangés.

Captures privées retenues :

- `20260828-194319-g4-k1-control-cfs-owner-observability-live-read-only-v2` ;
- `20260828-195248-g4-k1-control-cfs-owner-exclusion-guard-live-effect-v1`.

Le premier essai de la gate d'effet, session `20260828-195144...`, s'est arrêté
sur une erreur de syntaxe locale avant toute connexion ou commande. Il ne
constitue pas une preuve live.

## Fichiers canoniques

- `docs/48-observabilite-et-exclusion-proprietaire-cfs-v2.md` ;
- `packages/k1-control-v1/cfs-owner-observability-adapter-offline-v2/` ;
- `packages/k1-control-v1/cfs-owner-observability-live-read-only-v2/` ;
- `packages/k1-control-v1/cfs-owner-exclusion-guard-live-effect-v1/` ;
- `design/cfs-control-source-map-v1.json` ;
- `design/job-lifecycle-contract-v1.json`.

## Autorité et limites

Les captures sont consommées et leur répétition n'est pas autorisée. Aucun
propriétaire n'est installé, aucune commande filament n'est qualifiée et la
production reste fermée. Une reconnexion interne totalement silencieuse du
pilote CFS reste hors de ce qui peut être prouvé.

## Prochaine mission unique

Reprendre `G4-K1-CONTROL-START-SEQUENCE-OWNER-V1`. Concrètement, il faut rendre
le candidat hors imprimante réellement installable : ajouter le surveillant de
chauffe borné, vérifier les macros dans l'environnement K1 exact, figer la ligne
de purge, préparer sauvegardes et rollback, puis seulement décider d'une gate
physique séparée avec Thomas présent.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`, car la tranche combine
Klipper/Jinja, sécurité thermique et rollback. Option économique acceptable :
le même modèle en `medium`, avec davantage de risque de reprise lors de la revue
des chemins d'échec.
