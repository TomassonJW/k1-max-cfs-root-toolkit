# HANDOFF

Date: 2026-08-23 17:25 +02:00
Phase: P4 / FIRST-CALIBRATION-V2 validée ; corrections UI sûres et prototype composite préparés hors imprimante ; production fermée
Next operator: ouvrir Chrome, authentifier `http://localhost:4411/k1-control/`, puis lancer depuis l'écran l'unique campagne `6 × 6 / 1 mesh`

## Préflight CAMPAIGN-V1 du 23 août 2026

Thomas a reconfirmé que son autorisation globale couvre toutes les gates du
goal. Le premier préflight a rencontré un faux KO local : le validateur
comparait le core final installé au hash historique du delta BED-MESH-V2. Le
second demandait à tort au manifeste final PRESETS de couvrir `printer.cfg`.
Le contrôle corrigé utilise la carte finale PRESETS pour les sept destinations
UI/Moonraker et vérifie séparément le hash exact de `printer.cfg`.

La capture `20260823-171803-g4-k1-control-calibration-ui-campaign-v1` a ensuite
obtenu `PREFLIGHT_CALIBRATION_UI_CAMPAIGN_V1_OK`. UI finale exacte, Klippy
`ready`, `failed_components=[]`, `warnings=[]`, K1 au repos, cibles zéro,
profil robuste, Z accepté, `6 × 6` Lagrange chargé et deux CFS sont conformes.
Aucun chauffage, homing, mouvement, mesh ou changement Z n'a été lancé.

Le tunnel temporaire neuf `localhost:4411` répond HTTP 401 comme attendu. Le
navigateur intégré ne présente pas l'authentification HTTP et Chrome est fermé.
La prochaine action humaine est d'ouvrir Chrome, de s'authentifier sur cette
URL, puis de laisser Thomas seul déclencher les actions physiques depuis
l'écran. Codex reste en observation et validation.

## Clôture PRTOUCH-PRESETS-V1 du 23 août 2026

La capture `20260823-165742-g4-k1-control-calibration-ui-prtouch-presets-v1` a
obtenu le préflight, le déploiement et deux validations vertes. Les hashes sûrs
étaient déjà installés par les deltas précédents : le déployeur a conclu avec
`already_present=true` et `remote_write=false`, sans backup, transfert, restart
ou action physique. Klippy est `ready`, `failed_components=[]`, `warnings=[]`,
la K1 est au repos avec cibles zéro, le profil robuste, le Z accepté, le mesh
`6 × 6` Lagrange et les deux CFS conformes.

Le validateur CAMPAIGN-V1 a ensuite été corrigé hors imprimante pour épingler le
manifeste UI sûr réel, vérifier `server/info`, le mesh chargé et les versions des
deux CFS. Son plan, ses tests ciblés et la suite complète sont verts. La couche
d'approbation avait d'abord refusé le préflight SSH CAMPAIGN-V1. Thomas a depuis
reconfirmé son autorisation globale et le préflight corrigé est vert sous la
capture `20260823-171803-g4-k1-control-calibration-ui-campaign-v1`.

## Clôture RETRY-SAFETY-V1 du 23 août 2026

Thomas a autorisé `G4-K1-CONTROL-CALIBRATION-UI-RETRY-SAFETY-V1` jusqu'au vert,
sans redemander la même autorisation. L'audit a trouvé que la règle historique
`mesh_index < mesh_target_count` ne détectait plus un échec du protocole à un
mesh : l'état réel est `rolled_back`, `1 / 1`. Le correctif réinitialise donc
une seule fois les deux confirmations sur toute fin non acceptée `cancelled`,
`failed`, `mesh_rejected` ou `rolled_back`.

La capture `20260823-164558-g4-k1-control-calibration-ui-retry-safety-v1` a
obtenu le préflight, `DEPLOY_CALIBRATION_UI_RETRY_SAFETY_V1_OK`, la validation
intégrée puis une validation indépendante verte. Seul `app.js` a été remplacé,
après backup exact, sans aucun restart. Le hash installé est `3d3d53ea…` et le
backup MATRIX est `33a20db2…`. Le core, `index.html`, BED-MESH-V2 et
`printer.cfg` sont inchangés. Klippy est `ready`, `failed_components=[]`,
`warnings=[]`, la K1 est au repos, cibles zéro, runtime/Z/profil robuste,
`6 × 6` Lagrange et deux CFS conformes.

La preuve navigateur des octets exacts installés simule volontairement le cas
`rolled_back`, `1 / 1`, avec `replace_existing=true` côté serveur. Le premier
rendu force `replace_existing=false` et `plate_clear=false`; une coche
volontaire reste active pendant les rafraîchissements de la même phase, puis un
rechargement frais remet les deux cases à `false`. Aucun POST, clic de
calibration ou effet imprimante n'a eu lieu. RETRY-SAFETY-V1 est close.

## Clôture MATRIX-V1 du 23 août 2026

Le GO persistant de Thomas a autorisé la correction des gardes nécessaires sans
redemander le même GO. La capture
`20260823-161103-g4-k1-control-calibration-ui-matrix-v1` a obtenu
`PREFLIGHT_CALIBRATION_UI_MATRIX_V1_OK`,
`DEPLOY_CALIBRATION_UI_MATRIX_V1_OK`, puis une seconde validation indépendante
`VALIDATE_CALIBRATION_UI_MATRIX_V1_OK`.

Le core et les deux fichiers statiques ont été remplacés après backup exact ;
seul le Moonraker dédié a été redémarré. Les hashes installés sont
`9a6a2419…`, `4892294d…` et `33a20db2…`. Les trois fichiers de rollback sont
présents avec les hashes exacts de la baseline `12f7826f…`, `d764dcce…` et
`ad43bf7c…`. Le composant BED-MESH-V2 `8c8c4aaf…` et `printer.cfg`
`36cfb7e7…` sont inchangés.

Le contrôle direct final confirme Klippy `ready`, `failed_components=[]` et
`warnings=[]`. La validation complète confirme `standby`, cibles zéro, runtime
fermé, Z accepté valide, profil `k1_p001_t055_r001_n06x06`, configuration
chargée `6 × 6` Lagrange et deux CFS connectés. Aucun chauffage, homing,
mouvement, mesh, extrusion, impression, commande CFS ou écriture Z n'a eu lieu.
Le rollback n'a pas été exécuté car il annulerait la pose réussie ; son backup
exact est vérifié et conservé. MATRIX-V1 est close. Ne pas lancer de calibration
depuis l'écran avant les gates séparées suivantes.

La dernière preuve navigateur a utilisé les octets locaux dont les trois hashes
correspondent exactement aux fichiers installés. Chrome a rendu le titre
`K1 Control — calibration`, la seule matrice `6 × 6 — maximum PRTouch fiable`,
le seul algorithme Lagrange, `0 / 1` passage et 36 points. Aucun choix
`9/11/15` n'est présent et aucun bouton n'a été actionné. Cette origine locale
sans API a été utilisée parce que l'origine authentifiée `4409` restait
interceptée par son ancien service worker Mainsail ; aucun cache navigateur n'a
été supprimé. La preuve structurée privée est conservée dans la capture.

## Reprise MATRIX-V1 du 23 août 2026

`G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-BED-MESH-V2` a été posée et validée
sous la capture
`20260823-151026-g4-k1-control-calibration-ui-prtouch-bed-mesh-v2` : composant
exact, `printer.cfg` inchangé, Moonraker prêt, `failed_components=[]`,
`warnings=[]`, profil robuste et Z conservés, deux CFS connectés, aucune action
physique.

Thomas a ensuite donné le GO exact MATRIX-V1. La revue locale obligatoire a
trouvé avant toute connexion deux restes de l'ancien contrat : le préflight
essayait encore d'accepter `9/11/15`, désormais refusés par le core, et la
validation cherchait d'anciens marqueurs statiques absents. Aucun SSH MATRIX,
backup, transfert, restart ou effet distant n'a eu lieu.

Le déployeur corrigé vérifie maintenant l'acceptation unique `6 × 6` Lagrange,
le refus de `3/4/5/9/11/15` et de `6 × 6` bicubique, le composant BED-MESH-V2,
`printer.cfg`, le profil robuste, le stockage Z, les deux CFS et
`server/info` avec listes d'échec et d'avertissement vides. Son hash est
`8491c09ddb96e440f7733ef9720280a0f77ec6a6193a093f00487cc922649b3f`.
La suite complète passe 220 tests, avec 3 ignorés connus.

Comme les commandes revues ont changé après le GO, aucune pose MATRIX n'est
autorisée par ce GO. La prochaine instruction requise est de nouveau
`GO G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1` sur le commit corrigé. L'ancienne
UI ne doit toujours pas être relancée.

Thomas a renouvelé ce GO sur le commit corrigé. Le préflight SSH réel s'est
arrêté avant toute écriture parce que l'API expose la phase terminale sûre
`rolled_back`, laissée par la restauration de campagne, alors que la garde
MATRIX n'acceptait encore que `idle`, `accepted` et `cancelled`. Les autres
gardes de la chaîne, le core et l'interface reconnaissent déjà `rolled_back`
comme état fermé. Le déployeur MATRIX accepte désormais ce quatrième état
uniquement si `busy=false`; aucune pose, aucun backup, aucun transfert et aucun
restart n'ont eu lieu sous ce GO. Le script revu ayant de nouveau changé, la
mission revient en `ATTENDRE_GO` pour le même GO exact sur le nouveau commit.

## Décision de clôture de la session

Thomas a interrompu la reprise avant le nouveau préflight SSH et demandé un
handoff complet vers une tâche locale neuve. Cette décision remplace l'accord
d'exécution donné juste avant pour l'alias SSH élevé : aucune commande SSH,
aucune pose et aucune action physique n'ont été lancées après cette
interruption. Aucun processus de mutation n'était en cours.

La tâche suivante ne doit recevoir ni historique copié, ni fork, ni nouveau
worktree, ni nouvelle branche, ni Goal implicite. L'ancien Goal reste bloqué
dans la tâche source et ne constitue plus une autorisation d'exécution. La
reprise est `ATTENDRE_GO` : relire les documents, vérifier Git et préparer le
préflight est permis ; toute connexion nécessitant un accès élevé et toute
mutation de la K1 attendent une instruction fraîche de Thomas.

L'état physique courant n'a pas été revérifié pendant cette clôture. Le dernier
état distant effectivement validé reste celui du rollback de la campagne au
point 37 : `standby`, cibles zéro, axes non référencés, profil robuste
`k1_p001_t055_r001_n06x06`, Z accepté `−0,04 mm`, stockage `ok` et deux CFS
conformes. La K1 a été annoncée disponible et plateau libre plus tard, mais ce
constat humain n'a pas été confirmé par un nouveau préflight. L'ancienne UI
encore installée ne doit pas être relancée.

## Vérifications de clôture

- dépôt : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit` ;
- branche de mission intégrée :
  `codex/g4-k1-control-calibration-ui-retry-safety-v1` ;
- commit de handoff : `4a47aff162f88ddfa067d81d6b6607f5d20caa5d` ;
- commit d'intégration vérifié sur `main` local et distant :
  `4e4027e2a73b30dca69844c229712ec046150113` ;
- PR GitHub : `#36` ; sa référence `head` reste lisible et sa référence `merge`
  a disparu après l'intégration directe ;
- branche de mission locale et distante : **supprimées après preuve
  d'ascendance** ;
- worktrees : un seul checkout principal, propre, sur `main` ;
- suite locale : **OK**, 220 tests réussis, 3 ignorés connus ;
- parse de tous les scripts PowerShell : **OK** ;
- vérification réelle de la K1 pendant la clôture : **non exécutée**, par
  décision de Thomas ;
- client GitHub `gh` : **KO authentification** (`HTTP 401`) ; l'intégration a
  néanmoins été réalisée par le transport Git configuré, puis vérifiée par SHA
  local, SHA distant et ascendance.

## Message obligatoire au début de la prochaine session

Dire clairement à Thomas, avant toute proposition d'exécution :

- **l'autonomie calibration n'est pas encore atteinte** : l'essai `9 × 9` a
  prouvé une limite de trente-six contacts par séquence PRTouch et l'interface
  sûre `6 × 6 / 1 mesh` doit encore être reposée puis validée ; l'ADR-013 et le
  prototype hors imprimante ouvrent ensuite un vrai mode précision composite
  `11 × 11` en quatre sous-grilles, mais aucune acquisition composite n'est
  encore installée ni qualifiée sur la K1 ;
- **l'autonomie production n'est pas encore atteinte** : Orca, `START_PRINT`,
  l'ancien `+0,27 mm` et les températures CFS ne sont pas encore basculés vers
  le nouveau contrat ;
- le mesh robuste V2 et le Z `−0,04 mm` sont qualifiés, persistés et validés ;
  FIRST-CALIBRATION-V2 est close et ne doit pas être rejouée ;
- l'interface ne sera déclarée « nickel sans Codex » que lorsque Thomas pourra
  choisir les paramètres, lancer, comprendre le statut, enregistrer, annuler et
  restaurer depuis l'écran, puis imprimer normalement depuis Orca sans commande
  manuelle ni correction cachée.

Ne pas présenter Mainsail `v2.18.2`, la console ou les macros `KCTRL_*` comme
l'interface quotidienne terminée.

## Audit haute confiance après la panne au point 37

L'analyse locale et en ligne est consignée dans
`docs/19-audit-calibration-haute-confiance-k1-max-cfs.md` et l'ADR-013. La panne
borne une séquence PRTouch V2 à 36 contacts ; elle ne borne pas le profil Bed
Mesh que Klipper peut charger. Les 36 paires de seuils de cette machine sont
toutes identiques et les six maillages FIRST-CALIBRATION-V2 prouvent que le
compteur repart à zéro entre séquences.

Le prototype `packages/k1-control-v1/composite-mesh-v1/compose_mesh.py` fusionne
quatre sous-grilles `6 × 6`, `5 × 6`, `6 × 5`, `5 × 5` en 121 positions réelles
`11 × 11`. Il refuse plus de 36 contacts par passage, les sessions physiques
différentes, un restart Klipper, les trous, doublons et valeurs non finies. La
suite complète est verte : 203 tests, 3 ignorés connus.

Cette voie doit utiliser le moteur Bed Mesh standard de façon bornée sans
remplacer la commande stock, sans `pr_version: 1` et sans restart entre les
quatre sous-grilles. La prochaine gate physique de cette voie est une unique
sous-grille décalée avec rollback automatique ; le profil complet n'est lancé
qu'après cette preuve. Le mode `15 × 15` stock est refusé : neuf passages et
plus de quarante minutes de palpage ne sont pas raisonnables sans gain prouvé.

Le package physique `composite-subgrid-v1` est désormais préparé hors
imprimante. Il ne peut demander que la partition impaire/impaire `5 × 5`, 25
contacts de `34` à `266 mm`, après gate exacte et confirmation du plateau. Sa
pose ne redémarre que Moonraker ; son essai coupe les chauffes, recharge le
profil robuste et redémarre Klipper uniquement après la capture pour nettoyer
la session. Les 14 tests ciblés et la suite complète de 220 tests sont verts,
avec 3 ignorés connus. Détails :
`docs/20-g4-k1-control-composite-subgrid-v1.md`.

Un test de chaîne supplémentaire rejoue les hashes distants attendus dans
l'ordre BED-MESH-V2 → MATRIX → RETRY-SAFETY → PRESETS → COMPOSITE. Il prouve
que chaque baseline correspond exactement à la sortie précédente. Il montre
aussi que PRESETS est déjà produit bit pour bit par MATRIX + RETRY-SAFETY ; son
déployeur rend donc un succès idempotent sans écriture distante dans cet état.

Dans la reprise courante, le préflight final de campagne a joint la K1 et a
refusé comme prévu l'ancien core encore installé. Le préflight individuel
suivant n'a pas atteint la machine : le sandbox Windows exécute SSH sous
`CodexSandboxOnline`, sans la configuration de `C:\Users\janko\.ssh`, puis la
plateforme a refusé l'escalade parce qu'elle jugeait l'alias ambigu. Il faut une
approbation technique explicite après cet avertissement pour rendre visible
l'alias `k1max-root` déjà qualifié ; aucun contournement par adresse n'est
autorisé.

## CALIBRATION-PATH-V1 installé et validé

Thomas a nommé `G4-K1-CONTROL-CALIBRATION-PATH-V1` sans préfixe `GO`. Cette
instruction a sélectionné la préparation du lot ; elle n'a autorisé aucune
connexion ni mutation de la K1.

Le candidat ajoute un overlay séparé au runtime existant. Il impose une
descente centrale `5 → 2 → 1 → 0,5 → 0,3 → 0,2 → 0,15 → 0,1 mm`, ajuste le Z
seulement à la dernière hauteur, repositionne physiquement la buse à `0,1 mm`,
exige une confirmation puis une remontée de `5 mm` avant acceptation ou
annulation. Il n'a ni extrusion, ni chauffe, ni CFS, ni valeur Z par défaut.

La pose revue ajoute seulement
`/usr/data/printer_data/config/k1-control-calibration-path.cfg`, une inclusion
après le runtime puis un `RESTART` hôte. Sa validation appelle uniquement une
garde qui doit refuser et prouve que position, origine et cibles de chauffe ne
changent pas. Le rollback préserve entièrement le runtime installé. Détails :
`docs/17-g4-k1-control-calibration-path-v1.md` et ADR-005.

Le déployeur reste en `Plan` par défaut et toute action distante exige
`-Execute -Gate G4-K1-CONTROL-CALIBRATION-PATH-V1`. La pose n'est pas
autorisée avant le GO exact `GO G4-K1-CONTROL-CALIBRATION-PATH-V1` portant sur
le commit figé.

Thomas a envoyé ce GO. Le premier préflight a échoué avant mutation parce que
le candidat Base64 rendait la commande SSH trop longue pour Dropbear. Le
transport du parse Jinja passe maintenant par stdin, sans fichier distant. Le
préflight corrigé de la capture
`20260822-113503-g4-k1-control-calibration-path-v1` est vert : machine exacte,
`standby`, chauffes à zéro, runtime `ready=1`/`empty`, aucun Z accepté, overlay
absent, deux CFS `1.1.3`, fondation et parse Jinja exact conformes. Les axes
étaient référencés avant restart, état admis. Aucun backup, fichier, restart,
G-code ou état distant n'a été créé ou modifié.

La commande revue a changé après le GO consommé. Aucun `Deploy` n'a été lancé.
La prochaine autorisation doit renouveler exactement
`GO G4-K1-CONTROL-CALIBRATION-PATH-V1` sur le commit corrigé.

Thomas a renouvelé ce GO. La capture
`20260822-115608-g4-k1-control-calibration-path-v1` a obtenu un préflight frais
vert, créé et vérifié le backup, posé l'overlay et envoyé le `RESTART`. La
validation a toutefois interrogé le socket Klipper pendant sa transition et a
déclenché le rollback. Les fichiers ont été restaurés immédiatement ; le chemin
est resté un court moment chargé uniquement en mémoire car le `RESTART` du
rollback avait rencontré le même socket indisponible.

Après audit de cet état précis, l'action `Rollback` a été reprise sur le backup
exact et a obtenu `ROLLBACK_CALIBRATION_PATH_V1_OK`. Le préflight final a obtenu
`PREFLIGHT_CALIBRATION_PATH_V1_OK` : overlay absent, `printer.cfg` exact, axes
non référencés, chauffes à zéro, runtime `ready=1`/`empty`, deux CFS et fondation
conformes. Aucun mouvement, homing, chauffage, mesh ou état Z n'a eu lieu.

Le déployeur attend maintenant de façon bornée que le socket réponde avant la
lecture des objets après pose et avant le `RESTART` de rollback. Ce changement
de commande consomme l'autorisation précédente : une nouvelle pose exige encore
un GO exact renouvelé. Le préflight réel du déployeur corrigé est vert en
lecture seule.

Thomas a renouvelé une dernière fois le GO. La capture
`20260822-124207-g4-k1-control-calibration-path-v1` a obtenu le préflight frais,
`DEPLOY_CALIBRATION_PATH_V1_OK` puis
`VALIDATE_CALIBRATION_PATH_V1_OK`. Les quatre empreintes sont exactes, l'overlay
et son unique include sont retenus, le runtime reste `ready=1`/`empty`, les axes
sont non référencés, les chauffes à zéro et les deux CFS sont connectés. La garde
à vide a refusé sans changer position, origine Z ou cibles. Aucun chauffage,
homing, mouvement, extrusion, mesh, réglage ou enregistrement Z n'a été exécuté.

## Current state

Thomas rejected `G4-ZSAFE-START-V1` before deployment. Son `+0,27 mm` fixe, son
mesh `default` unique et son nettoyage manuel ne constituent pas un système
pérenne. Ce nom ne peut plus recevoir de GO. Les artefacts restants sont marqués
`rejected_never_deploy` et le macro échoue volontairement s'il est chargé.

La cible active est un produit cohérent `K1-CONTROL-V1` :

- interface quotidienne simple `K1 Control` ;
- Mainsail comme vue experte candidate, sur Moonraker épinglé et sécurisé ;
- réglage Z pendant une session de calibration, puis sauvegarde explicite ;
- Z accepté conservé après fin/redémarrage et invalidé par une nouvelle
  calibration de référence ;
- meshes par plaque et plage thermique, plus mesh adaptatif par travail ;
- ordre thermique/nettoyage/référence/mesh/Z/CFS/purge verrouillé ;
- températures dynamiques respectées sur les deux CFS ;
- profil Orca complet et versionné.

Le système est conçu et testé comme un tout, puis sera posé par étapes pour
garder un rollback simple. Aucun installateur communautaire n'est accepté tel
quel. Le post-traitement Orca actuel reste inchangé jusqu'à preuve complète de
son remplacement.

Le prototype complet hors imprimante est maintenant vert. L'écran parle à un
faux Moonraker sur `127.0.0.1` et ce faux service applique le moteur d'état
Python. Les 17 scénarios obligatoires passent, dont le blocage d'une purge trop
tôt, T0 vers T5 entre les deux CFS, l'invalidation Z et le rollback SHA-256.

La fondation V3 + PATHS-V1 a maintenant terminé son observation retenue. Thomas
a lancé manuellement l'impression normale à 12:48 et confirmé à la fin : qualité
correcte, un seul PLA, aucune intervention. Le premier observateur local a été
interrompu à 15:07 ; le journal persistant couvre le trou jusqu'à 18:43 sans
arrêt Klipper/MCU, perte de communication, trace Python ou erreur interne. Le
second observateur s'est fermé à 20:31:56 avec `exit_code=0`, puis la validation
en lecture seule a rendu `VALIDATE_PATHS_V1_OK`.

Le vrai adaptateur Moonraker reste fermé par défaut et reconnaît maintenant les
seules commandes structurées du candidat Z/mesh. Les sources Klipper exactes
`save_variables.py`, `gcode_macro.py`, `delayed_gcode.py` et `bed_mesh.py` ont
été copiées en lecture seule et vérifiées dans une capture privée ignorée.

Le runtime public `packages/k1-control-v1/z-mesh-runtime-v1/` ajoute une seule
structure persistante Z avec valeur précédente et contexte, les sessions
provisoires, l'invalidation, le préchauffage plateau/buse, le homing explicite,
les matrices 3–25 avec interpolation compatible, le commit mesh séparé et la
garde de mouvements bas. Il ne remplace pas `START_PRINT`, n'appelle aucun CFS
et n'extrude pas. Il est installé depuis la capture finale du 2026-08-22. Le
`save_variables.py` exact a été écarté ;
le stockage original contrôle le schéma et la somme, écrit en `0600`, synchronise,
remplace atomiquement et conserve une copie précédente sans restauration
silencieuse.

Thomas a envoyé le GO exact pour cette tranche. Le premier préflight s'est
arrêté sans mutation : les appels Python qui recevaient des arguments omettaient
le marqueur stdin `-`, donc Python cherchait un fichier nommé `0`. Les deux
formes concernées sont corrigées et un test dédié les verrouille. Le second
préflight, strictement en lecture seule, est vert sous la capture privée
`20260821-212431-g4-k1-control-z-mesh-runtime-v1`. Il confirme la machine au
repos, les chauffes à zéro, l'empreinte initiale, les cibles absentes, la
fondation et les deux CFS. Les axes sont encore référencés et `Base` est le mesh
transitoire actif, états admis avant le redémarrage hôte de la future pose.
Aucun fichier distant, backup, G-code, commande Klipper ou service n'a été
modifié. La commande revue ayant changé après le GO, le déploiement attend un GO
exact renouvelé.

Thomas a renouvelé ce GO. La capture
`20260821-213732-g4-k1-control-z-mesh-runtime-v1` a passé son préflight et
vérifié le backup, puis posé le runtime et redémarré l'hôte Klipper. La
validation a refusé l'état neuf : `integrity=empty` suivait la branche invalide
et laissait `ready=0`. La garde `K1_PRODUCTION_ASSERT_ARMED` n'a pas été appelée.

Le rollback automatique a retiré le runtime, mais son contrôle immédiat a vu T1
encore déconnecté. Le restart avait aussi normalisé seulement les espaces des
blocs générés `bed_mesh default` et `auto_addr`. Une complétion bornée a restauré
le backup exact sans autre restart. Le préflight final a confirmé le runtime
absent, le hash initial, Klipper `standby`, les axes non homés, les chauffes à
zéro, T1/T2 `1.1.3` et la fondation intacte. Aucun mouvement, chauffe, extrusion,
ordre CFS, calibration, impression, firmware restart ou reboot n'a eu lieu. Le
mesh transitoire `Base` a été perdu au restart ; `default` est de nouveau actif.

Le candidat offline possède désormais une branche `empty` prête pour calibrer
mais fermée à la production, une attente de stabilisation CFS de 60 secondes et
une seconde restauration du backup exact après le restart de rollback. Son hash
config est `3b0e5215d9bd58a343c57a681668ef1e466465980cceac3b1fd5944fec806f96`.
La suite exécute 96 tests : 95 passent localement et les 17 templates, dont le
rendu `empty`, passent sur le Python/Jinja exact de la K1.

Thomas a renouvelé une nouvelle fois le GO exact. La capture
`20260821-224828-g4-k1-control-z-mesh-runtime-v1` a passé son préflight et
vérifié le backup. Le runtime a été chargé, mais son état `ready` est resté à
zéro. Le journal a prouvé que le parseur G-code de cette K1 tronque
`K1_CONTROL_LOAD_STATE` en `K1`, commande inconnue : un chiffre placé au milieu
d'un nom étendu n'est pas accepté.

Le rollback a retiré le runtime et l'inclusion. Un `CXSAVE_CONFIG` Creality
tardif a ensuite normalisé les espaces des blocs générés. La comparaison locale
n'a trouvé aucun changement de valeur. Une complétion bornée a restauré le
backup exact sans restart, puis le préflight final a confirmé le runtime absent,
le hash initial, `default`, `standby`, axes non homés, chauffes à zéro, T1/T2
`1.1.3` et la fondation intacte. Aucun mouvement, homing, chauffe, extrusion,
ordre CFS, calibration, impression, firmware restart ou reboot n'a eu lieu.

Le candidat offline emploie désormais `KCTRL_*` dans le runtime, le stockage,
l'adaptateur et les futurs contrats Orca. Un test rejoue le parseur exact. Le
rollback attend la reconnexion CFS et une fenêtre silencieuse avant sa dernière
restauration, puis revérifie le hash après trois secondes. Les hashes courants
sont `1590b918dcdfe70e801c0be40fee4f19ab6b1e2dfa93936975b88aed5d4b1c79`
et `696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede` ;
la suite locale passe `98/98` et l'environnement exact de la K1 retourne
`K1_EXACT_RUNTIME_OK templates=17 commands=18` en mémoire.

Thomas a renouvelé une troisième fois le GO exact. La capture
`20260822-004338-g4-k1-control-z-mesh-runtime-v1` a passé le préflight, vérifié
le backup et chargé les objets `KCTRL_*`. Le démarrage différé a bien exécuté
`KCTRL_LOAD_STATE`, puis la première affectation texte a échoué avec
`Unable to parse 'empty' as a literal`. Le parseur Creality applique
`shlex.split` avant `ast.literal_eval` : `VALUE='empty'` perd ses guillemets et
arrive comme nom Python nu.

Le rollback automatique renforcé a retiré le runtime, attendu les deux CFS et
la fenêtre silencieuse, puis restauré et revérifié le backup exact. Le préflight
final confirme runtime absent, hash initial, `default`, `standby`, axes non
homés, chauffes à zéro, T1/T2 `1.1.3` et fondation intacte. Aucun mouvement,
homing, chauffe, extrusion, ordre CFS, calibration, impression, firmware
restart ou reboot n'a eu lieu.

Les 24 affectations texte utilisent désormais des littéraux protégés comme
`VALUE='"empty"'`. Le déployeur sauvegarde aussi son dernier snapshot avant
rollback si `ready` reste à zéro. Le hash config courant est
`dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113` ; le
module reste à
`696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede`.
La suite exécute 99 tests : 98 passent, et le contrôle exact en mémoire retourne
`K1_EXACT_RUNTIME_OK templates=17 commands=18 string_values=24`.

Thomas a renouvelé le GO exact. La capture
`20260822-011022-g4-k1-control-z-mesh-runtime-v1` a passé son préflight, vérifié
le backup et terminé par `DEPLOY_Z_MESH_RUNTIME_V1_OK`. Le runtime a chargé
l'état vide avec `ready=1`, puis `KCTRL_PRODUCTION_ASSERT_ARMED` a refusé comme
prévu sans changement de position, origine Z ou cible de chauffe.

La validation indépendante a d'abord vu une empreinte `printer.cfg` normalisée
par le `CXSAVE_CONFIG` différé de Creality. Le diff complet des copies privées
montre uniquement l'indentation des blocs générés `bed_mesh default` et
`auto_addr`, sans changement de valeur, section ou inclusion. La comparaison
normalisée obtient `PRINTER_CFG_NORMALIZED_EQUIVALENCE_OK`; le validateur épingle
les deux empreintes exactes et ne réécrit pas la machine.

La validation indépendante finale retourne
`VALIDATE_Z_MESH_RUNTIME_V1_OK`. État retenu : runtime installé, une inclusion,
`standby`, axes non homés, chauffes à zéro, `default`, T1/T2 `1.1.3`,
`ready=1`, `integrity=empty`, `accepted_z_valid=0`,
`block_reason=no_accepted_z`, `low_moves_armed=0` et fondation intacte. Aucun
mouvement, homing, chauffe, extrusion, ordre CFS, calibration, impression,
firmware restart, reboot ou rollback n'a eu lieu.
La suite finale exécute 100 tests : 99 passent et le contrôle Jinja local
ignoré reste couvert sur l'environnement exact de la K1.

La pile est figée : Moonraker MIPS embarqué au commit
`fccffa96c63ed77dc3953e18615e9fe9cd3d69ea`, nginx MIPS du même paquet et
Mainsail `v2.18.2`. Les trois archives ont été réellement assemblées et vérifiées
dans un bundle local temporaire. Aucun binaire communautaire n'est publié dans
Git.

Thomas a autorisé exactement `G4-K1-CONTROL-FOUNDATION-V1`. Son préflight réel
a confirmé la bonne machine, `standby`, les chauffes à zéro, T1/T2 connectés,
les ressources et l'absence des cibles. Il a ensuite détecté l'absence de
`logrotate` et de `/etc/logrotate.d`, prérequis obligatoire de V1. La pose s'est
arrêtée avant toute mutation ; V1 est définitivement fermée.

Thomas a ensuite autorisé exactement `G4-K1-CONTROL-FOUNDATION-V2`. Les essais
réels ont corrigé les écarts SCP/Dropbear, nginx/Buildroot, permissions,
fournisseur Moonraker, arrêt de service et origine WebSocket. Mainsail a chargé
le tableau de bord réel par tunnel, puis le test a prouvé que la version
`v2.18.2` ne sait pas créer ni utiliser un compte Moonraker. V2 a été rollbackée
et son nom est fermé. Aucun port LAN n'a été ouvert.

Thomas a choisi `CHOIX AUTH — NGINX`. Le remplacement
`G4-K1-CONTROL-FOUNDATION-V3` garde Moonraker en boucle locale et porte le compte
sur nginx. Le module MIPS requis est prouvé hors imprimante. Le mot de passe est
saisi deux fois en local, seul un hachage SSHA salé est transmis, les requêtes
anonymes doivent recevoir `401`, et les identifiants sont retirés avant le proxy
vers Moonraker. Les GO V3 renouvelés ont permis de corriger, avec rollback entre
chaque KO, le transport stdin, les droits `root:www-data` du fichier et du
dossier parent, puis la transition nginx vers l'écoute LAN. La capture finale
`20260821-015722-g4-control-foundation-v3` est installée et validée. Thomas a
créé puis vérifié son compte dans le vrai tableau de bord Mainsail. Moonraker
reste sur `127.0.0.1:7125` et Mainsail authentifié écoute sur `0.0.0.0:4409`.
Le raccourci `Ouvrir Mainsail K1 Max` sur le Bureau crée automatiquement le
tunnel SSH sécurisé et ouvre Mainsail sans commande manuelle.

Après connexion, Moonraker a affiché deux avertissements : son data path crée
`/usr/data/k1-control-v1/state/config` et `state/gcodes`, alors que la pile
Creality active utilise `/usr/data/printer_data/config` et
`/usr/data/printer_data/gcodes`. Une inspection distante bornée et sans mutation
a confirmé que les deux dossiers Moonraker sont présents et vides. Le code exact
installé produit ces avertissements lorsque les chemins ne désignent pas les
mêmes dossiers. La connexion Mainsail → Moonraker → Klipper fonctionne ; seule
l'intégration du gestionnaire de fichiers est incomplète.

Il ne faut pas appliquer la suggestion générique de modifier
`[virtual_sdcard]`. La correction retenue devait garder les chemins Creality,
relier les racines Moonraker selon la méthode officielle, rendre `config` non
modifiable par l'API et traiter explicitement le pouvoir d'écriture restant sur
`gcodes`. Le rapport public est dans
`experiments/p4/20260821-moonraker-path-warnings-read-only-report.md`.

Après revue du document 15, du déployeur et des tests, Thomas a renouvelé
exactement `GO G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1`. La capture
`20260821-111001-g4-control-foundation-v3-paths-v1` a obtenu un préflight vert,
sauvegardé l'état initial, posé les deux liens attendus et redémarré uniquement
Moonraker. Le dernier message du wrapper local a été perdu après deux heartbeats ;
Codex n'a pas relancé la mutation. Les preuves finales étaient présentes et une
commande séparée en lecture seule a obtenu `VALIDATE_PATHS_V1_OK`.

L'API expose maintenant `config=r` vers `/usr/data/printer_data/config` et
`gcodes=rw` vers `/usr/data/printer_data/gcodes`. Moonraker ne rapporte aucun
avertissement, Klipper est prêt et `standby`, les chauffes sont à zéro, les axes
ne sont pas homés, les deux CFS `1.1.3` sont connectés, nginx et les interfaces
Creality sont intacts. Aucun G-code, mouvement, chauffe, calibration, impression,
redémarrage imprimante ou rollback n'a été exécuté.

Le contrat, l'architecture et la comparaison des outils sont dans les documents
10, 11, 13, 14 et ADR-004. Les essais V2 et les tentatives V3 en KO ont
rollbacké uniquement les nouveaux chemins de fondation. La pose V3 finale
conserve les deux services dédiés et les ports prévus. Aucun profil Orca actif
ni comportement d'impression n'a été modifié.

Une lecture distante bornée a relevé environ 209 Mio de RAM totale, 118 Mio
disponibles, Python 3.8.2, 4,2 Gio libres et aucun port/processus Moonraker. La
marge mémoire impose une pile minimale et un test de durée ; le rapport public
anonymisé est dans `inventory/redacted/20260820-control-foundation-capacity/`.

Un écran `K1 Control` sans dépendance, un moteur d'état Python pur, un faux
Moonraker, le contrat Orca et la matrice exécutable sont présents sous
`prototype/`, `orca/` et `tests/`. Les vues bureau/mobile et les actions
calibration, sauvegarde, redémarrage et invalidation ont été vérifiées sans
erreur JavaScript. La suite courante exécute 131 tests : 129 passent et deux
contrôles Jinja locaux sont ignorés. Les 17 templates du runtime installé ont
déjà passé le Python/Jinja exact de la K1. L'overlay installé a également passé
son parse exact en mémoire avant toute écriture. Les noms de
commandes des deux lots sont contrôlés contre le parseur Creality exact.

## Preuves historiques utiles

The private intake is ready under
`inventory/raw/user-inputs/20260820-full-system-audit/`. Its instructions request
an Orca printer-config bundle, existing 3MF projects and G-codes, exact custom
G-code text, photos/notes and any already-held recovery artefact. Everything in
that path is ignored by Git.

Thomas has now supplied the active individual Orca profiles, the Z
post-processor, five 3MF projects and six candidate G-codes. The two private
capture batches contain 24 and 13 files respectively; every copy passed a local
SHA-256 comparison and no source file was changed.

Offline inspection selects P1-SINGLE, P2-FIVE-OBJECTS and
P3-ONE-MERGED-OBJECT as the first bounded session. P2 and P3 share all 639
recorded settings, estimated duration, material use and layer count; their
useful difference is five separate objects versus one assembled object. Ironing
is active on all three and does not invalidate the first-layer comparison.

Thomas supplied a corrected `P5-CFS-ONE-CHANGE` containing one intended `T0` to
`T1` transition. Its private copy and hashes are recorded; the first alternating
version remains private evidence only.

Passive session `20260820-154056-p123` is complete. It captured P1, P2, P3, P4,
two P5 attempts and P1 PETG. The trace ended with all heater targets at zero;
Codex stopped only the passive observer after Thomas confirmed completion.

The decisive Z finding is runtime evidence, not an inference from the file. On
P4, the visible Z stays at `0.00` through the stock startup and only becomes
`+0.27 mm` when the post-processor executes afterward. The current workaround
cannot protect the preceding purge. Live Z clicks call `Z_OFFSET_APPLY_PROBE`,
but P3 and PETG both end by applying the exact inverse and preparing `0.000` for
persistence. P1 PETG finished at `+0.38 mm`, `+0.11 mm` above its file baseline,
before that value was erased.

P2 and P3 share all 639 recorded settings and produced no reported visible
difference between separate and assembled objects. One `+0.010 mm` live Z click
occurred during P3, so this is not a fully untouched pair. It does not disprove
the historical large shifts and gives no evidence that object count alone
triggers them.

The first P5 attempt had three pauses after a likely filament break and is
excluded. The second completed without a pause. Its nozzle targets were
`115 -> 220 -> 205 -> 220 -> 0 °C`: the startup override is confirmed, while
the final `220 °C` cannot distinguish G-code from CFS ownership because both
request the same value.

The baseline acquisition, targeted source follow-up, physical session `20260819-185157-g3-aba` and separate `G4-SSH-KEY` deployment are complete. Thomas performed the prints and mechanical adjustments. Codex changed only root SSH access by adding one dedicated public key; no printer behaviour, service or configuration was changed. Raw captures remain local and ignored; only redacted inventories and conclusions are publishable.

Passwordless SSH is now available through local alias `k1max-root`. It selects the dedicated ECDSA P-256 key and forbids password fallback. Two independent final connections passed. A future password prompt must be treated as a failure and diagnosed, not shown to Thomas as a normal step.

Read-only session `20260819-215124-long` started from standby, captured one complete long production job and stopped automatically after the machine returned to standby. The observer used one persistent Klipper subscription and followed only new log data. It sent no print, movement, heating, calibration or configuration command.

This session closed the pressure-advance observability gap: startup applied `0.044`, then the print file restored `0.03`, which remained active through the CFS refill and to the end. The CFS did not overwrite pressure advance during this refill.

The automatic equivalent-PLA refill did overwrite temperature. Runout paused the print, selected another PLA slot and resumed in about 2 minutes 54 seconds. The resumed target returned to `220 °C` and stayed there until Thomas manually restored `190 °C`. Visible Z origin remained `+0.27 mm` throughout, with no live correction reported.

The same defect occurs during startup. The job supplies `190 °C` for the first layer and later uses `195 °C`, but the first CFS tool operation reports that it cannot read the purge speed and falls back to a `220 °C` purge. The file only regains control after the CFS load and purge. Thomas judged the final part broadly correct; granular ironing remains a separate OrcaSlicer-tuning hypothesis.

Read-only follow-up proved that the production file contains no temperature
command at `220 °C`. The generic PLA entry used by the CFS stores `220 °C`, while
per-slot state stores material type and colour but not a slot-specific
temperature or pressure advance. During refill, stock `RESUME` restores
`195 °C`, then the file reader replays the new physical tool and the compiled
CFS module reapplies `220 °C` afterward.

The static `G4-CFS-TEMP-PLA` candidate was rejected by Thomas before deployment.
It hard-coded Geeetech PLA and `190/195 °C`, so it did not meet the production
need. Its deployable files were removed from `main`; no printer file or service
was changed.

The accepted requirement is now explicit: while a print is active, G-code or
Thomas owns nozzle temperature. Equivalent refill preserves the active target.
An intentional material change receives the next tool's temperature from the
G-code. The CFS database may not silently replace either value.

Codex has permanent authority to complete all normal Git and GitHub operations for this repository, including push, pull-request management, fusion into `main` and cleanup, without requesting another `GO`. This authority does not replace the printer mutation gates.

## Confirmed acquisition outcomes

- firmware `2.3.5.34`, Buildroot 2020.02.1, Linux 4.4.94 MIPS;
- manufacturing identity and runtime selector report S12 structure 0;
- `/etc/ota_info` still reports S11 and is classified as inconsistent OTA metadata;
- active configuration and four includes mapped;
- CFS temperature value `Tn_extrude_temp: 220` identified;
- active saved Z offset at zero and one transient historical `-0.025` identified;
- startup, CFS, homing and levelling macro chains indexed;
- readable `CX_*`, `CXSAVE_CONFIG`, `G28` and PR Touch implementations captured and mapped;
- CFS `BOX_*` implementation identified as a compiled `box_wrapper` module;
- `G28` confirmed to establish Z through five PR Touch samples, their median and `self_z_offset`;
- persistent storage and large Klipper log footprint documented;
- no remote write performed.

## FIRST-CALIBRATION-V1 préparé hors imprimante

Le candidat `G4-K1-CONTROL-FIRST-CALIBRATION-V1` est maintenant présent sous
`packages/k1-control-v1/first-calibration-v1/`. Il n'installe aucun nouveau
fichier : son pilote local orchestre seulement les commandes déjà installées,
par checkpoints séparés.

Le contexte est figé : `PEI_TEXTURED_A` ID `1`, plateau `55 °C`, buse `140 °C`,
stabilisation `200 s`, nettoyage stock borné jusqu'à `180 °C`, homing après
nettoyage, deux meshes `6 × 6` Lagrange sur `5–295 mm` et seuil absolu maximum
`0,025 mm` sur les 36 points. Un KO s'arrête sans troisième mesh automatique.

Le second mesh qualifié pourra être enregistré sous
`k1_p001_t055_r001_n06x06`, puis la session Z partira du seed neutre explicite
`0,0 mm` et suivra les paliers déjà installés. Chaque mouvement bas reste une
action distincte. L'acceptation exige confirmation humaine et remontée de
`5 mm`.

Le mode `Plan` de `scripts/run-k1-control-first-calibration-v1.ps1` est purement
local. Les actions distantes exigent le GO exact, la capture privée et les
checkpoints précédents. `Cancel` ferme le Z provisoire et conserve le mesh ;
`Rollback` restaure le `printer.cfg` exact et l'état Z vide tout en conservant
le runtime et le chemin installés. Détails : document 18 et ADR-006.

Thomas a ensuite envoyé le GO exact. La capture
`20260822-140602-g4-k1-control-first-calibration-v1` a passé le préflight, créé
et vérifié le backup, puis terminé la préparation et le premier mesh. Le second
mesh a été exécuté une seule fois et sa qualification est KO : maximum
`0,062125 mm`, moyenne `0,018049 mm`, seuil `0,025 mm` sur 36 points.

L'arrêt prévu a coupé les chauffes. Aucun troisième mesh, profil persistant,
session Z ou état Z n'a été produit. Un contrôle final en lecture seule a
confirmé la base exacte, le profil cible absent, le stockage Z absent,
`standby` et les cibles à zéro avant de signaler les axes `xyz` encore
référencés. Le GO est consommé et ne couvre aucun rerun.

## FIRST-CALIBRATION-V2 exécutée jusqu'à la gate physique finale

L'analyse du module PR Touch exact et du journal privé a retrouvé 209 contacts
pour 72 points. Les gros faux contacts sont filtrés, mais deux meshes bruts ne
suffisent pas à prouver la répétabilité point par point. V2 ne modifie pas le
constructeur : il impose exactement six meshes, deux groupes indépendants de
trois réduits par médiane, puis trois limites simultanées : moyenne absolue
`0,020 mm`, RMS `0,025 mm` et maximum `0,060 mm`. Il n'existe aucun septième
passage automatique. Le candidat final est la médiane des six mesures et n'est
chargé, relu puis persisté qu'après qualification.

Thomas a ensuite envoyé le GO exact. La capture
`20260822-160948-g4-k1-control-first-calibration-v2` a passé le préflight frais,
créé et vérifié le backup, puis obtenu `PREPARE_FIRST_CALIBRATION_V2_OK` à
`55/140 °C` avec `200 s`. Les six meshes ont été exécutés exactement une fois.
La qualification est acceptée sur 36 points : moyenne absolue
`0,010788694 mm`, RMS `0,013996452 mm` et maximum `0,034352 mm`.

L'endpoint `update_mesh` a chargé et généré le profil robuste sans redémarrer
Klipper, alors que le premier validateur attendait à tort la perte du homing.
Le diff exact a prouvé que seule la section `K1_TRANSIENT` et ses 36 valeurs
avaient été ajoutées. Une reprise bornée a vérifié le hash, le backup, les
composants installés, l'état Z vide et la matrice avant d'envoyer la commande
déjà revue `KCTRL_MESH_COMMIT`. Le profil final
`k1_p001_t055_r001_n06x06` est conservé, le transitoire est absent et le diff
final ne contient que cette section générée. Le pilote attend désormais le
comportement réellement observé de `update_mesh`, avec un test de
non-régression et une nouvelle empreinte dans le manifeste.

Le chemin Z a d'abord été annulé sans observation, puis repris avec Thomas
présent sans refaire les six meshes. Une pile de dix épaisseurs a évalué la cale
papier à `0,09 mm`. Les pas provisoires ont trouvé une friction nette à
`−0,05 mm`; le retour à `−0,04 mm` a rendu la cale libre, ce qui encadre le jeu
visé de `0,10 mm`. Thomas a confirmé ce constat. La buse a été parquée avant le
commit atomique. `ACCEPT_FIRST_CALIBRATION_V2_OK` a enregistré `−0,04 mm` puis
coupé les chauffes.

Le premier `Validate` a signalé un faux KO documentaire : le pilote cherchait
`[bed_mesh ...]`, mais Klipper persiste réellement `#*# [bed_mesh ...]`. Le
correctif local, son test et la nouvelle empreinte du manifeste ne changent
aucune commande imprimante. La relance en lecture seule a obtenu
`VALIDATE_FIRST_CALIBRATION_V2_OK`. État final : `standby`, cibles zéro,
stockage `ok`, `accepted_z_valid=1`, `accepted_z_offset=-0,04`,
`session_active=0`, chemin `committed` non armé, profil robuste présent, deux
CFS et fondation conformes. La copie persistante de `printer.cfg` garde le hash
`36cfb7e71180268841ab5cedd31628c8d9953ba437c47662ced16df18bb1bacd`.

## CALIBRATION-UI-V1 préparée hors imprimante

Le candidat séparé `G4-K1-CONTROL-CALIBRATION-UI-V1` ajoute hors imprimante un
petit composant au Moonraker épinglé et une page statique `/k1-control/`. Les
choix plaque, températures, stabilisation, matrice, interpolation et seed Z y
sont réels. Le flux serveur survit à la fermeture du navigateur, exécute les six
meshes, guide les paliers Z et expose enregistrer, annuler, restaurer le Z ou
restaurer le backup complet. La stabilisation est annulable ; un homing,
nettoyage ou mesh déjà engagé finit seulement son opération bornée avant arrêt.

La pose UI future a un write-set exact : deux sources Python, deux caches
`cpython-38`, trois fichiers statiques et `moonraker.conf`. Elle sauvegarde la
configuration puis redémarre uniquement le Moonraker dédié. Elle ne lance
aucune calibration. Son paquet, ADR-008, manifeste, déployeur et tests sont
préparés. L'import exact sur la K1 reste dans le préflight de la pose.

La revue après FIRST-CALIBRATION-V2 a trouvé deux incompatibilités avant pose :
le chemin fermé réel est `committed`, pas seulement `idle`, et le `curl`
Creality signale `-fsS` comme options invalides tout en renvoyant le corps. Le
déployeur et le contrôleur n'acceptent désormais que `idle`, `committed` ou
`cancelled`, avec `motion_armed=0`. Les lectures Moonraker utilisent `curl` sans
ces options et `+` pour les espaces des macros. Le préflight compile et importe
les deux sources en mémoire sous le Python Moonraker `3.8.2`, par stdin et sans
fichier distant. Le déployeur lui-même est épinglé dans le manifeste.

Le plan local et le préflight réel en lecture seule sont verts :
`PLAN_CALIBRATION_UI_V1_OK` et `PREFLIGHT_CALIBRATION_UI_V1_OK`. Ils confirment
la base Moonraker exacte, les nouveaux chemins absents, `standby`, cibles zéro,
runtime fermé avec Z accepté et chemin `committed` non armé. Aucune pose,
création distante ou relance de service n'a eu lieu.

Thomas a ensuite donné le GO exact. La capture
`20260822-192821-g4-k1-control-calibration-ui-v1` a passé le préflight et créé
le backup exact. Le premier transfert s'est arrêté avant toute pose : OpenSSH
Windows a demandé SFTP, absent du Dropbear Creality. Le rollback automatique a
restauré le `moonraker.conf` exact, retiré tous les chemins candidats et
redémarré seulement Moonraker. Le préflight final est vert ; le staging de cet
essai est vide. Aucun chauffage, homing, mouvement, mesh ou Z n'a été exécuté.

Le candidat corrigé force maintenant le protocole SCP historique avec `-O` et
nettoie aussi le staging exact pendant un rollback. Le déployeur et son hash
ayant changé après le GO consommé, cette version a repassé
`PREFLIGHT_CALIBRATION_UI_V1_OK` en lecture seule. Elle doit recevoir un nouveau
GO exact avant toute nouvelle pose.

Thomas a renouvelé ce GO. La capture
`20260822-202014-g4-k1-control-calibration-ui-v1` a obtenu le préflight, posé le
paquet et passé ses validations par fichiers/API. La recette dans le vrai
navigateur a cependant trouvé deux défauts non couverts par le validateur : le
service worker Mainsail intercepte `/k1-control/` sur l'origine
`127.0.0.1:4409`, et le dossier UI avait été créé en mode `0700`. Sur l'origine
isolée `localhost:4409`, nginx a confirmé `Permission denied`. Le rollback exact
a retiré l'UI et le composant, restauré la configuration puis obtenu
`PREFLIGHT_CALIBRATION_UI_V1_OK`. Aucun chauffage, homing, mouvement, mesh ou Z
n'a eu lieu.

Le candidat corrigé hors imprimante crée et valide désormais le dossier UI en
`0755`. Un lanceur dédié ouvre `http://localhost:4409/k1-control/` sur le même
tunnel, ce qui isole la page du service worker Mainsail sans ajouter de port ni
de service. Cette origine possède sa propre session navigateur : Thomas devra y
saisir les mêmes identifiants une fois. Le déployeur et son empreinte ayant de
nouveau changé après le GO consommé, toute nouvelle pose exige encore un GO
exact renouvelé.

L'audit du parcours complet après rechargement a ensuite trouvé deux blocages
hors imprimante : le seed Z accepté n'était pas repris par le formulaire et la
case « plateau libre » redevenait décochée mais inaccessible après les six
meshes. Le composant expose maintenant le Z accepté ; le navigateur hydrate une
fois le formulaire depuis l'état serveur et laisse les confirmations physiques
accessibles. Le bouton Z exige simultanément « plateau libre » et « buse
propre ». Le manifeste épingle les nouvelles empreintes.

Le protocole séparé `G4-K1-CONTROL-CALIBRATION-UI-CAMPAIGN-V1` est préparé hors
imprimante. Après une pose UI entièrement verte, Thomas devra réaliser depuis
l'écran six meshes réels en `9 × 9`, `11 × 11`, `15 × 15`, puis six meshes et le
parcours Z complet en `6 × 6`. Les trois premiers niveaux sont annulés depuis
l'écran après qualification et capture en lecture seule. Aucun clic ou commande
de calibration Codex, septième passage par niveau ou rerun automatique ne sera
accepté. Le validateur expose `Plan`, `Preflight`, `CaptureLevel` et `Validate`;
son plan local est vert avec
`PLAN_CALIBRATION_UI_CAMPAIGN_V1_OK`.

La préparation production a progressé sans toucher à la K1 : OrcaSlicer `2.4.2`
sélectionne réellement la machine `Creality K1 Max (0.4 nozzle) - Copie` et le
processus `0.20mm - SpeedClassics - MultiMaterials`. Leurs quatre fichiers sont
capturés en privé avec empreintes. Le départ ancien, le changement vide et le
post-traitement `--start-z-offset 0.27` sont donc prouvés sur l'état courant.
L'objet live `box` expose `state` et `t_command`; le traceur passif les suit
désormais sans collecter l'inventaire CFS. Le cœur du refill reste compilé : ne
pas inventer de propriétaire de température ni ouvrir une bascule production
avant preuve pendant une impression utile.

## Next bounded mission

`G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1` est installée sous la capture
`20260822-222005-g4-k1-control-calibration-ui-matrix-v1`. Le préflight, le
déploiement et deux validations indépendantes sont verts. Seuls trois fichiers
ont été remplacés après backup exact et seul Moonraker a été redémarré. Le vrai
rendu Chrome authentifié confirme `6/9/11/15`, le bicubique forcé et Lagrange
désactivé au-delà de six. Le rechargement complet restaure `6 × 6` Lagrange, le
seed `−0,04 mm` et les confirmations décochées. La gate est close et son GO est
consommé.

Le préflight réel en lecture seule de la campagne écran est vert sous la capture
`20260822-222450-g4-k1-control-calibration-ui-campaign-v1`. L'UI est inactive,
la K1 est au repos, les cibles sont à zéro, le Z accepté et le profil rapide
sont présents, et les profils `9/11/15` sont absents comme attendu. La prochaine
gate unique est `G4-K1-CONTROL-CALIBRATION-UI-CAMPAIGN-V1`; elle prouvera
l'autonomie de calibration par vingt-quatre meshes et un parcours Z entièrement
pilotés depuis l'écran.

Le premier départ `9 × 9` a toutefois montré que la case de remplacement restait
cochée après une annulation à `0/6`; une seconde reprise a répété le problème.
Les deux tentatives ont été annulées avant toute mesure et l'état durable est
intact. Le paquet correctif séparé
`G4-K1-CONTROL-CALIBRATION-UI-RETRY-SAFETY-V1` ne remplace que `app.js`, sans
restart. Il remet une seule fois remplacement et plateau libre à faux après une
reprise incomplète. Ses 179 tests et son préflight réel sous la capture
`20260822-231240-g4-k1-control-calibration-ui-retry-safety-v1` sont verts.
L'autorité globale du goal a couvert sa pose sans nouveau GO. Le même identifiant
a obtenu le déploiement et deux validations vertes. Seul `app.js` a été remplacé
après backup exact, sans restart ni action physique. Le rechargement sur `4409`
a affiché le cache Mainsail ; le tunnel temporaire propre `127.0.0.1:4410` était
actif et attendait l'authentification humaine. L'action prévue à ce stade était
le vrai rendu des deux cases décochées sur `4410`, puis la reprise `9 × 9`.

Le tunnel `4410` a depuis été recréé avec un seul processus connecté et les
empreintes distantes confirment que l'interface et le correctif existent. Le
préflight de campagne bloquait toutefois à tort sur l'état sûr `cancelled`
laissé à `0/6`. Le validateur accepte maintenant uniquement un `idle` neuf ou
ce cas précis à zéro mesure avec backup ; il refuse une reprise après le premier
mesh. Le test ciblé est vert et la capture
`20260822-233717-g4-k1-control-calibration-ui-campaign-v1` a obtenu
`PREFLIGHT_CALIBRATION_UI_CAMPAIGN_V1_OK`. Il reste à recharger `4410`, constater
les deux confirmations décochées, puis lancer le niveau `9 × 9` depuis l'écran.

Le lancement a été conforme (`9 × 9`, bicubique, remplacement faux). Après la
chauffe, les `200 s`, le nettoyage et le homing, la première grille s'est
arrêtée à `1/6` avec `Le mesh ne contient pas le nombre de lignes attendu.`
Aucune matrice n'a été conservée. Les chauffes sont à zéro, le Z `−0,04 mm` et
le profil `6 × 6` sont intacts. Le firmware exact montre que `prtouch_v3`
utilise le `probe_count` chargé à `6,6` et ignore l'extension dynamique attendue.

ADR-011 et `G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-MATRIX-V1` corrigent cette
frontière sans contourner le capteur Creality : commutation atomique après
backup et avant chauffe, restart Klipper vérifié, restauration après coupure
des chauffes. La pose ajoute seulement le composant et sa section Moonraker,
sans toucher `printer.cfg`. La capture
`20260823-001724-g4-k1-control-calibration-ui-prtouch-matrix-v1` a obtenu le
déploiement et deux validations vertes. L'essai vide est restauré exactement en
phase `rolled_back`, avec le Z `−0,04 mm`, le profil `6 × 6`, le stockage et les
chauffes conformes.

Le delta statique `G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-PRESETS-V1` retire le
choix `4 × 4` inexécutable et conserve `3/5/6/9/11/15`. Son premier transfert a
rencontré un défaut de guillemets dans la validation locale puis a restauré
automatiquement les deux fichiers exacts. Après correction, la capture
`20260823-003755-g4-k1-control-calibration-ui-prtouch-presets-v1` a obtenu le
déploiement et deux validations vertes, sans restart ni action physique. La
suite complète compte 191 tests verts, 3 ignorés connus. Le préflight de reprise
`20260823-002500-g4-k1-control-calibration-ui-campaign-v1` est vert. À ce stade
historique, l'autorité globale du Goal couvrait encore la campagne et le seul
verrou était la confirmation physique fraîche du plateau. Cette autorité n'est
plus transférable après le handoff et aucun nouveau départ `9 × 9` n'est permis.

Thomas a relancé le `9 × 9`. Le composant V1 a chargé `probe_count=9,9`, puis
Klipper a refusé son démarrage avec XS3002 parce que l'algorithme persistant
restait `lagrange`. Aucun chauffage, homing, mouvement ou mesh n'avait commencé.
La garde de 120 s a déclenché le rollback automatique : `6,6 + lagrange`,
Klipper prêt, cibles zéro, Z `−0,04 mm`, profil rapide, stockage et deux CFS
intacts. La campagne `20260823-004305-421-calibration-ui-v1` est `failed` à
`0/6` avec son backup disponible.

Le paquet séparé
`G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-BED-MESH-V2` remplace seulement le
composant V1 et redémarre uniquement le Moonraker dédié. Son runtime commute et
relit ensemble `probe_count + algorithm`, refuse `9/11/15 + lagrange`, puis
restaure les deux valeurs après chauffes ou échec. La première pose a exposé une
lacune du validateur : la K1 utilise `lagrange` implicitement sans ligne
`algorithm`, ce qui avait placé le composant dans `failed_components` sans être
détecté. Aucun chauffage, homing ou mouvement n'a eu lieu. La révision corrigée
préserve exactement cette forme implicite et vérifie désormais `server/info`.
La capture `20260823-012755-g4-k1-control-calibration-ui-prtouch-bed-mesh-v2-r2`
a obtenu le préflight, le déploiement et deux validations vertes ;
`failed_components=[]` et `warnings=[]`. La campagne XS3002 reste restaurée
exactement et le préflight complet
`20260823-013151-g4-k1-control-calibration-ui-campaign-v1` est vert. La prochaine
action est uniquement le nouveau départ écran `9 × 9` avec confirmation fraîche
du plateau libre.

Ce départ a été exécuté sous la campagne
`20260823-021858-540-calibration-ui-v1`. Le journal Klipper exact montre le
premier mesh `9 × 9` atteindre `g29_cnt=36`, puis
`prtouch_v2_wrapper.py:1889` lever `IndexError: list index out of range` avant le
point physique 37. Le `1/6` affiché signifie que le contrôleur était dans son
premier des six passages prévus ; il ne signifie pas qu'un mesh valide a été
enregistré. L'erreur « nombre de lignes attendu » est la conséquence locale de
la matrice incomplète.

Le rollback API a obtenu la phase `rolled_back`. L'état final contrôlé est sûr :
`standby`, chauffes demandées à zéro, axes non référencés, deux CFS conformes,
profil robuste `k1_p001_t055_r001_n06x06`, Z accepté `−0,04 mm` et stockage
`ok`. Le XS3002 `nozzle_mcu` visible pendant la restauration est survenu pendant
le restart et Klipper a récupéré ; ce n'est pas la cause du point 37.

La configuration usine officielle contient exactement trente-six tables par
point. L'ADR-012 retire donc `9/11/15` au lieu de contourner le capteur. Le mode
quotidien devient uniquement `6 × 6` Lagrange, avec un seul mesh puis le chemin
Z. Les six meshes de FIRST-CALIBRATION-V2 restent la qualification statistique
initiale déjà validée, pas une répétition quotidienne. Le workaround
communautaire `pr_version: 1` avec retrait des tables est explicitement rejeté.

Les familles de payloads ont été corrigées hors imprimante. Les quatre deltas
sûrs PRTOUCH-BED-MESH-V2, MATRIX-V1, RETRY-SAFETY-V1 et PRTOUCH-PRESETS-V1 ont
depuis été préflightés, posés ou reconnus déjà présents, puis validés séparément.
La suite complète compte maintenant 220 tests verts et 3 ignorés connus. La
seule gate quotidienne restante est :

```text
GO G4-K1-CONTROL-CALIBRATION-UI-CAMPAIGN-V1
```

Après son préflight frais, Thomas lance depuis l'écran l'unique `6 × 6` et
termine le chemin Z. Codex reste en observation et validation uniquement. La
production et G5 restent hors périmètre.

La gate précédente est close avec `DEPLOY_CALIBRATION_PATH_V1_OK` et
`VALIDATE_CALIBRATION_PATH_V1_OK` sous la capture
`20260822-124207-g4-k1-control-calibration-path-v1`.

Autorisation de reprise : Thomas a donné puis reconfirmé une autorisation
globale. FIRST-CALIBRATION-V2, CALIBRATION-UI-V1 et les quatre deltas sûrs sont
validés et clos ; le préflight CAMPAIGN-V1 est vert. La prochaine mission unique
est la campagne quotidienne opérateur `6 × 6 / 1 mesh`; la sous-grille
composite et la bascule production restent des gates ultérieures séparées.

La bascule Orca reste une gate ultérieure unique : wrappers de travail côté
machine, trois champs Orca et retrait du post-traitement doivent changer
ensemble, après validation de ce runtime.

Le post-traitement PHP/Orca `+0,27 mm`, le Start G-code et le G-code de changement
de filament restent strictement inchangés. Le GO V2 ne couvre ni la pose UI, ni
la bascule Orca, ni G5.

## Stop conditions

Codex must stop without attempting a workaround if:

- the target host is ambiguous;
- root access fails;
- a required action may write to the printer;
- a command is not confidently read-only;
- the machine is printing or calibrating before an unplanned operation; the already authorised passive observer may remain connected during the job;
- a captured file contains secrets or unclear proprietary content;
- the observed hardware or firmware contradicts the assumed target.

The S11/S12 configuration-selection conflict is resolved in favour of S12 structure 0. Firmware recovery remains blocked until an exact image is matched despite the stale S11 OTA metadata.

## Information to bring back for analysis

- redacted manifest;
- active configuration entry point and complete include graph;
- macro names and paths for startup, homing, levelling and CFS operations;
- process/service map;
- mount and persistence map;
- relevant redacted logs;
- one G-code file that reproduced the bad first layer, kept private until reviewed;
- ideally, two logs from identical G-code executions with different Z outcomes.
- Orca `.orca_printer` export for the actual K1 Max profile;
- exact custom start/end/layer/tool-change and Z workaround text;
- existing representative 3MF/G-code for multi-object, hot-bed and CFS cases;
- already-held recovery image/procedure reference.

The first six items, readable extension sources, protocol, private inputs, one non-qualified A1/B/A2 trace and one complete long-production trace now exist. Compiled CFS internals remain opaque, but its refill temperature effect and the final active pressure advance have now been measured directly.
