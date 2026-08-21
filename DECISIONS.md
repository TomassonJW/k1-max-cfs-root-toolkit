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
