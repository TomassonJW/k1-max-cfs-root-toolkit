# HANDOFF — reprise autonome MESH-EDGE-DIAGNOSTIC-V1 suspendue

Date de passation : 2026-08-26 (Europe/Paris)
Projet : C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit
Branche de reprise : `codex/mesh-edge-diagnostic-v1`

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
- Au dernier état observé, le robuste est actif, les cibles sont à zéro et les
  axes sont libérés ; le profil diagnostic temporaire et les quatre G-code
  restent toutefois à retirer par rollback exact. Cet état peut être périmé.
- La prochaine action physique unique est ce rollback puis la validation finale,
  sans nouveau motif.
- Aucun `GO` exact ni identifiant de gate recopié n’est requis ; une demande
  normale de Thomas suffit, conformément à D-054.
- La présence de Thomas et le plateau réellement libre restent des faits à
  confirmer juste avant toute action physique.
- Le contrat complet de nettoyage, impression, filament, changement et fin est
  figé hors imprimante. Il n’est pas implémenté et n’ouvre pas la production.

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

- 21 tests ciblés Python verts ;
- 5 tests JavaScript verts ;
- 294 tests Python du dépôt verts, 3 ignorés connus ;
- sources Python compatibles avec la grammaire 3.8 ;
- parse des scripts PowerShell vert ;
- git diff --check vert ;
- recette dans le vrai navigateur intégré :
  - 121 cellules présentes ;
  - orientation arrière Y 295 en haut et avant Y 5 en bas ;
  - moyenne 0,000000000000 mm ;
  - correction centrale à 0,005 mm ;
  - undo et redo conformes ;
  - grille et aperçu 3D mutuellement exclusifs ;
  - erreur simulée sans mutation ;
  - aucun journal navigateur en erreur ou avertissement.

Le serveur local de recette a été arrêté. Aucun processus de démonstration ne
doit rester ouvert.

## 6. État physique connu et inconnu

Dernier état pleinement validé avant la comparaison V2 :

- standby ;
- cibles à zéro ;
- axes non référencés ;
- Z persistant −0,04 mm, stockage ok ;
- profils robuste et composite présents ;
- robuste rechargé ;
- deux CFS connectés.

Pendant V2, le composite était actif et Thomas a utilisé un Z temporaire
−0,24 mm. Cette valeur n’a pas été persistée et ne doit jamais l’être
automatiquement.

Après V2, aucun préflight frais n’a été exécuté. Ne pas affirmer sans preuve :

- l’état courant de Klipper ;
- les cibles ;
- le homing ;
- le profil actif ;
- la présence des deux CFS ;
- la plaque, sa propreté ou la liberté du plateau ;
- le retrait des G-code V2.

## 7. Prochaine mission unique : MESH-EDGE-DIAGNOSTIC-V1

### Incident du premier passage

La préparation et le motif source ont été exécutés, mais aucun filament n'a été
déposé. Le motif minimal avait retiré `Tn/START_PRINT` sans remplacer la
résolution d'outil, le chargement ou la purge CFS. La mention `T0` du protocole
était une invention de Codex, pas un fait fourni par Thomas.

Le passage n'est pas une preuve de buse bouchée : les commandes d'extrusion ont
été envoyées sans preuve que du filament atteignait l'extrudeur ou la buse. La
gate physique est suspendue.

### Objectif

Prouver physiquement, avec un motif borné et peu consommateur :

- le sens réel d’une correction locale unique de 0,010 mm ;
- la répétabilité du défaut aux bords ;
- l’influence éventuelle du tube PTFE ou du faisceau ;
- l’absence de dégradation du centre.

Cette gate prépare la future pose sûre d’un profil dérivé. Elle ne rend pas
encore autonome le mode Précision.

### Contraintes

- motif limité à X/Y 5..295 mm avec cadre, cellules et repères ;
- même plaque, filament réellement résolu, températures, tube PTFE et Z effectif
  entre variantes ;
- aucun `T0` ou autre outil physique supposé ;
- route CFS/slot confirmée et purge réellement visible avant chaque motif ;
- une seule petite région corrigée de 0,010 mm ;
- aucun réglage global Z en direct pour masquer un défaut ;
- aucune répétition longue automatique ;
- retour immédiat au robuste et retrait du G-code en cas de KO ;
- aucune exposition UI du mode Précision.

### Ordre recommandé

1. Lire les documents d’autorité et vérifier Git.
2. Retrouver la capture privée exacte de la tentative et son backup.
3. Exécuter exclusivement `Rollback`, puis `FinalValidate` ; ne pas relancer de
   motif dans la même reprise.
4. Vérifier réellement profil diagnostic absent, quatre G-code absents, robuste
   actif, cibles zéro et axes libérés.
5. Repasser ensuite le protocole corrigé et ses tests hors imprimante.
6. Obtenir un nouveau préflight K1 frais.
7. Demander à Thomas les faits non observables : présence, plateau libre,
   plaque, route filament et purge réellement visible.
8. Exécuter une seule comparaison bornée et arrêter au premier KO.
9. Recharger le robuste, couper les cibles, retirer les G-code et valider l’état
   final avant toute conclusion.

### Critères OK

- Z absolu et profil actif prouvés avant extrusion ;
- outil physique non supposé, route CFS/slot prouvée et purge visible ;
- motif identique hors unique correction locale ;
- sens Rapprocher/Éloigner confirmé ;
- défaut de bord répétable ou causalité PTFE clairement classée ;
- centre non dégradé ;
- retour au robuste et état final sûr prouvés ;
- verdict humain consigné sans inventer une analyse plus fine que les faits.

### Arrêt obligatoire

Ne pas enchaîner automatiquement MESH-DERIVED-PROFILE-V1. Ne pas installer un
profil dérivé, ne pas lancer une campagne complète et ne pas exposer le mode
Précision dans la même mission.

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
12. packages/k1-control-v1/mesh-edge-diagnostic-v1/PROTOCOL.md
13. packages/k1-control-v1/composite-first-layer-comparison-v2/RESULT.md
14. packages/k1-control-v1/mesh-editor-offline-v1/README.md

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

Après MESH-EDGE-DIAGNOSTIC-V1 seulement :

1. MESH-DERIVED-PROFILE-V1 ;
2. MESH-TUNING-CAMPAIGN-V1 ;
3. exposition éventuelle du mode Précision après deux feuilles complètes
   consécutives sans défaut grave et avec rollback prouvé.

La production reste séparée. Son contrat fonctionnel est désormais figé, mais
les implémentations restent absentes : audit V2, simulation du cycle, mouvement
de nettoyage à froid, référence, propriété des températures CFS, changement et
runout, pause/reprise, fin avec conservation engagée, bascule Orca atomique et
G5.

## 11. Modèle conseillé

Pour MESH-EDGE-DIAGNOSTIC-V1 :

- choix optimal : gpt-5.6-sol, raisonnement high ;
- justification : preuve physique sur matériel de production, état distant
  potentiellement périmé, rollback exact prioritaire, protocole comparatif,
  état filament et preuve de débit désormais obligatoires ;
- option économique acceptable : gpt-5.6-terra, raisonnement high, avec plus de
  risque de reprise sur le croisement G-code, état machine et preuve humaine ;
- un modèle léger augmenterait le risque de confondre défaut de protocole,
  effet Z et correction locale.

La confirmation factuelle de Thomas reste une gate humaine avant l’action
physique, quel que soit le modèle.
