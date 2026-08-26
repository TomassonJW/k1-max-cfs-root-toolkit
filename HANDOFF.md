# HANDOFF — routage dynamique des températures CFS à concevoir hors imprimante

Date de passation : 2026-08-26 21:14 +02:00
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`

## État à annoncer immédiatement à Thomas

- **Autonomie calibration quotidienne standard : atteinte.**
- **Autonomie de création et d'édition hors ligne d'un profil dérivé : atteinte.**
- **Autonomie du mode Précision réellement installé : non atteinte.**
- **Autonomie production : non atteinte.**
- Le robuste `k1_p001_t055_r001_n06x06` et le Z accepté `−0,04 mm` restent la
  base sûre connue.
- `MESH-EDGE-DIAGNOSTIC-V1` reste suspendue. Son rollback est validé par
  `VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK` : profil diagnostic et quatre G-code
  absents, robuste actif, cibles zéro et axes libérés lors de cette capture.
- L'audit CFS en lecture seule est clos. La route ponctuelle
  `CFS1 / slot A / Geeetech PLA noir` et le débit ont été prouvés par une purge,
  mais la séquence brute est refusée : `220 °C` imposés, homing X/Y caché et
  purge tentée avec le plateau trop haut.
- Aucun dommage visible n'a été constaté par Thomas. Le homing a été repris et
  la position froide `X=185,5 / Y=305 / Z=30 mm` a été validée visuellement.
- `CFS-BOUNDARY-GUARD-V1` et l'audit exact de `box_wrapper` sont clos hors
  imprimante. Aucune primitive stock n'est qualifiée pour un adaptateur.
- Une fiche matière CFS ne porte qu'un palier de buse : elle ne résout pas
  première couche, régime normal, plateau et géométrie comme un contrat unique.
- Autorisation de démarrage : **ATTENDRE_GO** pour la prochaine mission. Une
  demande normale et non ambiguë suffit pour le travail hors imprimante.
  Aucun `GO` exact hérité n'autorise une action K1.
- Avant toute future action physique, confirmer la présence de Thomas et le
  plateau réellement libre.

## Mission close

Le type matière du slot est résolu dans
`creality/userdata/box/material_database.json`. Sa valeur
`nozzle_temperature` devient la cible réelle du chargement, ici `220 °C`. Le
même chemin possède aussi des mouvements et le homing X/Y.

Écrire une autre température dans la matière peut corriger un seul palier de
buse. Ce n'est pas une solution complète : une impression doit distinguer buse
et plateau de première couche et de régime normal, puis conserver la bonne
cible pendant changement, refill, runout et reprise.

La décision retenue est de router les températures par phase du travail. La
base matière reste un filet de sécurité statique, pas une base globale réécrite
avant chaque impression. Une réaffirmation `M104` après `T` reste une défense,
pas une preuve qu'une purge précédente était correcte.

### Fichiers canoniques

- `docs/25-contrat-cycle-impression-nettoyage-cfs-v1.md`
- `design/job-lifecycle-contract-v1.json`
- `docs/27-incident-cfs-temperature-geometrie-v1.md`
- `docs/29-audit-box-wrapper-et-adaptateur-cfs-v1.md`
- `docs/30-audit-routage-temperatures-cfs-v1.md`
- ADR-016 à ADR-019 sous `docs/adr/`
- `DECISIONS.md`, D-064 à D-069

### Hors périmètre confirmé

- aucune connexion, lecture ou écriture K1 pendant la recherche finale ;
- aucune chauffe, homing, mouvement, commande CFS, purge ou impression ;
- aucune modification OrcaSlicer, Mainsail, Moonraker, nginx ou firmware ;
- aucun paquet installable et aucune production autorisée ;
- aucune nouvelle tâche Codex créée par cette passation.

## État Git à la préparation

- checkout : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit` ;
- branche : `main` ;
- `HEAD` de départ : `92a63bbbc959a3d722f41387f5e98c7fc0c89510` ;
- `origin/main` observé au départ : même SHA ;
- autre worktree : aucun ; branche/worktree de mission séparé : aucun.

La session de passation doit livrer son commit sur `main`, vérifier
`HEAD == origin/main` et laisser le checkout propre. À la reprise, relire le SHA
final avec `git rev-parse HEAD`.

## Vérifications obtenues

- audit local du binaire exact et de la trace : **OK** ;
- documentation officielle Creality et profil officiel : **OK** ;
- recoupements communautaires utilisés comme indices, pas comme preuve K1 :
  **OK** ;
- action K1 pendant cette mission : **non exécutée**, par interdiction ;
- validation physique du futur routage : **non exécutée**, aucun candidat ;
- validation production : **non exécutée**, production fermée.

## Prochaine mission unique

### `G4-K1-CONTROL-CFS-DYNAMIC-TEMP-ROUTING-V1`

Concevoir et tester hors imprimante le contrat qui donne au CFS la température
de buse exacte de la phase courante, tout en gardant plateau et géométrie sous
des propriétaires séparés et surveillés.

Le contrat doit exposer au minimum `NOZZLE_FIRST`, `NOZZLE_NORMAL`,
`BED_FIRST`, `BED_NORMAL`, les températures de retrait/chargement/purge, la
phase courante et la route CFS/slot fraîchement résolue.

### Travail à faire

1. Relire les documents obligatoires et vérifier `main`.
2. Cartographier le point où `get_material_target_temp` fournit la cible, sans
   lancer le binaire ni contacter la K1.
3. Comparer base matière statique, réaffirmation post-`T`, interception étroite
   de la résolution thermique et propriétaire série minimal.
4. Choisir la plus petite surface capable de fixer la cible **avant** tout
   chargement ou purge.
5. Étendre le contrat du travail et construire un simulateur déterministe.
6. Tester outil déjà engagé, chargement, changement, deux CFS, refill, runout,
   pause/reprise, annulation et coupure thermique.
7. Produire un paquet de conception et un plan futur de pose/backup/rollback ;
   ne pas exécuter ce plan.

### Interdits

- aucune connexion K1, même en lecture seule, dans cette première mission ;
- aucune réécriture dynamique de `material_database.json` sur la K1 ;
- aucun appel aux primitives stock refusées ou non qualifiées ;
- ne pas considérer un `M104` tardif comme réussite de la purge ;
- ne pas confier plateau, homing, X/Y, mesh ou Z au CFS ;
- ne pas reprendre `MESH-EDGE-DIAGNOSTIC-V1` ;
- aucun candidat de pose tant que les tests hors ligne ne ferment pas les
  chemins ;
- aucun ancien GO ne devient une autorisation physique.

### Critères de fin

- aucune température matière codée en dur dans le chemin du travail ;
- première couche et régime normal distincts pour buse et plateau ;
- chaque frontière reçoit une cible explicite avant son premier effet ;
- la base matière est un filet de sécurité, pas le propriétaire dynamique ;
- absence, incohérence ou route inconnue provoque un arrêt sûr ;
- deux CFS, refill, runout et pause/reprise sont testés ;
- les six invariants d'ADR-017 restent inchangés ;
- aucun transport K1 n'existe dans le paquet hors ligne ;
- tests, diff et documentation sont verts ;
- le résultat n'est pas présenté comme physiquement validé.

### Autorisation et Git

État : **ATTENDRE_GO**. Une future demande normale de Thomas autorise seulement
l'analyse et l'implémentation hors imprimante. La politique Git globale couvre
la clôture sur `main` en préservant tout travail étranger.

Toute connexion K1, pose, restart, chauffe, homing, mouvement, commande CFS ou
purge appartient à une mission ultérieure avec autorisation fraîche après revue
des fichiers, commandes, backup, rollback et critères OK/KO.

## Lecture obligatoire à la reprise

1. `AGENTS.md`, `HANDOFF.md`, `STATE.md`, `GATES.md`
2. `DECISIONS.md`, D-064 à D-069
3. `docs/25-contrat-cycle-impression-nettoyage-cfs-v1.md`
4. `design/job-lifecycle-contract-v1.json`
5. `docs/27-incident-cfs-temperature-geometrie-v1.md`
6. `docs/29-audit-box-wrapper-et-adaptateur-cfs-v1.md`
7. `docs/30-audit-routage-temperatures-cfs-v1.md`
8. ADR-016, ADR-017, ADR-018 et ADR-019
9. `packages/k1-control-v1/cfs-boundary-guard-v1/RESULT.md`
10. `packages/k1-control-v1/cfs-box-wrapper-audit-v1/RESULT.md`

Les captures `inventory/raw/` sont privées et ignorées. Ne jamais les nettoyer
globalement ni les publier.

## Suites différées

Après fermeture hors ligne de la mission seulement : revue d'un candidat de
pose, gate physique thermique/géométrique, reprise éventuelle de
`MESH-EDGE-DIAGNOSTIC-V1`, puis qualification du mode Précision. La production
reste séparée.

## Modèle conseillé

- optimal : `gpt-5.6-sol`, raisonnement `max` ;
- justification : firmware compilé, thermique caché, deux CFS et nombreux
  chemins de reprise à fermer avant toute pose ;
- option économique : `gpt-5.6-sol`, raisonnement `high`, avec plus de risque
  d'omettre un chemin refill/pause ou une interaction thermique/géométrique ;
- un modèle plus léger n'est pas conseillé pour cette décision d'architecture.
