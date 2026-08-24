# HANDOFF — reprise autonome `MESH-EDITOR-OFFLINE-V1`

Date de passation : 2026-08-24 (Europe/Paris)
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Tâche source Codex : `01a02ea1-9539-70e1-856e-d52846e91278`
Branche cible : `main`
Base Git avant le commit de passation : `5c7c4c00eee974f44f04f322c74bda99ca84927d`

## État obligatoire à annoncer immédiatement à Thomas

- **Autonomie calibration quotidienne standard : atteinte.**
- **Autonomie du mode Précision/composite : non atteinte.** Le profil physique `11 × 11` est qualifié techniquement, mais son résultat en première couche reste mauvais aux bords ; le mode reste caché.
- **Autonomie production : non atteinte.** Les séquences de départ, pause/reprise, CFS et fin ne sont pas encore remplacées ni validées.
- Le profil robuste `k1_p001_t055_r001_n06x06` et le Z persistant accepté `−0,04 mm` sont qualifiés et doivent être conservés.
- `FIRST-CALIBRATION-V2` est close et ne doit jamais être rejouée.
- La comparaison V2 confirme un gain central du `11 × 11`, mais refuse sa promotion à cause des défauts de bord.
- L’état physique actuel de la K1 n’est pas frais : aucun préflight SSH n’a été exécuté après la dernière comparaison V2.
- Prochaine mission unique : `MESH-EDITOR-OFFLINE-V1`, entièrement hors imprimante et sans toucher à la K1 ; elle prépare, mais ne lance pas, le motif de bord `5..295 mm`.
- Aucun `GO` exact ni identifiant de gate recopié n’est requis une fois que Thomas demande normalement de reprendre cette mission, conformément à D-054.

Autorisation au moment de cette passation : `ATTENDRE_GO` au sens « ne pas démarrer automatiquement dans la nouvelle tâche ».

Cette attente ne rétablit pas les anciens mots de passe littéraux : un simple « reprends », « continue » ou une mission/Goal actif suffit. Aucun Goal implicite ne doit être créé par la passation elle-même.

## 1. But de cette passation

Ce fichier est le point d’entrée canonique pour une tâche Codex neuve. Il
remplace l’ancien `HANDOFF.md` accumulatif, devenu trop long et porteur de
plusieurs anciennes « prochaines missions » désormais closes.

La chronologie exhaustive reste disponible dans Git ainsi que dans
[`STATE.md`](STATE.md), [`GATES.md`](GATES.md) et
[`DECISIONS.md`](DECISIONS.md). La présente passation ne conserve que :

- l’état utile et ses incertitudes ;
- les résultats techniques encore actifs ;
- les preuves privées à ne pas perdre ;
- le périmètre exact du prochain incrément ;
- les critères d’acceptation et les interdictions.

## 2. Identité et état Git

- Dépôt : `k1-max-cfs-root-toolkit`.
- Remote : `https://github.com/TomassonJW/k1-max-cfs-root-toolkit.git`.
- Branche de reprise : `main`.
- Un seul worktree connu au moment de la passation : le worktree principal.
- Branche distante étrangère à préserver :
  `origin/agent/bootstrap-safety-baseline`.
- Les répertoires ignorés `.codex-work/` et `inventory/raw/` contiennent des
  preuves privées utiles. Ne pas les nettoyer globalement.

À la reprise, vérifier avant toute modification :

```powershell
git status --short --branch
git rev-parse HEAD main origin/main
git worktree list --porcelain
git status --ignored --short
```

Résultat attendu : `main` propre, `HEAD = main = origin/main`, un seul
worktree principal. Le SHA exact du commit de passation est le `HEAD` trouvé à
ce moment-là ; il ne peut pas être inscrit dans le commit qui le calcule.

## 3. Ce qui est réellement qualifié

### 3.1 Calibration quotidienne standard

La calibration quotidienne standard est autonome depuis K1 Control :

- plaque qualifiée : `PEI_TEXTURED_A` ;
- campagne quotidienne : un seul mesh `6 × 6` Lagrange ;
- profil robuste : `k1_p001_t055_r001_n06x06` ;
- Z persistant accepté : `−0,04 mm` ;
- navigation Mainsail vers `/k1-control/` validée dans le vrai navigateur ;
- la limite physique du PRTouch propriétaire à 36 contacts est connue et
  intégrée dans l’interface.

Ne pas confondre cette autonomie quotidienne avec l’autonomie production.

### 3.2 Source composite physique `11 × 11`

Le profil `k1_p001_t055_r001_n11x11` provient de quatre sous-grilles carrées
`6 × 6` :

- 144 contacts physiques ;
- 121 positions uniques ;
- chevauchement brut maximal : `0,147858 mm` ;
- alignement par biais additif constant de chaque quadrant ;
- moyenne pondérée des biais remise à zéro ;
- écart maximal après alignement : `0,04374502944942382 mm` ;
- écart moyen après alignement : `0,013871331 mm` ;
- aucun lissage local inventé et aucune nouvelle mesure lors de la reprise ;
- empreinte de la matrice candidate :
  `9d975c32512b840cf06c0b942af6e4713f7f69c62ce35e140c41941540153100`.

Ce profil est une **source physique immuable**. La prochaine mission ne doit
jamais écraser ses 121 valeurs. Toute correction crée un profil dérivé nommé,
versionné et réversible.

### 3.3 Comparaisons de première couche

`G4-K1-CONTROL-COMPOSITE-FIRST-LAYER-COMPARISON-V1` est close KO :

- l’ancien post-traitement Orca `--start-z-offset 0.27` était encore présent ;
- il plaçait la couche environ `0,31 mm` au-dessus du Z accepté `−0,04 mm` ;
- seul le passage robuste a été imprimé ;
- le passage composite n’a pas été lancé ;
- les G-code V1 ont été retirés de la K1 ;
- V1 ne doit jamais être rejouée.

La comparaison V2 a ensuite été exécutée avec le profil composite actif :

- le Z persistant est resté `−0,04 mm` ;
- le Z effectif temporaire trouvé par Thomas était `−0,24 mm` ;
- une reprise stock a réécrit le Z effectif, puis Thomas a réappliqué
  `−0,24 mm` pendant l’impression ;
- `−0,24 mm` est une valeur temporaire de cette validation et **ne doit pas
  être persistée automatiquement** ;
- la grande zone centrale est nettement meilleure qu’avec le robuste ;
- les bords et certaines zones proches des côtés restent très mauvais ;
- verdict humain : gain réel, mais promotion du mode Précision refusée.

Les trois photos finales de cette V2 sont conservées dans le répertoire privé
ignoré :

`inventory/raw/20260824-composite-first-layer-v2-photos/`

Empreintes :

| Fichier | SHA-256 |
|---|---|
| `1-Photo-1.jpg` | `d798a75cbc89a0d3a9efe1841b53a0d81275fe0387d47881710dc041854a2802` |
| `2-Photo-2.jpg` | `775798e8ce253a52e7dd45218ecedcb2ab2163fc705e2c2f136a6ad4f02d706b` |
| `3-Photo-3.jpg` | `51925c2565d6e3bcb61e4c3f661c7cb4bef58597a2cd5a23abfa7dbcccc2e4c5` |

Ces fichiers sont des preuves privées : les lire localement si nécessaire,
mais ne pas les ajouter à Git.

## 4. Diagnostic technique acquis

L’hypothèse « Lagrange ou bicubique déforme principalement les bords » a été
testée sur le code Klipper exact de la K1 et n’explique pas le défaut observé.

Mesures hors imprimante :

- reproduction du profil robuste : erreur maximale `0,000000499 mm` ;
- différence maximale bicubique/direct sur le composite : `0,009877883 mm` ;
- différence maximale dans la couronne extérieure de 29 mm :
  `0,009712808 mm` ;
- overshoot local maximal : `0,000689867 mm`.

Conclusion : l’interpolation est un effet secondaire, trop faible pour
expliquer seule les défauts photographiés.

Causes à traiter comme hypothèses, dans cet ordre :

1. effort dépendant de la position du tube PTFE/CFS ou du faisceau sur la tête ;
2. contraintes du plateau et des quatre cellules de charge ;
3. résidu de biais entre quadrants composites ;
4. effets globaux de Z effectif, débit, température ou séquence d’impression.

La prochaine étape choisie par Thomas n’est pas de refaire immédiatement le
palpage : elle consiste à construire l’éditeur sûr et à rendre les corrections
locales traçables. La gate physique suivante devra ensuite distinguer erreur
stable et influence mécanique/PTFE.

## 5. État de la K1 : connu, observé et inconnu

### Dernier état pleinement validé avant la comparaison V2

- `standby` ;
- cibles buse et plateau à zéro ;
- axes non référencés ;
- Z persistant `−0,04 mm`, stockage `ok` ;
- profils robuste `6 × 6` et composite `11 × 11` présents ;
- robuste rechargé ;
- deux CFS connectés.

### Observations pendant la comparaison V2

- profil composite actif pendant l’impression ;
- Z effectif temporaire `−0,24 mm` après correction humaine ;
- Z persistant `−0,04 mm` intact.

### Inconnues actuelles obligatoires

Aucun préflight SSH frais n’a été exécuté après la fin de V2. Ne pas affirmer
sans nouvelle preuve :

- que la K1 est actuellement en `standby` ;
- que les cibles sont à zéro ;
- que les axes sont non référencés ;
- quel profil est actuellement actif ;
- que les deux CFS sont connectés ;
- que le plateau est libre, propre ou porte encore la même plaque ;
- que les G-code V2 ont été retirés du stockage distant.

Cette incertitude ne bloque pas `MESH-EDITOR-OFFLINE-V1`, car cette mission
n’a aucun besoin légitime de joindre la K1.

## 6. Prochaine mission unique : `MESH-EDITOR-OFFLINE-V1`

### 6.1 Objectif

Construire et valider entièrement hors imprimante le modèle, le moteur et
l’interface simulée qui permettront à Thomas de créer un profil mesh dérivé à
partir du `11 × 11`, sans modifier la source et sans dépendre de Codex pour
chaque ajustement futur.

### 6.2 Livrables attendus

Implémenter par petits incréments, probablement dans :

`packages/k1-control-v1/mesh-editor-offline-v1/`

Le paquet doit contenir au minimum :

1. **Modèle de données immuable**

   - référence explicite de la source physique ;
   - profil dérivé versionné, par exemple suffixe `_tuned_v001` ;
   - matrice source, deltas, matrice finale, métadonnées et état de
     qualification séparés ;
   - empreinte canonique reproductible ;
   - orientation X/Y explicite et testée ;
   - Z global totalement séparé des deltas du mesh.

2. **Moteur de corrections pur et testable**

   - sélection d’un point, d’une ligne, d’une colonne ou d’une petite région ;
   - actions utilisateur `Rapprocher` et `Éloigner` ;
   - pas `0,005 mm` et `0,010 mm` ;
   - normalisation à moyenne pondérée nulle ;
   - undo/redo, historique et rollback ;
   - aucune mutation silencieuse de la matrice source ;
   - aucune correction automatique ou lissage non demandé.

3. **Gardes**

   - avertissement lorsque la correction absolue dépasse `0,05 mm` ;
   - refus au-delà de `0,10 mm` ;
   - garde sur saut entre voisins au-delà de `0,08 mm` ;
   - messages compréhensibles indiquant le point, le delta et la raison ;
   - conventions de signe prouvées par les tests et affichées dans l’UI.

4. **Interface hors ligne dans le style K1 Control**

   - grille 2D orientée de 121 points ;
   - affichage commutable `Source / Deltas / Final` ;
   - sélection claire et clavier utilisable ;
   - boutons `Rapprocher`, `Éloigner`, undo, redo, comparer, restaurer ;
   - historique lisible ;
   - aperçu 3D pour comprendre et sélectionner, mais **pas de glisser vertical
     3D en V1** ;
   - puissance avancée progressive, sans surcharger l’usage courant.

5. **Fausse API et simulateur**

   - aucun appel Moonraker réel ;
   - états chargement, validation, erreur et restauration simulables ;
   - contrat assez proche de la future API pour éviter une réécriture de l’UI ;
   - tests du flux complet création → correction → undo/redo → export.

6. **Export Klipper déterministe**

   - bloc de profil complet de 121 valeurs ;
   - `bicubic` et limites physiques `5..295` cohérentes avec la source ;
   - format reconnu par le parseur exact ;
   - résultat bit à bit identique pour une même entrée ;
   - round-trip parse/export et rollback simulé ;
   - aucun déploiement ou script distant dans cette mission.

### 6.3 Source exacte des 121 valeurs

Ordre de confiance :

1. bloc composite dans le fichier privé :
   `inventory/raw/20260824-155319-g4-k1-control-composite-mesh-recovery-v1-run/printer.cfg.composite` ;
2. état privé associé :
   `inventory/raw/20260824-155319-g4-k1-control-composite-mesh-recovery-v1-run/composite-mesh-state.json` ;
3. manifeste public :
   `packages/k1-control-v1/composite-mesh-v1/recovery-deployment-manifest.json` ;
4. logique existante de composition et de rendu.

Empreintes privées vérifiées :

| Artefact | SHA-256 |
|---|---|
| `printer.cfg.composite` | `f88d6b52477592805384fca2b4d7abd00298deecd82227af2fa580085fe26fa2` |
| `composite-mesh-state.json` | `09fe8333dd1708dc781091e367efef7220d8056d40dab7ffefee26e55de9d8eb` |
| `final-printer-status.json` | `24490c6efc9f2d315a6772f62af20864d5ed8e492f92cb36076213cf7abbbc9e` |

Extraire seulement la matrice et ses métadonnées nécessaires vers un fixture
public nettoyé. Ne jamais committer le `printer.cfg` complet, les captures
brutes, les identifiants, les journaux privés ou les photos.

### 6.4 Tests obligatoires de sortie

- tests mathématiques sur les 121 valeurs exactes ;
- immutabilité bit à bit de la source ;
- orientation des quatre coins et des axes ;
- moyenne pondérée nulle après correction ;
- gardes `0,05 / 0,10 / 0,08 mm` ;
- undo/redo et historique déterministes ;
- export Klipper bit à bit reproductible ;
- round-trip parse/export ;
- tests UI sur les actions et le vocabulaire ;
- faux backend uniquement, sans URL ou transport K1 actif ;
- suite projet complète verte ;
- parse de tous les scripts PowerShell ;
- `git diff --check` et revue du diff.

### 6.5 Critères OK / KO

**OK** seulement si :

- la source composite est inchangée ;
- un profil dérivé peut être créé, corrigé, annulé, rétabli et exporté ;
- les 121 valeurs restent orientées correctement ;
- les bornes refusent réellement les corrections dangereuses ;
- la même entrée produit exactement le même export ;
- l’UI fonctionne contre la fausse API ;
- aucun code de cette gate ne contacte ou ne modifie la K1.

**KO** notamment si :

- la source est éditée en place ;
- le Z global est mélangé au mesh ;
- le sens `Rapprocher/Éloigner` n’est pas explicite et testé ;
- une correction est lissée ou renormalisée sans trace ;
- l’orientation est déduite visuellement sans fixture ;
- l’export dépend d’un arrondi non déterministe ;
- la mission ajoute déjà une pose K1, une impression ou une activation réelle.

### 6.6 Arrêt obligatoire de l’incrément

Arrêter la mission après la gate hors ligne verte. Ne pas, dans le même
incrément :

- joindre la K1 par SSH, tunnel, Moonraker ou API Creality ;
- préparer ou exécuter un déploiement ;
- créer ou lancer le motif physique de bord ;
- activer un profil dérivé réel ;
- exposer le mode Précision dans l’interface installée ;
- toucher aux séquences de production, Orca, CFS, pause/reprise ou fin ;
- persister `−0,24 mm`.

## 7. Lecture obligatoire avant de coder

Lire entièrement, dans cet ordre :

1. [`AGENTS.md`](AGENTS.md)
2. [`HANDOFF.md`](HANDOFF.md)
3. [`STATE.md`](STATE.md)
4. [`GATES.md`](GATES.md)
5. [`DECISIONS.md`](DECISIONS.md)
6. [`docs/23-audit-mesh-manuel-et-cycle-production-cfs.md`](docs/23-audit-mesh-manuel-et-cycle-production-cfs.md)
7. [`docs/adr/ADR-015-profils-mesh-derives-et-corrections-locales.md`](docs/adr/ADR-015-profils-mesh-derives-et-corrections-locales.md)
8. [`docs/adr/ADR-013-maillage-composite-et-interface-capacitaire.md`](docs/adr/ADR-013-maillage-composite-et-interface-capacitaire.md)
9. [`docs/adr/ADR-016-cycle-production-orchestre-et-propriete-cfs.md`](docs/adr/ADR-016-cycle-production-orchestre-et-propriete-cfs.md), uniquement pour préserver la frontière de la future production
10. [`docs/21-g4-k1-control-composite-mesh-v1.md`](docs/21-g4-k1-control-composite-mesh-v1.md)
11. [`docs/10-systeme-pilotage-perenne.md`](docs/10-systeme-pilotage-perenne.md)
12. [`packages/k1-control-v1/composite-first-layer-comparison-v2/RESULT.md`](packages/k1-control-v1/composite-first-layer-comparison-v2/RESULT.md)

Puis relire le code source utile :

- `packages/k1-control-v1/composite-mesh-v1/compose_mesh.py` ;
- `packages/k1-control-v1/composite-mesh-v1/render_profile.py` ;
- `packages/k1-control-v1/composite-mesh-v1/k1_control_composite_mesh_core.py` ;
- `packages/k1-control-v1/composite-mesh-v1/composite-mesh-contract.json` ;
- `packages/k1-control-v1/composite-mesh-v1/recovery-deployment-manifest.json` ;
- `packages/k1-control-v1/calibration-ui-navigation-v1/app.js` ;
- `packages/k1-control-v1/calibration-ui-prtouch-presets-v1/index.html` ;
- `packages/k1-control-v1/calibration-ui-v1/www/styles.css` ;
- `packages/k1-control-v1/calibration-ui-matrix-v1/k1_control_calibration_core.py` ;
- `tests/test_k1_control_composite_mesh.py` ;
- `tests/test_mesh_editor_and_lifecycle_contract.py` ;
- les tests UI K1 Control déjà présents.

Vérifier les chemins réels avec `rg --files` : ne pas inventer un fichier si
son nom a évolué.

## 8. Artefacts privés à préserver

Ne jamais supprimer globalement `.codex-work/` ou `inventory/raw/`.

Artefacts particulièrement utiles :

- `inventory/raw/20260824-155319-g4-k1-control-composite-mesh-recovery-v1-run/` ;
- `inventory/raw/20260824-171414-g4-k1-control-composite-first-layer-comparison-v2/` ;
- `inventory/raw/20260824-183614-g4-k1-control-first-layer-z-validation-v1/` ;
- `inventory/raw/20260824-composite-first-layer-v2-photos/` ;
- `.codex-work/20260824-composite-first-layer-v2/` ;
- `.codex-work/20260824-composite-first-layer-v2-retry/` ;
- `.codex-work/extract_binary_strings.py` ;
- `.codex-work/inspect-prtouch-v3.py` ;
- `.codex-work/read-bed-mesh-config.ps1`.

Ils restent ignorés par Git. Toute donnée publique nécessaire aux tests doit
être minimisée, nettoyée et justifiée avant ajout.

## 9. Roadmap après l’éditeur — ne pas anticiper

Ordre mesh :

1. `MESH-EDITOR-OFFLINE-V1` ;
2. `MESH-EDGE-DIAGNOSTIC-V1` ;
3. `MESH-DERIVED-PROFILE-V1` ;
4. `MESH-TUNING-CAMPAIGN-V1` ;
5. exposition éventuelle du mode Précision seulement après deux feuilles
   complètes consécutives sans défaut grave, sans correction Z en direct et
   avec rollback prouvé.

La gate physique M2 utilisera plus tard :

- plage utile `X/Y=5..295` ;
- carte des 121 cellules ;
- une seule petite région corrigée de `0,010 mm` ;
- même plaque, filament, température, PTFE et Z effectif ;
- présence de Thomas devant la machine ;
- comparaison de répétabilité et d’influence PTFE ;
- retour immédiat au robuste en cas de KO.

Ordre production, strictement différé :

1. `PRODUCTION-SEQUENCE-AUDIT-V2` ;
2. `JOB-LIFECYCLE-OFFLINE-V1` ;
3. `CLEAN-AND-REFERENCE-V1` ;
4. `CFS-TEMP-OWNER-V1` ;
5. `PAUSE-RESUME-SEMANTICS-V1` ;
6. `END-SEQUENCE-V1` ;
7. `ORCA-CUTOVER-V1` ;
8. gate G5.

Le retrait de l’ancien départ Orca et du `+0,27 mm` doit rester une seule
transaction future, avec rollback. Aucun paquet mesh ne doit les modifier.

## 10. Autorité, sécurité et communication

- D-054 s’applique : une mission clairement demandée autorise ses actions
  normales de bout en bout sans phrase littérale supplémentaire.
- Une instruction plus récente comme `stop`, `lecture seule` ou `ne touche pas
  à l’imprimante` prime toujours.
- Les dialogues d’approbation techniques de la plateforme peuvent encore
  apparaître ; ne pas les transformer en rituel projet.
- Pour cette mission hors ligne, toute tentative de connexion K1 est hors
  périmètre, même en lecture seule.
- Ne jamais considérer un ancien état distant comme frais.
- Ne jamais annoncer « mode Précision autonome » avant les gates physiques.
- Ne jamais annoncer « production autonome » avant le cutover et G5.
- Thomas veut à terme zéro intervention Codex pour les réglages ordinaires :
  chaque pouvoir utile doit devenir une option d’interface testable, avec
  rollback et mode avancé progressif.

## 11. Démarrage recommandé dans la nouvelle tâche

Quand Thomas demande de reprendre :

1. annoncer les trois statuts d’autonomie du début de ce fichier ;
2. confirmer que la mission est uniquement `MESH-EDITOR-OFFLINE-V1` ;
3. lire intégralement les documents obligatoires ;
4. vérifier Git et les artefacts privés, sans contacter la K1 ;
5. présenter un plan court et les décisions d’UI encore structurantes ;
6. implémenter le plus petit incrément utile ;
7. tester, relire le diff et clôturer Git complètement ;
8. s’arrêter après la gate hors ligne verte.

Modèle conseillé : `gpt-5.6-sol`, raisonnement `high`, car la mission combine
mathématiques, modèle de données, UI, tests de reproductibilité et forts risques
d’orientation/signe. Option plus économique acceptable : `gpt-5.6-terra`,
raisonnement `high`, avec davantage de risque de reprise lors de la validation
croisée des 121 valeurs.

## 12. Contrat de la nouvelle tâche Codex

La nouvelle tâche doit être créée localement, dans ce dépôt, sans fork, sans
worktree et sans branche automatique. Elle doit :

- rester en attente après avoir chargé cette passation ;
- ne créer aucun Goal implicite ;
- ne contacter ni modifier la K1 ;
- ne commencer qu’après une instruction normale de Thomas ;
- reprendre directement depuis ce fichier, sans exiger l’historique oral de la
  tâche source.

La tâche source reste non archivée tant que Thomas ne demande pas explicitement
son archivage.
