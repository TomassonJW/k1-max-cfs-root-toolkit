# GATES

Progression is evidence-based. Passing a gate authorises only the next bounded phase, not every later action.

These gates control evidence collection and changes affecting the printer. They do not gate normal Git or GitHub operations: under D-010, Codex may complete branches, commits, pushes, pull requests, merges into `main` and cleanup without requesting another operator approval. Repository integration never expands the printer-side authority granted by a gate.

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

### Prochaine gate nommée — `G4-K1-CONTROL-FIRST-CALIBRATION-V1`

Status: **préparation hors imprimante autorisée ; aucune exécution ni GO reçu**

Cette gate devra contenir avant présentation à Thomas :

- plaque, températures, stabilisation, matrice et interpolation explicites ;
- nettoyage et homing dans un ordre revu ;
- deux meshes transitoires comparables et un seuil de qualification borné ;
- session Z provisoire avec acceptation, annulation et restauration ;
- préflight, backup, preuves avant/après et rollback exacts ;
- contrat UX montrant comment les mêmes choix deviendront accessibles sans
  console ni assistance Codex.

Son éventuelle réussite qualifiera une première calibration. Elle ne validera
pas encore l'autonomie production, qui reste conditionnée par la bascule
interface/Orca/`START_PRINT`, le retrait du `+0,27 mm`, les températures CFS et
G5.

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
- plate/temperature mesh selection and per-job adaptive mesh behave as declared;
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
