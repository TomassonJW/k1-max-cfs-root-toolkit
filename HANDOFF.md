# HANDOFF — protocole minimal du propriétaire filament CFS à cartographier hors imprimante

Date de passation : 2026-08-26 21:58 +02:00
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`

## État à annoncer immédiatement à Thomas

- **Autonomie calibration quotidienne standard : atteinte.**
- **Autonomie de création et d'édition hors ligne d'un profil dérivé : atteinte.**
- **Autonomie du mode Précision réellement installé : non atteinte.**
- **Autonomie production : non atteinte.**
- `G4-K1-CONTROL-CFS-DYNAMIC-TEMP-ROUTING-V1` est close hors imprimante :
  architecture choisie, contrat exécutable et matrice `25/25` verte.
- Le choix est `minimal_separate_filament_owner`, mais il reste une conception :
  aucun protocole série appelable, aucun transport K1 et aucun candidat de pose.
- Le robuste `k1_p001_t055_r001_n06x06` et le Z accepté `−0,04 mm` restent la
  dernière base sûre connue. Ils n'ont pas été revérifiés sur la K1 pendant la
  mission close.
- `MESH-EDGE-DIAGNOSTIC-V1` reste suspendue ; le mode Précision reste caché.
- **Production fermée.** Le vert local ne vaut ni pose, ni essai physique, ni
  validation de débit, capteur, cutter ou coexistence avec le firmware stock.
- Autorisation de démarrage de la prochaine mission : **ATTENDRE_GO**. Une
  demande normale et non ambiguë de Thomas autorise seulement le travail hors
  imprimante décrit ci-dessous. Aucun ancien GO n'autorise une connexion K1.

## Mission close

### `G4-K1-CONTROL-CFS-DYNAMIC-TEMP-ROUTING-V1`

Les preuves privées exactes placent la résolution stock dans
`BoxAction.get_material_target_temp`, après lecture de la matière et avant la
première cible thermique observable du chargement. Dans l'incident, le chemin
stock a résolu `220 °C`, porté réellement la buse à `220 °C`, puis conservé un
paramètre de purge `190`. Le même chemin a aussi possédé de la géométrie.

Quatre voies ont été comparées :

1. la base matière statique reste un inventaire et un filet de sécurité ;
2. une réaffirmation après `T` reste une défense trop tardive ;
3. l'interception étroite de `get_material_target_temp` est refusée sans point
   d'extension stable et sans séparation de la géométrie ;
4. seul un propriétaire filament minimal séparé satisfait tout le contrat.

Le ticket thermique retenu arrive avant le premier effet filament. Il lie le
travail, la phase, l'opération, l'outil logique, une preuve de route CFS/slot
fraîche et consommable une fois, la cible de buse, la cible séparée du plateau
et les six invariants. Les températures de retrait, chargement et purge sont
distinctes. Refill et runout équivalents conservent la dernière cible explicite.
Une pause normale n'appelle aucun CFS.

Toute cible cachée, route absente ou périmée, commande thermique ou géométrique
du CFS, preuve de débit absente ou dérive Z/mesh coupe les deux cibles et bloque
la reprise. Le Z n'est jamais restauré à l'aveugle.

### Livrables canoniques

- `docs/31-routage-dynamique-temperatures-cfs-v1.md`
- `docs/adr/ADR-020-proprietaire-filament-minimal-et-ticket-thermique.md`
- `packages/k1-control-v1/cfs-dynamic-temp-routing-v1/contract.json`
- `packages/k1-control-v1/cfs-dynamic-temp-routing-v1/architecture-options.json`
- `packages/k1-control-v1/cfs-dynamic-temp-routing-v1/simulator.py`
- `packages/k1-control-v1/cfs-dynamic-temp-routing-v1/scenarios.json`
- `packages/k1-control-v1/cfs-dynamic-temp-routing-v1/RESULT.md`
- `packages/k1-control-v1/cfs-dynamic-temp-routing-v1/FUTURE-DEPLOYMENT-PLAN.md`
- `tests/test_cfs_dynamic_temp_routing_v1.py`

### Vérifications obtenues

- simulateur déterministe : **25/25** scénarios ;
- suite Python complète : **350 tests verts**, dont 3 ignorés déjà connus ;
- `git diff --check` et `git diff --cached --check` : **verts** ;
- transport réseau, SSH, série, G-code ou K1 dans le paquet : **absent** ;
- connexion K1 pendant la mission : **non exécutée**, par interdiction ;
- pose, restart, chauffe, homing, mouvement, commande CFS, purge et impression :
  **non exécutés** ;
- validation physique et production : **non exécutées**.

## État Git de la mission close

- checkout : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit` ;
- branche : `main` ;
- `HEAD` et `origin/main` observés au départ :
  `ecad754b78ead0370a37af3888364c5e627656a6` ;
- commit de mission : `1602867be97b2ac0bc58dee2a7aa9889c35f403d` ;
- autre worktree observé au départ : aucun ;
- branche ou worktree de mission séparé : aucun.

La session de passation doit commiter ce fichier, pousser `main`, vérifier
`HEAD == origin/main`, vérifier l'unique worktree et laisser le checkout propre.
À la reprise, relire l'état réel ; ne pas traiter ces SHA comme une preuve
éternelle.

## Prochaine mission unique

### `G4-K1-CONTROL-CFS-MINIMAL-OWNER-PROTOCOL-V1`

Cartographier hors imprimante le plus petit protocole nécessaire au propriétaire
filament retenu, uniquement depuis les preuves privées déjà capturées. Ne jamais
inventer une trame, un accusé, un état capteur ou une règle de coexistence.

### Travail à faire

1. Vérifier `main`, la propreté et les SHA local/distant.
2. Relire les contrats et résultats obligatoires ci-dessous.
3. Inventorier statiquement les messages déjà prouvés : adressage CFS, slot,
   avance, retrait, cutter, capteurs, états et accusés.
4. Distinguer clairement requête, réponse, événement, timeout et état inconnu.
5. Définir une liste minimale appelable ; toute trame incomplète ou ambiguë
   reste refusée.
6. Définir l'exclusion stricte entre propriétaire minimal et propriétaire
   stock : jamais deux propriétaires actifs sur la même frontière.
7. Modéliser doublon, réponse tardive, perte, reconnexion, changement de révision
   de route et deux CFS chaînés.
8. Construire un émulateur déterministe sans transport réel et des scénarios
   positifs/négatifs.
9. Fermer la mission OK seulement si chaque message appelable est relié à une
   preuve exacte ; sinon fermer KO borné en listant les preuves manquantes.

### Interdits

- aucune connexion K1, même en lecture seule ;
- ne jamais exécuter, importer ou charger le module MIPS/Cython ; l'analyse
  statique des octets déjà capturés est permise ;
- aucune commande série réelle, SSH, G-code, chauffe, homing, mouvement, cutter,
  avance, retrait, purge, restart ou impression ;
- aucune réécriture de `material_database.json` ;
- aucun remplacement ou appel global de `box_wrapper` ;
- aucun transport, déployeur, write-set distant ou paquet installable dans cette
  mission ;
- ne pas reprendre `MESH-EDGE-DIAGNOSTIC-V1` ;
- ne jamais publier ni nettoyer globalement `inventory/raw/`, qui reste privé ;
- aucun ancien GO ne devient une autorisation physique.

### Critères de fin

- sous-ensemble minimal versionné et traçable jusqu'aux preuves privées ;
- adresse CFS et slot explicites, sans `T0` physique supposé ;
- requêtes, réponses, événements et accusés séparés ;
- timeout, doublon, retard, reconnexion et état inconnu arrêtent sûrement ;
- exclusion du propriétaire stock modélisée et testée ;
- les deux CFS et les changements de route sont couverts ;
- aucune trame inconnue n'est appelable par défaut ;
- émulateur sans réseau, série, SSH, G-code ou K1 ;
- tests, diff, documentation et nouveau handoff verts ;
- aucune validation physique ou possibilité de déploiement revendiquée.

## Lecture obligatoire à la reprise

1. `AGENTS.md`, `HANDOFF.md`, `STATE.md`, `GATES.md`
2. `DECISIONS.md`, D-064 à D-070
3. `docs/25-contrat-cycle-impression-nettoyage-cfs-v1.md`
4. `design/job-lifecycle-contract-v1.json`
5. `docs/27-incident-cfs-temperature-geometrie-v1.md`
6. `docs/29-audit-box-wrapper-et-adaptateur-cfs-v1.md`
7. `docs/30-audit-routage-temperatures-cfs-v1.md`
8. `docs/31-routage-dynamique-temperatures-cfs-v1.md`
9. ADR-016 à ADR-020 sous `docs/adr/`
10. `packages/k1-control-v1/cfs-boundary-guard-v1/RESULT.md`
11. `packages/k1-control-v1/cfs-box-wrapper-audit-v1/RESULT.md`
12. `packages/k1-control-v1/cfs-dynamic-temp-routing-v1/README.md`
13. `packages/k1-control-v1/cfs-dynamic-temp-routing-v1/RESULT.md`
14. `packages/k1-control-v1/cfs-dynamic-temp-routing-v1/contract.json`

Les preuves privées utiles restent sous
`inventory/raw/20260826-cfs-box-wrapper-read-only-audit-v1/`. Les lire seulement
si elles existent localement ; ne pas les ajouter à Git.

## Autorisation et suites différées

État : **ATTENDRE_GO**. La politique Git globale couvre la clôture normale de la
future mission en préservant tout travail étranger. Elle ne couvre aucune action
sur la K1.

Après une cartographie protocolaire réellement verte seulement : préparer une
gate séparée de pose inactive, puis une gate physique bornée avec présence de
Thomas et plateau libre. La reprise du diagnostic de bord, le mode Précision et
la production restent des horizons distincts.

## Modèle conseillé

- optimal : `gpt-5.6-sol`, raisonnement `max` ;
- justification : preuves binaires partielles, protocole propriétaire, deux CFS
  et nombreux cas d'échec à distinguer sans inventer de comportement ;
- option économique : `gpt-5.6-sol`, raisonnement `high`, avec un risque plus
  élevé de manquer un accusé, une course de reconnexion ou une concurrence avec
  le propriétaire stock ;
- un modèle plus léger augmenterait le risque de faux vert et de reprise.
