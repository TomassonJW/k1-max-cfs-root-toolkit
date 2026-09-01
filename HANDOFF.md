# HANDOFF — index de reprise

Mise à jour : 2026-09-01, après qualification du capteur cutter et recadrage
du périmètre produit.

## État réel

Le capteur du cutter est **bon**. `BOX_CUT_HALL_TEST`, machine froide et `X/Y`
référencés, amène la tête à `Y304,5` et publie `[box] cut sensor state:1` puis
`:0`, avec `release_failed_num: 0`. ADR-041 établit que `box.cut_pos` ne
reflète jamais ce capteur : la garde qui bloquait le retrait lisait le mauvais
champ, et l'appui manuel sur le levier n'était pas un test valide.

ADR-042 recadre le périmètre : la bascule Orca sort du chemin critique et
devient du backlog V2. Le besoin canonique de Thomas est désormais écrit en
tête de `GOALS.md` et fait autorité.

Deux écarts ouverts, mesurés le 1er septembre :

- le Z accepté est stocké en **un seul enregistrement global**, pas par profil
  de mesh ; c'est un préalable bloquant à toute campagne multi-températures ;
- le mesh réellement chargé est `default`, pas `k1_p001_t055_r001_n11x11` ; le
  profil existe toujours mais a dérivé et devra être recalibré, filament retiré ;
- le contrat de design impose `end_full_unload` (ADR-035) alors que le paquet
  `job-lifecycle-offline-v1` modélise encore `end_keep_engaged` : son moteur ne
  connaît que la politique `keep_engaged` et lève `end_policy_mismatch` sinon.
  Le test `test_all_canonical_scenarios_are_implemented_once` est **laissé
  rouge volontairement** : il signale cette divergence réelle. La corriger
  demande une tranche dédiée sur le moteur hors imprimante, pas un correctif
  de test.

La suite complète passe à `874` tests, `1` échec — celui ci-dessus — contre
`12` échecs et `2` erreurs avant cette session.

État physique au moment de l'écriture : Klipper `ready`, `standby`, buse à
`26,5 °C`, cibles à zéro, `X/Y` référencés, `Z` non référencé, tête parquée en
`X100 Y150`, `T1A` engagé, deux capteurs filament actifs, aucune route stock.

## Prochaine action

Retrait intégré `T1A` sur le signal console, puis nettoyage manuel par Thomas,
puis une première impression mono-filament complète. Ensuite seulement le
correctif Z-par-profil, puis la recalibration.

## Archive

La passation détaillée précédente, `HANDOFF-CUTTER-SENSOR-PAUSE-2026-09-01.md`,
reste consultable pour l'historique des preuves. Sa liste de gestes humains est
en revanche **périmée** : son point 2, l'appui manuel sur le levier, est retiré
par ADR-041.

Le contenu ci-dessous est conservé comme archive historique. Il décrit l'état
antérieur à la qualification du capteur et ne doit plus piloter l'action.

# Archive — reprise après refus réel du cutter le 1er septembre 2026

La quantité de purge est corrigée et installée : la reprise fautive utilisait
`30 mm`, alors que le chargement initial stock observé utilise `140 mm`. Le
cycle lit désormais le vecteur et la matrice Orca du G-code ; le fichier
d'essai courant demande notamment `266,081080 mm` pour une transition `0→1`.

Le dernier essai s'est arrêté proprement avant retrait. La tête a essayé la
position stock `X38 Y304,5`, puis des pas de `0,5 mm` jusqu'à la limite publiée
`Y307,5`. Le capteur `cut_pos` est resté à `0` partout. Aucune commande de
retrait n'a donc été envoyée. `T1A` reste chargé, les deux capteurs filament
sont actifs, les chauffes sont à zéro, les axes sont libérés, le mesh
`k1_p001_t055_r001_n11x11` est actif et le Z accepté reste `−0,04 mm`.

Ne pas rejouer automatiquement le cutter et ne jamais dépasser `Y307,5`. La
prochaine étape est une vérification mécanique réelle, à froid, du levier du
cutter et de son capteur. ADR-040 et le `RESULT.md` du paquet
`stock-derived-cycle-activation-v1` sont les références canoniques.

Un moniteur manuel en lecture seule est prêt. Le préflight froid et la caméra
sont verts ; sa première fenêtre de `90 s` n'a vu aucune transition, mais
l'appui humain n'a pas été confirmé. Ne pas en déduire une panne. La prochaine
preuve est l'appui puis le relâchement du poussoir/levier solidaire de la tête,
avec observation obligatoire de `cut_pos : 0→1→0`.

Le texte ci-dessous est l'archive de la reprise précédente.

# Archive — reprise après KO borné de la V1 physique directe

La gate
`G4-K1-CONTROL-CFS-DIRECT-OWNER-PHYSICAL-LOAD-UNLOAD-V1` est close KO et ne
doit jamais être rejouée. Capture privée :
`20260831-132914-g4-k1-control-cfs-direct-owner-physical-load-unload-v1`.
L'activation s'est arrêtée sur `stock_auto_refill_invalid` après restart, avant
chauffe, trame CFS, moteur filament ou mouvement d'axe. Le rollback a remis
`enabled=false`, zéro cible, axes libérés, `11 × 11` et Z `−0,04`. Les deux
capteurs sont toujours actifs : le filament initial est resté engagé.

Thomas a corrigé la frontière produit et ADR-037 la rend canonique : tout
retrait passe d'abord par la position cutter et la coupe ; tout chargement est
immédiatement suivi d'une purge dans le vrai bac, de `3 à 4` allers-retours
francs de décrochage, puis d'une preuve caméra. Aucun palpage ou mesh après
insertion. La prochaine mission est uniquement
`G4-K1-CONTROL-CFS-CUTTER-PURGE-INTEGRATED-R2-OFFLINE-V1` : construire et
tester la chorégraphie complète hors imprimante, y compris la persistance
d'`auto_refill`, avant toute nouvelle action physique.

Le texte ci-dessous décrit l'état précédent et reste une archive.

La reprise canonique est désormais :

`docs/51-proprietaire-cfs-direct-candidat-pose-desactivee-v1.md`

ADR-036 est acceptée et `cfs-direct-owner-offline-v1` obtient `24/24`. Le cycle
intégré ne dépend plus d'aucun effet `BOX_*`. Le candidat désactivé obtient
`13/13`, puis il est posé sous
`20260831-123137-g4-k1-control-cfs-direct-owner-install-disabled-v1`. Le
composant est chargé avec `enabled=false`, transport non pris, commandes stock
non remplacées et zéro trame CFS. Une validation intégrée et deux validations
indépendantes sont vertes. L'état final est froid, au repos, axes libérés,
`11 × 11` actif, Z `−0,04`, deux CFS connectés et aucune route logique.

L'ancienne tranche annoncée était
`G4-K1-CONTROL-CFS-DIRECT-OWNER-PHYSICAL-LOAD-UNLOAD-V1` : activer sous
surveillance, qualifier un seul cycle direct `T1A`, puis remettre un état sûr.
Cette tranche est maintenant close KO et remplacée par ADR-037.

Lire le document 51, ADR-036, puis les derniers blocs de `STATE.md`, `GATES.md`
et `DECISIONS.md`. Le contenu ci-dessous est conservé comme archive des
clôtures antérieures ; il ne décrit plus l'état actuel et ne doit pas piloter
la prochaine action.

L'observabilité V2 est qualifiée hors imprimante puis sur la vraie K1. La gate
d'effet a ensuite désactivé une fois l'auto-remplacement stock, prouvé deux fois
la valeur `0`, restauré une fois la valeur précédente `1` et prouvé deux fois
ce retour exact. Le verdict final est
`CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED`. Les captures sont consommées
et ne doivent pas être rejouées.

`GOAL-P4-OFFLINE-CYCLE-CFS-V1` est terminé hors imprimante et
`GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` est terminé en lecture seule. La capture
canonique de ce second Goal reste
`20260827-142853-goal-p4-k1-read-only-qualification-v1`. Le Goal 3 reste en
cours à `2/7` ; le nettoyage automatique est clos KO et le nettoyage manuel
est obligatoire.

`G4-K1-CONTROL-CFS-OWNER-CORE-OFFLINE-V1` reste clos avec `21/21` scénarios.
Son successeur `G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1` est
maintenant clos avec `25/25` scénarios et `15/15` tests ciblés. Le garde pur
sauvegarde la valeur stock, prépare au plus une désactivation non exécutable,
exige deux lectures qui prouvent l'effet puis restaure exactement la valeur
précédente. Un acquittement seul ne prouve rien et un résultat incertain n'est
jamais rejoué.

Le vrai Z accepté `−0,04 mm` vient de `KCTRL_STATE`, sous une connexion
Moonraker persistante. `T1/T2`, l'absence de route, les chauffes zéro, le mesh
`11 × 11` et les configurations sont inchangés. Aucun filament, mouvement,
chauffage, fichier distant ou service n'a été touché. Le Goal 3 reste à `2/7`.

La prochaine mission unique est `G4-K1-CONTROL-START-SEQUENCE-OWNER-V1`.
Il faut d'abord rendre son candidat hors imprimante installable et réversible ;
la pose et l'essai physique resteront une tranche distincte. La production et
les primitives filament non qualifiées restent fermées.

## Archive historique — clôture initiale du Goal 2

Date de passation : 2026-08-27
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`
Nouvelle tâche créée : non
Goal actif : absent après clôture

## État à annoncer immédiatement à Thomas

- **`GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` est terminé.**
- La lecture réelle est qualifiée sans effet, mais la suite physique est
  bloquée : le mesh actif `default` diffère du profil robuste requis.
- Le profil robuste `k1_p001_t055_r001_n06x06` existe encore avec sa bonne
  empreinte ; il n'a pas été chargé, car le Goal 2 l'interdisait.
- Aucune impression, G-code, écriture distante, chauffe, mouvement, restart,
  action CFS ou reconnexion provoquée n'a eu lieu.
- La production reste fermée et le mode Précision reste caché.
- Cette session source doit rester visible et ne doit pas être archivée.

## État livré

La capture privée retenue est
`20260827-142853-goal-p4-k1-read-only-qualification-v1`. Le nettoyage a lieu sur
la K1 avant le retour local : aucun numéro de série, UUID, nom de fichier
d'impression ou contenu de configuration n'est exporté.

Deux lectures stables confirment Klippy prêt, l'imprimante en `standby`, les
cibles à zéro, les axes libérés, `T1/T2` connectés, `T3/T4` non configurés,
aucune route engagée, `t_command` vide, le capteur de tête actif et le Z accepté
à `−0,04 mm`. L'identité filament reste donc classée `engaged_unknown`.

Les lectures d'état ont pris `199,212 ms` et `235,525 ms`, sous le plafond de
`5 s`. La forme est identique entre les deux réponses. Les douze empreintes de
configuration, composants Moonraker et fichiers UI correspondent aux versions
revues et sont identiques avant/après.

Le seul écart bloquant est réel : le mesh actif `default` et le profil robuste
requis `k1_p001_t055_r001_n06x06` sont tous deux des matrices `6 × 6`, mais
leurs empreintes diffèrent. Le robuste existe toujours ; il n'est simplement
pas actif. Le statut fermé est `CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT`.

Le collecteur `GET`, la traduction pure, le délai et la règle d'invalidation du
mapping sont qualifiés. Une reconnexion très courte qui revient au même état
entre deux sondages reste invisible ; le futur composant Moonraker devra donc
prendre son époque dans les notifications.

Le pilotage macro est maintenant centralisé dans `GOALS.md` :

1. `GOAL-P4-OFFLINE-CYCLE-CFS-V1` — terminé hors imprimante ;
2. `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` — terminé en lecture seule avec KO
   borné du mesh actif ;
3. `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1` — installer et qualifier les
   fonctions physiques par petites tranches avec Thomas présent, après le
   chargement contrôlé du profil robuste ;
4. `GOAL-P4-DAILY-CUTOVER-V1` — basculer enfin vers le fonctionnement quotidien
   complet avant la campagne G5.

Ces noms sont des regroupements de pilotage. Ils ne remplacent pas les gates de
`GATES.md` et ne donnent aucune autorité d'installation ou de production.

## Git vérifié avant le commit de cette passation

- base de mission : `5927a7ff49b67dc52a9ae5af6f1a1193ff19003a` ;
- `main` local et `origin/main` étaient alignés sur cette base ;
- divergence : `0/0` ;
- checkout propre au départ ;
- un seul worktree ; travail réalisé sur `codex/k1-read-only-qualification-v1` ;
- aucune branche de mission ou ressource étrangère observée ;
- le SHA final contenant cette passation sera communiqué dans le compte rendu.

## Vérifications réutilisables

- preuve live nettoyée : **OK**, `2/2` lectures ;
- schéma réel : **OK**, stable et épinglé ;
- délai de lecture : **OK**, maximum observé `235,525 ms` sous `5 s` ;
- empreintes distantes : **OK**, exactes et inchangées ;
- CFS, Z et état au repos : **OK** pour la lecture seule ;
- mesh actif conforme au contrat quotidien : **KO borné** ;
- validation physique ou humaine : **non exécutée**, hors périmètre ;
- effet sur la K1 : **aucun** ;
- suite complète : **OK**, `488` tests exécutés, `485` verts et `3` ignorés ;
- scripts PowerShell : **OK**, `29` fichiers relus sans erreur.

## Prochaine mission unique

### Gate préalable au `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1`

Thomas doit être devant la K1. La prochaine gate vérifiera l'état sûr et les
empreintes, chargera uniquement `k1_p001_t055_r001_n06x06`, puis relira le nom
actif et la matrice sans lancer d'impression. Elle s'arrêtera au premier écart
et gardera un retour arrière exact.

Relire dans cet ordre : `HANDOFF.md`, `GOALS.md`, le document 41, le `RESULT.md`
et le contrat du paquet `k1-read-only-qualification-v1`, puis le plan futur.

Cette action modifie l'état d'exécution de la K1 et exige une nouvelle
autorisation explicite ; le Goal 2 clos ne l'autorise pas. Concrètement, le
prochain GO permettra seulement de charger le profil robuste déjà présent et
de vérifier sa matrice, pas d'imprimer ni de commencer toutes les tranches du
Goal 3.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`, car la tâche est petite
mais touche du matériel réel et doit distinguer précisément profil, matrice et
rollback. Option économique : `gpt-5.6-terra` en `medium`, avec un risque plus
élevé de reprise si un état transitoire ou une incohérence de preuve apparaît.
