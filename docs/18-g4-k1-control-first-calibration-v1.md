# G4 — K1 Control first calibration V1

Statut au 2026-08-22 : **GO exact consommé ; arrêt KO après deux meshes ; aucun
profil cible ni Z persistés ; aucun rerun autorisé**.

## Ce que cette gate devait faire

La gate devait qualifier un premier mesh de référence reproductible puis ouvrir la
session Z bornée déjà installée. Elle n'ajoute aucun logiciel ni configuration
de commande. Elle utilise uniquement le runtime Z/mesh et
`CALIBRATION-PATH-V1` déjà validés.

Même en cas de réussite, elle ne rendra pas l'interface autonome. Le pilote
PowerShell est un protocole de première mise en service revu, pas l'écran final
destiné à l'usage quotidien.

## Autorité actuelle

Autorisation : `LECTURE_ET_ANALYSE_HORS_IMPRIMANTE`.

Le GO exact `GO G4-K1-CONTROL-FIRST-CALIBRATION-V1` a été consommé par la
capture KO. Il n'autorise aucune troisième mesure ni reprise. Une future
campagne devra d'abord disposer d'un protocole distinct revu puis de sa propre
autorisation exacte.

## Base obligatoire

- K1 Max S12 structure `0`, firmware `2.3.5.34` ;
- `printer.cfg` :
  `0d59dd656844c3198ee43a81056b06830dbe60779d558b71aaa8c28fa708d9ee` ;
- runtime Z/mesh :
  `dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113` ;
- stockage atomique :
  `696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede` ;
- chemin du premier Z :
  `825aadac8679e0d0e9be140cc5ba4e7656b2bff0d197d1683a73d2b5be4e364e` ;
- runtime `ready=1`, `integrity=empty`, aucun Z accepté, aucune session et
  mouvements bas fermés ;
- chemin `idle`, non prêt, non armé ;
- `standby`, axes non référencés, chauffes demandées à zéro ;
- deux CFS `1.1.3` connectés ;
- profil `k1_p001_t055_r001_n06x06` absent en mémoire et dans `printer.cfg`.

Une différence arrête le préflight.

## Paramètres figés

| Paramètre | Valeur revue |
|---|---:|
| plaque | `PEI_TEXTURED_A`, ID `1` |
| plateau | `55 °C` |
| buse de mesure | `140 °C` |
| stabilisation | `200 s` |
| nettoyage | `NOZZLE_CLEAR`, min `140 °C`, max `180 °C`, lit `55 °C` |
| homing | `KCTRL_CALIBRATION_HOME`, après nettoyage |
| zone mesh | `5,5` à `295,295 mm` |
| matrice | `6 × 6` |
| interpolation | Lagrange |
| répétitions | `2`, sans troisième essai automatique |
| seuil | écart absolu maximum `0,025 mm` sur chacun des 36 points |
| profil final | `k1_p001_t055_r001_n06x06` |
| seed Z | `0,0 mm`, explicite et neutre |
| centre Z | `(150,150)` |
| paliers | `5 → 2 → 1 → 0,5 → 0,3 → 0,2 → 0,15 → 0,1 mm` |

Les `200 s` sont une valeur initiale à qualifier sur la machine. Après cette
attente, le pilote exige encore le plateau à `55 ± 2 °C` et la buse à
`140 ± 5 °C`. Un écart arrête la gate ; il n'allonge pas automatiquement
l'attente et ne relance pas un mesh.

Le nettoyage stock a été retenu uniquement pour cette calibration de référence :
son code exact chauffe et essuie sans extrusion ni commande CFS, puis le homing
suivant rétablit la référence finale. Il ne préjuge pas du futur nettoyage de
production demandé par Thomas.

## Actions du pilote

Le fichier `scripts/run-k1-control-first-calibration-v1.ps1` fonctionne en
`Plan` par défaut. Toutes les actions ci-dessous exigent `-Execute`, la gate
exacte, une capture au format
`AAAAMMJJ-HHMMSS-g4-k1-control-first-calibration-v1` et le dossier local exact
`inventory/raw/<capture>` déjà créé et ignoré par Git.

1. `Preflight` : lecture seule complète.
2. `Prepare -ConfirmPlateClear` : backup, chauffe, stabilisation, nettoyage,
   homing et checkpoint.
3. `Mesh1` : une mesure et capture des 36 points.
4. `Mesh2` : seconde mesure, comparaison locale, arrêt KO sans rerun.
5. `CommitMesh` : enregistre uniquement le second mesh qualifié ; le
   `SAVE_CONFIG` du runtime redémarre Klipper.
6. `BeginZ -ConfirmPlateClear -ConfirmNozzleClean` : restaure le contexte
   thermique, home, charge le profil, ouvre la session et se place à `5 mm`.
7. `StepZ -Height <palier>` : un seul palier revu par appel.
8. `AdjustZ -Delta <valeur>` : facultatif, seulement à `0,1 mm`.
9. `ConfirmGap -ConfirmGapObserved` : confirme puis remonte de `5 mm`.
10. `Accept -ConfirmAccept` ou `Cancel`.
11. `Validate` : vérification indépendante en lecture seule.
12. `Rollback` : restauration complète de la base si nécessaire.

Les actions physiques devront être lancées avec le wrapper gardé Windows et un
timeout métier adapté. `Prepare`, `Mesh1`, `Mesh2` et `BeginZ` peuvent rester
silencieuses plusieurs minutes ; elles ne doivent jamais être relancées tant que
leur processus précédent n'est pas terminé.

## Backup avant première chauffe

`Prepare` crée
`/usr/data/k1-control-v1/backups/<capture>/first-calibration-v1` et y conserve :

- `printer.cfg.before`, dont l'empreinte doit être exactement celle de la base ;
- `checksums.sha256`, vérifié avant toute chauffe ;
- `state-baseline-absent`, qui prouve que les fichiers courant, précédent et
  temporaire du stockage Z étaient absents.

Le backup reste sur la K1 comme preuve. Aucun fichier du paquet n'est installé.

## Qualification et arrêt KO

`compare_meshes.py` travaille uniquement sur les deux JSON privés capturés. Il
refuse les formes autres que `6 × 6`, les valeurs non finies et tout seuil non
positif. Son code retour est `0` pour OK, `2` pour une divergence qualifiée et
`3` pour une preuve invalide.

Si l'écart maximal dépasse `0,025 mm`, le pilote coupe les chauffes, écrit le
résultat KO et s'arrête. Il ne lance ni troisième mesure, ni commit mesh, ni
session Z.

## Résultat réel du 2026-08-22

La capture `20260822-140602-g4-k1-control-first-calibration-v1` a passé le
préflight, créé et vérifié le backup exact, puis obtenu les checkpoints
`Prepare` et `Mesh1`. Le second mesh a été mesuré exactement une fois.

Résultat de la comparaison locale :

- 36 points comparés, forme `6 × 6` conforme ;
- écart maximal `0,062125 mm` ;
- écart moyen `0,018049 mm` ;
- seuil `0,025 mm` ;
- décision `accepted=false`.

L'arrêt KO a coupé les chauffes. `CommitMesh`, `BeginZ`, les paliers, `Accept`
et la validation de succès n'ont pas été exécutés. Le contrôle final en lecture
seule a confirmé l'empreinte initiale de `printer.cfg`, le profil cible absent,
le stockage Z absent, `standby` et les deux cibles à zéro, puis s'est arrêté sur
les axes `xyz` encore référencés après les mesures. Le détail public est dans
`experiments/p4/20260822-first-calibration-v1-ko-report.md`.

## Acceptation, annulation et restauration

`Accept` n'est disponible qu'après confirmation humaine du jeu et remontée de
sécurité. Il enregistre le Z avec l'heure UTC Unix courante, coupe les chauffes
et exige : stockage `ok`, Z accepté, contexte `1/55/1/1/1`, session fermée,
mouvements bas toujours fermés et profil mesh présent.

`Cancel` parque si nécessaire, annule le Z provisoire et coupe les chauffes. Le
mesh qualifié reste disponible pour une reprise future ; aucun Z accepté n'est
créé.

`Rollback` parque et annule d'abord toute session active, coupe les chauffes,
restaure le `printer.cfg` exact, retire uniquement les trois variantes du fichier
d'état Z qui n'existaient pas au départ, synchronise puis redémarre Klipper. Il
vérifie ensuite runtime vide, chemin `idle`, axes non référencés, chauffes à zéro,
profil cible absent et fondation intacte. Après la fenêtre Creality différée, il
restaure encore le backup exact sans second restart et repointe son empreinte.

Le rollback ne retire ni le runtime ni le chemin de calibration installés.

## Critères finaux

Succès : `VALIDATE_FIRST_CALIBRATION_V1_OK`, un mesh qualifié persistant, un Z
accepté dans le même contexte, chauffes à zéro, aucun ordre CFS, aucune extrusion
et aucune modification Orca/`START_PRINT`/post-traitement.

Échec fermé : toute divergence d'identité, de hash, de contexte thermique, de
matrice, de session ou de confirmation humaine arrête l'action courante. Aucun
rerun automatique n'est prévu.

## Après cette gate

Une réussite qualifiera la première calibration mais laissera :

- autonomie calibration : **non atteinte**, tant que la vraie interface ne
  propose pas paramètres, résultats, save/cancel/restore et statut clair ;
- autonomie production : **non atteinte**, jusqu'à la bascule atomique
  Orca/`START_PRINT`, au retrait prouvé du `+0,27 mm`, à la propriété dynamique
  des températures CFS et à G5.
