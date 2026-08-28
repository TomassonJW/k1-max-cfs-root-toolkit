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
vérité. Un remplacement équivalent conserve la cible active. D-064 précise
ensuite le vrai changement de matière en trois phases explicites : retrait de
l'ancien, purge de transition et cible du prochain outil. La base générique CFS
ne doit jamais écraser ces valeurs.

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

## D-051 — Une fin non acceptée du mesh unique réinitialise les confirmations

Date: 2026-08-23

Status: installé et validé sous la capture `20260823-164558-g4-k1-control-calibration-ui-retry-safety-v1`

La règle historique de reprise comparait `mesh_index < mesh_target_count`, ce
qui convenait au protocole de six passages. Après le passage au mesh quotidien
unique, l'échec réel conserve `mesh_index=1` et `mesh_target_count=1` tout en
finissant `rolled_back` sans mesh accepté. La comparaison numérique ne prouve
donc plus qu'une tentative est sûre à reprendre.

L'interface réinitialise désormais une fois `replace_existing=false` et
`plate_clear=false` pour les phases terminales non acceptées `cancelled`,
`failed`, `mesh_rejected` et `rolled_back`. La clé campagne + phase empêche de
réappliquer ce reset pendant les rafraîchissements de la même page : l'opérateur
peut encore recocher volontairement le remplacement. Un rechargement frais
réapplique la sécurité. Cette décision ne change ni l'API, ni le core, ni un
service, ni le comportement physique de la K1.

## D-052 — La persistance du mesh quotidien autorise uniquement le bloc de points qualifié

Date: 2026-08-24

Status: campagne validée sous la capture `20260823-171803-g4-k1-control-calibration-ui-campaign-v1`

La campagne quotidienne doit remplacer le contenu du profil
`k1_p001_t055_r001_n06x06`. Exiger après acceptation le hash complet de
`printer.cfg` pris avant la mesure transforme donc le résultat attendu en faux
KO. À l'inverse, ignorer tout le fichier après campagne masquerait une mutation
hors périmètre.

Le validateur final exige désormais le backup exact dont le hash correspond à
la base revue, compare le nombre et l'ordre des lignes, puis autorise des
différences uniquement sur les six lignes de points du profil qualifié. Les 36
valeurs persistées doivent correspondre à la matrice privée acceptée avec une
tolérance de `0,000001 mm`. Toute autre différence, un autre chemin de backup,
une matrice incomplète ou un profil ambigu reste un KO.

Cette règle a obtenu `CAPTURE_CALIBRATION_UI_LEVEL_OK level=supported` puis
`VALIDATE_CALIBRATION_UI_CAMPAIGN_V1_OK`. Elle ne permet aucune nouvelle mesure,
aucun deuxième passage et aucune modification de configuration hors du profil
explicitement enregistré.

## D-053 — Le profil composite doit être construit après les quatre captures

Date: 2026-08-24

Status: décision candidate hors imprimante ; aucune persistance autorisée

Le `bed_mesh.py` Creality sait recalculer les points d'une acquisition depuis
`MESH_MIN`, `MESH_MAX` et `PROBE_COUNT`. En revanche, son endpoint
`update_mesh` remplace seulement la matrice observée du `ZMesh` actif. Il ne
transforme pas le dernier profil `5 × 5` en un nouvel objet `11 × 11`.

La campagne complète ne doit donc jamais injecter directement ses 121 valeurs
dans ce profil actif. Elle compose d'abord les quatre partitions strictes en
mémoire, coupe les chauffes, puis prépare un bloc Klipper complet avec ses
paramètres `11 × 11`, bicubiques et `5..295 mm`. Le prototype refuse une recette
différente, un profil cible déjà présent ou une base sans profil robuste unique.

Cette décision décrit la forme du futur candidat, pas son autorisation. Aucun
déployeur ni orchestrateur complet n'est créé avant la preuve physique
SUBGRID-V1. La transaction de fichier, le parse Python exact, le restart, la
relecture et le rollback bit à bit restent des gates obligatoires séparées.

## D-054 — L'autorité porte sur l'objectif, pas sur une phrase littérale

Date: 2026-08-24

Status: acceptée explicitement par Thomas ; règle permanente du projet

Un Goal actif ou une mission clairement décrite autorise Codex à réaliser de
bout en bout les actions normalement nécessaires dans ce périmètre. Thomas n'a
plus à recopier un nom de gate, un `GO` exact ni à renouveler une permission
après chaque correction revue. Une délégation générale confirme le périmètre
actif déjà décrit ; elle ne crée pas d'autorité future ou implicite.

Les gates `G4-*` deviennent exclusivement des contrôles techniques : périmètre,
état frais, backup, empreintes, validation, absence d'effet hors write-set et
rollback. Codex fournit lui-même leur identifiant aux scripts. Une correction
du candidat déclenche une nouvelle revue et de nouveaux tests, puis la mission
continue sous la même autorité.

Une restriction explicite plus récente reste prioritaire. Une action physique
doit figurer dans l'objectif actif et une donnée physique inconnue ne peut pas
être présentée comme vérifiée. Une confirmation comme « plateau libre » peut
donc rester nécessaire comme fait observable, jamais comme formule
d'autorisation. Les dialogues techniques imposés par la plateforme ne peuvent
pas être supprimés par le dépôt. Voir ADR-014.

## D-055 — Le bouton Mainsail utilise un alias exclu du service worker

Date: 2026-08-24

Status: décision acceptée et validée dans le vrai navigateur ; aucune action physique

NAVIGATION-V1 a posé les bons octets et Mainsail a affiché son bouton, mais le
clic vers `/k1-control/` a été intercepté par le `NavigationRoute` du service
worker installé. Ce worker renvoie `index.html` pour les navigations, sauf une
denylist dont le premier préfixe est `/access`.

Modifier le worker généré est refusé. NAVIGATION-V1-R2 crée à la place l'alias
symbolique original `access-k1-control -> k1-control` dans la racine statique et
repointe `navi.json` vers `/access-k1-control/`. Le chemin échappe au worker,
reste sur la même origine et réutilise l'authentification courante. La pose ne
redémarre aucun service et le rollback restaure exactement V1 puis retire
l'alias.

## D-056 — Une capture composite complète survit aux courses de redémarrage

Date: 2026-08-24

Status: décision installée et validée sur la sous-grille physique `5 × 5`

La matrice de 25 contacts était complète et validée avant le restart de
nettoyage, mais Klipper a brièvement accepté les lectures tout en refusant les
commandes. Une telle course ne justifie ni de perdre les mesures ni de refaire
les contacts. Les commandes de restauration sont désormais retentées de façon
bornée ; un état `failed` ne peut être requalifié que s'il contient la matrice
`5 × 5`, le backup et le contexte exacts, puis seulement après retour du profil
robuste et de toutes les gardes sûres.

Le composant utilisait aussi `schema: 1` alors que le stockage partagé exige
`version: 1`. La reprise migre uniquement ce marqueur par remplacement atomique,
après backup exact, sans modifier la matrice ni son contexte. Le rollback garde
un état chargeable par l'ancienne révision. Cette décision ne couvre aucune
deuxième sous-grille ni la persistance `11 × 11`.

## D-057 — Le composite retenu utilise quatre carrés et un alignement additif borné

Date: 2026-08-24

Status: décision installée et qualifiée sur la K1 réelle

La recette rectangulaire `6 × 6`, `5 × 6`, `6 × 5`, `5 × 5` est rejetée. Le
wrapper propriétaire termine bien les 30 contacts d'un rectangle `5 × 6`, puis
échoue dans son post-traitement. La recette retenue utilise quatre quadrants
carrés `6 × 6`, chacun compatible avec le chemin PRTouch exact, dans une seule
chauffe et un seul référencement. Elle produit 144 contacts et 121 positions
uniques.

Les positions communes ont révélé un biais presque constant propre à chaque
quadrant, introduit par le post-traitement propriétaire : l'écart brut maximal
était `0,147858 mm`. La fusion peut corriger uniquement un décalage additif par
quadrant, estimé par moindres carrés sur les recouvrements et recentré à moyenne
pondérée nulle. Elle ne peut appliquer ni pente, ni surface libre, ni correction
point par point. Après cet alignement, l'écart maximal vaut `0,043745029 mm` et
la moyenne `0,013871331 mm`, sous la limite revue de `0,05 mm`.

La capture physique complète ne doit pas être rejouée quand ses 144 contacts,
son contexte, son backup et ses empreintes sont intacts. Une reprise logique
séparée peut composer, persister puis relire le profil `11 × 11` sans chauffe,
homing, mouvement ou mesure. Le profil robuste `6 × 6` est rechargé à la fin.
L'exposition du mode Précision dans l'interface reste conditionnée par une
comparaison de premières couches montrant un gain utile.

## D-058 — La comparaison de première couche change uniquement le profil chargé

Date: 2026-08-24

Status: décision rejetée par l'essai physique ; V1 close KO

La paire utilise le carré PLA Geeetech `200 × 200 × 0,20 mm` déjà qualifié sous
G3, avec son empreinte exacte. Les deux G-code conservent le même T0, les mêmes
températures, le même démarrage stock et l'ancien Z Orca `+0,27 mm`. Leur seule
différence sémantique est la ligne `BED_MESH_PROFILE LOAD` placée après le
retour de `START_PRINT`.

Cette isolation était insuffisante : l'ancien `+0,27 mm` est environ `0,31 mm`
au-dessus du Z accepté `−0,04 mm`. Le passage robuste a donc produit une couche
trop haute et le composite n'a pas été lancé. Les fichiers distants sont
supprimés. Une comparaison future doit d'abord qualifier son Z absolu sur un
motif court ; l'égalité entre A et B ne compense jamais une valeur physique
fausse.

## D-059 — Une comparaison relative exige d'abord une première couche absolue valide

Date: 2026-08-24

Status: décision issue d'un KO physique

Avant toute paire de profils, un motif court et borné doit prouver que le Z
effectivement appliqué pendant l'extrusion correspond au Z accepté. Le contrôle
doit relire `gcode_move.homing_origin` après `START_PRINT`, avant le premier
mouvement de couche. Une ancienne correction Orca, même identique dans les deux
variantes, ferme la gate si elle contredit le stockage Z qualifié.

Le passage composite ne démarre jamais pour « voir quand même » après un défaut
du passage robuste. Le profil robuste reste chargé et le protocole fautif est
retiré de la K1 avant toute autre action physique.

## D-060 — Le composite `11 × 11` apporte un gain central mais échoue aux bords

Date: 2026-08-24

Status: décision issue de la comparaison physique V2 ; mode Précision toujours
fermé

La comparaison V2 a imprimé le profil composite avec un Z temporaire
`−0,24 mm`, observé pendant l'extrusion et non persisté. Thomas constate une
amélioration nette sur une grande zone centrale, mais plusieurs bandes de bord
restent beaucoup plus mauvaises, avec plis, arrachements et défauts localisés.
Le profil composite ne peut donc pas être promu dans l'interface quotidienne.

Le calcul hors imprimante reproduit le `bed_mesh.py` exact. Le bicubique actif
ne diffère d'une surface directe que de `0,009877883 mm` au maximum, dont
`0,009712808 mm` dans la bande extérieure. L'interpolation est une contribution
secondaire, pas la cause principale des défauts visibles. La différence locale
de forme entre robuste et composite atteint environ `±0,087 mm` après retrait
de la constante globale.

Le profil physique `k1_p001_t055_r001_n11x11` est conservé comme source, le
robuste reste le repli et le même motif V2 ne doit pas être rejoué sans
correction. L'état distant final après la fin de l'impression n'a pas été
re-préflighté pendant cette analyse.

## D-061 — Les corrections locales créent un profil dérivé immuable et auditable

Date: 2026-08-24

Status: architecture retenue pour prototype hors imprimante

K1 Control recevra un éditeur de grille `11 × 11`. Il ne modifiera jamais le
profil physique source ni le Z accepté. Chaque correction produit un profil
dérivé nommé et versionné, avec matrice source, deltas, matrice finale, contexte,
résultat physique et rollback.

La correction appliquée est normalisée à moyenne pondérée nulle afin de ne pas
devenir un offset Z global via le `fade_target` moyen de Klipper. L'interface
emploie `Rapprocher` et `Éloigner`, avec pas de `0,005/0,010 mm`, historique et
bornes. La vue 3D sert à inspecter ; la V1 modifie les valeurs depuis une grille
2D, pas par glisser-déposer imprécis.

Mainsail `v2.18.2` reste intact : son code ne fournit que le rendu des matrices
et les actions charger/renommer/supprimer. L'éditeur appartient à K1 Control.
Une erreur non répétable ou dépendante de la tension du tube PTFE ferme la gate
jusqu'à correction mécanique. Voir ADR-015.

## D-062 — K1 Control possède le cycle de travail, pas seulement des correctifs autour de `START_PRINT`

Date: 2026-08-24

Status: architecture retenue pour simulation ; production fermée

Le profil Orca final enverra un unique contrat `KCTRL_JOB_BEGIN`. Il ne cumulera
plus `G28`, `Tn`, `START_PRINT` et un offset post-traité. K1 Control pilotera
admission, chauffe du plateau lancée immédiatement, référence grossière
conditionnelle, nettoyage, référence Z finale, chargement mesh/Z, chargement et
purge CFS, amorçage, pause, reprise, changement, runout et fin.

Une pause normale ne déclenche ni coupe, ni changement, ni purge par défaut.
Le Z le plus récent ne peut pas être écrasé par un snapshot de reprise. Les
températures CFS viennent du contrat du matériau et restent surveillées pendant
toute la transition ; une réécriture tardive à `220 °C` ferme la phase au lieu
d'être masquée par un `M104` envoyé après coup.

Le cœur `box_wrapper` compilé n'est pas remplacé en bloc au premier incrément.
Ses primitives sont orchestrées et vérifiées ; une primitive n'est remplacée
que si les traces prouvent qu'elle empêche cette propriété. Le retrait de
l'ancien `+0,27 mm` est atomique avec la bascule Orca finale. Voir ADR-016.

## D-063 — La moyenne d'un profil dérivé est celle de sa surface Klipper

Date: 2026-08-25

Status: implémentée et validée hors imprimante

Une correction locale n'est pas recentrée par la simple moyenne des 121 points.
Le moteur reconstruit la surface cardinale bicubique `31 × 31` correspondant
au profil qualifié : `mesh_x_pps=2`, `mesh_y_pps=2`, `bicubic` et tension
`0.2`. Il retire la moyenne arithmétique des 961 valeurs interpolées à toute
la matrice de correction. Cette opération linéaire conserve la forme locale et
empêche la correction de devenir un Z global par la moyenne de fade.

Le profil physique `k1_p001_t055_r001_n11x11` reste immuable. Le dérivé
`k1_p001_t055_r001_n11x11_tuned_v001` conserve séparément la demande brute,
la correction normalisée, la matrice finale, l'historique, les gardes et la
qualification. Le Z global est absent du modèle et un export qui tente de
l'inclure est refusé.

La V1 reste un laboratoire local : fausse API en mémoire, serveur lié seulement
à `127.0.0.1`, export déterministe mais aucune pose, aucun transport K1 et
aucune activation du mode Précision. Le passage de cette gate ouvre uniquement
la préparation de `MESH-EDGE-DIAGNOSTIC-V1`.

## D-064 — Le cycle filament est un contrat explicite et conserve le bon filament engagé

Date: 2026-08-26

Status: contrat V1 figé hors imprimante ; production fermée

K1 Control possède toutes les phases du travail, mais aucune température cachée.
Le plateau et la buse suivent le contrat G-code ou la dernière action explicite
de Thomas. Un changement entre matières distingue la température de retrait de
l'ancien filament, la température de purge de transition et la température du
nouveau segment. Ces valeurs sont déclarées et bornées ; le CFS ne choisit
jamais son `220 °C` comme repli.

L'état filament n'est pas un booléen. Il distingue absence confirmée, engagement
connu, engagement inconnu, transition et défaut. Les capteurs prouvent seulement
une présence à leur emplacement ; l'identité et le débit exigent mapping
CFS/slot, historique accepté et purge réellement visible. Aucun `T0` n'est
supposé.

Le bon filament déjà engagé reste engagé au démarrage et, sous réserve de
qualification physique, à la fin. Il reçoit seulement une petite purge de
preuve. Le retrait devient l'action séparée `Désengager et nettoyer`, avec la
recette de l'ancien matériau et sans réchauffage différé sans présence humaine.

Le nettoyage autonome effectue référence grossière, chauffe au-dessus du
réceptacle, mouvements de brosse bornés, remontée et cibles zéro. La hauteur de
brosse est calibrée humainement à froid ; aucune palpation automatique de la
brosse ni température universelle `+10/+20`, `−30` ou `100 °C` n'est retenue.
Une calibration Z/mesh de métrologie garde le nettoyage manuel comme choix par
défaut jusqu'à qualification physique de la recette automatique.

Le premier motif de `MESH-EDGE-DIAGNOSTIC-V1` est classé invalide : il a chauffé
et bougé sans déposer de filament parce que le chemin minimal ne résolvait ni
outil CFS, ni chargement, ni purge. Il ne prouve ni une buse bouchée ni le mesh.
Le rollback exact et sa validation finale sont maintenant verts sous la capture
`20260826-090956-mesh-edge-diagnostic-v1`. La gate reste suspendue jusqu'à une
reprise sans `T0` supposé, avec route filament résolue et purge visible fraîche.

Voir `docs/25-contrat-cycle-impression-nettoyage-cfs-v1.md`,
`design/job-lifecycle-contract-v1.json` et ADR-016.

## D-065 — Une présence CFS sans route courante est `engaged_unknown`

Date: 2026-08-26

Status: audit en lecture seule validé ; action physique bloquée

La K1 expose deux objets `filament_switch_sensor`. Le premier est activé et
détecte une présence sur `!PC15`. Le second est désactivé, vaut faux, utilise
`^!nozzle_mcu:PA10` et est référencé par `box.cfg`. Ces associations logicielles
n'autorisent pas à inventer leur emplacement physique ni à transformer la
valeur du second capteur désactivé en preuve d'absence.

Les fiches matière `T1/T2` et `A..D` sont un inventaire déclaré. Les journaux
prouvent qu'un outil logique peut être remappé vers un autre slot physique. Au
moment de la capture, `box.t_command` est vide et `tn_data.json` ne conserve
aucune route courante `tnn_map`, `last_cmd` ou `last_tnn`. Une ancienne route
du journal ne peut donc pas être réutilisée comme route active.

L'état observé est `engaged_unknown` : présence oui, identité non résolue,
route non résolue et débit non prouvé. La reprise s'arrête avant toute
extrusion. Seule une future gate physique distincte peut résoudre la route et
obtenir une petite purge réellement visible. Aucun `T0` n'est supposé.

Voir `docs/26-audit-cfs-lecture-seule-v1.md`,
`design/cfs-read-only-preflight-v1.json` et
`packages/k1-control-v1/cfs-read-only-audit-v1/RESULT.md`.

## D-066 — Une frontière CFS protège aussi le plateau et le Z

Date: 2026-08-26

Status: garde V1 validée hors imprimante ; séquence brute refusée ; production
fermée

Le passage physique vers `CFS1 / A` a prouvé la route et le débit pour ce moment,
mais il a aussi prouvé que les primitives brutes ne respectent pas le contrat :
la demande `190 °C` a été remplacée par `220 °C` et un homing X/Y a été lancé.
Le plateau est resté à cible zéro pendant cet incident, sans que cela donne au
CFS le droit de le commander. Aucun dommage visible n'a été constaté par Thomas.

Une frontière CFS protège désormais six états ensemble : cible buse, cible
plateau, Z accepté, origine Z courante, profil mesh et axes référencés. Le
positionnement de purge appartient au pilote de mouvement avant la frontière ;
la hauteur stock `Z=30 mm` a été validée à froid par Thomas. Aucun homing, offset
ou changement de mesh n'est permis dans la phase filament.

Une correction tardive de température est refusée comme architecture : elle ne
rend pas correcte une purge déjà commencée. Une différence Z bloque sans
restauration automatique de l'ancienne valeur. Le cœur `box_wrapper` ne sera
remplacé que si l'analyse hors imprimante du binaire et la qualification de
primitives étroites montrent qu'aucune route stock ne respecte ces invariants.

Voir ADR-017, `docs/27-incident-cfs-temperature-geometrie-v1.md` et
`packages/k1-control-v1/cfs-boundary-guard-v1/`.

## D-067 — L'endpoint réseau privé reste derrière `k1max-root`

Date: 2026-08-26

Status: appliqué et validé localement ; aucune mutation K1

Les scripts, les déployeurs et les lanceurs conservent un seul nom logique :
`k1max-root`. Ils ne stockent jamais l'adresse privée de la K1. La réservation
DHCP stable est portée par la configuration SSH locale ; `HostKeyAlias`
conserve l'identité de clé déjà connue et `StrictHostKeyChecking` reste actif.

Mainsail passe par le tunnel `127.0.0.1:4409:127.0.0.1:4409`. K1 Control utilise
la même origine locale et `navi.json` un chemin relatif. Aucun de ces éléments
ne dépend donc de l'adresse DHCP de la K1 et aucune modification distante n'est
requise lors d'un changement d'endpoint local.

Voir `docs/28-routage-reseau-k1-v1.md`.

## D-068 — Aucune primitive stock n'entre encore dans l'adaptateur CFS

Date: 2026-08-26

Status: audit exact clos en lecture seule ; adaptateur fail-closed ; production
fermée

Le binaire `box_wrapper` capturé correspond exactement à l'empreinte historique.
Il expose une surface thermique et géométrique comprenant notamment la
température matière, des commandes `M109/M104`, `G28 X Y`, la position sûre et
`BED_MESH_CLEAR`. Le journal complet de l'incident prouve que le chemin de
chargement a choisi `220 °C` et déclenché sa géométrie avant la purge de 10 mm,
alors même que celle-ci conservait son paramètre `TEMP=190`.

`BOX_EXTRUDE_MATERIAL` est donc refusée. `BOX_EXTRUDER_EXTRUDE` et
`BOX_MATERIAL_FLUSH` ne sont pas déclarées sûres : le passage les appelait dans
le même script sans snapshot complet entre les commandes. L'adaptateur étroit
V1 conserve une liste de primitives appelables vide et n'est pas un candidat de
pose.

La branche suivante est la préparation hors imprimante d'un propriétaire
filament minimal séparé, sauf si une preuve statique plus forte qualifie une
primitive étroite. Remplacer tout `box_wrapper`, corriger la température après
coup ou lancer un nouvel essai physique sont refusés dans cette gate.

Voir ADR-018, `docs/29-audit-box-wrapper-et-adaptateur-cfs-v1.md` et
`packages/k1-control-v1/cfs-box-wrapper-audit-v1/`.

## D-069 — Les températures d'impression appartiennent à la phase du travail

Date: 2026-08-26

Status: recherche hors imprimante close ; conception suivante autorisée hors
K1 seulement ; production fermée

La température `220 °C` de l'incident a été résolue depuis le type matière du
slot et sa base locale. Inscrire une autre valeur dans cette base peut donc
modifier un palier de buse, mais ne porte ni la distinction première
couche/régime normal, ni les deux températures du plateau, ni la géométrie de
purge.

Le contrat du travail devient la source principale de
`NOZZLE_FIRST`, `NOZZLE_NORMAL`, `BED_FIRST` et `BED_NORMAL`. Chaque frontière
CFS doit recevoir la cible de buse de sa phase et préserver séparément celle du
plateau. Une réaffirmation après `T` reste une défense, pas la preuve qu'une
purge antérieure était correcte.

La base matière CFS reste un filet de sécurité statique. Sa réécriture
dynamique par travail est refusée sans preuve de relecture à chaud, d'isolation
par slot, de rollback et d'absence d'effet sur les deux CFS, le refill et la
reprise.

La prochaine mission est
`G4-K1-CONTROL-CFS-DYNAMIC-TEMP-ROUTING-V1`, strictement hors imprimante. Toute
pose ou action physique formera une gate ultérieure avec autorisation fraîche.

Voir ADR-019 et `docs/30-audit-routage-temperatures-cfs-v1.md`.

## D-070 — Le routage dynamique utilise un ticket thermique et un propriétaire minimal

Date: 2026-08-26

Status: conception et simulation closes hors imprimante ; transport, pose et
production fermés

La mission `G4-K1-CONTROL-CFS-DYNAMIC-TEMP-ROUTING-V1` compare quatre voies.
La base matière reste un filet statique ; une réaffirmation après `T` reste une
défense tardive ; l'interception de `get_material_target_temp` est refusée faute
de point d'extension stable et parce que le chemin stock conserve la géométrie.

Le choix de conception est `minimal_separate_filament_owner`. Chaque frontière
reçoit avant son premier effet un ticket immuable avec travail, phase,
opération, outil logique, route CFS/slot fraîche, cible buse, cible plateau et
snapshot des six invariants. Une preuve de route n'est utilisable qu'une fois et
une reconnexion invalide sa révision.

Le contrat expose désormais séparément retrait, chargement et purge. Refill et
runout équivalents conservent la dernière cible explicite ; une pause normale
n'appelle aucun CFS. Toute cible cachée, route absente ou incohérente, commande
thermique/géométrique CFS, preuve de débit manquante ou dérive Z/mesh coupe les
deux cibles et bloque la reprise sans restauration Z aveugle.

Le paquet hors ligne obtient `25/25` scénarios. Il ne contient aucun transport
K1, script de pose ou température matière codée dans le moteur ; il n'est pas
un candidat de déploiement. La prochaine mission unique est la cartographie
hors imprimante du protocole minimal.

Voir ADR-020, `docs/31-routage-dynamique-temperatures-cfs-v1.md` et
`packages/k1-control-v1/cfs-dynamic-temp-routing-v1/`.

## D-071 — Le protocole minimal CFS ferme en KO borné avec une liste vide

Date: 2026-08-26

Status: gate close hors imprimante ; preuves insuffisantes ; production fermée

`G4-K1-CONTROL-CFS-MINIMAL-OWNER-PROTOCOL-V1` ne déduit aucune trame depuis un
nom Cython ou une symétrie de slot. Les quatre captures privées sont épinglées
par empreinte et restent hors Git ; leur carte publique retire les identifiants
matériels.

Le journal prouve des requêtes sur les adresses 1 et 2 et une seule route
d'effet `T1A`, adresse 1, slot A. Il ne prouve ni retrait, ni coupe ou purge
isolée, ni B/C/D, ni effet sur le second CFS. La règle d'intégrité, la
resynchronisation et l'exclusion du propriétaire constructeur sont également
inconnues. Deux mentions d'un heartbeat désactivé ne constituent pas un contrat
d'exclusion et de restitution.

La décision est donc `gate_verdict=KO_BOUNDED`, `callable_messages=[]`, aucun
transport et aucun candidat de pose. Un émulateur hors ligne met en quarantaine
les clés `(adresse, commande)` après timeout, refuse les doublons et invalide
les routes après reconnexion ou changement de mapping. Sa matrice `25/25`
prouve le refus sûr, pas une capacité matérielle.

La branche suivante peut seulement acquérir ou préparer les preuves manquantes.
Toute connexion à la K1 ou action filament exigera une autorité fraîche.

Voir ADR-021, `docs/32-protocole-proprietaire-filament-minimal-cfs-v1.md` et
`packages/k1-control-v1/cfs-minimal-owner-protocol-v1/`.

## D-072 — La preuve de retrait enrichit le dossier sans ouvrir la surface appelable

Date: 2026-08-26

Status: gate de preuve close hors imprimante ; avancée partielle ; production
fermée

`G4-K1-CONTROL-CFS-MINIMAL-OWNER-EVIDENCE-V1` trouve dans un ancien journal un
cycle constructeur de retrait sur le chemin `T1A`. Deux requêtes locales
`0x11`, vers le tampon puis le capteur matière, reçoivent chacune une réponse
d'état zéro avec un timeout hôte de 150 secondes. Le capteur local passe de
présent à libre.

Les deux fichiers qui portent ces lignes ne comptent pas comme deux essais : le
premier est le préfixe exact du second. Une règle CRC-8 publique redonne l'octet
final de la réponse capturée, mais la requête complète sur le fil reste absente.

La rétroanalyse publique la plus détaillée utilise une table de commandes
différente de la capture locale. Elle reste un appui sémantique, jamais une
preuve de trame pour ce binaire.

La liste reste `callable_messages=[]`. La prise exclusive et la restitution du
propriétaire stock, les autres slots, le second CFS, la coupe, la purge et les
reprises après faute ne sont pas qualifiés. Aucun transport ni paquet de pose
n'est créé.

La prochaine gate possible est une capture passive revue séparément. Elle ne
peut ni se connecter ni démarrer sans le GO exact
`GO G4-K1-CONTROL-CFS-MINIMAL-OWNER-PASSIVE-CAPTURE-V1`.

Voir ADR-022, `docs/33-preuves-proprietaire-filament-minimal-cfs-v1.md` et
`packages/k1-control-v1/cfs-minimal-owner-evidence-v1/`.

## D-073 — Le retrait immédiat reste propriétaire Creality mais devient gardé

Date: 2026-08-27

Status: capture réelle close ; retrait stock `T1A` qualifié ; propriétaire
série indépendant toujours fermé ; production fermée

Sous le GO exact `G4-K1-CONTROL-CFS-MINIMAL-OWNER-PASSIVE-CAPTURE-V1`, une
écoute sans écriture a encadré un lancement explicitement autorisé de
`BOX_QUIT_MATERIAL`. La route fraîche était `T1A`. La macro a terminé, les deux
phases de retrait ont répondu et le premier CFS est passé de `A` à `None`.

La K1 a demandé elle-même `220 °C`, puis a laissé cette cible active après la
fin de la macro. `TURN_OFF_HEATERS` a été nécessaire et son effet à zéro a été
relu. Une tentative `%20` mal encodée a aussi montré qu'un `result=ok` HTTP ne
prouve pas l'exécution du G-code.

Le capteur de la tête reste actif après le retrait côté CFS : le segment situé
après le cutter n'est pas retiré par cette action. La coupe appartient à la
séquence stock, mais aucun capteur dédié ou retour humain ne la qualifie
directement.

La décision est de préparer un garde autour de la macro stock avant de poursuivre
un propriétaire série indépendant. Ce garde devra vérifier l'état avant et
après, surveiller la vraie fin et couper toujours les chauffes. La liste série
reste `callable_messages=[]`.

Voir ADR-023, `docs/34-capture-retrait-officiel-cfs-v1.md` et
`packages/k1-control-v1/cfs-minimal-owner-passive-capture-v1/`.

## D-074 — Le retrait stock exige une preuve d'effet et aucun retry automatique

Date: 2026-08-27

Status: garde close hors imprimante ; tests verts ; aucun transport ;
production fermée

`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-V1` enveloppe la macro Creality sans
reproduire le protocole série. Avant effet, elle refuse une machine occupée, un
CFS incomplet, une commande active ou une route ambiguë sans envoyer aucun
G-code.

Après une tentative unique de `BOX_QUIT_MATERIAL`, une réponse HTTP positive ne
suffit pas. Le succès exige la fin stock, la route libérée et la commande CFS
vide. Tous les chemins post-tentative demandent une seule fois
`TURN_OFF_HEATERS` et exigent ensuite les deux consignes à zéro. Aucun retrait
n'est relancé automatiquement après timeout ou perte de transport.

Le contrôleur et sa fausse API n'ont aucun transport réel. La prochaine gate
peut seulement vérifier en lecture seule la correspondance des champs live sur
la K1 ; elle demandera un GO exact distinct et n'autorisera aucun retrait.

Voir ADR-024, `docs/35-garde-retrait-officiel-cfs-v1.md` et
`packages/k1-control-v1/cfs-stock-unload-guard-v1/`.

## D-075 — La fin du retrait vient de la route libérée, pas d'un état fictif

Date: 2026-08-27

Status: préflight live clos en lecture seule ; mapping OK avec correction ;
aucune action physique ; production fermée

`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-LIVE-PREFLIGHT-V1` a lu deux fois l'état
réel de la K1 sans G-code ni écriture. Klipper est prêt, `T1` et `T2` sont
connectés, les cibles sont à zéro, `t_command` est vide et aucune route CFS
n'est engagée. Les trois configurations gardent leurs empreintes exactes.

L'objet `box` n'expose aucun `stock_unload_state`. La capture historique prouve
en outre que `t_command` est resté vide pendant le retrait stock. Le garde est
donc corrigé : après sa tentative unique, il exige le retour sans erreur de la
requête, la disparition réelle de la route et `t_command` vide, puis les
chauffes à zéro. HTTP `ok` seul reste insuffisant.

L'état courant est `BLOCKED_NO_ENGAGED_ROUTE`, donc aucune tentative ne serait
permise. La prochaine gate construit seulement l'adaptateur de réponse K1 hors
imprimante, à partir d'exemples nettoyés.

Voir ADR-025, `docs/36-preflight-live-garde-retrait-cfs-v1.md` et
`packages/k1-control-v1/cfs-stock-unload-guard-live-preflight-v1/`.

## D-076 — La forme K1 reste séparée du garde et de tout transport

Date: 2026-08-27

Status: adaptateur clos hors imprimante ; matrice et tests verts ; production
fermée

`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-OFFLINE-V1` introduit une seule
fonction de traduction entre une réponse K1 déjà nettoyée et les huit champs du
garde. Le contrôleur ne connaît donc ni Moonraker, ni la forme privée de `box`,
ni un futur transport.

Une route absente et un second CFS déconnecté restent des états traduisibles :
le garde les refuse ensuite avec ses préconditions normales. Plusieurs routes,
un filament déclaré sur une unité déconnectée, une unité `T3/T4` connectée, un
champ absent ou une température invalide sont refusés par l'adaptateur.

Les dix exemples sont synthétiques et sans identité matérielle. La matrice
obtient `10/10`, les tests ciblés `17/17` et la suite complète exécute `429`
tests, dont `426` verts et `3` ignorés connus. Le paquet n'importe aucun module
réseau, série ou processus ; il n'a ni G-code, ni connexion K1, ni candidat de
pose.

La prochaine gate possible est une validation live séparée et strictement en
lecture seule. Elle devra nettoyer avant traduction et ne devra jamais appeler
le chemin d'effet du garde.

Voir ADR-026, `docs/37-adaptateur-hors-ligne-garde-retrait-cfs-v1.md` et
`packages/k1-control-v1/cfs-stock-unload-guard-adapter-offline-v1/`.

## D-077 — Nettoyer sur liste blanche avant l'adaptateur live

Date: 2026-08-27

Status: validation live close en lecture seule ; production fermée

`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-LIVE-READ-ONLY-V1` garde la
capture complète sous `inventory/raw`, puis impose localement la forme exacte
observée. Le validateur reconstruit une réponse minimale avant l'adaptateur :
les champs `sn`, `uuid` et tous les champs sans utilité fonctionnelle ne
franchissent pas cette frontière. Un champ nouveau dans l'état, `box` ou une
unité CFS provoque un arrêt.

Deux lectures fraîches produisent le même résultat : `T1/T2` connectés, aucune
route engagée, commande CFS vide, cibles zéro et état
`BLOCKED_NO_ENGAGED_ROUTE`. Les trois configurations gardent les mêmes
empreintes. La forme réelle prouve aussi `T3/T4.state = "None"` ; cette seule
valeur est ajoutée comme état inactif, toutes les autres valeurs inconnues
restant refusées.

Les tests ciblés obtiennent `61/61` et la suite complète exécute `443` tests,
dont `440` verts et `3` ignorés connus.

Le garde n'est ni importé ni appelé. Aucun G-code, fichier distant, service,
chauffage, mouvement ou retrait n'a lieu. La prochaine gate proposée devra
construire hors imprimante le futur transport à partir de réponses synthétiques
ou enregistrées, sans connexion K1.

Voir `docs/38-validation-live-adaptateur-garde-retrait-cfs-v1.md` et
`packages/k1-control-v1/cfs-stock-unload-guard-adapter-live-read-only-v1/`.

## D-078 — Fermer le cycle complet hors imprimante avant tout connecteur réel

Date: 2026-08-27

Status: Goal 1 clos hors imprimante ; production et connexion K1 fermées

`GOAL-P4-OFFLINE-CYCLE-CFS-V1` sépare trois responsabilités : le transport
simulé qui impose délais et envois uniques, le moteur pur qui porte le cycle
complet, et un plan futur inerte qui épingle sources, destinations, sauvegardes
et rollback. Aucun connecteur réel, service ou nouveau framework n'est ajouté.

Le vieux prototype à 17 cas n'est pas étendu : les 27 scénarios canoniques du
nouveau contrat couvrent démarrage, filament correct, absent ou incorrect,
changements, runout, pause, reprise, annulation, reboot, fin et retrait séparé.
Une route est fraîche et consommable une fois ; une cible est posée avant tout
effet ; un timeout ou une preuve ambiguë coupe les cibles simulées et interdit
tout retry.

Le transport obtient `13/13`, le cycle `27/27` et les tests ciblés du moteur
`20/20`. La suite complète exécute `476` tests, dont `473` verts et `3` ignorés
connus. Ces résultats ne prouvent ni réseau, ni mouvement, ni débit, ni effet
physique. Le prochain Goal est uniquement une qualification K1 en lecture
seule, sous une autorité séparée.

Voir ADR-027, `docs/39-transport-hors-ligne-garde-retrait-cfs-v1.md`,
`docs/40-cycle-complet-hors-imprimante-v1.md` et
`packages/k1-control-v1/job-lifecycle-offline-v1/`.

## D-079 — Retirer HTTP Basic de la passerelle du LAN privé

Date: 2026-08-27

Status: installé et validé ; exposition Internet interdite

À la demande explicite de Thomas, la passerelle Mainsail du port `4409` ne
demande plus de compte ni de mot de passe. Le premier diagnostic a prouvé que
nginx, Moonraker et Klipper étaient sains tandis qu'un Chrome neuf obtenait
`ERR_INVALID_AUTH_CREDENTIALS`.

La frontière durable devient réseau : nginx accepte seulement la boucle locale
et les plages IPv4 privées. Moonraker reste inaccessible directement sur le
LAN et reçoit les requêtes du seul proxy local approuvé. Le fichier de compte
reste inutilisé pour permettre un retour arrière exact.

L'appel LAN anonyme de `/server/info` est vert et le vrai Chrome rend Mainsail
en `Standby` sans erreur console. Aucun G-code, chauffe, mouvement, impression,
changement de mesh ou restart Moonraker/Klipper n'a eu lieu.

Voir ADR-028,
`experiments/p4/20260827-gateway-private-lan-no-auth-v1-deployment-report.md` et
`packages/k1-control-v1/gateway-private-lan-no-auth-v1/`.

## D-080 — Réserver « robuste » à un verdict et prendre le `11 × 11` comme meilleure référence actuelle

Date: 2026-08-27

Status: décision acceptée ; correction live close sans mouvement

Tous les profils actuels présentent des défauts de bord. Le `6 × 6` reste une
ancienne recette quotidienne et un repli historique, mais il n'est pas robuste.
Le composite `k1_p001_t055_r001_n11x11` est le meilleur résultat global observé
et le moins mauvais aux bords ; il reste imparfait et devient la source immuable
des corrections.

Le mot `robuste` désigne désormais uniquement un futur verdict obtenu après une
validation physique complète de la zone utile. Les noms historiques contenant
`ROBUST-*` restent inchangés pour conserver la traçabilité, mais ne portent plus
ce verdict produit.

La gate corrective `G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1` a chargé une
seule fois le `11 × 11` exact, sans chauffe, mouvement, homing, fichier distant,
restart, palpage ni impression. Deux lectures indépendantes confirment le
profil actif et les configurations inchangées.

L'éditeur hors ligne existant reste le seul outil de correction : il sait déjà
sélectionner un point, une ligne, une colonne ou une zone, appliquer un delta
explicite et produire un dérivé versionné sans toucher à la source ni au Z
global. L'interface rend maintenant l'édition point par point et l'absence de
profil robuste explicites.

Voir ADR-029, `docs/24-mesh-editor-offline-v1.md` et
`packages/k1-control-v1/best-current-mesh-restore-v1/`.

## D-081 — Quatre Goals terminent le projet, sans P5 ou P6 obligatoire caché

Date: 2026-08-27

Status: décision de pilotage acceptée par Thomas

Le plan précédent affichait quatre Goals tout en repoussant encore la validation
production en P5 et le durcissement en P6. Cette structure contredisait la
promesse opérationnelle selon laquelle les quatre Goals devaient terminer le
projet et rendait le compteur trompeur.

Le compteur canonique reste désormais strictement limité à quatre Goals. Les
Goals 1 et 2 sont terminés. Le Goal 3 ferme toutes les qualifications physiques,
y compris le nettoyage, le cycle filament et la correction des bords. Le Goal 4
regroupe la bascule quotidienne, le rollback, le redémarrage à froid, les trois
impressions consécutives, les deux CFS, la conservation du Z et du mesh, la
baseline V1, la documentation et la fermeture Git.

Quand le Goal 4 passe, le projet est terminé : aucune gate obligatoire, P5 ou P6
ne reste ouverte. Les améliorations communautaires éventuelles deviennent un
backlog optionnel extérieur au projet et ne peuvent pas repousser sa clôture.

## D-082 — Le propriétaire CFS décide hors transport et refuse toute reprise ambiguë

Date: 2026-08-28

Status: cœur propriétaire clos hors imprimante ; effets, pose et production
fermés

ADR-032 reste la décision d'architecture : K1 Control possède le cycle complet
et le pilote Creality ne pourra exécuter que de petites primitives qualifiées
séparément. `G4-K1-CONTROL-CFS-OWNER-CORE-OFFLINE-V1` rend cette règle
exécutable sans connecter la K1.

Le verrou enregistre la valeur précédente de l'auto-remplacement stock, exige
sa désactivation prouvée avant de devenir actif et sa restitution exacte à la
fin. Un rappel stock, une cartographie périmée ou une nouvelle époque de
connexion invalide le travail. Chaque intention est ordonnée, unique, non
exécutable et limitée à une tentative ; un résultat inconnu n'est jamais rejoué.

L'auto-remplacement K1 Control exige une seule bobine approuvée avec même
référence, type, couleur, diamètre et recette thermique. Zéro ou plusieurs
candidats restent en pause. La matrice synthétique qualifie le choix logique de
`T1A` vers `T2A`, mais la capture S12 ne contenait aucune paire identique réelle
et aucune primitive physique n'est promue.

La reprise ne peut pas être autorisée par un booléen « état complet ». Le cœur
conserve puis compare le contexte structuré de pause : position de retour,
modes de mouvement, extrusion, mesh, Z, cibles thermiques, ventilateurs,
facteurs vitesse/débit, pressure advance, outil logique, route, capteurs et
fraîcheur de cartographie.

La mission suivante était
`G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1`. Elle devait préparer
seulement le garde de désactivation, vérification et restauration de la
politique stock, sans connexion ni candidat de pose. Elle est désormais close
par D-083.

Voir ADR-032, `docs/45-coeur-proprietaire-cfs-hors-imprimante-v1.md` et
`packages/k1-control-v1/cfs-owner-core-offline-v1/`.

## D-083 — Une preuve d’état, jamais un acquittement, ouvre ou ferme le propriétaire CFS

Date: 2026-08-28

Status: garde d’exclusion clos hors imprimante ; effet réel non qualifié

`G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1` matérialise la frontière
prévue par ADR-032. La valeur stock d’auto-remplacement est lue deux fois et
sauvegardée. Une désactivation n’est préparée qu’une fois si cette valeur vaut
`1`. Le propriétaire n’est accordé qu’après deux lectures à `0`. La fermeture
restaure de la même manière la valeur exacte précédente.

Un retour HTTP ou un acquittement ne compte pas comme preuve. Une issue inconnue
n’est jamais rejouée. Si l’effet est ensuite observé, seul le rollback exact est
préparé et le propriétaire reste fermé. La cartographie, l’époque de connexion,
la politique d’impression, le mesh, le Z, les axes, les chauffes, les routes et
l’activité stock sont comparés ; toute dérive ferme le chemin.

Le paquet obtient `25/25` scénarios et `15/15` tests ciblés. Ses intentions sont
`dispatchable=false`, il n’importe aucun transport et n’est pas un candidat de
pose. La prochaine mission proposée est une validation live strictement en
lecture seule de la forme des états. La première commande réelle restera une
gate humaine séparée.

Voir `docs/46-garde-exclusion-proprietaire-cfs-hors-imprimante-v1.md` et
`packages/k1-control-v1/cfs-owner-exclusion-guard-offline-v1/`.

## D-084 — Une lecture stable ne remplace ni une époque de connexion ni le Z accepté

Date: 2026-08-28

Status: validation live close en lecture seule ; adaptateur bloqué

Deux lectures réelles, nettoyées sur la K1, confirment un état stable et sûr,
les deux CFS connectés, aucune route engagée et les configurations inchangées.
Elles ne qualifient pourtant pas le passage au chemin d'effet.

Les objets lus n'exposent aucune époque de connexion. Une déconnexion suivie
d'une reconnexion au même état entre les sondages resterait invisible. Cette
valeur ne sera ni inventée ni déduite d'une simple égalité des réponses.

L'empreinte du stockage Z accepté reste stable, mais sa valeur n'est pas
présente dans la projection. `gcode_move.homing_origin[2]`, observé proche de
zéro, n'est pas le Z accepté `−0,04 mm` et ne peut pas lui être substitué. Le
garde refuse donc avec `connection_epoch_invalid` et
`effective_z_source_unqualified`.

La capture V1 est consommée et ne doit pas être rejouée. La prochaine mission
est un adaptateur d'observabilité V2 hors imprimante ; toute nouvelle connexion
ou tout effet réel restera une gate séparée.

Voir `docs/47-validation-live-lecture-seule-garde-exclusion-proprietaire-cfs-v1.md`.

## D-085 — L'exclusion stock exige une observation continue et une restitution exacte

Date: 2026-08-28

Status: observabilité V2 et effet réel clos OK ; production fermée

L'époque utilisable par le garde est la connexion WebSocket Moonraker
persistante accompagnée de la séquence des transitions CFS rapportées. Le Z
accepté vient uniquement de `gcode_macro KCTRL_STATE.accepted_z_offset`, avec le
stockage `k1_control_store` comme témoin d'intégrité. `homing_origin` ne peut pas
le remplacer. Une reconnexion de l'observateur ou une transition rapportée
invalide les lectures ; une reconnexion interne totalement silencieuse n'est
pas prétendue détectable.

Sous cette observation continue, la valeur stock `1` a été sauvegardée,
désactivée une fois, prouvée deux fois à `0`, puis restaurée une fois et prouvée
deux fois à `1`. Un acquittement n'a jamais servi de preuve. Le garde hors
imprimante rejoue exactement la trace et passe par `owner_granted` avant de
terminer `closed_safe`.

Cette preuve qualifie la frontière d'exclusion et de restitution ; elle
n'installe pas le propriétaire et ne qualifie aucune primitive filament. La
suite revient au démarrage possédé `START-SEQUENCE-OWNER-V1`, qui doit être
rendu installable et réversible avant une nouvelle gate physique.

Voir `docs/48-observabilite-et-exclusion-proprietaire-cfs-v2.md`.
