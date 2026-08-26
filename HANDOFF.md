# HANDOFF — incident CFS audité ; réseau K1 stabilisé

Date de passation : 2026-08-26 (Europe/Paris)
Projet : C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit
Branche de reprise : `main`

## État à annoncer immédiatement à Thomas

- **Autonomie calibration quotidienne standard : atteinte.**
- **Autonomie de création et d’édition hors ligne d’un profil dérivé :
  atteinte.**
- **Autonomie du mode Précision réellement installé : non atteinte.**
- **Autonomie production : non atteinte.**
- Le robuste k1_p001_t055_r001_n06x06 et le Z persistant accepté −0,04 mm
  restent la base sûre.
- Le composite physique k1_p001_t055_r001_n11x11 reste une source immuable.
- L’éditeur local v001 est validé et le mode Précision reste caché.
- MESH-EDGE-DIAGNOSTIC-V1 reste suspendue. Le débit a ensuite été prouvé sur une
  purge séparée, mais la séquence utilisée est refusée pour température et
  géométrie.
- La capture `20260826-090956-mesh-edge-diagnostic-v1` a obtenu le rollback et
  `VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK` : profil diagnostic et quatre G-code
  absents, base exacte, robuste actif, cibles zéro, axes libérés, runtime Z sûr
  et deux CFS connectés.
- L'audit CFS strictement en lecture seule est clos OK sous la capture privée
  `20260826-final-cfs-read-only-audit-v1`.
- Thomas a explicitement choisi `CFS1 / slot A`, Geeetech PLA noir. La purge a
  prouvé cette route et le débit pour ce passage seulement.
- La séquence a imposé `220 °C` malgré la demande `190 °C`, référencé X/Y et
  tenté de purger avec le plateau trop haut. Aucun dommage visible selon Thomas.
- Le homing a ensuite été repris proprement. La position froide
  `X=185,5 / Y=305 / Z=30 mm` a été validée visuellement comme position de purge
  avec une marge suffisante.
- Le lien `k1max-root` est requalifié sur la réservation fixe : `standby`,
  cibles zéro, robuste et Z `−0,04 mm` conformes ; l'adresse reste hors Git.
- `CFS-BOUNDARY-GUARD-V1` est validé hors imprimante. Il protège buse, plateau,
  Z accepté, origine Z, mesh et axes référencés, et refuse la trace réelle.
- Statut technique actuel : **ATTENDRE_GO_PAQUET_REVU** avant toute nouvelle
  action physique ou pose sur la K1. Ce marqueur interne n'impose aucune phrase
  littérale à Thomas ; une demande normale et non ambiguë suffit selon D-054.
- Aucun nouveau motif n’est autorisé avec les commandes brutes du 26 août.
- Aucun `GO` exact ni identifiant de gate recopié n’est requis ; une demande
  normale de Thomas suffit, conformément à D-054.
- La présence de Thomas et le plateau réellement libre restent des faits à
  confirmer juste avant toute action physique.
- Le contrat complet de nettoyage, impression, filament, changement et fin est
  figé hors imprimante. Il n’est pas implémenté et n’ouvre pas la production.

## Clôture vérifiée de la mission précédente

- Mission livrée : audit CFS exact en lecture seule, contrat de préflight,
  analyseur déterministe et verdict `engaged_unknown`.
- Capture privée de preuve :
  `inventory/raw/20260826-final-cfs-read-only-audit-v1`.
- Les captures privées restent ignorées et ne sont pas publiées sur GitHub ;
  aucun nouvel artefact de génération n'est requis pour cet audit.
- Gate humaine : aucune validation de mesh, de buse ou de débit ; aucun passage
  imprimé exploitable.
- Prochaine autorisation : `ATTENDRE_GO_PHYSIQUE` avant toute action K1.

## Mission courante close hors imprimante

- Incident documenté dans `docs/27-incident-cfs-temperature-geometrie-v1.md`.
- Décision d'architecture figée dans ADR-017 et D-066.
- Contrat machine étendu aux six invariants CFS.
- Paquet local `packages/k1-control-v1/cfs-boundary-guard-v1/` avec fixture
  réelle, fixture synthétique et évaluation déterministe.
- 324 tests Python verts, 3 ignorés historiques.
- Aucune écriture K1, chauffe, mouvement, purge ou impression pendant cette
  préparation hors imprimante.
- Le routage réseau local est corrigé et vérifié. Mainsail, Moonraker, nginx,
  les deux lanceurs et `navi.json` ne contiennent aucune adresse K1 en dur ;
  aucune écriture distante ni aucun restart n'a été nécessaire.
- Prochaine étape : récupérer en lecture seule le journal complet et le binaire
  exact `box_wrapper`, puis préparer un adaptateur étroit. Toute pose ou tout
  essai physique reste séparé.

## 1. Résultat de la mission close précédente

MESH-EDITOR-OFFLINE-V1 est close OK. Elle est restée entièrement hors
imprimante :

- aucun SSH, tunnel, Moonraker ou appel Creality ;
- aucun chauffage, homing, mouvement, palpage ou G-code ;
- aucune écriture de printer.cfg ou du Z ;
- aucune pose et aucune exposition du mode Précision.

Le paquet est dans :

packages/k1-control-v1/mesh-editor-offline-v1/

Le rapport canonique est :

docs/24-mesh-editor-offline-v1.md

## 2. Pouvoirs désormais disponibles hors ligne

L’interface locale permet de :

- créer k1_p001_t055_r001_n11x11_tuned_v001 à partir de la source physique ;
- sélectionner un point, une ligne, une colonne ou une zone de 3 × 3 maximum ;
- appliquer Rapprocher, delta négatif, ou Éloigner, delta positif ;
- utiliser un pas de 0,005 mm ou 0,010 mm ;
- consulter Source, Deltas, Final et un aperçu 3D ;
- annuler, rétablir, comparer et restaurer la source ;
- simuler chargement, refus de validation et restauration ;
- exporter un document JSON versionné ou un bloc Klipper déterministe.

La source, la correction demandée, la correction normalisée et la matrice
finale restent distinctes. Le Z global est absent du modèle.

## 3. Définition mathématique retenue

Le moteur reproduit la surface bicubique cardinale 31 × 31 du profil Klipper
11 × 11, avec mesh_x_pps=2, mesh_y_pps=2 et tension 0,2.

Il retire à toute correction demandée la moyenne arithmétique des 961 valeurs
interpolées. La forme locale est conservée et la moyenne utilisée par le fade
Klipper reste nulle. La tolérance interne est 0,000000000001 mm. Après export
Klipper à six décimales, la tolérance est 0,000001 mm.

Gardes :

- avertissement si la correction normalisée dépasse 0,050 mm en valeur absolue ;
- refus au-delà de 0,100 mm ;
- refus si deux voisins diffèrent de plus de 0,080 mm ;
- un refus ne modifie ni l’état ni l’historique ;
- aucun lissage ou réglage automatique n’est permis.

## 4. Source publique et preuves privées

La fixture publique nettoyée contient les 121 valeurs persistées du bloc
composite, dans l’ordre Y 5 vers Y 295 et X 5 vers X 295.

Empreinte canonique de la matrice publique à six décimales :

bee530fb9738773d1f2ccb63d47743e15776690f1bcdf92a3daac7661f0f50bf

Empreintes privées vérifiées avant l’extraction :

| Artefact | SHA-256 |
|---|---|
| printer.cfg.composite | f88d6b52477592805384fca2b4d7abd00298deecd82227af2fa580085fe26fa2 |
| composite-mesh-state.json | 09fe8333dd1708dc781091e367efef7220d8056d40dab7ffefee26e55de9d8eb |
| final-printer-status.json | 24490c6efc9f2d315a6772f62af20864d5ed8e492f92cb36076213cf7abbc9e |

Les preuves privées restent ignorées. Ne jamais nettoyer globalement
inventory/raw/ ou .codex-work/.

## 5. Validation obtenue

- 311 tests Python du dépôt verts, 3 ignorés connus ;
- parse des scripts PowerShell vert ;
- `git diff --check` vert ;
- `WAIT_COMPLETE_MESH_EDGE_DIAGNOSTIC_V1_OK` avant restauration ;
- `ROLLBACK_MESH_EDGE_DIAGNOSTIC_V1_OK` ;
- `VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK` ;
- contrat humain et contrat JSON cohérents ;
- branche de mission poussée puis intégrée par fast-forward dans `main`.

Le serveur local de recette a été arrêté. Aucun processus de démonstration ne
doit rester ouvert.

## 6. État physique connu et inconnu

État validé après le rollback de la capture
`20260826-090956-mesh-edge-diagnostic-v1` :

- standby ;
- cibles à zéro ;
- axes non référencés ;
- Z persistant −0,04 mm, stockage ok ;
- profils robuste et composite présents ;
- robuste rechargé ;
- profil diagnostic absent ;
- quatre G-code temporaires absents ;
- base `printer.cfg` exacte ;
- deux CFS connectés.

Cet état est une capture ponctuelle, pas une promesse permanente. Restent
inconnus sans Thomas ou nouvelle observation : filament physiquement engagé,
identité réelle de la bobine, route jusqu'à la buse, débit, plaque présente,
propreté et liberté du plateau.

## 7. Audit CFS clos et prochaine gate physique

L'audit `CFS-READ-ONLY-AUDIT-V1` est clos OK. Son rapport public est
`docs/26-audit-cfs-lecture-seule-v1.md` et son résultat opérationnel est dans
`packages/k1-control-v1/cfs-read-only-audit-v1/RESULT.md`.

### Verdict exact

- `filament_sensor` est activé et détecte une présence ;
- `filament_sensor_2` est désactivé et ne détecte rien ;
- leur association logicielle et leurs broches sont connues, mais pas leur
  emplacement physique exact ;
- les CFS `T1` et `T2` sont connectés ;
- `box.t_command` est vide et les données persistantes courantes ne contiennent
  aucune route `tnn_map`, `last_cmd` ou `last_tnn` exploitable ;
- l'historique prouve que le mapping outil logique vers slot physique est
  dynamique ;
- aucune purge visible n'a eu lieu pendant cet audit.

Le classement sûr est `engaged_unknown`. La présence est prouvée, mais
l'identité, la route courante et le débit ne le sont pas.

### Prochaine action interdite sans nouveau GO

Ne pas chauffer, référencer, déplacer, charger, couper, retirer, purger ou
imprimer. Ne pas supposer `T0` ni un autre outil. La future gate physique doit
d'abord obtenir de Thomas le matériau et le slot réellement choisis, résoudre
la route fraîche sur la K1, puis exiger une petite purge visible avant tout
motif.

Autorisation de démarrage : **ATTENDRE_GO_PHYSIQUE**.

## 8. Lecture obligatoire à la reprise

1. AGENTS.md
2. HANDOFF.md
3. STATE.md
4. GATES.md
5. DECISIONS.md
6. docs/24-mesh-editor-offline-v1.md
7. docs/adr/ADR-015-profils-mesh-derives-et-corrections-locales.md
8. docs/23-audit-mesh-manuel-et-cycle-production-cfs.md
9. docs/25-contrat-cycle-impression-nettoyage-cfs-v1.md
10. docs/adr/ADR-016-cycle-production-orchestre-et-propriete-cfs.md
11. design/job-lifecycle-contract-v1.json
12. packages/k1-control-v1/mesh-edge-diagnostic-v1/RESULT.md
13. packages/k1-control-v1/mesh-edge-diagnostic-v1/PROTOCOL.md
14. packages/k1-control-v1/composite-first-layer-comparison-v2/RESULT.md
15. packages/k1-control-v1/mesh-editor-offline-v1/README.md
16. docs/26-audit-cfs-lecture-seule-v1.md
17. packages/k1-control-v1/cfs-read-only-audit-v1/RESULT.md
18. docs/27-incident-cfs-temperature-geometrie-v1.md
19. docs/adr/ADR-017-frontiere-cfs-buse-plateau-z.md
20. packages/k1-control-v1/cfs-boundary-guard-v1/RESULT.md

Relire aussi les sources et tests du paquet hors ligne avant de réutiliser son
contrat ou ses signes.

## 9. Autorité et sécurité

D-054 reste l’autorité : une mission clairement demandée couvre ses actions
normales sans réclamer une phrase GO littérale. Une restriction plus récente
prime toujours.

Une mission physique autorisée ne transforme pas un fait non observable en
certitude. La liberté du plateau, la présence de Thomas et la plaque réelle
doivent encore être confirmées au moment utile.

L’autorisation Git globale couvre la branche, le commit, le push, la PR,
l’intégration dans main et le nettoyage. Préserver les changements étrangers,
les worktrees étrangers et les preuves ignorées.

## 10. Roadmap non autorisée par cette passation

Après l'incident CFS désormais audité :

1. récupération en lecture seule du journal complet et du binaire exact
   `box_wrapper` ;
2. qualification hors imprimante des primitives et préparation d'un adaptateur
   étroit ou d'un propriétaire minimal ;
3. revue complète du paquet avant toute pose ou reprise physique ;
4. reprise bornée de MESH-EDGE-DIAGNOSTIC-V1 seulement avec les six invariants ;
5. MESH-DERIVED-PROFILE-V1 puis MESH-TUNING-CAMPAIGN-V1 ;
6. exposition éventuelle du mode Précision après deux feuilles complètes
   consécutives sans défaut grave et avec rollback prouvé.

La production reste séparée. Son contrat fonctionnel est désormais figé, mais
les implémentations restent absentes : audit V2, simulation du cycle, mouvement
de nettoyage à froid, référence, propriété des températures CFS, changement et
runout, pause/reprise, fin avec conservation engagée, bascule Orca atomique et
G5.

## 11. Modèle conseillé

La prochaine étape est d'abord une analyse en lecture seule du binaire compilé
et du journal exact ; elle ne demande aucune manipulation humaine de la K1.

Pour cette analyse puis la préparation de l'adaptateur :

- choix optimal : gpt-5.6-sol, raisonnement high ;
- justification : rétro-analyse bornée d'un module Cython/MIPS, attribution des
  écritures thermiques et géométriques, puis design de rollback sûr ;
- option économique acceptable : gpt-5.6-terra, raisonnement high, avec plus de
  risque de reprise sur les chemins cachés et les preuves négatives ;
- un modèle plus léger augmente le risque de conclure trop tôt qu'un paramètre
  `TEMP` visible couvre aussi le plateau, le homing et le Z.
