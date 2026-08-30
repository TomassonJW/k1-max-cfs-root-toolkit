# Handoff — Goal 3, pilote caméra et R3 validés à froid

> **Supersédé le 30 août 2026** par
> `HANDOFF-GOAL3-CALIBRATION-BEFORE-INSERTION-PREFLIGHT-2026-08-30.md`.
> Les gestes manuels sont faits, mais R3 ne doit jamais être posé ni exécuté :
> ADR-034 impose toutes les palpations avant l'insertion du filament et le
> préflight a aussi trouvé le mesh actif `default` en `6 × 6`.

Date : 2026-08-30
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Nouvelle tâche créée : non
Nouveau Goal Codex : absent
Reprise : `ATTENDRE_GO` — ici, attendre le constat des trois gestes manuels, pas
un nouveau GO général ni un identifiant à recopier.

## État livré

`G4-K1-CONTROL-CAMERA-REFERENCE-LIBRARY-AND-R3-COLD-VALIDATION-V1` est close
avec `CLOSED_OK_CAMERA_READ_ONLY_AND_R3_COLD_VALIDATED`. Le Goal 3 reste en
cours à `2/7`. Le run thermique R5 reste clos KO sans retry ; aucune preuve de
cette tranche ne le transforme en succès.

Le nouveau paquet
`packages/k1-control-v1/camera-reference-library-and-r3-cold-validation-v1/`
contient un pilote caméra, la bibliothèque versionnée, la validation froide R3,
les preuves et un plan inerte pour la prochaine gate. Le pilote résout l'adresse
de `k1max-root` par `ssh -G`, sans ouvrir de session distante, puis fait un seul
`GET` caméra. Il exige le cadrage `1280 × 720`, mesure la netteté, extrait les
zones buse, bac et plateau et compare leurs pixels à une référence fournie. Il
ne connaît ni Moonraker, ni G-code, ni commande CFS et conserve toujours
`semantic_state_confirmed=false`.

La bibliothèque contient exactement une référence acquise : `SAFE_IDLE_PARK`,
dont l'image privée vient de l'arrêt sûr après R5. `ROUGH_HOME_READY`,
`BIN_PURGE_ACTIVE`, `BIN_RELEASED_CLEAN`, `PRIME_OUTSIDE_BED` et
`FIRST_LAYER_GOOD` restent absentes. Une image fraîche du 30 août est nette et
les trois écarts normalisés avec la référence sont compris entre `0,009603` et
`0,010838`. La revue visuelle montre la tête haute, le plateau descendu et
aucune activité visible. Cela ne prouve ni une buse propre, ni une route
filament, ni un bon Z de première couche.

R3 est validé à froid : la première pause caméra bloque avant `ACCURATE_G28`,
la seconde bloque avant `RESUME_BASE`, seules `PAUSE_BASE` et `RESUME_BASE` sont
utilisées et le watchdog appelle `TURN_OFF_HEATERS` sans confirmer d'image. Les
`16` blocs G-code ont été parsés par le Jinja2 du Python déjà présent sur la K1,
via stdin uniquement. Aucun fichier distant n'a été créé.

## Vérifications et limites

- pilote sur la référence elle-même : **OK** ; cadrage, netteté, trois découpes
  et différences nulles ;
- capture caméra fraîche : **OK** ; image nette et comparaison candidate verte,
  revue sémantique automatique toujours désactivée ;
- validation statique R3 : **OK** ; deux blocages, macros de base et timeout sûr ;
- parse Jinja réel : **OK**, `REMOTE_R3_JINJA_PARSE_OK sections=16` ;
- tests ciblés caméra, R3 et registre Goal 3 : **OK**, `19/19` ;
- contrôles de passation et d'autorité : **OK**, `5/5` ;
- suite complète : **OK**, `797` tests exécutés, `794` verts et `3` ignorés
  connus ;
- parse des deux scripts PowerShell du paquet : **OK** ;
- pose R3, G-code, chauffe, homing, mouvement, extrusion, CFS, service et
  configuration distante : **non exécutés** ;
- références physiques autres que `SAFE_IDLE_PARK` : **non acquises** ;
- autonomie fine du Z par caméra : **non qualifiée**.

La preuve live privée reste sous
`inventory/raw/20260830-camera-reference-library-and-r3-cold-validation-v1/`.
L'adresse résolue n'est pas exportée. Les fichiers privés et les anciens
journaux restent hors Git.

## Git

La mission est partie de `main = origin/main` au commit
`69dbd490090437277a16da80f0d86e1c0c7a7fbc`. Elle a été réalisée sur
`codex/camera-reference-r3-cold-v1`. Le commit final, l'alignement distant et le
nettoyage de cette branche sont communiqués dans le compte rendu de clôture qui
accompagne ce handoff. Aucun worktree ou travail étranger n'a été touché.

## Prochaine mission unique

La prochaine gate candidate est
`G4-K1-CONTROL-START-SEQUENCE-OWNER-CAMERA-PURGE-R3-HOT-PREFLIGHT-V1`. Son plan
est figé dans `next-hot-preflight.json`, mais son statut reste
`BLOCKED_WAITING_REAL_MANUAL_RESET_NO_EFFECT_AUTHORIZED`.

Avant de reprendre, Thomas doit faire seulement trois choses réelles : nettoyer
la buse, nettoyer et libérer le plateau, puis réengager `T1A` avec la fonction
officielle. Il suffit ensuite de dire que ces trois gestes sont terminés ; aucun
texte de gate n'est à recopier. Le préflight suivant prendra une image et relira
l'état, la route, le `11 × 11`, le Z accepté et les empreintes. Il préparera les
sauvegardes et le rollback, mais interdira encore pose, chauffe, mouvement,
extrusion, CFS et impression. Cette ancienne suite est annulée : ADR-034 ferme
maintenant toute pose ou tout essai chaud de R3.

La prochaine action est une gate humaine : aucun modèle Codex n'est nécessaire
pour nettoyer et réengager la machine. Après ce constat, le modèle optimal pour
le préflight est `gpt-5.6-sol` en raisonnement `high`, car il faut croiser image,
état Klipper et rollback matériel. L'option économique est `gpt-5.6-terra` en
`high`, avec davantage de risque de reprise sur les états transitoires.

La tâche source reste visible et ne doit pas être archivée.
