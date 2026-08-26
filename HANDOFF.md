# HANDOFF — audit CFS avant reprise de MESH-EDGE-DIAGNOSTIC-V1

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
- MESH-EDGE-DIAGNOSTIC-V1 est en cours mais suspendue après un passage source
  sans dépôt de filament. Ce passage ne qualifie ni la buse ni le mesh.
- La capture `20260826-090956-mesh-edge-diagnostic-v1` a obtenu le rollback et
  `VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK` : profil diagnostic et quatre G-code
  absents, base exacte, robuste actif, cibles zéro, axes libérés, runtime Z sûr
  et deux CFS connectés.
- Aucun nouveau motif n’est autorisé sans reprise explicite, route CFS/slot
  fraîchement résolue et purge réellement visible.
- Aucun `GO` exact ni identifiant de gate recopié n’est requis ; une demande
  normale de Thomas suffit, conformément à D-054.
- La présence de Thomas et le plateau réellement libre restent des faits à
  confirmer juste avant toute action physique.
- Le contrat complet de nettoyage, impression, filament, changement et fin est
  figé hors imprimante. Il n’est pas implémenté et n’ouvre pas la production.

## Clôture vérifiée de la mission

- Mission livrée : contrat du cycle filament figé, passage source sans débit
  classé invalide, rollback exact exécuté et état final K1 validé.
- Commits de mission intégrés dans `main` : `1dde204` et `05bf3a0`.
- Capture privée de preuve :
  `inventory/raw/20260826-090956-mesh-edge-diagnostic-v1`.
- Artefacts de génération privés : `.codex-work/mesh-edge-diagnostic-v1` ; ils
  restent ignorés et ne sont pas publiés sur GitHub.
- Gate humaine : aucune validation de mesh ni de buse ; aucun passage imprimé
  exploitable.
- Prochaine autorisation : `ATTENDRE_GO` dans la future session.

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

## 7. Prochaine mission unique : audit CFS en lecture seule pour MESH-EDGE-DIAGNOSTIC-V1

Autorisation de démarrage : **ATTENDRE_GO**.

### Incident du premier passage

La préparation et le motif source ont été exécutés, mais aucun filament n'a été
déposé. Le motif minimal avait retiré `Tn/START_PRINT` sans remplacer la
résolution d'outil, le chargement ou la purge CFS. La mention `T0` du protocole
était une invention de Codex, pas un fait fourni par Thomas.

Le passage n'est pas une preuve de buse bouchée : les commandes d'extrusion ont
été envoyées sans preuve que du filament atteignait l'extrudeur ou la buse. La
gate physique est suspendue.

Le rollback de la tentative est désormais clos. La capture
`20260826-090956-mesh-edge-diagnostic-v1` a obtenu
`ROLLBACK_MESH_EDGE_DIAGNOSTIC_V1_OK` puis
`VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK`, sans nouveau motif.

### Objectif

Établir sans mouvement ni chauffe ce que la K1 exacte sait réellement sur :

- le mapping outil logique, CFS et slot physique ;
- les deux objets `filament_switch_sensor` et leur état utile ;
- l'état persistant du dernier filament ;
- les limites entre présence capteur, identité, route jusqu'à l'extrudeur et
  débit réel à la buse ;
- la manière sûre d'obtenir ensuite une petite purge visible avant un motif.

La sortie est un contrat de préflight et des preuves en lecture seule. Elle
n'autorise pas encore une impression ni le mode Précision.

### Contraintes

- lecture seule sur la K1 et les deux CFS ;
- aucun chauffage, homing, mouvement, chargement, retrait, coupe, purge ou
  impression ;
- aucun `T0` ou autre outil physique supposé ;
- ne jamais transformer un capteur de présence en preuve d'identité ou de
  débit ;
- préserver la base sûre validée par la capture de rollback ;
- aucune exposition UI du mode Précision.

### Ordre recommandé

1. Lire les documents d’autorité et vérifier Git.
2. Lire `RESULT.md` et ne pas répéter le rollback déjà clos.
3. Obtenir un préflight K1 frais strictement en lecture seule.
4. Inventorier les objets Moonraker/Klipper/CFS disponibles, leurs valeurs et
   leurs transitions déjà présentes dans les journaux, sans les provoquer.
5. Distinguer faits exacts, hypothèses et informations encore humaines.
6. Produire le contrat de préflight filament et les scénarios hors imprimante.
7. Mettre à jour le paquet et ses tests sans lancer de motif.

### Critères OK

- chaque objet et valeur observés sont sourcés par la K1 exacte ;
- les deux capteurs sont nommés sans inventer leur rôle physique ;
- le mapping outil/CFS/slot a un niveau de confiance explicite ;
- les états `engaged_known`, `engaged_unknown`, `absent_confirmed` et `fault`
  ont des règles de décision testables ;
- la purge visible reste une preuve séparée ;
- la K1 est relue inchangée et sûre en fin d'audit ;
- aucun paquet physique n'est posé.

### Arrêt obligatoire

Ne pas lancer le motif de bord, charger ou purger un filament, installer un
profil dérivé, lancer une campagne complète ou exposer le mode Précision dans
la même mission.

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

Après l'audit CFS en lecture seule seulement :

1. reprise physique bornée de MESH-EDGE-DIAGNOSTIC-V1 sous un nouveau GO ;
2. MESH-DERIVED-PROFILE-V1 ;
3. MESH-TUNING-CAMPAIGN-V1 ;
4. exposition éventuelle du mode Précision après deux feuilles complètes
   consécutives sans défaut grave et avec rollback prouvé.

La production reste séparée. Son contrat fonctionnel est désormais figé, mais
les implémentations restent absentes : audit V2, simulation du cycle, mouvement
de nettoyage à froid, référence, propriété des températures CFS, changement et
runout, pause/reprise, fin avec conservation engagée, bascule Orca atomique et
G5.

## 11. Modèle conseillé

Pour l'audit CFS en lecture seule :

- choix optimal : gpt-5.6-sol, raisonnement high ;
- justification : croisement de l'état Moonraker/Klipper, des deux CFS, des
  journaux et du contrat filament sans provoquer de transition physique ;
- option économique acceptable : gpt-5.6-terra, raisonnement high, avec plus de
  risque de reprise sur la distinction capteur, identité, route et débit ;
- un modèle léger augmenterait le risque de transformer une présence logique
  en certitude physique.

Thomas n'a pas besoin d'être devant la K1 pour cet audit strictement en lecture
seule. Sa confirmation redevient obligatoire avant une future purge ou
impression.
