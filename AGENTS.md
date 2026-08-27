# AGENTS.md — K1 Max CFS Root Toolkit

## Mission

Build a reproducible, evidence-driven and reversible way to diagnose and improve a rooted Creality K1 Max with the classic CFS upgrade and two chained CFS units.

The printer is production hardware. It is never treated as a disposable sandbox.

## Current authority and phase

The active phase is **P4 — V1 and V2 foundations are closed; V3, PATHS-V1, the
Z/mesh runtime and CALIBRATION-PATH-V1 are installed and validated;
FIRST-CALIBRATION-V1 stopped KO; FIRST-CALIBRATION-V2 is installed and validated;
CALIBRATION-UI-V1 et ses correctifs historiques sont installés ; la campagne
réelle `9 × 9` a ensuite prouvé la limite physique PRTouch à trente-six points
par un `IndexError` au point 37 ; le rollback est vert ; la correction hors
imprimante impose désormais `6 × 6` Lagrange et un seul mesh quotidien ; les
deltas sûrs PRTOUCH-BED-MESH-V2, MATRIX-V1, RETRY-SAFETY-V1 et
PRTOUCH-PRESETS-V1 sont installés et validés ;
la campagne quotidienne `6 × 6 / 1 mesh` et NAVIGATION-V1-R2 sont acceptées et
validées ; SUBGRID-V1 et sa reprise R2 sont installées, et l'essai physique
`5 × 5` de 25 contacts est qualifié ; COMPOSITE-MESH-V1-R2 a capturé quatre
quadrants carrés `6 × 6`, soit 144 contacts et 121 positions uniques ; la
reprise logique a qualifié et persisté le profil `11 × 11` sans nouvelle
mesure ; la comparaison V2 a prouvé un gain central mais un KO sévère aux
bords ; MESH-EDITOR-OFFLINE-V1 est validé sans connexion K1 ; le mode
Précision reste caché ; le diagnostic physique borné des bords est suspendu
après un passage sans débit ; le contrat complet du cycle filament est figé
hors imprimante ; CFS-DYNAMIC-TEMP-ROUTING-V1 est clos avec 25 scénarios verts
et un propriétaire minimal choisi sans transport ;
CFS-MINIMAL-OWNER-PROTOCOL-V1 est clos en KO borné avec une liste appelable
vide ; CFS-MINIMAL-OWNER-EVIDENCE-V1 ajoute une preuve historique exacte du
retrait `T1A` mais reste close en KO borné, sans message appelable ;
CFS-MINIMAL-OWNER-PASSIVE-CAPTURE-V1 qualifie un retrait stock réel `T1A`,
révèle une cible `220 °C` laissée active et maintient le protocole série fermé ;
CFS-STOCK-UNLOAD-GUARD-V1 encadre maintenant hors imprimante cette macro avec
preuve d'effet, aucun retry et arrêt thermique vérifié ;
CFS-STOCK-UNLOAD-GUARD-LIVE-PREFLIGHT-V1 cartographie les champs réels en lecture
seule, retire l'hypothèse d'un état direct de fin et constate aucune route
engagée ; CFS-STOCK-UNLOAD-GUARD-ADAPTER-OFFLINE-V1 traduit maintenant dix
réponses synthétiques vers le garde, refuse les ambiguïtés et reste sans
transport ; CFS-STOCK-UNLOAD-GUARD-ADAPTER-LIVE-READ-ONLY-V1 confirme deux
lectures nettoyées, aucune route et des configurations inchangées sans appeler
le garde ; CFS-STOCK-UNLOAD-GUARD-TRANSPORT-OFFLINE-V1 est clos avec `13/13`
scénarios et aucun connecteur réel ; `GOAL-P4-OFFLINE-CYCLE-CFS-V1` est terminé
avec `27/27` scénarios canoniques, un moteur pur et un plan futur inerte ;
`GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` est clos en lecture seule avec deux
réponses stables, des lectures à moins de `236 ms`, les empreintes exactes et
aucun effet ; sa capture bloque la suite physique parce que le mesh actif
`default` différait du profil robuste encore présent
`k1_p001_t055_r001_n06x06` ; une lecture fraîche après la correction de la
passerelle montre désormais le composite `k1_p001_t055_r001_n11x11` actif,
toujours différent du robuste requis ; la prochaine gate doit charger et
vérifier uniquement le robuste avant le Goal 3 ;
GATEWAY-PRIVATE-LAN-NO-AUTH-V1 est installé et validé : le port `4409` ne
demande plus de mot de passe, reste limité aux réseaux IPv4 privés, et présente
uniquement son proxy local approuvé à Moonraker ; production remains closed**.

La capture `20260823-165742-g4-k1-control-calibration-ui-prtouch-presets-v1` a
clos PRTOUCH-PRESETS-V1 après un préflight frais, un déploiement idempotent et
deux validations. Les hashes sûrs étaient déjà présents : aucune écriture
distante, aucun backup et aucun restart n'ont été nécessaires. Klippy, les
listes d'échec et d'avertissement, le profil robuste, le Z accepté, le mesh
`6 × 6` Lagrange et les deux CFS sont conformes. La capture
`20260823-171803-g4-k1-control-calibration-ui-campaign-v1` a ensuite obtenu un
mesh quotidien complet de 36 points, le parcours Z `5..0,1 mm`, l'acceptation
à `−0,04 mm`, `CAPTURE_CALIBRATION_UI_LEVEL_OK` et
`VALIDATE_CALIBRATION_UI_CAMPAIGN_V1_OK`. Le validateur final autorise seulement
les six lignes de points du profil mesuré et refuse toute autre différence de
`printer.cfg` avec le backup exact.

Le delta `G4-K1-CONTROL-CALIBRATION-UI-NAVIGATION-V1` a été posé sans restart ni
action physique, puis son vrai rendu a montré que le service worker Mainsail
interceptait `/k1-control/`. La révision R2 garde le worker constructeur intact,
crée l'alias original `access-k1-control -> k1-control` et repointe `navi.json`.
Sous la capture `20260824-112535-g4-k1-control-calibration-ui-navigation-v1-r2`,
le préflight, la pose et deux validations SSH sont verts. Le vrai Chrome
authentifié ouvre maintenant K1 Control depuis le bouton Mainsail, sans nouvelle
authentification, et affiche le texte Z final corrigé. SUBGRID-V1 a ensuite
obtenu son préflight, sa pose et deux validations SSH sous la capture
`20260824-113026-g4-k1-control-composite-mesh-subgrid-v1`. Seul le Moonraker
dédié a redémarré ; aucune action physique n'a eu lieu. Thomas a ensuite confirmé
le plateau libre et `PEI_TEXTURED_A`, puis la capture
`20260824-113434-g4-k1-control-composite-mesh-subgrid-v1-run` a obtenu les 25
contacts et une matrice finie. Deux défauts de reprise ont été corrigés sans
nouvelle mesure : la course Klipper après restart et le marqueur persistant
`schema` incompatible avec le stockage `version`. La reprise R2 est posée sous
`20260824-121607-g4-k1-control-composite-mesh-subgrid-recovery-v1-r2`, puis
`VALIDATE_RUN_COMPOSITE_SUBGRID_V1_OK` a qualifié la capture existante. La
capture privée `20260824-131000-g4-k1-control-composite-mesh-v1-r2-run` a
ensuite obtenu quatre quadrants carrés `6 × 6`, `144/144` contacts et 121
positions uniques. Le delta de reprise
`20260824-155319-g4-k1-control-composite-mesh-recovery-v1` a aligné le biais
additif constant du post-traitement propriétaire, sans déformation locale ni
nouvelle mesure, puis persisté le profil `k1_p001_t055_r001_n11x11`. L'écart
maximal aligné vaut `0,043745029 mm`, sous la limite `0,05 mm`. Le profil
robuste `6 × 6` reste actif ; l'état final est `standby`, cibles zéro, axes non
référencés, Z `−0,04 mm`, stockage `ok` et deux CFS connectés. La prochaine
mission historique était une comparaison contrôlée de premières couches
`6 × 6` contre `11 × 11`. Le mode Précision ne devient pas visible dans l'UI
avant un gain observable sur toute la zone utile.

La première comparaison de couche
`G4-K1-CONTROL-COMPOSITE-FIRST-LAYER-COMPARISON-V1` est **close KO**. Elle a
gardé à tort l'ancien offset Orca `+0,27 mm`, soit environ `0,31 mm` au-dessus du
Z accepté `−0,04 mm`. Le passage robuste a terminé avec une couche trop haute ;
le composite n'a pas été lancé. Les deux G-code et leurs miniatures ont été
supprimés de la K1. `printer.cfg` conserve le hash exact `f88d6b52…`, le profil
robuste est actif, les cibles sont à zéro et les axes libérés. Ne jamais rejouer
V1. Un successeur doit d'abord prouver le Z absolu sur un motif court.

La comparaison V2 a ensuite utilisé le profil composite et un Z temporaire
`−0,24 mm`, observé pendant l'impression mais non persisté. Elle montre un gain
clair sur une grande zone centrale et des défauts beaucoup plus graves dans
plusieurs bandes de bord. Le calcul avec le `bed_mesh.py` exact borne l'écart
bicubique/direct à `0,009877883 mm` : l'interpolation n'est pas la cause
principale. V2 est close avec gain partiel et KO de promotion UI. Le profil
physique reste une source immuable, le robuste reste le repli et le même motif
ne doit pas être rejoué sans correction. `MESH-EDITOR-OFFLINE-V1` est clos :
profil dérivé versionné, correction normalisée sur la surface bicubique
`31 × 31`, grille 2D, aperçu 3D, historique, gardes, rollback et exports
déterministes sont validés contre une fausse API locale. Aucun transport K1
n'existe dans le paquet. La mission physique suivante avait été
`MESH-EDGE-DIAGNOSTIC-V1` ; elle est maintenant suspendue après son premier
passage invalide sans débit. L'état distant final après l'impression V2 n'avait
pas été re-préflighté pendant l'audit ni pendant la gate hors ligne.

Le premier passage source de `MESH-EDGE-DIAGNOSTIC-V1` a ensuite chauffé et
déplacé la tête sans déposer de filament. Le G-code minimal ne résolvait aucun
outil CFS, ne chargeait pas et ne purgeait pas. La mention `T0` était une
hypothèse de Codex, pas un fait fourni par Thomas. Ce passage ne qualifie ni la
buse ni le mesh. Au dernier état observé, le robuste est actif, les cibles sont
à zéro et les axes sont libérés. La capture
`20260826-090956-mesh-edge-diagnostic-v1` a ensuite obtenu le rollback exact et
`VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK` : base `printer.cfg` exacte, profil
diagnostic et quatre G-code absents, robuste actif, runtime Z sûr et deux CFS
connectés. Aucun nouveau motif n'est permis avant une route CFS/slot fraîchement
résolue et une purge réellement visible.

Le 26 août 2026, Thomas a figé le contrat complet de nettoyage autonome,
démarrage, filament, changement, runout, pause, reprise et fin. Les autorités
canoniques sont `docs/25-contrat-cycle-impression-nettoyage-cfs-v1.md`,
`design/job-lifecycle-contract-v1.json`, ADR-016 et D-064. Le bon filament déjà
engagé doit être conservé ; la fin cible le conserve aussi sous réserve de
qualification physique. Le retrait devient le bouton séparé `Désengager et
nettoyer`. Aucun `T0`, capteur de débit, palpage de brosse ou delta thermique
universel ne peut être supposé. Ce gel est hors imprimante et n'autorise aucune
production.

`G4-K1-CONTROL-CFS-DYNAMIC-TEMP-ROUTING-V1` est désormais close hors
imprimante. ADR-020 choisit `minimal_separate_filament_owner` : ticket par
phase, cible avant le premier effet, route CFS/slot fraîche et consommable une
fois, températures distinctes de retrait/chargement/purge et six invariants
inchangés. La matrice obtient `25/25`. Le paquet n'a aucun transport K1,
`deployment_candidate=false` et n'autorise ni pose ni reprise physique. La
mission suivante `G4-K1-CONTROL-CFS-MINIMAL-OWNER-PROTOCOL-V1` a ensuite
cartographié les captures privées sans connexion K1. Elle est close en KO
borné : deux adresses répondent aux requêtes d'état, mais la seule route
d'effet est `T1A`, adresse 1, slot A. Retrait, coupe, purge isolée, B/C/D,
effets sur le second CFS, intégrité de trame, resynchronisation et exclusion du
propriétaire stock restent non prouvés. La liste appelable est vide, aucun
transport n'existe et les `25/25` scénarios qualifient seulement le refus sûr.
La branche canonique suivante est
`G4-K1-CONTROL-CFS-MINIMAL-OWNER-EVIDENCE-V1`, hors imprimante par défaut ;
toute connexion ou action physique exige une autorité fraîche distincte.

Cette gate de preuve est maintenant close hors imprimante. Un ancien journal
contient les deux requêtes locales `RETRUDE_PROCESS` de `T1A`, leurs réponses
d'état zéro, un timeout de 150 secondes et le passage du capteur local de
présent à libre. Le journal court est le préfixe exact du journal long : une
seule observation est comptée. Le CRC-8 public au polynôme `0x07` correspond à
la réponse capturée, mais la requête complète sur le fil reste absente. La
source publique de retrait utilise une autre table de commandes et ne peut pas
être substituée au binaire local. L'exclusion du propriétaire stock, B/C/D, le
second CFS, coupe, purge, arrêt et reprises après faute restent non prouvés.
`callable_messages=[]`, aucun transport ni candidat de pose. À cette clôture,
la gate suivante était `G4-K1-CONTROL-CFS-MINIMAL-OWNER-PASSIVE-CAPTURE-V1`,
avec revue et GO exact distincts avant toute connexion ou action physique.

Thomas a ensuite donné ce GO, puis a explicitement autorisé Codex à lancer une
fois le retrait officiel. La capture privée
`20260827-001616-g4-k1-control-cfs-minimal-owner-passive-capture-v1` est OK :
route fraîche `T1A`, macro `BOX_QUIT_MATERIAL` terminée, deux phases de retrait
réussies et premier CFS passé de `A` à aucun filament engagé. La K1 a demandé
`220 °C` mais n'a pas remis la cible à zéro à la fin. Une tentative locale
`M104%20S0` a été refusée comme commande inconnue malgré le retour HTTP `ok` ;
`TURN_OFF_HEATERS` a réellement ramené les cibles à zéro. Le capteur de la tête
reste actif : le segment après cutter reste présent. Les configurations sont
inchangées et l'état final est `standby`, CFS connecté, cibles zéro. Aucun
message série ne devient appelable. La prochaine branche proposée est
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-V1`, hors imprimante seulement : encadrer
la macro stock avec vérification d'état et arrêt garanti des chauffes.

Thomas a ensuite donné le GO exact de cette gate hors imprimante.
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-V1` est close OK sans connexion K1. Le
garde refuse avant effet une machine occupée, un état CFS incomplet, une
commande active ou une route ambiguë. Après une tentative unique de
`BOX_QUIT_MATERIAL`, il exige la fin stock, le slot libéré et la commande CFS
vide ; il demande ensuite une fois `TURN_OFF_HEATERS` et vérifie les deux cibles
à zéro. Un HTTP `ok` ne suffit jamais et aucun retrait n'est relancé.

Le paquet ne contient aucun transport ou candidat de pose. La prochaine branche
proposée est
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-LIVE-PREFLIGHT-V1` : lecture seule des
champs réels nécessaires au garde, sans G-code, chauffe, mouvement, retrait ou
fichier distant. Cette connexion exige un GO exact distinct ; un essai réel
ultérieur restera une autre gate.

Thomas a ensuite donné ce GO exact. Deux lectures live stables confirment
Klipper prêt, `standby`, `T1/T2` connectés, `t_command` vide, les cibles à zéro,
le segment après cutter encore présent et aucune route CFS engagée. Les trois
configurations sont inchangées ; aucun G-code, fichier distant, service ou effet
physique n'a été produit. Le premier collecteur avec `curl -sS` a signalé des
options incompatibles et n'est pas retenu ; la seconde capture utilise le curl
Creality exact.

La K1 n'expose aucun champ direct `stock_unload_state`, et `t_command` est resté
vide pendant le retrait historique. Le garde est corrigé pour qualifier la fin
par le retour sans erreur de la requête, la route réellement libérée,
`t_command` vide et les chauffes à zéro. L'état courant est
`BLOCKED_NO_ENGAGED_ROUTE`.

`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-OFFLINE-V1` est ensuite close OK
hors imprimante. ADR-026 sépare la forme K1 du garde : l'adaptateur extrait
seulement huit champs, traduit une route absente ou un second CFS déconnecté et
refuse plusieurs routes, les incohérences, les champs absents et les
températures invalides. Ses dix exemples sont synthétiques, sa matrice obtient
`10/10`, ses tests ciblés `17/17` et la suite complète exécute `429` tests dont
`426` verts et `3` ignorés connus. Aucun réseau, G-code, processus, accès K1 ou
candidat de pose n'existe. La prochaine branche proposée est
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-LIVE-READ-ONLY-V1` : une future
lecture fraîche et nettoyée, sans appel du chemin d'effet du garde. Cette
connexion n'est pas autorisée par la gate hors imprimante close.

Thomas a ensuite autorisé cette lecture seule. La capture privée
`20260827-110102-g4-k1-control-cfs-stock-unload-guard-adapter-live-read-only-v1`
est close OK : deux lectures stables, `T1/T2` connectés, aucune route engagée,
commande vide, cibles zéro et empreintes de configuration inchangées. `sn` et
`uuid` sont retirés avant l'adaptateur et tout champ nouveau est refusé. La
forme réelle `T3/T4.state = "None"` est désormais reconnue comme inactive ; les
autres valeurs inconnues restent fermées. Le garde n'est ni importé ni appelé,
les tests ciblés obtiennent `61/61` et la suite complète exécute `443` tests,
dont `440` verts et `3` ignorés connus. Aucun G-code, fichier distant, service
ou effet physique n'a lieu.

Thomas a ensuite autorisé `GOAL-P4-OFFLINE-CYCLE-CFS-V1` avec `$session-tas`.
Le transport simulé du garde est clos avec `13/13` scénarios : seules les deux
commandes déjà figées sont acceptées, chacune au plus une fois, et tout effet
incertain reste non rejouable. Le cycle complet hors imprimante est clos avec
`27/27` scénarios canoniques et `20/20` tests ciblés du moteur. Il couvre les
états filament, le démarrage, le nettoyage, les changements, le runout, la
pause, la reprise, l'annulation, le reboot, la fin et l'action séparée de
désengagement. Le plan futur épingle trois sources, trois destinations, les
sauvegardes, le rollback et sept tranches humaines, mais contient zéro commande
distante et aucun connecteur réel. Aucune connexion K1, G-code, chauffe,
mouvement, fichier distant ou action physique n'a eu lieu. La suite complète
exécute `476` tests, dont `473` verts et `3` ignorés connus. Le prochain Goal
unique est `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1`, qui exige une autorité de
connexion séparée et ne permettra aucun effet.

Thomas a ensuite lancé ce Goal 2 complet avec `$session-tas`. La capture privée
`20260827-142853-goal-p4-k1-read-only-qualification-v1` contient deux lectures
nettoyées sur la K1 avant leur retour local. La forme est stable, les requêtes
d'état prennent `199,212 ms` et `235,525 ms` sous un plafond de `5 s`, Klippy
est prêt, les chauffes sont à zéro, les axes sont libérés, `T1/T2` sont
connectés, aucune route n'est engagée et le Z accepté reste à `−0,04 mm`. Les
empreintes des configurations et composants correspondent aux versions revues
et restent identiques avant/après. Aucun G-code, fichier distant, restart,
chauffe, mouvement, appel du garde ou reconnect CFS n'a eu lieu.

Le Goal 2 est clos avec `CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT` : le mesh actif
`default` est une matrice `6 × 6` différente du profil robuste requis
`k1_p001_t055_r001_n06x06`, même si ce dernier existe encore avec son empreinte
attendue. Le collecteur `GET`, le délai, le nettoyage, la traduction et la
règle d'invalidation du mapping sont qualifiés hors effet. Une reconnexion
brève qui revient au même état n'est pas détectable par deux sondages ; le futur
composant Moonraker devra fournir une époque de connexion par notification. La
prochaine action n'est pas le Goal 3 complet : Thomas doit être présent pour une
gate distincte qui vérifie puis charge seulement le profil robuste, avec
rollback au premier écart et sans impression. Les tests ciblés Goal 2 et cycle
obtiennent `32/32`, la suite complète exécute `488` tests dont `485` verts et
`3` ignorés connus, et les `29` scripts PowerShell se relisent sans erreur.

Thomas authorised V1, but the mandatory preflight proved that `logrotate` was
absent. V1 is closed and must never be deployed. Thomas later authorised V2;
real attempts reached a working tunnel-only Mainsail, then proved that Mainsail
`v2.18.2` cannot satisfy the Moonraker-account gate. Every V2 attempt was
rolled back and V2 is closed. V3 keeps the bounded BusyBox syslog, moves the
account boundary to nginx, and is installed. The separate PATHS-V1 package was
created only after its first exact GO arrived, so that GO was not consumed: G4
requires exact reviewed files, commands, backups and rollback before approval.
Thomas then renewed the exact GO after review. PATHS-V1 was deployed under
capture `20260821-111001-g4-control-foundation-v3-paths-v1` and independently
validated. No further printer mutation is authorised; classified read-only
observation remains allowed. The retained observation covered the manual normal
print and its local-monitor gap through the persistent Klipper log, then ended
with `VALIDATE_PATHS_V1_OK`. The runtime preflight correction adds the required
Python stdin marker to two remote commands; it changes no runtime payload, but
G4 still requires a renewed exact GO before deployment because the reviewed
command changed after the first approval. The later renewed GO was consumed by
capture `20260821-213732-g4-k1-control-z-mesh-runtime-v1`. The runtime rejected
its empty store, and the first rollback check raced CFS reconnection. The runtime
was corrected offline, then a further renewed GO was consumed by capture
`20260821-224828-g4-k1-control-z-mesh-runtime-v1`. The exact Creality parser
proved that embedded digits truncate every intended `K1_*` command to `K1`, so
the delayed state load never ran. The rollback then raced Creality's delayed
`CXSAVE_CONFIG`; a bounded exact-backup restoration completed it without another
restart. The runtime is absent again, the exact baseline hash and full health
are restored. A third renewed GO was consumed by capture
`20260822-004338-g4-k1-control-z-mesh-runtime-v1`. The `KCTRL_*` boot command
ran, but Creality's `shlex` layer stripped the single quotes from
`VALUE='empty'`; `ast.literal_eval` then rejected the bare name. The strengthened
rollback completed automatically and the exact baseline and full health were
confirmed again. All runtime text assignments now keep an inner quoted Python
literal, and the deployer preserves a not-ready snapshot. No further printer
mutation is authorised until this changed package receives a new exact GO.
Thomas then renewed the exact GO. Capture
`20260822-011022-g4-k1-control-z-mesh-runtime-v1` obtained the fresh preflight,
`DEPLOY_Z_MESH_RUNTIME_V1_OK` and `VALIDATE_Z_MESH_RUNTIME_V1_OK`. A delayed
Creality `CXSAVE_CONFIG` changed only indentation in generated `bed_mesh` and
`auto_addr` blocks; the exact diff and normalized comparison proved no value or
include change, so the validator pins both reviewed hashes instead of rewriting
the printer. The runtime is retained with `ready=1`, `integrity=empty`,
`accepted_z_valid=0` and `low_moves_armed=0`. No further printer mutation,
including calibration, is authorised by the completed runtime gate.

Le candidat séparé `G4-K1-CONTROL-CALIBRATION-PATH-V1` est maintenant préparé
hors imprimante. Il ajoute un overlay original pour évaluer le premier Z par
une descente centrale bornée, sans extrusion et sans valeur Z cachée. Sa pose
prévue ne ferait qu'ajouter l'include et recharger l'hôte Klipper ; elle ne
chauffe, ne home, ne bouge et n'écrit aucun état. Le nom envoyé sans le préfixe
`GO` a sélectionné cette mission de préparation mais n'autorise aucune mutation.
Une pose exige encore la revue du commit figé puis le GO exact
`GO G4-K1-CONTROL-CALIBRATION-PATH-V1`. La première calibration restera une
gate différente, `G4-K1-CONTROL-FIRST-CALIBRATION-V1`.

Thomas a ensuite envoyé le GO exact. Le premier préflight a joint la K1 puis a
échoué avant toute écriture parce que le candidat Base64 dépassait la ligne de
commande acceptée par Dropbear. Le parse Jinja passe désormais par stdin, sans
fichier distant. Le préflight corrigé de la capture `20260822-113503` est vert
et confirme la base exacte, le runtime vide, les chauffes à zéro, deux CFS et
l'overlay absent. Aucun déploiement n'a été lancé. La commande revue ayant
changé après le GO consommé, la pose exige un nouveau GO exact sur le commit
corrigé.

Thomas a renouvelé ce GO. La capture
`20260822-115608-g4-k1-control-calibration-path-v1` a passé le préflight, créé le
backup exact, posé l'overlay et envoyé le `RESTART`. La validation a interrogé
le socket Klipper pendant sa transition et le premier `RESTART` du rollback a
rencontré le même état. L'action `Rollback` reprise sur le backup exact a obtenu
`ROLLBACK_CALIBRATION_PATH_V1_OK`, puis le préflight final a prouvé la base
exacte, l'overlay absent, les axes non référencés, les chauffes à zéro, le
runtime vide, deux CFS et la fondation conformes. Aucun mouvement, homing,
chauffage, mesh ou état Z n'a eu lieu. Le déployeur attend maintenant le socket
de façon bornée après pose et avant le restart du rollback. Cette commande ayant
changé après le GO consommé, aucune nouvelle pose n'est autorisée avant un
nouveau GO exact. Le préflight réel du déployeur corrigé est vert en lecture
seule.

Thomas a renouvelé une dernière fois le GO. La capture
`20260822-124207-g4-k1-control-calibration-path-v1` a obtenu le préflight frais,
`DEPLOY_CALIBRATION_PATH_V1_OK` puis
`VALIDATE_CALIBRATION_PATH_V1_OK`. L'overlay et son unique include sont retenus
avec leurs empreintes exactes. Le runtime reste `ready=1`/`empty`, les axes sont
non référencés, les chauffes demandées sont à zéro, deux CFS et la fondation sont
conformes, et la garde à vide refuse sans changement de position, origine Z ou
cible. Aucun chauffage, homing, mouvement, extrusion, mesh, réglage ou
enregistrement Z n'a été exécuté. `CALIBRATION-PATH-V1` est clos ; aucune autre
mutation n'est autorisée. La gate suivante
`G4-K1-CONTROL-FIRST-CALIBRATION-V1` a ensuite été préparée hors imprimante :
plaque `PEI_TEXTURED_A`, `55/140 °C`, stabilisation `200 s`, nettoyage stock
borné à `180 °C`, deux meshes `6 × 6` Lagrange, seuil `0,025 mm`, aucun rerun
automatique et chemin Z par checkpoints.

Thomas a ensuite envoyé le GO exact sur le commit figé. La capture
`20260822-140602-g4-k1-control-first-calibration-v1` a obtenu le préflight, le
backup vérifié, `PREPARE_FIRST_CALIBRATION_V1_OK` et
`MESH1_FIRST_CALIBRATION_V1_OK`. Le second mesh a été mesuré une seule fois puis
refusé : écart maximal `0,062125 mm` pour un seuil de `0,025 mm` et moyenne
`0,018049 mm` sur 36 points. Le pilote a coupé les chauffes et s'est arrêté sans
troisième mesh, persistance, session Z ou écriture Z. Le contrôle final en
lecture seule a confirmé la base persistante exacte, le stockage Z absent,
`standby` et les cibles à zéro avant de s'arrêter, comme attendu, sur les axes
encore référencés. Ce GO est consommé et n'autorise aucun rerun.

L'analyse hors imprimante a ensuite préparé
`G4-K1-CONTROL-FIRST-CALIBRATION-V2`. Thomas a donné le GO exact. La capture
`20260822-160948-g4-k1-control-first-calibration-v2` a exécuté exactement six
meshes à `55/140 °C`, `200 s`, `6 × 6` Lagrange. Les deux médianes indépendantes
sont acceptées : moyenne absolue `0,010788694 mm`, RMS `0,013996452 mm` et
maximum `0,034352 mm`. Le profil robuste `k1_p001_t055_r001_n06x06` est
persisté ; aucun septième passage n'a eu lieu.

Le premier commit a rencontré un faux KO du pilote : l'endpoint `update_mesh`
a chargé la matrice robuste sans redémarrer Klipper et a conservé le homing
`xyz`. Le diff exact ne contenait que le profil transitoire attendu. Une reprise
bornée a revérifié backup, hashes, matrice et runtime vide, puis exécuté la
commande de commit déjà revue. Le pilote attend désormais le comportement réel
avec un test dédié.

Thomas a repris le chemin Z devant la K1 sous le même GO V2. Une pile de dix
épaisseurs a évalué la cale papier à `0,09 mm`. Les pas provisoires de
`−0,01 mm` ont trouvé une friction nette à `−0,05 mm`; le retour d'un pas à
`−0,04 mm` a rendu la cale libre et vise le jeu final de `0,10 mm`. Thomas a
confirmé ce constat. Le chemin a parqué la buse, enregistré atomiquement
`−0,04 mm` et coupé les chauffes. La validation finale est verte : stockage
`ok`, `accepted_z_valid=1`, `session_active=0`, chemin `committed`, profil
robuste présent, `standby`, cibles zéro, deux CFS et fondation conformes.

Le premier `Validate` a rencontré un faux KO local : il cherchait l'en-tête
persistant non commenté, alors que Klipper génère `#*# [bed_mesh ...]`. Le
contrôle corrigé et testé reconnaît ce format réel ; la relance en lecture seule
a obtenu `VALIDATE_FIRST_CALIBRATION_V2_OK`. FIRST-CALIBRATION-V2 est close et
son GO ne couvre aucun rerun, la pose UI ou la production.

Le candidat séparé `G4-K1-CONTROL-CALIBRATION-UI-V1` est préparé hors
imprimante. Il ajoute un composant au Moonraker épinglé et une page statique
`/k1-control/` pour choisir plaque, températures, stabilisation, matrice,
interpolation et seed Z, puis enregistrer, annuler et restaurer sans console.
Le flux robuste reste côté serveur, la chauffe et la stabilisation sont
annulables, et un backup complet peut restaurer `printer.cfg` et l'état Z. Sa
pose future redémarrerait Moonraker seulement et ne lancerait aucune
calibration. Elle exige une revue figée puis son propre GO exact séparé.

La revue post-calibration a corrigé le candidat UI sans toucher à la K1 : le
préflight et le contrôleur acceptent maintenant uniquement les phases fermées
`idle`, `committed` et `cancelled`; le transport Moonraker utilise le `curl`
Creality sans options incompatibles et encode les espaces par `+`. Le préflight
compile et importe en mémoire les deux sources avec le Python Moonraker `3.8.2`
exact, par stdin et sans fichier distant. Le déployeur est lui-même épinglé dans
le manifeste. Le préflight réel en lecture seule a obtenu
`PREFLIGHT_CALIBRATION_UI_V1_OK`. Aucune pose ni aucun restart n'a eu lieu ; le
GO exact UI reste obligatoire.

Thomas a ensuite donné le GO exact. La capture
`20260822-192821-g4-k1-control-calibration-ui-v1` a obtenu le préflight vert et
le backup exact, puis le premier transfert a échoué avant toute pose :
l'OpenSSH Windows récent a tenté SFTP alors que Dropbear ne fournit pas
`/usr/libexec/sftp-server`. Le rollback automatique a retiré les chemins
candidats, restauré la base exacte, redémarré seulement Moonraker et le
préflight final a de nouveau obtenu `PREFLIGHT_CALIBRATION_UI_V1_OK`. Aucun
chauffage, homing, mouvement, mesh ou Z n'a eu lieu. Le transport utilise
désormais le SCP historique explicite `scp -O` et le rollback nettoie aussi le
staging exact. Le déployeur et son empreinte ayant changé après le GO consommé,
le paquet corrigé a obtenu un nouveau `PREFLIGHT_CALIBRATION_UI_V1_OK` en
lecture seule. Aucune nouvelle pose n'est autorisée avant un nouveau GO exact
`GO G4-K1-CONTROL-CALIBRATION-UI-V1` sur le commit corrigé.

Thomas a renouvelé ce GO. La capture
`20260822-202014-g4-k1-control-calibration-ui-v1` a obtenu le préflight, la pose
et les validations scriptées vertes. La validation navigateur a cependant
révélé deux défauts non couverts : le service worker Mainsail intercepte la
route sous l'origine `127.0.0.1:4409`, et le dossier statique créé en `0700`
provoque `403 Forbidden` sous l'origine isolée `localhost:4409`. Le syslog a
confirmé `Permission denied`. Le rollback exact et le préflight final sont
verts ; l'UI et son composant sont de nouveau absents, la K1 est revenue à sa
base sûre. Hors imprimante, le déployeur applique désormais `chmod 0755` et
valide le mode `755`; un lanceur dédié ouvre l'origine `localhost` sans nouveau
port ni service, suivant ADR-009. Ce paquet changé exige encore un nouveau GO
exact avant toute pose.

L'audit de reprise navigateur a ensuite trouvé deux défauts supplémentaires
hors imprimante : le seed accepté n'était pas réinjecté dans le formulaire et,
après rechargement entre mesh et Z, la confirmation « plateau libre » redevenait
fausse tout en restant désactivée. Le composant expose désormais le Z accepté,
le formulaire reprend l'état serveur exact et les confirmations physiques
restent accessibles et obligatoires avant le Z. Le candidat séparé
`G4-K1-CONTROL-CALIBRATION-UI-CAMPAIGN-V1` fixe le protocole de preuve : six
meshes physiques pour chacun des niveaux `9 × 9`, `11 × 11`, `15 × 15` et
`6 × 6`, puis parcours Z et acceptation sur le niveau rapide uniquement depuis
l'écran, sans console ni commande Codex, sans septième passage par niveau ni
rerun automatique. L'UI doit d'abord
être posée, validée et rendue dans le vrai navigateur ; la campagne exigera
ensuite son propre GO exact.

La préparation production en lecture seule a ensuite capturé directement les
profils Orca actuellement sélectionnés sous OrcaSlicer `2.4.2`. La machine
active garde son ancien départ, le changement de filament vide et le processus
actif garde le post-traitement `--start-z-offset 0.27`. Le blocage « profil actif
non capturé » est levé. Sur la K1, `box.state` et `box.t_command` sont exposés et
le traceur passif les suit désormais, mais les commandes de départ/refill CFS
restent dans le module compilé. Aucun propriétaire de température, wrapper
`KCTRL_JOB_*`, changement Orca ou paquet de bascule production n'est encore
installé ou autorisé.

Thomas a renouvelé le GO exact UI. La capture
`20260822-211633-g4-k1-control-calibration-ui-v1` a obtenu le préflight frais,
`DEPLOY_CALIBRATION_UI_V1_OK` et deux
`VALIDATE_CALIBRATION_UI_V1_OK`. Le dossier statique est confirmé en `0755`,
l'API est `idle`, le Z accepté vaut `−0,04 mm`, la K1 reste `standby`, les
cibles sont à zéro et les mouvements bas sont désarmés. Seul Moonraker a été
redémarré ; aucune chauffe, référence, mesure, extrusion, commande CFS,
impression ou écriture Z n'a eu lieu. L'origine `localhost` attend maintenant
l'authentification humaine. Le vrai rendu Chrome a ensuite confirmé l'API, les
paramètres `PEI_TEXTURED_A`, `55/140 °C`, `200 s`, `6 × 6` Lagrange et le seed
`−0,04 mm`. Un rechargement complet a restauré les mêmes valeurs depuis le
serveur tout en laissant les confirmations physiques décochées. Cette gate est
close. Son GO est consommé et ne couvre pas la campagne physique séparée.

Thomas a ensuite relevé que l'interface installée s'arrêtait à `6 × 6`, alors
que le contrat produit prévoyait aussi `9 × 9`, `11 × 11` et `15 × 15`. Après
son GO exact, le delta séparé `G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1` a été
posé sous la capture `20260822-222005-g4-k1-control-calibration-ui-matrix-v1`.
Le préflight, le déploiement et deux validations indépendantes ont obtenu leurs
marqueurs OK. Seuls le core Moonraker et deux fichiers statiques ont été
remplacés après backup exact, puis le Moonraker dédié a été redémarré. Aucune
chauffe, référence, mesure, extrusion, commande CFS, impression ou écriture Z
n'a eu lieu. Le vrai rendu Chrome authentifié a confirmé `6/9/11/15`, la
bascule automatique vers le bicubique et le blocage de Lagrange pour `9/11/15`.
Un rechargement complet a restauré `6 × 6` Lagrange et les confirmations
physiques décochées. Cette gate est close et son GO est consommé.

Le préflight strictement en lecture seule de la campagne suivante est vert sous
la capture `20260822-222450-g4-k1-control-calibration-ui-campaign-v1`. Il
confirme l'UI inactive, la K1 au repos, les cibles à zéro, le Z accepté et le
profil rapide présents, ainsi que l'absence attendue des profils `9/11/15`. Le
GO de campagne envoyé avant la correction de matrice n'a pas été consommé. Le
goal global donné ensuite autorise toutefois explicitement Codex à poursuivre
les corrections nécessaires et la campagne jusqu'au vert sans redemander de
GO.

La première tentative écran `9 × 9` a ensuite révélé que la case volontaire
`replace_existing` restait cochée après une annulation à `0/6`; une seconde
reprise l'a réutilisée malgré l'instruction humaine. Les deux tentatives ont été
annulées avant toute mesure, dont la seconde par l'action de sécurité UI de
Codex. Les contrôles réels ont confirmé les chauffes coupées, le profil `6 × 6`
et le Z `−0,04 mm` intacts. Le correctif séparé
`G4-K1-CONTROL-CALIBRATION-UI-RETRY-SAFETY-V1` remet une seule fois
`replace_existing=false` et `plate_clear=false` après une reprise incomplète,
sans supprimer la possibilité d'un remplacement volontaire. Il ne remplacerait
que `app.js`, sans restart ni action physique. Ses 179 tests et son préflight
réel `20260822-231240-g4-k1-control-calibration-ui-retry-safety-v1` sont verts.
L'autorité globale explicite du goal couvre cette correction nécessaire sans
nouveau GO. Le même identifiant a ensuite obtenu
`DEPLOY_CALIBRATION_UI_RETRY_SAFETY_V1_OK` et deux
`VALIDATE_CALIBRATION_UI_RETRY_SAFETY_V1_OK`. Seul `app.js` a été remplacé après
backup exact, sans restart, chauffe, homing, mouvement, mesure ou Z. Le rendu
réel attend l'authentification humaine sur le tunnel temporaire neuf `4410`,
créé pour éviter le cache Mainsail de l'origine `4409`. La campagne ne reprend
pas avant la preuve des deux cases décochées sur ce vrai rendu.

Le tunnel `4410` a ensuite été recréé avec un seul processus connecté et les
empreintes distantes prouvent que l'interface corrigée est toujours présente.
Le préflight de campagne rejetait à tort l'état sûr `cancelled` laissé à `0/6`.
Il accepte désormais uniquement un départ `idle` sans backup ou cette reprise
bornée à zéro mesure avec backup ; une annulation après le premier mesh reste
un KO. Le test ciblé et le préflight réel de la capture
`20260822-233717-g4-k1-control-calibration-ui-campaign-v1` sont verts. À ce stade
historique, l'action physique suivante était le rendu des cases décochées puis
le lancement écran du niveau `9 × 9`.

Thomas a lancé ce niveau correctement. La chauffe, les `200 s`, le nettoyage et
le homing ont réussi, puis la première grille s'est arrêtée à `1/6` avec
`Le mesh ne contient pas le nombre de lignes attendu.` Aucune matrice exploitable
n'a été stockée. Les chauffes sont à zéro, le Z `−0,04 mm`, le profil `6 × 6`,
le stockage et le chemin restent conformes. L'audit du firmware exact montre
que le wrapper propriétaire `prtouch_v3` utilise le `[bed_mesh] probe_count`
chargé au démarrage, resté à `6,6`, plutôt que le paramètre dynamique amont.

ADR-011 et
`G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-MATRIX-V1` ajoutent un adaptateur séparé
qui commute atomiquement cette seule valeur après backup et avant chauffe,
redémarre Klipper, relit la valeur et les gardes, puis restaure la valeur
précédente après coupure des chauffes. Sa pose ne modifie pas `printer.cfg` et
redémarre seulement le Moonraker dédié. La capture
`20260823-001724-g4-k1-control-calibration-ui-prtouch-matrix-v1` a obtenu
`DEPLOY_CALIBRATION_UI_PRTOUCH_MATRIX_V1_OK` et deux validations vertes.
L'essai vide a ensuite été restauré exactement : phase `rolled_back`, backup
reconnu, `printer.cfg` de base, Z `−0,04 mm`, profil `6 × 6`, chauffes et runtime
conformes.

Le correctif statique séparé `PRTOUCH-PRESETS-V1` retire le choix `4 × 4`
inexécutable et conserve `3/5/6/9/11/15`. Son premier transfert a rencontré un
bug local de guillemets dans la validation et a restauré automatiquement les
deux fichiers exacts. Après correction, la capture
`20260823-003755-g4-k1-control-calibration-ui-prtouch-presets-v1` a obtenu le
déploiement et deux validations vertes, sans restart ni action physique. La
suite complète compte 191 tests verts, 3 ignorés connus. Le préflight de reprise
`20260823-002500-g4-k1-control-calibration-ui-campaign-v1` est vert ; il attend
le nouveau départ écran `9 × 9` avec une confirmation fraîche de plateau libre.

Thomas a relancé ce départ. Le composant V1 a correctement écrit `9,9`, mais a
laissé l'algorithme persistant `lagrange`. Klipper a donc refusé son démarrage
avec XS3002 avant toute chauffe, homing ou mesure. La garde bornée a restauré
automatiquement `6,6 + lagrange` ; Klipper est prêt, les chauffes sont à zéro,
le Z `−0,04 mm`, le profil rapide et les deux CFS sont intacts. Le paquet séparé
`G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-BED-MESH-V2` remplace seulement le
composant déjà installé et commute désormais le couple exact. Sa première pose
a révélé après coup une lacune de validation : sur la configuration réelle,
`lagrange` est implicite et la ligne `algorithm` est absente ; le composant était
donc listé dans `failed_components` malgré les anciens marqueurs verts. Aucun
mouvement ni chauffage n'a eu lieu. La révision corrigée préserve exactement
cette absence, insère `bicubic` seulement pendant `9/11/15` et refuse désormais
un composant Moonraker échoué. La capture
`20260823-012755-g4-k1-control-calibration-ui-prtouch-bed-mesh-v2-r2` a obtenu le
préflight, le déploiement et deux validations vertes ; `server/info` confirme
`failed_components=[]` et `warnings=[]`. Le préflight complet
`20260823-013151-g4-k1-control-calibration-ui-campaign-v1` est vert. La prochaine
action est le nouveau départ écran `9 × 9` avec confirmation fraîche du plateau
libre.

Thomas a relancé ce départ sous la campagne
`20260823-021858-540-calibration-ui-v1`. Le premier mesh a atteint exactement
`g29_cnt=36`, puis `prtouch_v2_wrapper.py` a levé `IndexError: list index out of
range` avant le point 37. Le message applicatif sur le nombre de lignes était
donc une conséquence de la matrice incomplète, pas la cause. L'arrêt automatique
a coupé les chauffes et le rollback API a restauré un état sûr : `standby`,
cibles zéro, axes non référencés, profil robuste `6 × 6` et Z `−0,04 mm`
inchangés. Le XS3002 `nozzle_mcu` observé ensuite appartient au restart de
restauration ; Klipper a récupéré et il n'a pas causé l'arrêt du mesh.

La configuration usine exacte expose seulement trente-six paires
`tri_min_hold_1..36` / `tri_max_hold_1..36`. L'ADR-012 remplace donc l'hypothèse
des grandes matrices : K1 Control doit proposer uniquement `6 × 6` Lagrange et
exécuter un seul mesh quotidien. Les six passages de FIRST-CALIBRATION-V2
restent la qualification scientifique initiale déjà close. Le contournement
communautaire par `pr_version: 1` et retrait des tables est rejeté à cause de la
perte des compensations et d'un retour de démarrage bloqué après coupure.

Les packages core, matrice, retry-safety, adaptateur, presets, campagne et la
preuve composite bornée ont été corrigés hors imprimante. La suite locale compte
224 tests verts et 3 ignorés connus ; les scripts PowerShell se parsèrent
correctement et `git diff --check` est vert. Les corrections
PRTOUCH-BED-MESH-V2, MATRIX-V1, RETRY-SAFETY-V1 et PRTOUCH-PRESETS-V1 ont
ensuite été posées ou reconnues déjà présentes puis validées séparément, avec
les backups et restarts strictement prévus et aucune action physique. La
campagne CAMPAIGN-V1 a ensuite réussi sous la capture
`20260823-171803-g4-k1-control-calibration-ui-campaign-v1`, avec un mesh
`6 × 6`, le parcours Z et la validation finale. NAVIGATION-V1-R2 est maintenant
posée et validée dans le vrai navigateur ; le profil composite `11 × 11` est
qualifié techniquement. La comparaison V2 prouve un gain central mais refuse
son exposition à cause de défauts de bord. L'éditeur de profil dérivé hors
ligne est maintenant validé ; la qualification physique d'une correction
locale reste à faire.

Thomas demande que chaque prochaine reprise commence par un état explicite de
l'autonomie, sans confondre le runtime installé avec une interface terminée :

- **autonomie calibration quotidienne standard** : atteinte ; la campagne
  physique est complète et le vrai écran corrigé est compréhensible sans
  console ni traduction Codex ;
- **autonomie d'édition hors ligne d'un profil dérivé** : atteinte ; création,
  correction, historique, restauration et export sont utilisables dans le
  laboratoire local ;
- **autonomie du mode Précision installé** : pas encore atteinte ; le composite
  reste caché après son KO de bord et exige encore diagnostic physique, pose,
  qualification et rollback depuis K1 Control ;
- **autonomie production** : pas encore atteinte ; elle exige en plus la bascule
  atomique Orca/`START_PRINT`, le retrait prouvé du `+0,27 mm`, la propriété des
  températures CFS et la validation G5 sans intervention Codex.

Au début de la prochaine session, l'agent doit rappeler ces quatre statuts,
indiquer la prochaine gate unique et expliquer ce qu'elle rendra autonome. Il
ne doit jamais annoncer « interface prête » sur la seule présence de Mainsail
ou des macros `KCTRL_*`.

Authority order:

1. an explicit decision from Thomas;
2. this repository's `GATES.md`, `STATE.md`, `DECISIONS.md` and current handoff;
3. observed machine state, captured files, logs and checksums;
4. original scripts, tests and documented results in this repository;
5. external documentation, which must not silently override evidence from the exact machine revision.

When instructions conflict, fail closed and report the conflict.

## Autorité par objectif — décision de Thomas du 24 août 2026

Un Goal actif ou une mission clairement décrite autorise Codex à exécuter de
bout en bout les actions normalement nécessaires dans ce périmètre. Aucune
phrase `GO ...` exacte, aucun identifiant de gate recopié par Thomas et aucun
renouvellement après une correction revue et testée ne sont requis. Une formule
générale comme « tu as les autorisations » confirme le périmètre actif déjà
décrit ; elle ne crée pas un périmètre futur ou implicite.

Les identifiants `G4-*` restent des contrôles techniques internes. Codex les
fournit aux scripts, vérifie l'état frais, le backup, les empreintes, le
write-set, la validation et le rollback. Une action physique n'est couverte que
si l'objectif actif la décrit ; une donnée non observable à distance, comme un
plateau réellement libre, peut encore nécessiter une confirmation factuelle.

Une instruction plus récente et plus restrictive comme « stop », « lecture
seule » ou « ne touche pas à l'imprimante » prime. Les dialogues d'approbation
imposés techniquement par la plateforme ne peuvent pas être supprimés par le
dépôt. Cette section remplace les anciennes règles normatives `ATTENDRE_GO` ou
de renouvellement littéral pour une étape déjà comprise dans l'objectif actif ;
leurs mentions historiques restent seulement des faits sur les campagnes
passées.

## Hard prohibitions during P0/P1

Until a clear mission or active Goal covers a named change, an agent must not:

- write, create, replace, rename or delete any file on the printer;
- install or update a package, helper script, service, firmware or dependency;
- run a firmware downgrade or recovery flash;
- restart, stop, kill, enable or disable any process or service;
- reboot or power-cycle the printer;
- remount a filesystem or change permissions, ownership or links;
- run remote commands using output redirection, `tee`, `sed -i`, `rm`, `mv`, `cp`, `chmod`, `chown`, `ln`, `mount`, package managers or an installer;
- upload a file to the printer through SSH, SCP, Moonraker, Creality APIs or another path;
- modify `printer.cfg`, included configuration, `START_PRINT`, homing, levelling or CFS macros;
- launch a print, extrusion, heater command, movement or calibration on its own initiative;
- persist an SSH key or credential on the printer;
- commit raw captures, backups, credentials, private network data, cloud identifiers, serial numbers or unreviewed vendor files.

A command being reversible in theory does not make it authorised.

## Allowed work during P0/P1

An agent may:

- inspect the local repository and create ignored local working directories;
- connect to the exact host supplied by Thomas;
- run read-only commands listed or classified in `docs/01-read-only-acquisition.md`;
- copy files **from the printer to the local workstation** without changing the remote source;
- calculate hashes locally or remotely using read-only tools;
- build an inventory, dependency map and macro call graph;
- sanitise local copies;
- commit only reviewed, redacted and legally publishable artefacts;
- update repository documentation, tests and the current handoff;
- stop immediately when a path, command or side effect is uncertain.

## SSH and secret handling

- Receive the printer target through an existing SSH config alias or a local environment variable such as `PRINTER_HOST`.
- Never write an IP address, password, token, SSID, MAC address or private hostname into tracked files.
- Do not echo credentials into a shell history, log, prompt or report.
- Prefer an already configured local SSH agent. Creating persistent access on the printer is outside P0/P1.
- Record the executed command class and result, not secret-bearing connection strings.

## Acquisition discipline

Before connecting:

1. read `STATE.md`, `GATES.md`, `HANDOFF.md` and `docs/01-read-only-acquisition.md`;
2. inspect `git status` and avoid mixing unrelated changes;
3. create a unique capture ID;
4. create raw storage only under ignored local paths;
5. verify that the printer is idle and that Thomas has completed the manual root step.

During acquisition:

- execute the smallest command set needed;
- log each command and whether it succeeded;
- avoid broad recursive reads until targeted paths are known;
- preserve timestamps and calculate checksums where practical;
- never infer that two similarly named files have the same role.

After acquisition:

- retain raw material outside Git;
- produce a redaction report;
- commit only sanitised outputs;
- update `STATE.md` and `HANDOFF.md` with facts, unknowns and the next safe action;
- open a draft pull request, review its publishable scope, then complete the normal GitHub integration without requiring another operator approval.

## Mutation discipline after G4

A future mutation task requires all of the following:

- exact scope and expected effect;
- source and destination paths;
- pre-change backup with checksum;
- reviewed diff;
- validation command or physical test;
- explicit rollback procedure;
- a clear mission or active Goal covering that named change, without any
  required literal phrase;
- one change class at a time.

Prefer original overlay files and wrappers over editing manufacturer files in place. Never combine root setup, helper installation, macro replacement, CFS changes and Z tuning into one deployment.

## Git discipline

### Permanent Git and GitHub authority for this repository

Thomas permanently delegates to Codex the complete Git and GitHub lifecycle for this project. Codex may inspect, branch, stage, commit, fetch, pull, rebase, merge, push, tag, create or update pull requests, mark them ready, merge them into `main`, and clean up merged mission branches without requesting another `GO` or human validation.

This standing authority applies to repository integration only. Gates G0–G5 and named deployment approvals continue to govern every action that can affect the printer. Platform-enforced safety controls also remain applicable.

Codex must still preserve unrelated work, worktrees and useful history; keep secrets, raw captures and unreviewed vendor material out of Git; avoid force-push or published-history rewrites unless Thomas explicitly names that exceptional operation; and verify both local and remote state after integration.

- Use a dedicated branch for each acquisition, experiment or deployment.
- Keep commits narrow and readable.
- Never commit secrets or unreviewed raw files, even temporarily.
- Do not rewrite published history or force-push without explicit instruction.
- Record vendor file hashes and paths; do not publish copied vendor content unless redistribution is clearly permitted.
- Update tests and documentation with each behaviour-changing patch.

## Reporting

Reports must distinguish:

- confirmed facts;
- measured results;
- hypotheses;
- unverified assumptions;
- changes made;
- changes not made;
- validation performed;
- remaining risks;
- next safe action.

Never report a printer change unless the remote state was actually modified and verified.
