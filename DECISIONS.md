# DECISIONS

## D-001 — Public repository with strict sanitisation

Date: 2026-08-19  
Status: accepted

The repository is public to maximise community value. Raw backups, credentials, private network information, unnecessary hardware identifiers and unreviewed vendor files remain local and ignored.

## D-002 — Observe the stock CFS stack before replacing it

Date: 2026-08-19  
Status: accepted

The initial target is rooted stock firmware plus controlled observation and later minimal overrides. A full Klipper replacement is not the default because preserving two-CFS behaviour, toolhead hardware, screen integration and proprietary state machines may otherwise become a large reverse-engineering project.

## D-003 — Codex is a bounded operator, not a permanent observer

Date: 2026-08-19  
Status: accepted

ChatGPT carries diagnosis, experiment design and review. Codex receives finite local/SSH missions for inventory, scripting, deployment and verification. This reduces context cost and limits accidental remote mutation.

## D-004 — Raw acquisition stays outside Git

Date: 2026-08-19  
Status: accepted

Complete backups and raw logs are stored under ignored local paths. Git receives manifests, hashes, original code, patches and redacted evidence only.

## D-005 — Yellow bed springs are not the Z root cause

Date: 2026-08-19  
Status: accepted

The same Z problem existed before and after spring installation. The springs improved bed levelling but had no observed effect on the Z-offset issue. Future diagnosis must not reopen this causal hypothesis without new contradictory evidence.

## D-006 — Publish original overlays and patches, not vendor payloads

Date: 2026-08-19  
Status: accepted

Manufacturer files may be inventoried by path, role and checksum. Public changes should be expressed as original override files, minimal patches or documented diffs whenever redistribution rights are unclear.

## D-007 — One intervention class at a time

Date: 2026-08-19  
Status: accepted

Root setup, interface installation, startup changes, Z correction, mesh strategy and CFS temperature logic are separate lots. Combining them would destroy diagnostic attribution and make rollback unreliable.

## D-008 — No OrcaSlicer fork during initial stabilisation

Date: 2026-08-19  
Status: accepted

OrcaSlicer integration is valuable, but a slicer fork is a separate software product. It is deferred until printer-side behaviour is stable and a specific remaining integration gap has been proven.

## D-009 — Licence remains open

Date: 2026-08-19  
Status: open

A public reuse licence is desirable for community adoption, but no licence is selected silently because licence grants are not fully reversible. Add a `LICENSE` only after Thomas chooses the intended reuse model.

## D-010 — Permanent Git and GitHub delegation to Codex

Date: 2026-08-19
Status: accepted

Thomas delegates the complete Git and GitHub lifecycle of this repository to Codex on a standing basis. Normal operations — including branches, commits, pushes, pull requests, readiness transitions, merges into `main`, tags and cleanup of merged mission branches — require no additional `GO` or human validation.

This decision does not authorise printer mutation and does not relax sanitisation, secret handling, preservation of unrelated work or platform safety controls. Force-pushes and published-history rewrites remain exceptional and require an explicit instruction naming that operation.

## D-011 — Comparable stock traces precede custom installation

Date: 2026-08-19
Status: accepted

The custom installation decision is deferred until one controlled A1/A2 pair has been qualified under the G3 protocol. The pair uses one byte-identical private G-code file, fixed plate/nozzle/filament/CFS conditions, one boot session and matched thermal starting windows. D-012 adds B between them to isolate geometry without replacing the identical-file pair.

No extra trial beyond the approved session plan is performed automatically. A non-comparable pair is reported as such. The first default intervention remains a narrow, reversible overlay; a broader stack replacement requires evidence that minimal interventions cannot solve the confirmed mechanism while preserving the screen and both CFS units.

## D-012 — Geometry is isolated before reboot and CFS tests

Date: 2026-08-19
Status: accepted

Local comparison confirmed that inputs A (`200 × 200 mm`) and B (`200 × 201 mm`) have identical slicer settings and control commands. The first physical sequence is therefore A1/B/A2 in one boot session with one Geeetech filament. A1/A2 provide the identical-file pair; B isolates the one-millimetre geometry change.

No reboot or multi-filament CFS transition is added until this sequence has been analysed. This prevents random stock bed checks, boot state, temperature, pressure advance and CFS behaviour from being mixed into one result.

## D-013 — No sacrificial print campaign after the first G3 session

Date: 2026-08-19
Status: accepted

Session `20260819-185157-g3-aba` completed A1/B/A2 but did not produce a qualified geometry comparison because the bed screws changed between the trials. It nevertheless confirmed variable Z retries, multiple Z-establishing phases and a competing pressure-advance value.

Thomas's reported production symptom — especially after a long print followed by a differently configured or multi-object file — is treated as valid diagnostic context, not as a claim that must be proven through repeated plastic-consuming tests. Future traces will be collected passively around useful production jobs. No fourth print or broad combinatorial campaign is launched without one narrow question that cannot be answered offline or from existing logs.

## D-014 — Dedicated ECDSA key for the stock SSH server

Date: 2026-08-19
Status: accepted and deployed

The K1 Max uses Dropbear `2019.78`, which predates Ed25519 support for
`authorized_keys`. Passwordless access therefore uses one dedicated ECDSA P-256
key, selected by local alias `k1max-root`, with password fallback disabled.

The key is for this printer only. Its private half stays in the Windows SSH
profile and outside Git. This access change does not authorise printer-behaviour
changes and does not weaken the named G4 requirement for later deployments.

## D-015 — Premier correctif CFS limité au Geeetech PLA 190/195

Date: 2026-08-20
Status: rejected on 2026-08-20; never deployed

Ce premier candidat remplaçait la température fixe `220` par `195 °C` et
imposait un contrat Geeetech PLA `190/195`. Thomas l'a rejeté : il aurait empêché
les changements normaux de marque, de matériau, de profil et de température.

La décision qui la remplace est fonctionnelle : pendant une impression, le
G-code ou la dernière modification explicite de Thomas est l'unique source de
vérité. Un remplacement équivalent conserve la cible active ; un vrai changement
reçoit la cible du prochain outil depuis le G-code. La base générique CFS ne doit
jamais écraser ces valeurs.

Les fichiers déployables du candidat et son test ont été retirés de `main`. Son
ADR reste comme historique d'une option refusée. Aucun G4 ne porte son nom.

## D-016 — Niveau A renforcé avant Eddy ou remplacement complet

Date: 2026-08-20

Status: accepté le 2026-08-20 pour conception hors imprimante ; aucun déploiement autorisé

La première voie recommandée conserve le firmware `2.3.5.34`, les interfaces
Creality et les CFS. Elle commence par un analyseur local en lecture seule, puis
utilise des fichiers originaux et réversibles pour donner un propriétaire
explicite au démarrage, à la sécurité Z, au mesh, aux températures dynamiques et
à la valeur finale de pression.

BTT Eddy n'est pas un prérequis. Il devient la voie suivante uniquement si une
séquence stock propre, thermiquement stable et déterministe prouve encore que PR
Touch est dangereux ou insuffisamment répétable. SimpleAF, un Klipper moderne et
un MMU ouvert restent un programme de recherche séparé, car la documentation
actuelle de SimpleAF n'offre pas de prise en charge prête à l'emploi du CFS
propriétaire.

Le contournement Z Orca actuel reste en place jusqu'à ce que son remplacement
côté machine et le profil Orca propre soient validés ensemble. Cette proposition
est détaillée dans `docs/08-audit-systeme-complet-et-trajectoire.md` et ADR-002.
Elle n'autorise aucune modification de l'imprimante.

## D-017 — La sécurité Z précède les autres correctifs de comportement

Date: 2026-08-20

Status: **supersédé et rejeté le 2026-08-20 ; jamais déployé**

Session `20260820-154056-p123` a mesuré deux mécanismes directs : la correction
`+0.27 mm` du post-traitement arrive seulement après `START_PRINT`, puis la
séquence de fin annule les corrections Z faites en direct et prépare de nouveau
`0.000` pour la persistance. P1 PETG a terminé à `+0.38 mm` avant cette remise à
zéro.

Le premier paquet de comportement à préparer est donc une séquence de sécurité
Z réversible. Elle interdit purge et mouvement bas avant la référence Z finale,
la politique de mesh et la correction effective. Elle doit également empêcher
l'effacement silencieux d'une correction validée. Le script Orca actuel reste
actif jusqu'à la validation complète de son remplacement.

Cette priorité avait conduit à un paquet fixe et trop étroit. D-019 et D-020 la
remplacent : la sécurité Z reste une barrière obligatoire, mais elle est conçue
dans un produit cohérent avec calibration persistante, mesh, interface, Orca et
températures CFS. Le déploiement reste découpé pour le rollback.

## D-018 — Point d'entrée `START_PRINT` conservé, corps surchargé par include

Date: 2026-08-20

Status: **supersédé et rejeté le 2026-08-20 ; jamais déployé**

L'ancien paquet Z conservait le nom public `START_PRINT`. Un fichier original,
chargé après `gcode_macro.cfg`, remplace seulement son corps grâce au comportement
`RawConfigParser(strict=False)` observé dans la version capturée de Klipper.
Le fichier stock reste intact et le post-traitement Orca actuel continue donc à
reconnaître `START_PRINT` et à réappliquer sa correction absolue `+0,27 mm`.

L'ancien paquet exigeait un nettoyage manuel confirmé, chargeait explicitement
le mesh `default`, appliquait et vérifiait `+0,27 mm`, puis ouvrait une garde
avant tout appel CFS ou purge. La correction finale était capturée avant la fin
stock, mais restait un candidat non réappliqué automatiquement. ADR-003 porte la
comparaison des options et les conséquences. Cette base fixe est remplacée par
ADR-004.

## D-019 — Rejet définitif de `G4-ZSAFE-START-V1`

Date: 2026-08-20

Status: accepté

Thomas a refusé le paquet avant tout déploiement. Il figeait `+0,27 mm`, le mesh
`default` et un nettoyage manuel, sans résoudre la calibration persistante,
l'interface, les meshes thermiques, le contrat Orca ni les températures CFS.

Le paquet reste uniquement comme preuve historique et échoue volontairement
s'il est chargé par erreur. Il n'existe aucun GO futur valide portant ce nom.
Le post-traitement Orca actuel n'a pas été retiré de la machine.

## D-020 — Un produit cohérent, posé par étapes réversibles

Date: 2026-08-20

Status: accepté pour conception et prototype hors imprimante ; déploiement non autorisé

La cible est un seul système de pilotage : interface quotidienne `K1 Control`,
interface experte candidate Mainsail, API candidate Moonraker épinglée, état Z
et mesh séparé des fichiers constructeur, séquence sûre, températures CFS
dynamiques et contrat Orca versionné.

D-007 reste valable pour la pose : une classe de mutation à la fois afin de
savoir ce qui a cassé et de revenir en arrière. Elle ne signifie pas que Thomas
doit gérer une collection de correctifs isolés ou refaire des réglages à chaque
impression. L'architecture, les profils et les tests sont préparés comme un
tout avant le premier G4.

Aucun installateur communautaire n'est exécuté tel quel. Les versions, droits,
ports, ressources et conséquences de Moonraker/Mainsail doivent être prouvés
sur la K1 Max `2.3.5.34` avec écran et deux CFS.

## D-021 — Le Z accepté survit jusqu'à une nouvelle calibration

Date: 2026-08-20

Status: accepté pour conception et prototype hors imprimante ; déploiement non autorisé

Le réglage Z se fait pendant une session de calibration dédiée. Les clics ne
modifient que cette session. Une action explicite `Enregistrer` crée un état
accepté lié à la plaque, la température, la buse, la référence capteur et les
fichiers pertinents.

Cet état survit à la fin d'impression, au redémarrage et à la remise à zéro
interne Creality. Une nouvelle calibration ou toute modification capable de
changer la référence l'invalide. L'ancienne valeur reste disponible comme
historique, mais n'est jamais réutilisée en silence. Il n'existe aucune valeur
Z universelle inscrite dans le système.

## D-022 — Fondation Mainsail/Moonraker posée avant les règles de comportement

Date: 2026-08-20

Status: accepté pour le paquet hors imprimante ; déploiement non autorisé

La première pose de `K1-CONTROL-V1` ajoute seulement Moonraker et Mainsail en
observation. Elle n'expose pas encore `K1 Control` réel et ne modifie ni le Z,
ni le mesh, ni le démarrage, ni la purge, ni les températures CFS, ni Orca.

Le paquet MIPS du Helper Script est réutilisé comme archive auditée, jamais par
son installateur. Il contient Moonraker au commit
`fccffa96c63ed77dc3953e18615e9fe9cd3d69ea`. Mainsail est figé en `v2.18.2`.
Moonraker écoute seulement en boucle locale ; la première connexion Mainsail se
fait par tunnel SSH et le port LAN ne s'ouvre qu'après création du compte.

Cette séparation sert à mesurer mémoire, stabilité et coexistence avant de
confier à la nouvelle pile le moindre comportement d'impression. Le candidat
s'appelle `G4-K1-CONTROL-FOUNDATION-V1` et requiert son propre GO exact.

## D-023 — V1 arrêtée au préflight, V2 réutilise le syslog stock borné

Date: 2026-08-20

Status: historique ; V1 et V2 fermées

Thomas a donné le GO exact V1. Le préflight réel a confirmé la bonne machine,
l'état au repos, les chauffes à zéro, les deux CFS, les ressources et l'absence
des cibles. Il a aussi prouvé que `logrotate` et `/etc/logrotate.d` n'existent
pas. V1 exigeait cette dépendance ; elle a donc été arrêtée avant toute copie et
son nom est fermé.

La machine possède déjà `/sbin/syslogd -n` et `/dev/log`. L'aide de son BusyBox
confirme une rotation par défaut à 200 Kio avec une sauvegarde. V2 envoie les
erreurs nginx à ce journal stock et conserve la rotation interne de Moonraker.
Elle n'installe aucun paquet, cron ou troisième service.

Le remplacement s'appelle `G4-K1-CONTROL-FOUNDATION-V2`. Le GO V1 ne l'autorise
pas. V2 exige un nouveau GO exact après reconstruction et tests du paquet.

Le GO V2 a ensuite été reçu. Les essais réels ont été rollbackés et le nom V2
a été fermé par D-024.

## D-024 — V2 fermée, authentification déplacée vers nginx dans V3

Date: 2026-08-21

Status: accepté pour préparation hors imprimante ; V3 non autorisée

La pose V2 a fini par rendre Mainsail réellement fonctionnel par tunnel, sans
modifier le comportement d'impression. Elle a aussi prouvé que Mainsail
`v2.18.2` ne sait pas créer ni utiliser un compte Moonraker. La confiance locale
nécessaire au proxy ne peut donc pas être retirée sans casser Mainsail, ni être
conservée après ouverture LAN sans rendre tous les clients nginx fiables.

V2 a été rollbackée et son nom est fermé. V3 garde Moonraker sur
`127.0.0.1:7125`, fiable uniquement pour nginx local, et place le contrôle
d'accès sur nginx. Le binaire MIPS figé contient les directives `auth_basic` et
`auth_basic_user_file`.

Le mot de passe V3 est saisi deux fois en local, jamais passé en argument, et
seul un hachage SSHA salé est écrit en mode `0600`. Les identifiants HTTP sont
retirés avant le proxy vers Moonraker. Le LAN reste limité aux plages IPv4
privées et ne s'ouvre qu'après un test HTTP `401/200` par tunnel et un signal
humain explicite.

Cette décision n'ajoute pas TLS. HTTP Basic reste réservé à un LAN privé de
confiance ; tout accès depuis un réseau non fiable doit utiliser le tunnel SSH.
Le nouveau candidat s'appelle `G4-K1-CONTROL-FOUNDATION-V3` et requiert son GO
exact. Les GO V1 et V2 ne l'autorisent pas.

## D-025 — Fondation V3 + PATHS-V1 retenue après observation

Date: 2026-08-21

Status: accepté et installé

V3 et sa correction PATHS-V1 ont été installées sous leurs GO exacts, avec
sauvegardes, validations et rollback prêts. L'observation finale comprend une
impression normale lancée manuellement, le journal persistant couvrant le trou
du premier observateur et une seconde observation passive arrivée à son terme.

Thomas a confirmé une pièce correcte, un seul PLA et aucune intervention. Les
journaux ne montrent aucun arrêt Klipper/MCU, perte de communication, trace
Python ou erreur interne sur le créneau reconstruit. La validation finale a
obtenu `VALIDATE_PATHS_V1_OK`. Cette preuve accepte la fondation comme base ;
elle ne prétend pas corriger les défauts aléatoires Z/CFS.

## D-026 — Le runtime Z/mesh précède et ne remplace pas encore START_PRINT

Date: 2026-08-21

Status: accepté pour candidat hors imprimante ; déploiement non autorisé

Le premier runtime ajoute l'état Z courant/précédent, les sessions provisoires,
l'invalidation, les températures de calibration, le homing explicite, le choix
de matrice/interpolation, les profils mesh qualifiés et une garde fermée avant
les mouvements bas. Il ne contient ni CFS, ni extrusion, ni remplacement de
`START_PRINT` : la bascule machine/Orca doit rester atomique dans l'étape
suivante.

Le `save_variables.py` exact permet une seule structure composite, mais écrit
son fichier directement. Ce risque est refusé. Le candidat utilise un petit
module original à schéma borné, somme SHA-256, permissions `0600`, `fsync`,
remplacement atomique et copie précédente. Une intégrité douteuse bloque la
production ; une récupération antérieure n'est jamais chargée silencieusement.

## D-027 — Une correction du déployeur après GO exige un GO renouvelé

Date: 2026-08-21

Status: accepté

Le premier préflight réel Z/mesh a échoué avant mutation : deux programmes
Python transmis sur stdin recevaient leurs arguments sans le marqueur de script
`-`. La correction ajoute ce marqueur aux formes snapshot et G-code ; les deux
fichiers runtime, leurs empreintes et les effets distants prévus ne changent pas.

Le préflight corrigé est vert et reste une observation en lecture seule. Malgré
son faible volume, la correction change une commande revue après le GO. Le
principe G4 d'approbation des commandes exactes s'applique : aucune pose n'est
permise avant le renouvellement du même GO exact.

## D-028 — L'état vide est calibrable, jamais prêt pour la production

Date: 2026-08-21

Status: accepté hors imprimante après rollback réel

La pose Z/mesh a prouvé qu'un stockage neuf `integrity=empty` était confondu avec
un enregistrement corrompu. Garder `ready=0` ferme correctement la production,
mais bloque aussi toute création de la première calibration Z.

L'état vide devient donc prêt uniquement pour les opérations de calibration :
`ready=1`, `block_reason=no_accepted_z`, `accepted_z_valid=0` et
`low_moves_armed=0`. Un état réellement invalide reste à `ready=0`. La garde de
production continue d'exiger séparément un Z accepté, un mesh qualifié et la
relecture de leurs valeurs effectives.

Le même essai a montré que Klipper peut être prêt avant les deux CFS et qu'un
restart peut normaliser les espaces des blocs `SAVE_CONFIG`. Les validations de
pose et rollback attendent désormais la stabilisation complète. Après restart
de rollback, le backup exact est restauré une seconde fois sans autre restart,
afin que l'état chargé reste sémantiquement identique et que l'empreinte disque
revienne exactement à la baseline revue.

## D-029 — Les commandes étendues utilisent `KCTRL_*` et le rollback attend les écritures Creality

Date: 2026-08-21

Status: accepté hors imprimante après deuxième rollback réel

La deuxième pose a chargé les objets runtime, mais la commande différée
`K1_CONTROL_LOAD_STATE` a été interprétée comme `K1` et refusée. La source
`gcode.py` exacte de cette K1 découpe les commandes avec
`([A-Z_]+|[A-Z*/])` : un chiffre au milieu d'un nom étendu le tronque. Toute la
famille exécutable du produit devient donc `KCTRL_*`, y compris le stockage et
les futurs contrats Orca. Un test reproduit ce parseur pour empêcher toute
régression.

Le même essai a montré que la première stabilisation CFS ne suffit pas si
Creality termine ensuite un `CXSAVE_CONFIG`. Le rollback attend désormais le
runtime déchargé, les deux CFS reconnectés et une fenêtre silencieuse avant sa
restauration finale, puis revérifie l'empreinte après un délai supplémentaire.
La pose corrigée est un nouveau payload et exige un nouveau GO exact.

## D-030 — Les valeurs texte conservent un littéral Python à travers le parseur Creality

Date: 2026-08-22

Status: accepté hors imprimante après troisième rollback réel

La troisième pose a chargé les objets `KCTRL_*`, puis le chargement différé a
échoué sur `SET_GCODE_VARIABLE ... VALUE='empty'`. La source exacte et la trace
montrent que le parseur Creality applique `shlex.split` avant
`ast.literal_eval` : les guillemets simples sont consommés et `empty` arrive
comme nom Python nu.

Toutes les affectations texte utilisent désormais un littéral protégé par deux
niveaux, par exemple `VALUE='"empty"'`. Le test de non-régression rejoue
exactement `shlex.split` puis `ast.literal_eval` sur les 24 affectations texte.
Le déployeur conserve aussi son dernier snapshot si le runtime n'atteint pas
`ready=1`, afin qu'un futur échec reste directement observable avant rollback.

Le rollback automatique a restauré l'empreinte exacte et l'état sain. Comme le
payload et le déployeur ont changé après le GO consommé, une nouvelle pose exige
une revue puis un nouveau GO exact.

## D-031 — La validation épingle aussi l'empreinte normalisée par Creality

Date: 2026-08-22

Status: accepté après installation réelle verte

La pose finale a obtenu `DEPLOY_Z_MESH_RUNTIME_V1_OK`, puis le
`CXSAVE_CONFIG` différé de Creality a modifié uniquement l'indentation des blocs
générés `bed_mesh default` et `auto_addr`. Le diff complet et une comparaison
normalisée prouvent qu'aucune valeur, section ou inclusion n'a changé. Les deux
fichiers runtime ont conservé leurs hashes exacts.

Réécrire `printer.cfg` après chaque démarrage pour lutter contre cette
normalisation constructeur ajouterait une mutation inutile et fragile. La
validation accepte donc seulement deux empreintes épinglées : celle juste après
l'insertion revue et celle obtenue après la normalisation exacte observée. Elle
exige toujours une seule inclusion et les hashes exacts des deux fichiers
runtime. La validation indépendante a ensuite obtenu
`VALIDATE_Z_MESH_RUNTIME_V1_OK` sans nouvelle mutation.

## D-032 — L'autonomie se valide dans l'interface, pas dans la console

Date: 2026-08-22

Status: accepté par Thomas pour le pilotage et le handoff

Le runtime Z/mesh installé est une fondation technique, pas encore un produit
utilisable seul. Mainsail fournit la vue experte et la console, mais la saisie
manuelle de commandes `KCTRL_*` ou l'assistance de Codex ne satisfont pas la
cible d'usage quotidien.

Deux seuils séparés deviennent des critères de pilotage :

1. **autonomie calibration** : Thomas choisit dans une interface les paramètres
   de plaque, température, stabilisation, matrice et interpolation, lance la
   séquence sûre, voit les deux mesures et leur qualification, puis peut
   enregistrer, annuler ou restaurer sans console ni Codex ;
2. **autonomie production** : Orca et la machine appliquent automatiquement la
   calibration acceptée, le bon mesh et les températures des deux CFS, sans
   ancien `+0,27 mm`, modification manuelle de fichier ou intervention Codex.

Une première calibration pilotée et surveillée ne vaut donc pas validation de
l'interface autonome. Chaque nouvelle session doit annoncer le seuil atteint,
les éléments manquants et la prochaine gate unique avant de proposer une
mutation.

## D-033 — Le premier Z exige un chemin borné installé avant la calibration

Date: 2026-08-22

Status: accepté hors imprimante

Le runtime installé sait conserver une session Z provisoire, mais sa garde de
mouvements bas exige déjà un Z accepté. Utiliser la console, une commande libre
ou l'ancien `+0,27 mm` pour amorcer le premier Z contournerait donc la sécurité
et réintroduirait une valeur non qualifiée.

La pose du chemin physique et la calibration sont séparées. La gate
`G4-K1-CONTROL-CALIBRATION-PATH-V1` ajoute seulement un overlay puis le valide
au repos, sans chauffe ni mouvement. La gate ultérieure
`G4-K1-CONTROL-FIRST-CALIBRATION-V1` pourra seule employer ses paliers.

Le chemin retenu impose le centre `(150, 150)`, une première hauteur de `5 mm`,
la descente `5 → 2 → 1 → 0,5 → 0,3 → 0,2 → 0,15 → 0,1 mm`, les ajustements
uniquement à la dernière hauteur, un repositionnement physique à `0,1 mm` après
chaque incrément, une confirmation explicite et une remontée relative de `5 mm`
avant acceptation ou annulation. Il n'existe aucune valeur Z par défaut.

## D-034 — Le candidat Jinja transite par stdin, pas par la ligne SSH

Date: 2026-08-22

Status: accepté après préflight réel sans mutation

Le premier préflight de `CALIBRATION-PATH-V1` encodait le programme Python et
le candidat dans la commande distante. La ligne obtenue dépassait la taille
acceptée par Dropbear, qui fermait la connexion avant le parse. Aucun effet
distant n'avait encore eu lieu.

Le programme complet est désormais envoyé sur l'entrée standard de
`ssh.exe` vers la commande distante courte
`/usr/share/klippy-env/bin/python -`. Il reste exécuté uniquement en mémoire et
ne crée aucun fichier. Le préflight corrigé a obtenu
`PREFLIGHT_CALIBRATION_PATH_V1_OK` sur l'environnement Jinja exact de la K1.

Comme cette commande fait partie du paquet revu, sa correction après le GO
consommé impose un nouveau GO exact avant toute pose.

## D-035 — Toute lecture post-restart attend le socket Klipper

Date: 2026-08-22

Status: accepté hors imprimante après rollback exact

La tentative `20260822-115608` a envoyé le `RESTART` prévu, puis la validation a
lu immédiatement la liste des objets. Le socket Klipper existait mais ne
répondait pas encore dans sa fenêtre de cinq secondes. Le rollback a restauré
les fichiers, puis son propre `RESTART` a rencontré le même socket en transition.

La reprise explicite du rollback a obtenu
`ROLLBACK_CALIBRATION_PATH_V1_OK`. Le préflight final a confirmé la base exacte,
l'overlay absent, les axes non référencés, les chauffes à zéro, le runtime vide,
les deux CFS et la fondation. Aucun acte physique de calibration n'a été lancé.

Le déployeur remplace maintenant les lectures immédiates par une attente bornée
de la liste des objets. Il applique la même garde avant le `RESTART` de rollback
afin de ne pas traiter une transition normale comme une panne définitive.
Comme la commande revue change, une nouvelle pose exige un nouveau GO exact.

## D-036 — CALIBRATION-PATH-V1 est retenu après validation indépendante

Date: 2026-08-22

Status: accepté et installé

Le GO renouvelé a ouvert la capture
`20260822-124207-g4-k1-control-calibration-path-v1`. Le préflight frais a validé
la base exacte, puis la pose corrigée a obtenu
`DEPLOY_CALIBRATION_PATH_V1_OK`. L'attente bornée a absorbé la transition du
socket Klipper et des deux CFS sans seconde commande concurrente.

L'action `Validate`, exécutée séparément, a obtenu
`VALIDATE_CALIBRATION_PATH_V1_OK`. Elle a confirmé les quatre empreintes, le
runtime toujours vide, les axes non référencés, les chauffes à zéro, les deux
CFS, la fondation et le refus de la garde sans modification physique.

Le chemin est retenu mais reste inerte : `idle`, non prêt, non armé et sans droit
de commit. Il n'autorise aucune calibration implicite. La prochaine mutation
possible appartient à la gate séparée
`G4-K1-CONTROL-FIRST-CALIBRATION-V1` après préparation, revue et GO exact.

## D-037 — La première calibration est sérielle, observable et sans rerun automatique

Date: 2026-08-22

Status: accepté hors imprimante, non autorisé à l'exécution

La première calibration ne sera ni une macro monolithique, ni le bouton
générique de Mainsail. Le pilote local sépare préflight, chauffe/nettoyage/homing,
les deux meshes, leur qualification, la persistance mesh, chaque palier Z et
l'acceptation. Chaque phase laisse une preuve privée avant la suivante.

Le contexte initial a d'abord été figé avec `PEI_TEXTURED_A` ID `1`, plateau
`60 °C`, buse `140 °C` et stabilisation `600 s`. D-038 remplace le plateau et
la durée avant toute exécution ; la buse reste inchangée. Le reste reste :
nettoyage stock borné jusqu'à `180 °C`, mesh
`6 × 6` Lagrange sur `5–295 mm`. Deux mesures sont obligatoires et l'écart
absolu maximum entre points homologues doit rester à `0,025 mm`. Un KO coupe les
chauffes et s'arrête ; aucune troisième mesure automatique n'est autorisée.

Le profil initial prévu était `k1_p001_t060_r001_n06x06` ; D-038 le remplace
par l'identité thermique `t055`. Le Z part du seed
neutre explicite `0,0 mm`, suit uniquement les paliers d'ADR-005 et ne peut être
enregistré qu'après confirmation humaine puis remontée de `5 mm`.

`Cancel` ferme la session Z mais conserve le mesh qualifié. `Rollback` restaure
le `printer.cfg` exact et l'absence initiale du stockage Z, tout en conservant
le runtime et le chemin installés. Aucun acte de ce protocole n'est autorisé
avant le GO exact `GO G4-K1-CONTROL-FIRST-CALIBRATION-V1` sur le commit revu.

Une réussite qualifiera la première calibration mais ne validera ni l'autonomie
de calibration dans l'interface, ni l'autonomie production.

## D-038 — Le premier contexte PLA passe à 55 °C et 200 s

Date: 2026-08-22

Status: accepté hors imprimante, non autorisé à l'exécution

Avant toute calibration, Thomas remplace le plateau `60 °C` par `55 °C` et la
stabilisation `600 s` par `200 s`. La buse reste à `140 °C`. Tous les autres
paramètres et toutes les gardes de D-037 restent inchangés.

Les `200 s` sont une valeur de départ revue, pas une stabilité déjà prouvée.
L'exécution doit encore confirmer les tolérances thermiques puis la répétabilité
des deux meshes ; un écart arrête la gate sans prolongation ou rerun automatique.

L'identité thermique devient `55` et le profil qualifié prévu devient
`k1_p001_t055_r001_n06x06`. Le pilote, le contrat, le manifeste, les tests et la
documentation doivent être à nouveau figés ensemble.

Le mot `GO` joint à cette décision ne déclenche aucune action distante : il ne
reprend pas le nom exact de la gate et précède le nouveau commit revu. Après
intégration du candidat révisé, l'exécution exige toujours le GO exact
`GO G4-K1-CONTROL-FIRST-CALIBRATION-V1`.

## D-039 — Le premier couple de meshes est refusé sans rerun

Date: 2026-08-22

Status: accepté par exécution du contrat

Thomas a envoyé le GO exact sur le candidat figé à `55/140 °C` et `200 s`.
Préflight, backup, préparation et premier mesh ont passé leurs checkpoints. Le
second mesh a été mesuré une seule fois puis comparé au premier sur 36 points.

L'écart maximal observé est `0,062125 mm` et la moyenne `0,018049 mm`, pour le
seuil contractuel `0,025 mm`. La qualification est donc refusée. Conformément à
D-037 et D-038, le pilote coupe les chauffes et ne lance ni troisième mesure,
ni persistance mesh, ni session Z.

Cette mesure ne suffit pas à attribuer la divergence aux `200 s`, à la mécanique
ou au palpage. Le GO est consommé. Toute nouvelle campagne exige d'abord une
analyse hors imprimante et un protocole révisé explicitement autorisé.

## D-040 — V2 qualifie deux groupes robustes de trois meshes

Date: 2026-08-22

Status: exécuté et validé

Le module PR Touch exact et le journal privé montrent que les gros faux
contacts sont filtrés, mais que le bruit résiduel point par point rend deux
meshes insuffisants. Le code constructeur n'est pas modifié. V2 exécute six
meshes, réduit séparément les passages 1–3 et 4–6 par médiane point par point,
puis exige simultanément moyenne absolue `≤ 0,020 mm`, RMS `≤ 0,025 mm` et
maximum `≤ 0,060 mm` entre les deux groupes.

La médiane des six devient le candidat seulement après qualification. Elle est
chargée par l'endpoint Klipper exact, relue puis persistée. Aucun septième
passage ou ajustement automatique des seuils n'est autorisé.

L'exécution réelle a accepté les deux médianes avec moyenne absolue
`0,010788694 mm`, RMS `0,013996452 mm` et maximum `0,034352 mm`. Le profil
robuste est conservé. Le chemin Z a ensuite été repris avec Thomas présent,
confirmé physiquement et persisté à `−0,04 mm`. La validation finale est verte.

## D-041 — L'interface de calibration est un composant Moonraker borné

Date: 2026-08-22

Status: accepté hors imprimante, non autorisé à la pose

Une page JavaScript seule ne peut pas garantir l'arrêt des chauffes ni conserver
les six matrices si le navigateur se ferme. Un second serveur serait une
dépendance inutile. Le candidat retenu ajoute donc un petit composant au
Moonraker épinglé et sert une page statique sous `/k1-control/`.

Le serveur expose dix routes métier, jamais une route G-code libre. La chauffe
et la stabilisation sont annulables ; une primitive physique déjà engagée finit
avant l'arrêt, sans lancer la suivante. Le backup précède la chauffe et peut
restaurer exactement `printer.cfg` et l'état Z. La pose de l'interface est une
gate séparée qui redémarre Moonraker seulement et ne démarre aucune calibration.

## D-042 — `update_mesh` conserve le homing sur la K1 exacte

Date: 2026-08-22

Status: accepté par observation réelle

Sur la K1 exacte, l'endpoint Klipper `update_mesh` a remplacé la matrice active
et généré la section `K1_TRANSIENT` sans redémarrer Klipper : `standby`, homing
`xyz` et profil actif sont restés présents. Le premier validateur attendait une
perte du homing et a donc signalé un faux KO avant le commit final.

Avant toute reprise, le hash et le diff exact de `printer.cfg`, les composants
installés, le backup, le runtime Z vide et les 36 valeurs ont été revérifiés.
La commande `KCTRL_MESH_COMMIT` déjà incluse dans le protocole revu a ensuite
persisté le profil final et supprimé le transitoire. Le pilote attend désormais
explicitement `standby`, homing `xyz`, profil actif `K1_TRANSIENT` et présence
du profil avant sa relecture. Un test empêche le retour de l'attente erronée
d'un redémarrage.

## D-043 — Le premier Z est encadré par contact puis relâchement d'un cran

Date: 2026-08-22

Status: accepté par observation réelle

La cale disponible n'était pas certifiée. Sa mesure directe au pied à coulisse
était trop proche de la résolution de l'outil ; une pile de dix épaisseurs a
donné `0,90 mm`, soit environ `0,09 mm` par épaisseur. Les checkpoints ont prouvé
que chaque ajustement changeait bien l'origine et la position physique de
`0,01 mm`.

La friction nette est apparue à `−0,05 mm`. Le retour de `+0,01 mm` à
`−0,04 mm` a rendu la cale libre et vise donc le jeu de référence `0,10 mm`.
Thomas a confirmé cette observation avant le parcage et le commit atomique.

Klipper persiste les profils mesh générés sous l'en-tête commenté
`#*# [bed_mesh ...]`. Le validateur doit compter cette forme exacte, et non la
forme de section active non commentée. Cette correction locale ne change aucune
commande ni aucun fichier de l'imprimante.

## D-044 — L'UI doit accepter un Z déjà commité et prouver son import avant pose

Date: 2026-08-22

Status: accepté hors imprimante et confirmé par préflight en lecture seule

Après la première calibration validée, le chemin reste correctement en phase
`committed`. Exiger uniquement `idle` aurait bloqué la pose UI avant écriture et
toute nouvelle campagne. Le déployeur et le contrôleur acceptent donc exactement
les trois phases fermées `idle`, `committed` et `cancelled`, toujours avec
`motion_armed=0`. Aucun état intermédiaire n'est admis.

Le `curl` Creality exact ne supporte pas `-fsS` et son Moonraker attend `+` pour
les espaces des noms de macros. Les lectures ont été corrigées sur cette preuve
machine. Le préflight injecte désormais les deux sources par stdin, les compile
et les importe en mémoire sous le Python Moonraker `3.8.2` et ses vrais modules,
sans fichier distant. Le déployeur est épinglé comme les fichiers posés.

Le préflight réel en lecture seule est vert. Cette preuve ne constitue pas un GO
de pose et n'a redémarré aucun service.

## D-045 — Les transferts vers Dropbear forcent le protocole SCP historique

Date: 2026-08-22

Status: accepté hors imprimante après rollback réel

Le premier déploiement UI autorisé a atteint son backup exact puis le premier
transfert. L'OpenSSH Windows actuel emploie SFTP par défaut pour `scp`, tandis
que le Dropbear Creality ne fournit pas `/usr/libexec/sftp-server`. Le transfert
s'est donc fermé avant tout payload. Le rollback automatique a restauré la base
exacte et le préflight final est vert.

Le déployeur force désormais le protocole historique avec `scp -O`. Cette
option reste limitée à la fonction de transfert vers la K1 ; SSH, les hashes et
les contrôles ne changent pas. Le rollback supprime également les six noms de
staging exacts puis retire leur répertoire vide. Le script et son empreinte ayant
changé après le GO consommé, une seconde tentative exige un nouveau GO exact.

## D-046 — L'interface calibration utilise une origine navigateur isolée et un dossier traversable

Date: 2026-08-22

Status: accepté hors imprimante après second rollback réel

Le second déploiement UI a passé les contrôles par fichiers et API, mais la
recette dans le vrai navigateur a prouvé deux écarts. Sur
`127.0.0.1:4409/k1-control/`, le service worker de Mainsail renvoie sa propre
application. Sur l'origine distincte `localhost:4409`, nginx atteint bien la
route mais refuse le dossier UI créé en `0700`. Le journal nginx a confirmé
`Permission denied`. Le rollback exact a restauré l'état sûr.

La page calibration s'ouvre désormais par un lanceur dédié sur
`http://localhost:4409/k1-control/`. Elle conserve le même tunnel et la même
authentification nginx, sans ajouter de port ou de service sur la K1, mais son
origine navigateur distincte l'isole du service worker Mainsail. La session
d'authentification est propre à cette origine et doit donc être saisie une fois
par l'opérateur.

Le déployeur crée explicitement le dossier UI en `0755` et le validateur exige
ce mode exact en plus des empreintes. Toute autre permission, ou toute réponse
Mainsail à la place de la page K1 Control, est un KO. Ces changements suivent
l'ADR-009 et exigent un nouveau GO exact avant pose.

## D-047 — L'état serveur reprend le formulaire, les confirmations physiques ne sont jamais héritées

Date: 2026-08-22

Status: accepté hors imprimante

Une campagne serveur survit volontairement à la fermeture du navigateur, mais
la première interface ne restaurait pas ses paramètres dans le formulaire. Plus
grave, après les six meshes, la case « plateau libre » revenait décochée au
rechargement tout en restant désactivée ; le Z devenait impossible à lancer
depuis l'écran.

Le statut métier expose désormais le Z accepté du runtime. À son premier rendu,
le navigateur reprend ce seed, ou les paramètres exacts de la campagne si elle
existe. Cette hydratation n'est faite qu'une fois par campagne afin de ne pas
écraser les modifications humaines pendant l'édition.

Les confirmations physiques ne sont jamais reprises de l'état serveur :
« plateau libre » et « buse propre » doivent être cochées à nouveau par
l'opérateur. Elles restent accessibles après rechargement et conditionnent
ensemble le bouton de démarrage Z. Cette séparation permet une vraie reprise
sans console tout en refusant de transformer une observation passée en fait
physique courant.

## D-048 — La limite PRTouch réelle fixe l'usage quotidien à un mesh `6 × 6`

Date: 2026-08-23

Status: accepté hors imprimante

La campagne `20260823-021858-540-calibration-ui-v1` a atteint exactement
`g29_cnt=36`, puis le wrapper Creality a levé `IndexError` avant le
trente-septième point. Les trente-six tables usine par point confirment que les
grandes matrices de l'ADR-010 dépassent la frontière physique du PRTouch exact.

Le contournement communautaire par `pr_version: 1` et retrait des tables de
compensation est rejeté : il change le mode du capteur, perd les corrections
usine et comporte un retour de démarrage bloqué après coupure électrique. Aucun
risque de ce type n'est acceptable pour gagner une résolution fictive.

K1 Control expose donc uniquement `6 × 6` Lagrange et exécute un seul mesh par
calibration quotidienne. Les six meshes de FIRST-CALIBRATION-V2 restent la
qualification statistique initiale déjà réussie ; ils ne sont pas répétés à
chaque usage. Le serveur et l'adaptateur refusent toute autre taille avant
chauffe. Cette décision est détaillée dans l'ADR-012.

## D-049 — La limite de 36 contacts ne limite pas le profil composite final

Date: 2026-08-23

Status: accepté hors imprimante ; amende D-048 pour le futur mode précision

L'audit complémentaire distingue maintenant l'acquisition et le profil. Le
PRTouch V2 exact reste strictement limité à 36 contacts par séquence. Les 36
paires de seuils de la configuration exacte ont cependant toutes les mêmes
valeurs, et six séquences successives ont déjà prouvé la remise à zéro du
compteur entre deux maillages.

Un mode précision peut donc être qualifié sans modifier `pr_version` ni retirer
les tables : quatre sous-grilles bornées `6 × 6`, `5 × 6`, `6 × 5`, `5 × 5`
dans la même chauffe et le même référencement, puis fusion de 121 mesures
physiques en un profil `11 × 11` bicubique. Le prototype hors imprimante refuse
toute rupture de session, tout restart, dépassement, trou, doublon ou valeur non
finie.

D-048 reste la règle du mode standard et de l'interface actuellement sûre : un
seul `6 × 6`. Le composite est une mission séparée qui ne devient visible
qu'après qualification physique, comparaison de première couche, coupure
complète, reprise et preuve des deux CFS. La décision détaillée est l'ADR-013.

## D-050 — Le préflight MATRIX doit prouver le refus des anciennes matrices

Date: 2026-08-23

Status: installé et validé sous la capture `20260823-161103-g4-k1-control-calibration-ui-matrix-v1`

Après le GO exact MATRIX-V1, la revue locale obligatoire a trouvé deux restes
du contrat historique : l'import distant demandait encore au core d'accepter
`9 × 9`, `11 × 11` et `15 × 15`, et la validation cherchait des marqueurs
statiques supprimés par le nouveau payload `6 × 6`. Le préflight aurait donc
échoué avant mutation, mais ce conflit a été corrigé avant toute connexion SSH.

Le préflight exécute maintenant sur le Python Moonraker exact l'acceptation de
`6 × 6` Lagrange et le refus de `3/4/5/9/11/15` ainsi que de `6 × 6`
bicubique. La baseline épingle aussi le composant BED-MESH-V2 déjà posé et
`printer.cfg`. La validation exige Moonraker prêt, aucune composante échouée ni
avertissement, le Z accepté, le profil robuste, `6 × 6` Lagrange chargé et les
deux CFS connectés.

Ces changements renforcent les commandes revues après le GO. Conformément à
D-027, aucune pose n'est autorisée avant un nouveau GO exact MATRIX-V1 sur le
commit corrigé.

Ce GO renouvelé a ensuite ouvert le préflight SSH réel. Il s'est arrêté avant
toute écriture sur `phase=rolled_back`, `busy=false`, état terminal sûr produit
par la restauration de campagne. Le core, l'interface et les autres gardes de
déploiement reconnaissent déjà cet état. La garde MATRIX l'accepte désormais
explicitement, sans élargir les phases actives ou échouées acceptables. Comme ce
changement modifie encore le script revu, D-027 impose un nouveau GO exact avant
la pose.

Thomas a ensuite autorisé ce GO à rester valable pour les corrections
nécessaires jusqu'au vert. Le préflight corrigé, la pose et deux validations ont
réussi. La pose a remplacé uniquement le core et deux fichiers statiques après
backup exact, puis redémarré seulement Moonraker. Les fichiers hors write-set,
l'état physique inactif, le profil robuste, le Z accepté, les deux CFS et les
listes `failed_components=[]` / `warnings=[]` sont conformes. MATRIX-V1 est
close ; cette autorisation ne couvre aucune calibration ni gate suivante.
