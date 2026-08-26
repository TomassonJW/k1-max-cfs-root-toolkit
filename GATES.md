# GATES

Progression is evidence-based. Une gate prouve qu'une phase bornée est sûre et
conforme ; elle n'est pas une formule d'autorisation à faire recopier par
Thomas.

These gates control evidence collection and changes affecting the printer. They do not gate normal Git or GitHub operations: under D-010, Codex may complete branches, commits, pushes, pull requests, merges into `main` and cleanup without requesting another operator approval. Repository integration never expands the printer-side authority granted by a gate.

Depuis D-054, un Goal actif ou une mission clairement décrite couvre les
actions normalement nécessaires dans son périmètre. Codex fournit lui-même les
identifiants `G4-*` aux scripts et poursuit après une correction revue et testée
sans réclamer un nouveau `GO`. Une restriction explicite plus récente reste
prioritaire, et les faits physiques non observables doivent toujours être
confirmés avant l'action qui en dépend.

## Reprise après la campagne quotidienne du 24 août 2026

Statut : **CAMPAIGN-V1, NAVIGATION-V1-R2, la sous-grille `5 × 5` et le profil
composite physique `11 × 11` validés ; autonomie quotidienne standard
atteinte ; comparaison V2 meilleure au centre mais KO aux bords ; mode
Précision fermé**.

BED-MESH-V2 est installée et validée sous la capture
`20260823-151026-g4-k1-control-calibration-ui-prtouch-bed-mesh-v2`.
Après deux corrections de préflight sans mutation, Thomas a rendu le GO MATRIX
persistant pour terminer cette mission sans redemander la même autorisation.
La capture `20260823-161103-g4-k1-control-calibration-ui-matrix-v1` a passé le
préflight, la pose et deux validations. Backup exact, hashes installés, fichiers
hors write-set, Klippy `ready`, `failed_components=[]`, `warnings=[]`, état au
repos, profil robuste, Z accepté et deux CFS sont conformes. Seul Moonraker a été
redémarré et aucune action physique n'a eu lieu. MATRIX-V1 est close.

RETRY-SAFETY-V1 est également close sous la capture
`20260823-164558-g4-k1-control-calibration-ui-retry-safety-v1`, sans restart ni
action physique. PRTOUCH-PRESETS-V1 est close sous la capture
`20260823-165742-g4-k1-control-calibration-ui-prtouch-presets-v1` : les hashes
sûrs étaient déjà installés, donc le déployeur idempotent n'a effectué aucune
écriture distante, aucun backup et aucun restart. CAMPAIGN-V1 a ensuite réussi
depuis l'écran et obtenu sa capture puis sa validation finale sous
`20260823-171803-g4-k1-control-calibration-ui-campaign-v1`. Le delta UX
NAVIGATION-V1 a obtenu son préflight, sa pose et deux validations SSH vertes
sous `20260824-110936-g4-k1-control-calibration-ui-navigation-v1`, sans restart
ni action physique. Le vrai navigateur a ensuite prouvé que le bouton est
affiché mais que le service worker Mainsail intercepte `/k1-control/`. R2 ajoute
un alias statique original sous `/access-k1-control/`, préfixe déjà exclu par le
worker exact, sans modifier ce fichier constructeur. La capture
`20260824-112535-g4-k1-control-calibration-ui-navigation-v1-r2` a ensuite obtenu
le préflight, la pose et deux validations SSH vertes. Chrome a prouvé le clic
Mainsail vers le vrai écran, sans nouvelle authentification, ainsi que le texte
Z final corrigé. COMPOSITE-MESH-SUBGRID-V1 a ensuite obtenu le préflight, la
pose et deux validations SSH sous
`20260824-113026-g4-k1-control-composite-mesh-subgrid-v1`. Seul le Moonraker
dédié a redémarré et aucune action physique n'a eu lieu. L'essai séparé a ensuite
capturé 25 contacts sous `20260824-113434-g4-k1-control-composite-mesh-subgrid-v1-run`.
La course de reprise Klipper et le marqueur `schema/version` ont été corrigés
sans deuxième mesure. La reprise R2 sous
`20260824-121607-g4-k1-control-composite-mesh-subgrid-recovery-v1-r2` et la
validation indépendante de la matrice existante sont vertes.

La chaîne locale post-campagne est maintenant stricte : SUBGRID-V1 exige le
hash `printer.cfg` contenant le mesh quotidien validé, puis les deux fichiers
finaux de NAVIGATION-V1. COMPOSITE-MESH-V1-R2 a ensuite capturé quatre quadrants
carrés `6 × 6`, soit `144/144` contacts et 121 positions uniques. La reprise
logique a qualifié puis persisté le profil `11 × 11`, tout en rechargeant le
profil robuste `6 × 6`. L'interface Précision reste volontairement fermée
après la comparaison V2 : son gain central ne compense pas ses défauts de bord.

## Gates suivantes après l'éditeur hors ligne

### `MESH-EDITOR-OFFLINE-V1`

Statut : **passée le 25 août 2026 ; aucune connexion ni mutation K1**.

Critères :

- profil physique `11 × 11` traité comme source immuable ;
- profil dérivé versionné avec corrections à moyenne pondérée nulle ;
- grille 2D orientée, pas `0,005/0,010 mm`, undo/redo et historique ;
- source, deltas, matrice finale et surface calculée prévisualisables ;
- bornes par point et entre voisins ;
- export Klipper reproductible, parse exact et rollback simulé ;
- aucun accès distant, chauffage, homing, mouvement ou écriture K1.

Preuves :

- source publique nettoyée de 121 valeurs, empreinte canonique
  `bee530fb9738773d1f2ccb63d47743e15776690f1bcdf92a3daac7661f0f50bf` ;
- normalisation sur la surface bicubique exacte `31 × 31`, moyenne nulle ;
- modèle source/demande/normalisation/final, empreinte et qualification séparés ;
- gardes `0,05 / 0,10 / 0,08 mm`, sélection bornée et refus sans mutation ;
- undo, redo, branche d'historique, restauration et exports déterministes ;
- fausse API en mémoire et serveur lié uniquement à `127.0.0.1` ;
- recette navigateur réelle : 121 cellules, actions, aperçu 3D exclusif et
  erreur simulée sans mutation ;
- 294 tests Python verts, 3 ignorés connus, et 5 tests JavaScript verts.

Voir [`docs/24-mesh-editor-offline-v1.md`](docs/24-mesh-editor-offline-v1.md).
Passer cette gate autorise seulement la préparation du motif physique suivant.
Elle n'autorise pas automatiquement une impression, une pose ou l'exposition
du mode Précision.

### `MESH-EDGE-DIAGNOSTIC-V1`

Statut : **en cours ; passage source sans débit invalide et suite physique
suspendue**.

Le premier motif a chauffé, déplacé la tête et envoyé des commandes d'extrusion,
mais aucun filament n'a été déposé. Le chemin minimal ne résolvait pas le CFS,
ne chargeait pas le filament et n'exigeait aucune purge visible. La mention
`T0` était une hypothèse de Codex et n'est pas retenue comme fait. Ce passage ne
qualifie ni le mesh ni une buse bouchée.

Le rollback exact est maintenant clos sous la capture
`20260826-090956-mesh-edge-diagnostic-v1`. Il a restauré la base, retiré le
profil temporaire et les quatre G-code, rechargé le robuste et obtenu
`VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK`. Aucun motif n'a été relancé.

Le prérequis séparé `CFS-READ-ONLY-AUDIT-V1` est clos **OK** sous la capture
privée `20260826-final-cfs-read-only-audit-v1`. La K1 est relue sûre et les
empreintes avant/après sont identiques. Le verdict filament est toutefois
`engaged_unknown` : présence observée, mais identité, route outil/CFS/slot et
débit à la buse non prouvés. L'audit réussit ; le préflight physique reste
bloqué en sécurité.

Thomas a ensuite résolu explicitement `CFS1 / slot A`, Geeetech PLA noir, et la
purge visible a prouvé le débit pour ce passage. La séquence reste **KO** : elle
a imposé `220 °C` malgré la demande `190 °C`, référencé X/Y et tenté la purge
alors que le plateau n'était pas descendu. Aucun dommage visible n'a été
constaté. Après récupération, `X=185,5 / Y=305 / Z=30 mm` a été validé à froid
par Thomas comme position de purge avec une marge suffisante.

### `CFS-BOUNDARY-GUARD-V1`

Statut : **candidat hors imprimante validé ; primitive brute refusée ; aucune
pose ni reprise physique autorisée**.

Le garde protège simultanément cible buse, cible plateau, Z accepté, origine Z,
profil mesh et axes référencés. Sa fixture réelle refuse l'incident pour cible
buse cachée, homing interdit et changement des axes référencés. Les champs
Z/mesh non capturés pendant la frontière restent inconnus. Les fixtures
séparées refusent aussi une dérive plateau ou Z et interdisent toute restauration
Z automatique.

La récupération en lecture seule du binaire exact `box_wrapper` et du journal
complet est maintenant close. L'empreinte correspond au manifeste et la
chronologie attribue au chemin de chargement le `220 °C` et la géométrie
interne. `BOX_EXTRUDE_MATERIAL` est refusée ; `BOX_EXTRUDER_EXTRUDE` et
`BOX_MATERIAL_FLUSH` restent non qualifiées faute de frontière isolée.

### `CFS-BOX-WRAPPER-AUDIT-V1`

Statut : **audit exact OK ; adaptateur étroit fermé ; aucune pose ni reprise
physique autorisée**.

Le contrat local vérifie l'identité ELF 32 bits MIPS du module sans le charger,
les chaînes thermiques et géométriques, puis l'ordre des marqueurs du journal.
Son résultat attendu est un refus sûr : la liste des primitives appelables est
vide et `deployment_candidate=false`.

La suite est encore hors imprimante : préparer un propriétaire filament minimal
séparé, ou obtenir une preuve statique plus forte d'une primitive étroite. Les
commandes brutes du 26 août ne doivent pas être rejouées.

### `G4-K1-CONTROL-CFS-DYNAMIC-TEMP-ROUTING-V1`

Statut : **passée hors imprimante ; architecture choisie ; aucun transport ni
candidat de pose ; production fermée**.

Le paquet compare base matière, réaffirmation post-`T`, interception de
`get_material_target_temp` et propriétaire minimal séparé. Seule la dernière
voie reçoit la cible avant le premier effet tout en gardant plateau et géométrie
hors du CFS. Elle reste un choix de conception : le protocole série et
l'exclusion du propriétaire stock ne sont pas encore qualifiés.

Le contrat impose une preuve de route fraîche consommable une fois, une cible
par phase, les températures distinctes de retrait/chargement/purge et les six
invariants inchangés. La matrice locale obtient `25/25` sur les deux CFS,
first/normal, filament engagé, chargement, changement, refill, runout,
pause/reprise, annulation et arrêts sûrs. Aucun accès K1, G-code, chauffe,
mouvement, commande CFS, purge, restart ou fichier distant n'a été produit.

Passer cette gate autorise seulement la mission hors imprimante suivante :
`G4-K1-CONTROL-CFS-MINIMAL-OWNER-PROTOCOL-V1`. Elle n'ouvre ni pose, ni essai
physique, ni reprise de `MESH-EDGE-DIAGNOSTIC-V1`.

Avant toute reprise physique restante : route filament fraîchement résolue,
position de purge sûre et primitive qualifiée par les six invariants. Une purge
visible et un capteur de présence ne suffisent pas si température ou géométrie
dérivent.

Critères :

- motif première couche borné à `X/Y=5..295`, avec cadre, cellules et repères ;
- état K1 frais et présence humaine avant lancement ;
- même plaque, filament, température, tube PTFE et Z effectif ;
- une seule petite région corrigée de `0,010 mm` ;
- sens `Rapprocher/Éloigner` prouvé sans dégrader le centre ;
- répétabilité de bord et influence PTFE classées avant réglage général ;
- arrêt, retrait du G-code et retour au robuste en cas de KO.
- aucun outil physique supposé ; mapping CFS/slot observé avant chaque variante ;
- purge visible fraîche obligatoire avant chaque motif.

### `MESH-DERIVED-PROFILE-V1`

Statut : **non commencée**.

Pose UI/API au repos uniquement. Elle crée un nouveau profil après backup,
restart Klipper borné et relecture, puis recharge le robuste. Elle ne lance
aucune impression. `failed_components=[]`, `warnings=[]`, source, Z et robuste
intacts sont obligatoires.

### `MESH-TUNING-CAMPAIGN-V1`

Statut : **non commencée**.

Le mode Précision n'est exposé qu'après deux feuilles complètes consécutives
sans défaut grave, sans correction Z en direct et avec rollback prouvé. Sinon
le profil dérivé est rejeté et le robuste reste l'unique mode quotidien.

### Gates production

Le contrat fonctionnel V1 est figé hors imprimante dans
`docs/25-contrat-cycle-impression-nettoyage-cfs-v1.md` et
`design/job-lifecycle-contract-v1.json`. Cela n'installe aucun propriétaire de
cycle et n'ouvre pas la production.

L'ordre est : `PRODUCTION-SEQUENCE-AUDIT-V2`,
`JOB-LIFECYCLE-OFFLINE-V1`, `CLEAN-MOTION-V1`,
`CLEAN-AND-REFERENCE-V1`, `CFS-TEMP-OWNER-V1`,
`TOOL-CHANGE-AND-RUNOUT-V1`, `PAUSE-RESUME-SEMANTICS-V1`,
`END-SEQUENCE-V1`, puis `ORCA-CUTOVER-V1` et G5.

Le cutover Orca retire le départ historique et le `+0,27 mm` dans une seule
transaction. Aucun paquet précédent ne doit les retirer. Une pause normale doit
être prouvée sans purge CFS et sans restauration d'un ancien Z. Les deux CFS
sont qualifiés par incréments séparés.

La cible de fin conserve par défaut le bon filament engagé, sous réserve de sa
qualification physique. Le retrait devient l'action séparée `Désengager et
nettoyer`. Toute impression exige une purge visible, même si les capteurs
indiquent déjà une présence.

## G0 — Repository bootstrap

Status: **passed**

Criteria:

- public scope and safety boundary exist;
- raw/private paths are ignored;
- agent rules prohibit remote mutation;
- state, roadmap and decisions are explicit.

## G1 — Ready for read-only acquisition

Status: **passed on 2026-08-19**

Required:

- root enabled manually by Thomas;
- exact target host supplied outside Git;
- printer idle;
- visible printer and CFS versions recorded;
- likely board revision recorded but still subject to machine verification;
- recovery image and recovery procedure candidates stored locally, or the absence explicitly acknowledged before connection;
- Codex reads `AGENTS.md` and the acquisition protocol;
- local raw destination is inside an ignored path.

Passing G1 authorises read-only commands and remote-to-local copying only.

## G2 — Stock acquisition complete

Status: **passed on 2026-08-19 with documented limitations**

Required:

- system and firmware manifest completed;
- configuration entry points and includes inventoried;
- services, processes, mounts and persistence paths inventoried;
- relevant files and logs copied to private local storage;
- checksums recorded;
- command log completed;
- sanitisation performed;
- public artefacts reviewed for secrets and vendor redistribution risk;
- no remote mutation occurred.

Passing G2 authorises analysis of captured evidence, not printer changes.

Recorded limitations: listener output was incomplete, CFS versions remain UI-reported, and the online recovery image/procedure has not been validated locally. These do not authorise widening the scope or mutating the printer.

Follow-up evidence on 2026-08-19 resolved the runtime board selection as S12 structure 0 and mapped the readable CX, persistence, homing and PR Touch sources. The CFS state machine remains a compiled boundary. G2 remains passed; G3 still requires comparable traces and a narrow intervention.

## G3 — Diagnosis sufficiently grounded

Status: **passed on 2026-08-20 for offline G4 preparation only**

Execution status: session `20260819-185157-g3-aba` completed A1/B/A2 in one boot session on 2026-08-19. Q1 passed. Q2 failed because Thomas adjusted the bed screws between the prints and again around A2. Q3 failed because the Z retry path differed, Q4 remained incomplete, and Q5 is inconclusive. The session is useful evidence but is not a qualified comparable pair.

Observed evidence includes two Z-establishing phases around cleaning, A2 retrying through index 7 with large internal outliers, and runtime pressure advance `0.044` competing with the files' requested `0.03`. No fourth print is authorised or needed for this session.

Passive production session `20260819-215124-long` then captured one complete normal job. It resolved the pressure-advance uncertainty: startup `0.044` was replaced by file-requested `0.03`, and `0.03` remained active through the automatic CFS refill and print end. It also proved that the initial CFS load/purge and an equivalent-PLA refill use the stock CFS temperature `220 °C` instead of respecting the first-layer target or preserving the prior print temperature. Visible Z origin stayed at `+0.27 mm`; this job did not reproduce the historical Z shift.

Required:

- startup and CFS call graphs exist;
- all known Z-offset, homing, levelling, mesh and temperature writers are mapped;
- at least two identical-job traces are compared where possible;
- Z repeatability and Z reset are treated as separate hypotheses;
- first intervention is named, narrow and justified;
- success and failure criteria are measurable.

Passing G3 authorises preparation of a patch and rollback plan, not deployment.

No additional sacrificial print is required before offline G4 preparation. The
temperature owner remains a separate, dynamic and material-independent package.

The static Geeetech PLA `190/195` candidate prepared on 2026-08-20 was rejected
by Thomas before deployment because it was not material- or temperature-agnostic.
Its deployable files were removed. G3 temperature work now requires proof of a
dynamic owner that follows G-code targets through startup, both CFS units,
equivalent refill and intentional material changes.

Session `20260820-154056-p123` then captured P1, P2, P3, P4, two P5 attempts and
P1 PETG in one passive trace. It directly proved that the current `+0.27 mm`
post-processor executes only after the stock startup sequence, so it cannot
protect an earlier purge. It also proved that live Z adjustments invoke
`Z_OFFSET_APPLY_PROBE`, but the end-of-print path applies the exact inverse and
prepares `0.000` for persistence. P1 PETG finished at `+0.38 mm`, `+0.11 mm`
above the file baseline, before that correction was erased at completion.

P2 and P3 share their 639 recorded slicer settings and produced no reported
visible difference despite separate versus assembled objects. One live
`+0.010 mm` Z click occurred during P3, so this is not a fully untouched pair.
It does not reproduce the historical large Z shift and provides no support for
the simplistic claim that object count alone causes it. A bed-screw change after
P3 prevents extending the comparison to P4.

The second corrected P5 completed one intentional tool change without a pause.
Its measured nozzle targets were `115 -> 220 -> 205 -> 220 -> 0 °C`. The first
`220 °C` confirms the startup override. The final `220 °C` equals the requested
second-filament target, so this test cannot distinguish G-code ownership from a
stock CFS rewrite. The first P5 attempt had three pauses after a likely filament
break and is excluded from behavioural qualification.

These results satisfy G3 because the Z reset and physical repeatability
hypotheses are separated and runtime ownership is measured. Ils avaient d'abord
conduit à un paquet Z fixe, rejeté ensuite par Thomas. G3 autorise maintenant la
conception et le prototype hors imprimante du système cohérent décrit dans
ADR-004 : calibration persistante, mesh, séquence, interface, Orca et
températures CFS. Il n'autorise aucun déploiement ni autre mutation.

## G4 — One mutation ready for deployment

Status: **passed and deployed on 2026-08-19 for `G4-SSH-KEY` only**

The named change installed one dedicated ECDSA P-256 public key in
`/root/.ssh/authorized_keys`. The original file and directory were absent. The
final file contains exactly one active key, is owned by root with mode `600`,
and two independent connections succeeded with password authentication disabled.

An initial Ed25519 attempt was rejected because the observed Dropbear `2019.78`
predates Ed25519 `authorized_keys` support. Its malformed first transfer was
repaired, the unsupported key was removed, and its unused local private key was
deleted. Private evidence and backup checksums remain outside Git.

This pass does not authorise any other printer mutation. Every future named
change must satisfy G4 independently.

Candidate `G4-CFS-TEMP-PLA`: **rejected and never deployed**. It must not be
reopened. A future G4 requires a new name and a dynamic, material-independent
design backed by the full transition matrix.

Candidate `G4-ZSAFE-START-V1`: **rejected by Thomas on 2026-08-20 and never
deployed**. Son nom ne peut plus recevoir de GO. Les fichiers restants sont des
preuves historiques marquées `rejected_never_deploy` ; le macro échoue
volontairement s'il est chargé par erreur.

Candidate `G4-K1-CONTROL-FOUNDATION-V1`: **GO reçu, préflight KO le 2026-08-20,
jamais déployée, nom fermé**. La machine réelle ne possède ni `logrotate`, ni
`/etc/logrotate.d`, alors que V1 les exigeait avant toute copie. Le préflight a
arrêté la pose sans créer de dossier, fichier, service ou port sur la machine.
Un autre GO V1 ne peut pas rouvrir ce paquet.

Candidate `G4-K1-CONTROL-FOUNDATION-V2`: **GO reçu, essais réels rollbackés le
2026-08-21, nom fermé**. V2 a atteint un Mainsail fonctionnel par tunnel après
correction des écarts Buildroot et WebSocket. Elle a ensuite prouvé que Mainsail
`v2.18.2` ne sait pas utiliser un compte Moonraker. Le port LAN n'a pas été
ouvert. Après rollback, les chemins et services V2 sont absents, les ports
`7125`/`4409` fermés et la pile Creality présente. Un autre GO V2 ne peut pas
rouvrir ce paquet.

Candidate `G4-K1-CONTROL-FOUNDATION-V3`: **GO reçu, installation réelle verte
le 2026-08-21**. Les tentatives intermédiaires ont rollbacké complètement après
avoir révélé le partage de stdin, les droits du fichier et du dossier parent,
puis l'impossibilité pour nginx d'élargir son écoute par simple reload. La pose
finale utilise `root:www-data` avec `0710/0640`, prouve la lecture sous
`www-data` avant la saisie et redémarre uniquement la passerelle nginx lors du
passage LAN.

La capture `20260821-015722-g4-control-foundation-v3` a obtenu
`INSTALL_BOOTSTRAP_OK`, `SET_GATEWAY_ACCOUNT_OK`, `ACTIVATE_LAN_OK` et
`VALIDATE_OK`. Thomas a vérifié le compte dans le vrai tableau de bord Mainsail.
Moonraker reste en boucle locale sur `7125`; Mainsail authentifié écoute sur le
LAN privé en `4409`; les ports Creality, Klipper et les deux CFS sont intacts.
Aucun G-code, mouvement, chauffe, calibration, extrusion, impression ou
redémarrage imprimante n'a été exécuté.

Le prototype reste vert à 17/17 et la suite passe 57/57. G4 est passée pour
cette fondation uniquement. L'acceptation durable reste soumise aux huit heures
d'observation prévues, avec une impression normale lancée par Thomas.

Le diagnostic post-installation en lecture seule du 2026-08-21 a ensuite
confirmé deux avertissements de chemins : Moonraker dérive ses racines vides
`state/config` et `state/gcodes`, tandis que Klipper et Creality utilisent
`printer_data/config` et `printer_data/gcodes`. La chaîne Mainsail → Moonraker →
Klipper fonctionne ; le gestionnaire de fichiers n'est pas encore aligné. Il est
interdit de modifier `[virtual_sdcard]` ou `printer.cfg` pour masquer cet écart.

Candidate `G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1`: **GO exact renouvelé, déployé
et validé le 2026-08-21**. Le paquet revu conserve les chemins Creality comme
référence, utilise deux liens symboliques, verrouille l'écriture API de `config`
et documente l'accès en écriture restant sur `gcodes`. Le premier GO avait été
reçu avant que le paquet existe et n'avait pas été consommé ; Thomas a renouvelé
le même texte exact après la revue.

La capture `20260821-111001-g4-control-foundation-v3-paths-v1` a sauvegardé et
vérifié la configuration et les deux dossiers vides avant mutation. Elle a posé
les liens `state/config -> printer_data/config` et
`state/gcodes -> printer_data/gcodes`, installé le hash revu
`fef837a1acaa59af400ac63c244df78dec6e70a71e1707d61f242f56cb1c7fba`, puis
redémarré uniquement Moonraker. La validation indépendante a obtenu
`VALIDATE_PATHS_V1_OK` : `config=r`, `gcodes=rw`, aucun avertissement, Klipper
prêt et au repos, chauffes à zéro, axes non homés, deux CFS `1.1.3`, nginx,
ports/processus et ressources conformes. Aucun G-code ni rollback n'a été lancé.
L'observation retenue est terminée. Elle couvre l'impression normale lancée par
Thomas, le trou du premier observateur par le journal persistant, la seconde
capture arrivée à sa durée et une validation finale
`VALIDATE_PATHS_V1_OK`. Aucun événement critique Klipper/MCU n'a été détecté.

Candidate `G4-K1-CONTROL-Z-MESH-RUNTIME-V1`: **GO renouvelé, installé et validé
le 2026-08-22**. Le paquet
ajoute deux fichiers originaux et une
seule inclusion, puis recharge uniquement l'hôte Klipper. Il ne modifie ni
`START_PRINT`, ni Orca, ni le post-traitement `+0,27 mm`, ni le CFS. Son état Z
utilise validation, SHA-256, `fsync`, remplacement atomique et copie précédente.
La validation appelle seulement une garde qui doit refuser et prouve qu'aucune
position, origine ou cible de chauffe n'a changé. Le rollback sauvegarde aussi
les données Z avant retrait.

La suite courante exécute 96 tests : 95 OK localement, un contrôle Jinja ignoré
faute de dépendance Windows mais remplacé par une validation en mémoire des 17
templates avec le Python/Jinja exact de la K1. Le module atomique compile et
s'exécute aussi en mémoire sur ce Python exact.

Le premier préflight réel s'est arrêté avant mutation : le programme Python
transmis sur stdin était lancé avec `0` comme chemin de script. Les deux appels
avec arguments utilisent maintenant `python -`; un test dédié couvre la forme
snapshot et la forme G-code. Le second préflight en lecture seule est vert sous
la capture `20260821-212431-g4-k1-control-z-mesh-runtime-v1`. Il confirme
`standby`, chauffes à zéro, fondation intacte, empreinte initiale conforme,
cibles absentes et deux CFS connectés. Aucun fichier, backup distant, service
ou état Klipper n'a été modifié.

Le GO exact renouvelé a ensuite ouvert la capture
`20260821-213732-g4-k1-control-z-mesh-runtime-v1`. Préflight et backup étaient
verts. Après pose et restart hôte, la validation a prouvé qu'un stockage neuf
`integrity=empty` restait par erreur à `ready=0`. La garde sans mouvement n'a
pas été appelée. Le rollback a retiré les cibles, mais son premier contrôle a
rencontré T1 encore déconnecté et une normalisation textuelle des blocs générés
de `printer.cfg`.

La complétion bornée du rollback a restauré une dernière fois le backup exact
sans restart supplémentaire. Le préflight final est vert : runtime absent,
hash initial, `standby`, axes non homés, chauffes à zéro, deux CFS `1.1.3` et
fondation intacte. Le restart a seulement perdu le mesh transitoire `Base`; le
profil persistant `default` est actif. Aucun mouvement, chauffe, extrusion,
ordre CFS, calibration, impression, firmware restart ou reboot n'a eu lieu.

Le candidat offline distingue maintenant `empty` d'un état invalide, conserve
le Z non accepté et les mouvements bas fermés, attend la stabilisation complète
des CFS et restaure l'empreinte exacte après restart de rollback. Son hash config
est `3b0e5215d9bd58a343c57a681668ef1e466465980cceac3b1fd5944fec806f96`.
Les 17 templates et le rendu `empty` passent sur le Python/Jinja exact de la K1.

Le payload et les commandes ayant changé après le GO consommé, cette correction
n'était pas autorisée avant un nouveau GO. Thomas l'a ensuite renouvelé avec le
même texte exact `GO G4-K1-CONTROL-Z-MESH-RUNTIME-V1`.

Le GO suivant a ouvert la capture
`20260821-224828-g4-k1-control-z-mesh-runtime-v1`. Préflight et backup étaient
verts, mais le runtime n'a jamais atteint `ready=1`. Le journal et la source
`gcode.py` exacte prouvent que le parseur Creality tronque une commande dès le
chiffre placé au milieu : `K1_CONTROL_LOAD_STATE` devient `K1`, inconnue. La
garde sans mouvement n'a pas été appelée.

Le rollback a retiré le runtime et l'inclusion, puis un `CXSAVE_CONFIG` tardif a
normalisé les espaces des blocs générés. Une complétion bornée a restauré
l'empreinte exacte sans restart. Le préflight final confirme runtime absent,
hash initial, `default`, `standby`, axes non homés, chauffes à zéro, deux CFS
`1.1.3` et fondation intacte. Aucun mouvement, chauffe, homing, extrusion,
ordre CFS, calibration, impression, firmware restart ou reboot n'a eu lieu.

Le candidat offline renomme tous les points d'entrée exécutables en `KCTRL_*`,
y compris le stockage et les futurs contrats Orca. Le rollback attend aussi la
fin des écritures de démarrage avant sa restauration finale.

Thomas a renouvelé une troisième fois le même GO exact. La capture
`20260822-004338-g4-k1-control-z-mesh-runtime-v1` a passé le préflight et le
backup, puis chargé les objets `KCTRL_*`. Le démarrage différé s'est bien lancé,
mais `SET_GCODE_VARIABLE ... VALUE='empty'` a échoué : le `shlex` Creality
retire ces guillemets avant `ast.literal_eval`, qui refuse alors le nom nu
`empty`. La garde sans mouvement n'a pas été appelée.

Le rollback automatique renforcé a restauré l'empreinte exacte et l'état sain ;
le préflight final confirme runtime absent, `default`, `standby`, axes non
homés, chauffes à zéro, deux CFS `1.1.3` et fondation intacte. Les 24 valeurs
texte utilisent maintenant un littéral protégé comme `VALUE='"empty"'`, et le
déployeur conserve son dernier snapshot si `ready` reste à zéro. Les hashes
courants sont
`dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113`
pour la configuration et
`696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede`
pour le module. La suite exécute 99 tests : 98 passent, un contrôle Jinja local
est remplacé par la validation en mémoire sur la K1
`K1_EXACT_RUNTIME_OK templates=17 commands=18 string_values=24`. Ces changements
exigent une nouvelle revue puis un nouveau GO exact.

Thomas a renouvelé le GO exact. La capture
`20260822-011022-g4-k1-control-z-mesh-runtime-v1` a obtenu
`PREFLIGHT_Z_MESH_RUNTIME_V1_OK`, vérifié le backup, puis terminé par
`DEPLOY_Z_MESH_RUNTIME_V1_OK`. Le runtime a chargé son état vide avec `ready=1`
et la garde de production a refusé sans modifier position, origine ou cible de
chauffe.

La première validation indépendante a observé le `CXSAVE_CONFIG` différé de
Creality : seuls les espaces des blocs générés `bed_mesh default` et `auto_addr`
différaient. Les trois versions ont été copiées en lecture seule, le diff complet
n'a montré aucun changement de valeur ou d'inclusion et la comparaison
normalisée a obtenu `PRINTER_CFG_NORMALIZED_EQUIVALENCE_OK`. Le validateur
épingle désormais l'empreinte immédiatement posée et l'unique empreinte
normalisée, sans réécrire la machine.

La validation indépendante finale a obtenu
`VALIDATE_Z_MESH_RUNTIME_V1_OK`. Le runtime est retenu avec les hashes exacts de
ses deux fichiers, une seule inclusion, `standby`, axes non homés, chauffes à
zéro, `default`, deux CFS `1.1.3`, `ready=1`, `integrity=empty`,
`accepted_z_valid=0`, `block_reason=no_accepted_z` et `low_moves_armed=0`.
Aucun mouvement, homing, chauffe, extrusion, ordre CFS, calibration, impression,
firmware restart, reboot ou rollback n'a eu lieu. Cette gate est terminée et
n'autorise aucune calibration ni nouvelle mutation. La suite finale exécute
100 tests : 99 passent et le contrôle Jinja local ignoré reste couvert sur
l'environnement exact de la K1.

Required for each named change:

- exact files and commands identified;
- pre-change backup and checksums available;
- patch reviewed in Git;
- validation procedure written;
- rollback procedure written and plausible;
- no unrelated changes bundled;
- explicit approval from Thomas for this exact deployment.

Pour le système de pilotage, un G4 exige aussi :

- version exacte et empreinte de Moonraker/Mainsail si inclus ;
- preuve de ressources, ports, sécurité et coexistence avec les services
  Creality et deux CFS ;
- aucune valeur Z ou température matière universelle cachée ;
- prototype complet hors imprimante déjà vert ;
- ancien post-traitement Orca conservé jusqu'à preuve atomique de son
  remplacement.

Passing G4 authorises only that named mutation.

### Gate installée — `G4-K1-CONTROL-CALIBRATION-PATH-V1`

Status: **installée et validée sous la capture
`20260822-124207-g4-k1-control-calibration-path-v1`**

Cette gate ajoute uniquement le chemin borné non extrusif nécessaire au premier
Z. Les sources, empreintes, destinations, backup, validation sans mouvement et
rollback sont figés dans
`packages/k1-control-v1/calibration-path-v1/`,
`scripts/deploy-k1-control-calibration-path-v1.ps1` et
`docs/17-g4-k1-control-calibration-path-v1.md`.

Sa pose retenue devait :

- partir du runtime installé, `ready=1`, `empty`, sans Z accepté ;
- parser le candidat en mémoire avec le Python/Jinja exact de la K1 avant toute
  écriture ;
- ajouter un seul fichier et un seul include ;
- ne faire qu'un `RESTART` de l'hôte Klipper ;
- ne lancer ni chauffe, ni homing, ni mesh, ni mouvement, ni écriture Z ;
- prouver que la garde à vide refuse sans changement physique ;
- rollbacker uniquement cet overlay tout en préservant le runtime existant.

Le texte reçu `G4-K1-CONTROL-CALIBRATION-PATH-V1` a sélectionné la préparation
du lot. Sans le préfixe exact `GO`, il n'autorise aucune action distante.

Thomas a ensuite envoyé le GO exact. Le premier préflight a joint la K1 mais
Dropbear a fermé la session sur la ligne SSH trop longue contenant tout le
candidat Base64. Il n'avait encore exécuté aucune écriture. Le transport Jinja
utilise désormais stdin avec une commande distante courte. Le préflight corrigé
de la capture `20260822-113503-g4-k1-control-calibration-path-v1` a obtenu
`PREFLIGHT_CALIBRATION_PATH_V1_OK` : base exacte, runtime vide et prêt, overlay
absent, chauffes à zéro, `standby`, deux CFS et fondation conformes, parse Jinja
exact vert. Aucun backup, fichier distant, restart, G-code ou état n'a été créé
ou modifié.

La commande revue ayant changé après le GO, aucun `Deploy` n'a été lancé. La
pose exige un nouveau GO exact sur le commit corrigé.

Thomas a renouvelé ce GO. La capture
`20260822-115608-g4-k1-control-calibration-path-v1` a passé son préflight, créé
le backup exact, posé l'overlay et envoyé le `RESTART`. La validation a interrogé
le socket Klipper avant sa stabilisation, puis le premier `RESTART` du rollback
a rencontré le même socket en transition. Les fichiers étaient déjà restaurés,
mais le chemin restait chargé en mémoire.

L'action `Rollback` reprise sur le backup exact a obtenu
`ROLLBACK_CALIBRATION_PATH_V1_OK`. Le préflight final a obtenu
`PREFLIGHT_CALIBRATION_PATH_V1_OK` et prouve l'overlay absent, la base exacte,
les axes non référencés, les chauffes à zéro, le runtime vide et prêt, deux CFS
et la fondation conformes. Aucun mouvement, homing, chauffage, mesh ou état Z
n'a été produit.

Le déployeur attend désormais le socket de façon bornée avant les lectures
d'objets après pose et avant le `RESTART` du rollback. Cette commande ayant
changé après le GO consommé, une nouvelle tentative exige un nouveau GO exact.
Son préflight corrigé est déjà vert en lecture seule.

Thomas a renouvelé une dernière fois le GO exact. La capture
`20260822-124207-g4-k1-control-calibration-path-v1` a obtenu le préflight frais,
`DEPLOY_CALIBRATION_PATH_V1_OK` puis la validation indépendante
`VALIDATE_CALIBRATION_PATH_V1_OK`. L'attente bornée a absorbé la transition du
socket et des CFS. Les quatre empreintes sont exactes, l'overlay et son unique
include sont retenus, le runtime reste vide, les axes sont non référencés et les
chauffes demandées sont à zéro. La garde à vide refuse sans modifier position,
origine Z ou cibles. Aucun chauffage, homing, mouvement, extrusion, mesh ou état
Z n'a été exécuté.

La suite hors imprimante exécute 131 tests : 129 passent et deux contrôles Jinja
locaux sont ignorés. Celui du runtime installé a déjà été validé sur
l'environnement exact de la K1. Celui du nouvel overlay est intégré au
préflight distant en mémoire et a été vert avant la première écriture.

### Gate exécutée KO — `G4-K1-CONTROL-FIRST-CALIBRATION-V1`

Status: **GO exact consommé ; arrêt KO après exactement deux meshes ; aucun
rerun autorisé**

Le prérequis `G4-K1-CONTROL-CALIBRATION-PATH-V1` était installé et validé à
vide. Thomas a ensuite envoyé le GO exact sur le contexte thermique révisé
`55/140 °C` et `200 s` du commit figé.

La capture `20260822-140602-g4-k1-control-first-calibration-v1` a obtenu
`PREFLIGHT_FIRST_CALIBRATION_V1_OK`, créé et vérifié le backup avant chauffe,
puis obtenu `PREPARE_FIRST_CALIBRATION_V1_OK` et
`MESH1_FIRST_CALIBRATION_V1_OK`. Le second mesh a été capturé une seule fois.
Sa comparaison sur 36 points retourne `accepted=false`, maximum
`0,062125 mm`, moyenne `0,018049 mm`, pour le seuil `0,025 mm`.

Le pilote a exécuté l'arrêt KO prévu et coupé les chauffes. Aucun troisième
mesh, `CommitMesh`, `BeginZ`, palier bas, acceptation ou validation de succès
n'a été lancé. Le profil cible est absent de `printer.cfg`, les trois fichiers
d'état Z restent absents et la base persistante conserve son empreinte exacte.
Le contrôle final en lecture seule confirme `standby` et les cibles à zéro ; il
s'arrête ensuite sur les axes `xyz` encore référencés, état normal après les
mesures. Le backup exact reste sur la K1 comme preuve.

Le paquet préparé contient :

- plaque, températures, stabilisation, matrice et interpolation explicites ;
- nettoyage et homing dans un ordre revu ;
- deux meshes transitoires comparables et un seuil de qualification borné ;
- session Z provisoire avec acceptation, annulation et restauration ;
- préflight, backup, preuves avant/après et rollback exacts ;
- contrat UX montrant comment les mêmes choix deviendront accessibles sans
  console ni assistance Codex.

Le candidat se trouve dans
`packages/k1-control-v1/first-calibration-v1/`, son pilote est
`scripts/run-k1-control-first-calibration-v1.ps1` et son contrat complet est
documenté dans `docs/18-g4-k1-control-first-calibration-v1.md` et ADR-006.

Le lot fige `PEI_TEXTURED_A` ID `1`, plateau `55 °C`, buse `140 °C`,
stabilisation `200 s`, nettoyage stock borné à `180 °C`, puis deux meshes
`6 × 6` Lagrange sur `5–295 mm`. L'écart point par point doit rester inférieur
ou égal à `0,025 mm`; sinon la mission s'arrête sans troisième essai automatique.
Le second mesh qualifié pourra être persisté sous
`k1_p001_t055_r001_n06x06`, puis le chemin installé guidera le Z à partir du
seed neutre explicite `0,0 mm`.

Le mode `Plan` du pilote est purement local. Toute action distante exigera
`-Execute`, la gate exacte, une capture privée et les checkpoints précédents.
Le backup avant première chauffe conserve le `printer.cfg` exact et la preuve
d'absence du stockage Z. `Cancel` préserve le mesh qualifié ; `Rollback` restaure
la base vide exacte tout en conservant le runtime et le chemin installés.

Son éventuelle réussite qualifiera une première calibration. Elle ne validera
pas encore l'autonomie production, qui reste conditionnée par la bascule
interface/Orca/`START_PRINT`, le retrait du `+0,27 mm`, les températures CFS et
G5.

### Gate validée et close — `G4-K1-CONTROL-FIRST-CALIBRATION-V2`

Status: **VALIDATE_FIRST_CALIBRATION_V2_OK ; mesh robuste et Z `−0,04 mm` retenus**

V2 remplace la preuve fragile à deux meshes par exactement six mesures dans le
même contexte `PEI_TEXTURED_A`, `55/140 °C`, `200 s`, `6 × 6` Lagrange. Les
mesures 1–3 et 4–6 forment deux médianes point par point indépendantes. Leur
écart doit respecter moyenne absolue `≤ 0,020 mm`, RMS `≤ 0,025 mm` et maximum
`≤ 0,060 mm`. Aucun septième mesh automatique n'est permis. La médiane des six
n'est chargée, relue et persistée qu'après succès des trois critères.

La capture `20260822-160948-g4-k1-control-first-calibration-v2` a passé le
préflight et le backup avant chauffe, puis exécuté exactement six meshes. La
qualification accepte les deux médianes indépendantes : moyenne absolue
`0,010788694 mm`, RMS `0,013996452 mm`, maximum `0,034352 mm` sur 36 points.
Le profil robuste `k1_p001_t055_r001_n06x06` est le seul ajout persistant à
`printer.cfg`.

Le premier commit local a rencontré un faux KO : l'endpoint `update_mesh`
conserve le homing `xyz` au lieu de redémarrer Klipper. Le hash et le diff exact
ont prouvé que la matrice robuste seule était chargée sous `K1_TRANSIENT` ; une
reprise bornée a alors exécuté la commande de commit déjà revue. Le pilote est
corrigé hors imprimante pour attendre cet état réellement observé.

Le chemin Z a été repris avec Thomas présent sans refaire les meshes. Une pile
de dix épaisseurs a évalué la cale papier à `0,09 mm`. Le premier contact net a
été observé à `−0,05 mm`; le retour à `−0,04 mm` a laissé la cale libre et vise
le jeu de `0,10 mm`. Thomas a confirmé l'observation. La buse a été parquée,
l'état Z a été persisté atomiquement, puis les chauffes ont été coupées.

La validation finale confirme stockage `ok`, `accepted_z_valid=1`, offset
`−0,04 mm`, session fermée, chemin `committed`, profil robuste présent,
`standby`, cibles zéro, deux CFS et fondation conformes. Un premier faux KO du
pilote cherchait l'en-tête non commenté du profil ; Klipper le génère sous
`#*# [bed_mesh ...]`. Le contrôle corrigé et testé a ensuite obtenu
`VALIDATE_FIRST_CALIBRATION_V2_OK`. Le GO est consommé et n'autorise aucun rerun.

### Gate exécutée — `G4-K1-CONTROL-CALIBRATION-UI-V1`

Status: **installée, validée et close**

Cette gate pose deux composants Python, leurs deux caches `cpython-38`, trois
fichiers statiques et une configuration Moonraker qui ajoute uniquement
`[k1_control]`. Elle crée un backup exact avant la première modification,
redémarre seulement le Moonraker dédié et valide l'API métier. Elle ne chauffe,
ne home, ne bouge, ne mesure et n'écrit aucun Z.

L'interface choisit plaque, températures, stabilisation, matrice,
interpolation et seed ; elle orchestre côté serveur le protocole robuste, la
descente Z, l'enregistrement, l'annulation et les deux restaurations. Sa pose
devait rester une gate distincte de la campagne physique. Cette gate n'a ouvert
l'autonomie calibration quotidienne qu'après la campagne complète depuis
l'écran, désormais close et validée.

La revue post-calibration accepte uniquement les phases de chemin fermées
`idle`, `committed` et `cancelled`, corrige le transport du `curl` Creality et
importe les deux sources en mémoire sous le Python Moonraker `3.8.2` exact avant
toute mutation. Le déployeur est épinglé dans le manifeste. Le plan local et le
préflight réel en lecture seule avaient obtenu `PLAN_CALIBRATION_UI_V1_OK` et
`PREFLIGHT_CALIBRATION_UI_V1_OK`. Les nouveaux chemins étaient alors absents et
aucun service n'avait été relancé.

Un premier GO exact a ensuite été consommé par la capture
`20260822-192821-g4-k1-control-calibration-ui-v1`. Le préflight et le backup
étaient verts, mais le premier `scp` a tenté SFTP et s'est arrêté parce que le
Dropbear Creality ne fournit pas `sftp-server`. Aucun payload n'a été posé. Le
rollback automatique a restauré la base exacte, retiré les chemins candidats,
redémarré seulement Moonraker et le préflight final est vert. Le candidat
corrigé force maintenant le protocole historique avec `scp -O` et retire le
staging exact au rollback. Comme le déployeur revu a changé, cette nouvelle
version a repassé `PREFLIGHT_CALIBRATION_UI_V1_OK` en lecture seule, mais sa pose
exige un nouveau GO exact séparé.

Ce second GO exact a ensuite été consommé par la capture
`20260822-202014-g4-k1-control-calibration-ui-v1`. Le déploiement et les
contrôles par fichiers/API ont d'abord été verts, mais la validation dans le
navigateur réel a refusé l'interface : le service worker Mainsail interceptait
le chemin sur l'origine `127.0.0.1` et nginx ne pouvait pas traverser le dossier
UI créé en mode `0700`. Le journal nginx a confirmé `Permission denied`. Le
rollback exact a retiré le composant et l'interface, restauré la configuration,
redémarré seulement Moonraker puis obtenu un nouveau
`PREFLIGHT_CALIBRATION_UI_V1_OK`. Aucun chauffage, homing, mouvement, mesh ou Z
n'a été exécuté.

Le candidat hors imprimante impose maintenant le mode `0755` du dossier UI et
le valide exactement. Le lanceur calibration utilise l'origine isolée
`http://localhost:4409/k1-control/`, sur le même tunnel et la même frontière
d'authentification, afin que le service worker Mainsail ne puisse pas masquer la
page. Ces changements de déployeur et de parcours navigateur exigent une
nouvelle revue figée puis un nouveau GO exact séparé.

L'audit du parcours complet après rechargement a encore corrigé le candidat hors
imprimante : l'API expose le Z accepté, le formulaire reprend le seed et les
paramètres de campagne depuis l'état serveur, tandis que « plateau libre » et
« buse propre » restent des confirmations physiques à refaire et conditionnent
le bouton Z. Cela permet de fermer puis rouvrir le navigateur sans console et
sans perdre la campagne. Les empreintes du paquet ont changé ; le prochain GO
exact devra porter sur cette version figée.

Thomas a renouvelé le GO exact sur cette version. La capture
`20260822-211633-g4-k1-control-calibration-ui-v1` a obtenu
`PREFLIGHT_CALIBRATION_UI_V1_OK`, `DEPLOY_CALIBRATION_UI_V1_OK`, puis un second
`VALIDATE_CALIBRATION_UI_V1_OK` indépendant. Le dossier UI est en `0755`, l'API
est `idle`, le Z accepté est `−0,04 mm`, la K1 est `standby`, les cibles sont à
zéro et les mouvements bas sont désarmés. Seul Moonraker a été redémarré. Le GO
est consommé et ne couvre pas la campagne. Après authentification humaine sur
`localhost`, le vrai rendu Chrome a confirmé l'API, les paramètres exacts et le
seed `−0,04 mm`. Un rechargement complet a restauré ces valeurs depuis le
serveur tout en laissant les confirmations physiques décochées. La gate est
close.

### Gate exécutée — `G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1`

Status: **correction `6 × 6` installée et validée**

La révision actuelle retire les choix historiques `3/4/5/9/11/15` et expose
uniquement `6 × 6` Lagrange avec un seul mesh quotidien. Le serveur refuse toute
autre combinaison avant chauffe.

Deux défauts de préflight ont d'abord été corrigés sans mutation : les anciennes
assertions `9/11/15`, puis l'omission de la phase terminale sûre `rolled_back`.
Le GO persistant de Thomas a ensuite couvert les corrections nécessaires jusqu'au
vert. Le déployeur prouve sur le Python Moonraker exact l'acceptation unique de
`6 × 6` Lagrange et le refus de `3/4/5/9/11/15` et de `6 × 6` bicubique.

La capture `20260823-161103-g4-k1-control-calibration-ui-matrix-v1` a obtenu
`PREFLIGHT_CALIBRATION_UI_MATRIX_V1_OK`,
`DEPLOY_CALIBRATION_UI_MATRIX_V1_OK`, puis une validation indépendante
`VALIDATE_CALIBRATION_UI_MATRIX_V1_OK`. Le core, `index.html` et `app.js` ont été
remplacés après backup exact, puis seul le Moonraker dédié a été redémarré. Les
hashes installés et de rollback sont conformes ; BED-MESH-V2 et `printer.cfg`
sont inchangés. Klippy est `ready`, `failed_components=[]`, `warnings=[]`, la K1
est au repos avec cibles zéro, le Z accepté et le profil robuste sont valides,
`6 × 6` Lagrange est chargé et les deux CFS sont connectés. Les 220 tests sont
verts avec 3 ignorés connus. Aucune calibration, chauffe, référence, mesure,
extrusion, commande CFS, impression ou écriture Z n'a eu lieu. La gate est close.

Chrome a enfin rendu les octets dont les hashes correspondent exactement aux
trois fichiers distants : titre `K1 Control — calibration`, unique matrice
`6 × 6 — maximum PRTouch fiable`, unique interpolation Lagrange, `0 / 1`
passage et 36 points. Les choix `9/11/15` sont absents et aucun bouton n'a été
actionné. Le rendu a utilisé une origine locale temporaire sans API parce que
l'origine authentifiée `4409` restait interceptée par l'ancien service worker
Mainsail ; aucun cache navigateur n'a été supprimé.

### Gate corrective — `G4-K1-CONTROL-CALIBRATION-UI-RETRY-SAFETY-V1`

Status: **correction `1 mesh` installée et validée**

La révision historique comparait `mesh_index < mesh_target_count`. L'état réel
après l'échec du mesh quotidien unique est pourtant `rolled_back`, `1 / 1` : le
test ne détectait plus cette fin non acceptée. La règle actuelle réinitialise
une fois `replace_existing=false` et `plate_clear=false` sur `cancelled`,
`failed`, `mesh_rejected` ou `rolled_back`, puis laisse l'opérateur réactiver
explicitement un remplacement volontaire.

Thomas a autorisé cette gate jusqu'au vert sans redemander la même autorisation.
La capture `20260823-164558-g4-k1-control-calibration-ui-retry-safety-v1` a
obtenu le préflight, le déploiement et deux validations. Seul `app.js` a été
remplacé après backup exact, sans restart. Le hash installé `3d3d53ea…`, le
backup `33a20db2…`, les fichiers hors write-set, Klippy `ready`,
`failed_components=[]`, `warnings=[]`, l'état au repos, le profil robuste, le Z,
`6 × 6` Lagrange et les deux CFS sont conformes.

La preuve navigateur sur les octets exacts installés a simulé `rolled_back`,
`1 / 1`, avec `replace_existing=true` côté serveur. Les deux cases étaient
décochées au premier rendu ; une coche volontaire du remplacement a survécu aux
rafraîchissements, puis un rechargement frais a de nouveau décoché les deux
cases. Aucun POST ou clic de calibration n'a eu lieu. Les 220 tests sont verts,
avec 3 ignorés connus. La gate est close.

### Gate validée — `G4-K1-CONTROL-CALIBRATION-UI-CAMPAIGN-V1`

Status: **`VALIDATE_CALIBRATION_UI_CAMPAIGN_V1_OK` ; un mesh `6 × 6`, chemin Z et acceptation persistés**

Cette gate ne pose aucun fichier. La révision actuelle qualifie depuis l'écran
un seul mesh physique `6 × 6` Lagrange avec `PEI_TEXTURED_A`, `55/140 °C` et
`200 s`, puis le chemin Z borné et l'acceptation humaine du jeu. Codex n'envoie
aucune commande de calibration et ne clique pas à la place de Thomas ; ses
contrôles restent en lecture seule.

Tout rejet ou mesh incomplet, deuxième passage, rerun automatique, matrice autre
que `6 × 6` Lagrange, intervention console, perte de l'API, mouvement inattendu
ou impossibilité d'observer un jeu sûr est un KO avec restauration exacte et
arrêt sans rerun. Le contrat, le manifeste et le validateur sont épinglés.

MATRIX-V1 et son rendu fixe `6 × 6` sont maintenant clos. La campagne reste
fermée jusqu'aux gates séparées RETRY-SAFETY-V1 et PRTOUCH-PRESETS-V1, puis à
son propre préflight frais et son autorisation. Les captures de campagne
`20260822-*` et leurs départs `9 × 9` appartiennent au protocole historique
supersédé ; elles ne constituent plus une autorisation de relance.

Le départ écran a ensuite été conforme mais s'est arrêté proprement à `1/6`,
sans matrice exploitable, avec `Le mesh ne contient pas le nombre de lignes
attendu.` Les chauffes, le Z et le profil `6 × 6` ont été vérifiés sûrs. Le
firmware exact prouve que le wrapper Creality `prtouch_v3` utilise le
`probe_count` chargé depuis `[bed_mesh]` et non le paramètre dynamique amont.

### Gate corrective — `G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-MATRIX-V1`

Status: **installée et validée**

Le composant séparé ne remplace ni le core UI ni le runtime Klipper. Sa pose
ajoute un fichier, ajoute sa section au `moonraker.conf` dédié et redémarre
seulement ce Moonraker, sans modifier `printer.cfg` ni lancer d'action physique.
Pendant une future calibration, il commute atomiquement l'unique
`[bed_mesh] probe_count` après le backup et avant la chauffe, redémarre Klipper,
relit la valeur chargée et toutes les gardes, puis restaure la valeur précédente
après `TURN_OFF_HEATERS`. Le préflight exact de la capture
`20260823-001724-g4-k1-control-calibration-ui-prtouch-matrix-v1` a obtenu
`PREFLIGHT_CALIBRATION_UI_PRTOUCH_MATRIX_V1_OK`,
`DEPLOY_CALIBRATION_UI_PRTOUCH_MATRIX_V1_OK` et deux
`VALIDATE_CALIBRATION_UI_PRTOUCH_MATRIX_V1_OK`. L'essai `9 × 9` vide a ensuite
été restauré exactement ; le nouveau préflight de campagne est vert sous
`20260823-002500-g4-k1-control-calibration-ui-campaign-v1`.

### Gate corrective — `G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-PRESETS-V1`

Status: **installée et validée**

Ce delta statique retire le choix pair `4 × 4` que le parcours spiralé Creality
refuse, conserve `3/5/6/9/11/15` et remplace le repli JavaScript par `5 × 5`.
Il sauvegarde et remplace seulement `index.html` et `app.js`, sans restart ni
action physique. Le premier transfert a rencontré un défaut local de guillemets
dans la validation et a restauré automatiquement les deux fichiers exacts. La
capture corrigée
`20260823-003755-g4-k1-control-calibration-ui-prtouch-presets-v1` a ensuite
obtenu le déploiement et deux validations vertes. La suite complète compte 191
tests verts et 3 ignorés connus.

Le second départ `9 × 9` a ensuite prouvé une seconde dépendance chargée au
démarrage : avec `probe_count=9,9` mais `algorithm=lagrange`, Klipper a affiché
XS3002 avant toute chauffe ou mesure. Le rollback automatique a restauré
`6,6 + lagrange`, Klipper prêt, chauffes zéro, Z et profil rapide intacts.

### Gate corrective — `G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-BED-MESH-V2`

Status: **révision sûre `6 × 6 / 1 mesh` installée et validée**

V2 remplace uniquement le composant prtouch V1 et redémarre le Moonraker dédié,
sans modifier `printer.cfg` pendant la pose ni lancer d'action physique. Pendant
la campagne, il commute atomiquement puis relit le couple
`probe_count + algorithm` après le backup et avant la chauffe. Les niveaux
`9/11/15` exigent `bicubic`; le niveau `6` revient à `lagrange`. Un échec restaure
les deux valeurs ensemble. Le préflight réel a obtenu
`PREFLIGHT_CALIBRATION_UI_PRTOUCH_BED_MESH_V2_OK` sur l'état XS3002 restauré à
zéro mesh. La capture
`20260823-005835-g4-k1-control-calibration-ui-prtouch-bed-mesh-v2` a d'abord
obtenu des marqueurs verts insuffisants : le validateur ne contrôlait pas
`failed_components`, et la K1 omet la ligne `algorithm` pour son `lagrange`
implicite. Le composant avait donc échoué au chargement sans action physique.
La révision corrigée préserve exactement cette forme implicite, ajoute
`bicubic` seulement pendant les grandes matrices et valide le chargement réel.
La capture `20260823-012755-g4-k1-control-calibration-ui-prtouch-bed-mesh-v2-r2`
a obtenu le préflight, le déploiement et deux validations vertes ; Moonraker
rapporte `failed_components=[]` et `warnings=[]`. Après rollback exact de la
campagne XS3002, le préflight complet
`20260823-013151-g4-k1-control-calibration-ui-campaign-v1` est vert.

L'audit de chaîne hors imprimante montre maintenant que MATRIX-V1 puis
RETRY-SAFETY-V1 produisent déjà exactement les deux hashes finaux de
PRTOUCH-PRESETS-V1. Le déployeur PRESETS est donc idempotent : après ces deux
lots il exécute la validation complète et écrit seulement sa preuve locale,
sans backup, transfert ni remplacement distant. Le chemin historique de copie
reste fermé sauf si les hashes de base et de sortie diffèrent réellement.

La capture `20260823-165742-g4-k1-control-calibration-ui-prtouch-presets-v1` a
confirmé ce chemin idempotent sur la K1 réelle. Le préflight, la validation
intégrée et la validation indépendante sont verts avec `already_present=true`
et `remote_write=false`. Klippy est prêt, ses listes d'échec et d'avertissement
sont vides, le profil robuste, le Z accepté, `6 × 6` Lagrange et les deux CFS
sont conformes. Aucune action physique n'a eu lieu.

Le départ suivant, campagne `20260823-021858-540-calibration-ui-v1`, a atteint
exactement `g29_cnt=36` pendant son premier mesh `9 × 9`, puis le wrapper
Creality a levé `IndexError: list index out of range` avant le point 37. La
matrice incomplète a ensuite produit le message applicatif sur le nombre de
lignes. Le rollback API a restauré `standby`, cibles zéro, axes non référencés,
profil robuste `6 × 6`, stockage `ok` et Z accepté `−0,04 mm`. Aucun résultat de
ce mesh n'est retenu.

Cette preuve invalide `9/11/15` dans une seule séquence PRTouch. L'ADR-012 fixe
le contrat standard à `6 × 6 + lagrange` et à un seul mesh. L'ADR-013 précise
désormais que le profil final n'est pas borné à six : quatre sous-grilles de 36
contacts maximum peuvent former 121 vraies mesures `11 × 11`, mais seulement
après une qualification séparée dans la même chauffe et le même référencement.
Les six meshes de FIRST-CALIBRATION-V2 restent une qualification initiale
historique ; ils ne sont plus répétés par l'UI. Le contournement
`pr_version: 1` avec retrait des tables usine reste rejeté.

Les révisions corrigées de PRTOUCH-BED-MESH-V2, MATRIX-V1, RETRY-SAFETY-V1 et
PRTOUCH-PRESETS-V1 sont maintenant installées et validées séparément. Le
validateur CAMPAIGN-V1 a été renforcé hors imprimante pour contrôler le manifeste
UI exact, `server/info`, le mesh chargé et les deux CFS ; ses tests sont verts.
Deux faux KO locaux ont d'abord comparé le core final au hash historique de
BED-MESH-V2 puis demandé à PRESETS de couvrir `printer.cfg`. Le validateur
corrigé contrôle la carte finale complète PRESETS et vérifie séparément le hash
exact de `printer.cfg`. La capture
`20260823-171803-g4-k1-control-calibration-ui-campaign-v1` a d'abord obtenu le
préflight vert.

Thomas a ensuite lancé depuis le vrai écran l'unique mesure `6 × 6`. Les 36
contacts sont complets, la qualification est acceptée, les huit paliers Z
`5/2/1/0,5/0,3/0,2/0,15/0,1 mm` ont été parcourus, le jeu final a été confirmé
et le Z `−0,04 mm` enregistré. Aucun deuxième mesh ni rerun n'a eu lieu.

Le premier `CaptureLevel` final a rencontré un faux KO : `printer.cfg` ne peut
plus garder son hash de préflight puisque le profil robuste contient justement
le nouveau mesh quotidien. Le diff exact avec le backup ne change que les six
lignes de 36 points sous
`#*# [bed_mesh k1_p001_t055_r001_n06x06]`. Le validateur corrigé épingle le
backup, refuse tout autre changement et compare chaque valeur persistée à la
matrice privée acceptée. Il a ensuite obtenu
`CAPTURE_CALIBRATION_UI_LEVEL_OK level=supported` et
`VALIDATE_CALIBRATION_UI_CAMPAIGN_V1_OK`. L'état final confirme `standby`,
cibles zéro, chemin Z `committed`, stockage `ok`, profil transitoire absent,
`6 × 6` Lagrange chargé, deux CFS et Moonraker sans échec ni avertissement.

Le vrai écran avait gardé le texte trompeur « Qualifie d'abord le mesh robuste »
pendant la préparation Z et après acceptation. NAVIGATION-V1-R2 corrige
maintenant ce texte et son vrai rendu est validé.

### Gate UX close — `G4-K1-CONTROL-CALIBRATION-UI-NAVIGATION-V1-R2`

Status: **posée et validée côté SSH et dans le vrai Chrome ; aucune action
physique**

Le premier delta a corrigé `app.js` et créé
`/usr/data/printer_data/config/.theme/navi.json`. Son lien `/k1-control/` a été
rejeté après un KO navigateur réel. R2 a conservé le worker constructeur, créé
`access-k1-control -> k1-control` et repointé le lien vers
`/access-k1-control/`. La capture
`20260824-112535-g4-k1-control-calibration-ui-navigation-v1-r2` et le vrai rendu
Chrome sont verts. Le rollback exact vers V1 reste vérifié.

### Gate exploratoire — `G4-K1-CONTROL-COMPOSITE-MESH-SUBGRID-V1`

Status: **passed — 25 contacts physiques et matrice `5 × 5` qualifiés**

Cette gate historique ne couvre qu'une sous-grille PRTouch décalée de 36
contacts maximum. Elle conserve le `pr_version: 2`, les 72 tables exactes, la
commande stock et les deux CFS ; le profil composite complet est couvert par la
gate suivante.

Le fusionneur hors imprimante reste sous
`packages/k1-control-v1/composite-mesh-v1`. Le paquet physique séparé
`composite-subgrid-v1` impose maintenant une première grille impaire/impaire
`5 × 5`, 25 contacts aux positions `34..266 mm`, puis chauffes zéro, nettoyage
de la session et profil robuste restauré. Sa pose redémarre Moonraker seulement
et son essai redémarre Klipper uniquement après la capture. La campagne réelle
a prouvé les 25 contacts. La reprise R2 corrige la course post-restart et migre
atomiquement le marqueur d'état sans changer la matrice. La suite complète de
237 tests est verte, avec 3 tests historiquement ignorés. Cette gate ne couvre
pas encore les trois autres partitions ni la persistance finale `11 × 11`.

### Gate précision — `G4-K1-CONTROL-COMPOSITE-MESH-V1-R2`

Status: **passed — 144 contacts, 121 positions et profil persistant `11 × 11`
qualifiés**

La première campagne complète a rejeté la recette rectangulaire après les 30
contacts du deuxième passage, sans persistance, puis restauré la base exacte.
R2 utilise quatre quadrants carrés `6 × 6` dans une seule chauffe et un seul
référencement. La capture
`20260824-131000-g4-k1-control-composite-mesh-v1-r2-run` contient les quatre
matrices complètes. L'écart brut maximal des recouvrements, `0,147858 mm`,
provenait d'un biais additif constant du post-traitement propriétaire. Le
solveur retenu applique un seul décalage par quadrant, recentré à moyenne
pondérée nulle, sans correction locale. L'écart aligné maximal est
`0,043745029 mm` et la moyenne `0,013871331 mm`, sous la limite `0,05 mm`.

Le delta `G4-K1-CONTROL-COMPOSITE-MESH-RECOVERY-V1` a été posé et validé deux
fois sous `20260824-155319-g4-k1-control-composite-mesh-recovery-v1`, sans
chauffe, homing, mouvement ni mesure. La reprise logique a obtenu
`RECOVER_COMPOSITE_MESH_V1_OK` puis
`VALIDATE_RUN_COMPOSITE_MESH_V1_OK`. Le profil
`k1_p001_t055_r001_n11x11` est persistant avec onze lignes de onze valeurs ; le
profil robuste `6 × 6` reste actif. État final : `standby`, cibles zéro, axes
non référencés, Z `−0,04 mm`, stockage `ok`, deux CFS connectés.

Cette gate ferme l'acquisition et la persistance composite. Elle n'ouvre pas
encore le mode Précision dans l'UI : une comparaison contrôlée de premières
couches doit d'abord montrer un gain utile, sans nouveau palpage.

### Gate comparaison — `G4-K1-CONTROL-COMPOSITE-FIRST-LAYER-COMPARISON-V1`

Status: **failed closed — Z `+0,27 mm` trop haut ; composite non lancé ;
fichiers distants supprimés**

La source privée est le carré mono-couche G3 de SHA-256
`50b54577a4b8a76a0bb5fb2b48e915d1dc6ea9e5bb87aa1f32404c559a54f856`.
Les deux sorties ne diffèrent que par le profil chargé après `START_PRINT`.
L'hypothèse de garder l'ancien Z Orca identique est rejetée. Le premier passage
robuste a imprimé environ `0,31 mm` au-dessus du Z accepté et ne qualifie rien.
Le passage composite n'a pas été lancé. La configuration persistante et le
profil robuste sont intacts ; les deux G-code ont été retirés. Un successeur
doit prouver d'abord un Z absolu correct sur un motif court.

## G5 — V1 production baseline

Status: **not passed**

Required:

- cold boot followed by three successful consecutive prints on a known plate without manual Z-offset correction;
- requested temperatures respected during validated CFS transitions;
- both CFS units exercised;
- fast and reference startup paths behave as documented;
- configuration survives reboot;
- a saved live Z calibration survives print end and reboot, while a new
  reference calibration invalidates it;
- plate/temperature/nozzle mesh selection behaves as declared ; aucun mesh
  adaptatif par travail n'est autorisé sans qualification séparée ;
- rollback has been tested or safely simulated;
- repository state matches the deployed state;
- normal jobs need no Codex intervention or per-print manual file edit;
- calibration can be completed from the daily interface without console input,
  with plate/temperature/matrix/interpolation selection and visible
  qualification, save, cancel and restore actions;
- the interface reports `Prêt` or `Bloqué` with an actionable reason and never
  requires Codex to translate an internal runtime state;
- remaining limitations are explicit.

The presence of Mainsail, Moonraker or `KCTRL_*` macros alone does not satisfy
either calibration autonomy or this production gate.

Le profil Orca réellement actif a maintenant été capturé directement depuis la
configuration `2.4.2` : ancien départ avec `G28` et outil avant `START_PRINT`,
changement de filament vide et processus actif gardant
`--start-z-offset 0.27`. Les indicateurs live `box.state` et `box.t_command` sont
disponibles et intégrés au traceur passif. Cela lève le manque d'identité du
profil actif, mais pas la frontière CFS compilée : aucun propriétaire de
température ou paquet de bascule production n'est encore suffisamment prouvé
pour recevoir un GO.
