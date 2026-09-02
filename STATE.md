# STATE

Last updated: 2026-09-02

Mise à jour prioritaire : le popup de correspondance des filaments n'avait pas
disparu, il n'avait jamais été appelé. Il appartient aux surfaces Creality —
écran tactile, application, page web — et dix-neuf impressions sur vingt sont
parties de Fluidd ou de Mainsail, qui ne l'ont pas. Le firmware analyse pourtant
chaque fichier tranché et propose déjà la correspondance : `types : PLA;PLA;PLA;PLA`,
`colors : #000000;#ffffff;#ff0000;#0080ff`, puis `T1A=T1A T1B=T1D T1C=T2A T1D=T2B`.
Il l'applique par `BOX_MODIFY_TN`, qui écrit `Tnn_map` dans `tn_data.json`.
Second verrou : Klipper ne publie pas cette table, donc `START_PRINT` ne pouvait
pas lire la réponse. Un objet en lecture seule, `kctrl_slot_map`, la publie
désormais ; `START_PRINT` résout l'emplacement par `map["T1A"]` et refuse de
démarrer si la table est illisible, au lieu de repartir sur `T1A` en silence.
La variable `kctrl_slot` est supprimée : une seule table, trois écrivains — le
popup, le rechargement automatique, `KCTRL_SLOT`. Vérifié à froid le 2 septembre,
aucune impression lancée. Voir doc 55 et ADR-056.

Mise à jour prioritaire : la chaîne de calibration est autonome et le plateau a
atteint son plancher mécanique. Deux commandes suffisent désormais et Thomas les
lance seul depuis un panneau Mainsail dédié : `KCTRL_BED_SCREWS` mesure le plan
en vingt-cinq contacts et sort la correction de chaque vis en huitièmes de tour,
`KCTRL_MESH_CALIBRATE` acquiert le `11 × 11` en quatre quadrants, fusionne,
normalise au point de palpage et recharge. La fusion vit dans un module Klipper,
`kctrl_mesh`, parce qu'elle demande du calcul matriciel et une écriture fichier
qu'une macro Jinja ne sait pas faire, et parce que `SAVE_CONFIG` est interdit sur
cette machine.

Le plateau est passé de `0,262` à `0,114 mm` d'inclinaison entre vis. Le reste
est un voile de la tôle mesuré trois fois à `0,15 mm`, invariant en amplitude
comme en forme : aucune vis ne le corrige, le réglage mécanique s'arrête là et le
maillage prend le relais. Les positions réelles des quatre vis ont été relevées
sur la machine et sont asymétriques. Voir ADR-047.

Risque matériel ouvert : une perte de pas Z de `2,78 mm` a été détectée et
refusée par le firmware pendant une acquisition. Non reproduite sur quatre tours
de contrôle, non corrigée, l'accès à l'entraînement demandant un outillage
indisponible. Non bloquant tant que le contrôle de fin de maillage la rattrape,
mais aucune protection équivalente n'existe pendant une impression. Voir ADR-048.

Mise à jour prioritaire : le maillage se retouche à la main, point par point,
depuis une page servie par l'imprimante sur le port `7130`. On clique un point,
puis `+` ou `−` le corrige d'un pas choisi entre 0,005 / 0,010 / 0,020 /
0,050 mm — maintenir la touche élargit le pas par multiples entiers. `Maj+clic`
étend la sélection à tout un rectangle, `Ctrl+clic` ajoute ou retire un point,
et `+` / `−` déplacent alors toute la sélection d'un coup, en tout ou rien : si
un point ne peut pas encaisser la correction, aucun ne bouge. Un bouton réduit
la sélection à sa couronne, la forme sous laquelle les défauts de bord se
présentent. Un double-clic ouvre la saisie pour taper la valeur, sur cette
cellule seulement. La surface se redessine, un bouton enregistre. Aucune
écriture ne passe par le serveur : il dépose la matrice et `KCTRL_MESH_APPLY`
valide, sauvegarde puis persiste, donc la mémoire de Klipper et `printer.cfg`
ne peuvent pas diverger. Chaque enregistrement laisse la matrice précédente
horodatée à côté de `printer.cfg`, et ce fichier est lui-même rejouable. Chaîne
vérifiée de bout en bout sur la machine, matrice finale identique bit à bit à
celle de la calibration. Une retouche par zone existe en parallèle pour les
défauts de bord. Voir ADR-050 et ADR-052.

Correctif retiré le soir même : le capteur de filament de tête n'est plus
réarmé au démarrage. `END_PRINT` retire le filament par le cutter, donc le
capteur se vide à chaque fin normale et déclenchait une pause runout après la
dernière couche, buse à `140 °C`, sans rien à reprendre. Ce que l'ADR-049
prenait pour un oubli du CFS est une précaution. La détection de fin de bobine
attend la reprise en main de `END_PRINT`. Règle retenue : armer une protection
sans posséder la séquence qui doit la désarmer transforme une fin normale en
incident. Voir ADR-051.

Mise à jour prioritaire : le chargement CFS du démarrage est corrigé. Une seule
poussée ne suffit pas. Le CFS épuise ses cinq tentatives internes, signale
`key836`, puis rend la main **sans faire échouer la séquence** ; la suite se
serait déroulée à vide et seul le garde de filament a arrêté l'impression. Pire,
l'erreur se verrouille : toute relance de `BOX_EXTRUDE_MATERIAL` est un no-op
muet tant que `BOX_ERROR_CLEAR` n'a pas été rejoué. Le pas matière fait
maintenant jusqu'à quatre tentatives, chacune précédée de son effacement
d'erreur, et se saute de lui-même dès que le capteur de tête voit du filament.
Le capteur de tête, que le CFS désactive pour charger et ne restaure jamais, est
réactivé après la purge : les impressions tournaient sans détection de fin de
bobine. Correctif vérifié au chargement, pas encore rejoué depuis un départ
complet. Voir ADR-049.

Verrou ajouté : la buse ne peut plus dépasser sa température de contact pendant
un palpage. `M104` et `M109` sont interceptés et refusent toute consigne
au-dessus du plafond tant que la fenêtre de palpage est ouverte, ce qui couvre
aussi les modules Creality compilés puisqu'ils passent par le dispatcher G-code.
Le contact est fixé à `100 °C` pour toutes les matières, jamais dérivé de la
température d'impression. Plafonner la consigne ne suffisait pas : une buse
laissée chaude par une purge manuelle ou un chargement avorté reste chaude
quand la fenêtre s'ouvre, et la trempe de vingt secondes ne la refroidit pas.
L'ouverture de la fenêtre coupe donc la chauffe et attend la descente réelle
sous le plafond avant d'autoriser le moindre contact. Relevé le 1er septembre
2026 avec la buse à `244 °C` et la consigne déjà revenue à zéro.

Mise à jour prioritaire : la voie CFS stock est rétablie et physiquement
qualifiée. Le blocage de trois semaines venait d'une garde applicative lisant
`box.cut_pos`, un champ qui ne reflète jamais le capteur du cutter, et dont le
retrait n'avait jamais été implémenté. Les trois inclusions propriétaires sont
passées en variante `disabled` dans `printer.cfg` et un cycle complet retrait
puis chargement a été exécuté et capturé : coupe réelle, rembobinage CFS,
chargement jusqu'à `box.T1.filament: A`, purge visible, filament inséré. La
machine peut produire. Voir ADR-044.

Règle contraignante ajoutée : aucune calibration ni palpage Z sans nettoyage
manuel de la buse confirmé par Thomas, ce qui impose le retrait préalable du
filament. Aucun substitut automatique n'existe. Voir ADR-045.

Défaut de température : la purge utilisait `flush_temp: 220` issu de
`Tn_extrude_temp` codé en dur dans `box.cfg`. **Traité le 2 septembre** : la clé
n'est pas modifiable à chaud, la valeur est descendue à `200` dans le fichier
avec redémarrage Klipper. Réserve PETG, il faut la remonter pour une session
PETG. Voir doc 54 et ADR-055.

Purge de démarrage, état arrêté le 2 septembre : les `140 mm` annoncés par
`box.cfg` ne sortent pas. La reconstitution du log donne de l'ordre de
`55 mm` réels pour la purge stock. `_KCTRL_PURGE_BALL` complète, valeur par
défaut `120 mm`, posée après `KCTRL_WAIT_FILAMENT` et après le `M109` pour
que rien ne pousse avant que le filament soit dans la tête. `200 mm` donnent
la boule qui se décroche, `180 mm` débordent du bac, `120 mm` est le plafond
retenu. Le rapport
automatique ne mesure rien d'utile — les routines box remettent l'axe
extrudeur à zéro — il le dit désormais au lieu d'afficher un chiffre faux.

Surface imprimable réelle : `X 0 → 300`, `Y 0 → 295`, `Z 0 → 300`. La limite
`Y` est appliquée ligne par ligne pendant l'impression dès qu'un CFS est
déclaré, et met l'impression en pause. Détail et conséquences dans l'ADR-054.

Mise à jour prioritaire : la purge de récupération de `30 mm` n'était pas une
purge stock. Les traces exactes donnent `140 mm` au chargement initial ; le
cycle actif lit maintenant les quantités Orca du G-code, y compris les matrices
de changement de couleur. Trois correctifs distants ont été posés et validés :
quantité de purge, conservation de la route `T1A` pendant l'accès cutter et
suppression de la réconciliation moteur lorsque le propriétaire direct possède
déjà cette route.

L'essai réel suivant est fermé avant retrait : `cut_pos` est resté à `0` à la
position stock `X38 Y304,5` puis jusqu'à la limite machine `Y307,5`. Aucune
rétraction n'a été envoyée. La K1 est revenue chauffes à zéro, axes libérés,
`T1A` chargé, deux capteurs filament actifs, mesh `11 × 11` et Z `−0,04 mm`.
Tout nouvel essai cutter est interdit avant une vérification mécanique à froid
du levier et de son capteur. Voir ADR-040.

Mise à jour prioritaire : la gate physique directe T1A est close KO avant tout
effet filament. Le préflight actif a refusé `auto_refill=1` après restart ; le
rollback a restauré le propriétaire désactivé, les chauffes zéro, les axes
libérés, le `11 × 11` et le Z `−0,04`. Aucune chauffe, trame CFS, coupe, purge,
avance ou rétraction n'a eu lieu ; le filament reste engagé selon les deux
capteurs. ADR-037 remplace la dérogation sans cutter : retrait = position cutter
puis coupe ; chargement = purge immédiate dans le bac, `3 à 4` allers-retours
de décrochage et preuve caméra. La suite reste hors imprimante.

Thomas a approuvé le 24 août 2026 l'autorité par objectif définie par D-054. Un
Goal actif ou une mission clairement décrite couvre désormais les actions
normalement nécessaires dans son périmètre ; aucun identifiant de gate ni `GO`
exact ne doit lui être redemandé. Les gates restent des preuves techniques
internes. Cette décision couvre la poursuite de la roadmap active, en commençant
par la correction sans action physique de NAVIGATION-V1. Les restrictions explicites
plus récentes et les confirmations de faits physiques restent prioritaires.

La campagne quotidienne `G4-K1-CONTROL-CALIBRATION-UI-CAMPAIGN-V1` est
maintenant réussie et validée sous la capture privée
`20260823-171803-g4-k1-control-calibration-ui-campaign-v1`. Thomas a lancé
depuis l'écran l'unique mesh `6 × 6` Lagrange à `55/140 °C` après `200 s`, puis
a parcouru les huit paliers Z de `5 mm` à `0,1 mm`, confirmé le jeu et enregistré
le Z. L'API termine en phase `accepted`, `mesh_index=1`, qualification
`single_firmware_bounded_mesh`, chemin Z `committed` et Z accepté `−0,04 mm`.

Le profil `k1_p001_t055_r001_n06x06` contient désormais les 36 valeurs du mesh
quotidien réellement mesuré. Le premier contrôle final a signalé un faux KO :
il exigeait encore le hash complet de `printer.cfg` antérieur à la campagne.
Le diff exact entre le backup et l'état final ne change que les six lignes de
points de ce profil. Le validateur vérifie désormais le hash du backup revu,
refuse tout changement hors de ces lignes et compare chaque valeur persistée à
la matrice privée acceptée. Il a obtenu
`CAPTURE_CALIBRATION_UI_LEVEL_OK level=supported` puis
`VALIDATE_CALIBRATION_UI_CAMPAIGN_V1_OK`. La K1 termine `standby`, cibles zéro,
profil transitoire absent, stockage Z `ok`, deux CFS connectés et
`failed_components=[]` / `warnings=[]`.

NAVIGATION-V1 a ensuite été posé sous la capture
`20260824-110936-g4-k1-control-calibration-ui-navigation-v1`. Le préflight, la
pose et la validation SSH indépendante sont verts ; seuls `app.js` et
`.theme/navi.json` ont changé après backup, sans restart ni action physique.
Le vrai navigateur a toutefois obtenu un KO : le bouton apparaît dans Mainsail,
mais `/k1-control/` reste intercepté par le `NavigationRoute` du service worker
et recharge Mainsail. La révision R2 est préparée et 232 tests sont verts. Elle
ne modifie pas `sw.js` : elle ajoute seulement l'alias symbolique original
`access-k1-control -> k1-control` et repointe le bouton vers le préfixe
`/access-k1-control/`, déjà présent dans la denylist exacte du worker. R2 a été
posée et validée sous
`20260824-112535-g4-k1-control-calibration-ui-navigation-v1-r2`. Le vrai Chrome
authentifié confirme le bouton `K1 Control`, son lien exact, le rendu de la page
et le texte « Mesh 6 × 6 et Z enregistrés. La calibration est terminée. »
Aucune nouvelle authentification ni action physique n'a eu lieu.

## Current phase

**P4 — Goals 1 et 2 clos ; meilleur profil observé `11 × 11` actif et
revérifié ; tous les profils actuels ont des défauts de bord ; aucun profil
actuel n'est qualifié robuste ; éditeur point par point disponible hors ligne ;
Goal 3 compte `2/7` exigences passées ; le run thermique R5 est clos KO après
une purge hors bac, sans décrochage de la boule, et une hauteur physique
incohérente ; la caméra locale est maintenant un capteur canonique ; pilote
caméra minimal et R3 validés à froid sans effet ; production volontairement
bloquée**

Le registre local
`packages/k1-control-v1/physical-slices-qualification-v1/` fixe désormais les
sept exigences physiques déjà prévues et la frontière du Goal 4. Son contrôle
retourne `GOAL3_LEDGER_OK_IN_PROGRESS`, avec `2/7` exigences closes. Il interdit
de déclarer le Goal 3 terminé en remplaçant une preuve
humaine par des tests ou en déplaçant une exigence vers un nouveau Goal.

Le pilote historique `G4-K1-CONTROL-CLEAN-AND-REFERENCE-V1` reprend exactement
le carré E4.
Thomas a fixé Geetech et `220 °C`, six allers-retours rapides, puis un frottement
lent piloté par la température réelle avec remontée de `Z32` à `Z34`. Un premier
passage s'est arrêté après chauffe, sans nettoyage, puis les chauffes ont été
coupées. La chauffe séparée est supprimée : le cycle atomique finit autour de
`140 °C` avec les deux cibles à zéro, sans attendre de verdict. Son nouveau
préflight live sans effet est vert à la position sûre `X204,5 Y304,5 Z35`, avec
le `11 × 11` exact et les configurations conformes. Le cycle physique attend
seulement Thomas devant la K1 ; son nettoyage automatique reste clos KO.
ADR-033 réutilise seulement le mouvement E4 qualifié pour décrocher la boule
après une purge explicite dans le bac, sous deux contrôles caméra bloquants.

La caméra `1280 × 720` est accessible en lecture seule sur le service local de
la K1. L'image prise après l'annulation R5 montre le plateau descendu et la tête
garée haute à droite ; elle est rangée dans l'inventaire brut privé. Cette image
ne prouve pas la purge passée. Le document 49 fixe la petite bibliothèque à
apprendre lors de la reprise et interdit de remplacer une image par un marqueur
logiciel.

`G4-K1-CONTROL-GATEWAY-PRIVATE-LAN-NO-AUTH-V1` est installé et validé. Le mot
de passe HTTP Basic n'est plus utilisé sur `4409`. Nginx continue de limiter
l'entrée à la boucle locale et aux plages IPv4 privées ; Moonraker reste lié à
`127.0.0.1:7125` et voit uniquement le proxy local approuvé. L'appel LAN
anonyme de `/server/info` est vert et le vrai Chrome affiche Mainsail en
`Standby` sans erreur. Le fichier de compte persistant reste inutilisé pour un
retour arrière exact. Seul `S57k1_control_gateway` a été rechargé ; aucun effet
physique ni changement de profil mesh n'a eu lieu.

La lecture de passation montrait le profil composite
`k1_p001_t055_r001_n11x11` actif, alors que la capture Goal 2 observait
`default`. La cause de cette dérive intermédiaire reste non qualifiée et la
mission passerelle n'avait envoyé aucune commande de mesh.

L'ancienne nomenclature a conduit à charger le `6 × 6` sous la gate historique
`G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1`. ADR-029 corrige cette erreur de
classement : le `6 × 6` est un ancien profil quotidien, pas un profil robuste.
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1` a ensuite remis le meilleur profil
observé `k1_p001_t055_r001_n11x11` actif en une commande. Aucun rollback n'a
été nécessaire. Deux lectures indépendantes ont confirmé sa matrice
`58fd96c5…`, les configurations inchangées, l'état `standby`, les cibles zéro,
les axes libérés, le Z `−0,04 mm` et les deux CFS connectés.

La première tranche physique `G4-K1-CONTROL-CLEAN-MOTION-V1` est close OK.
La capture live strictement en lecture seule
`20260827-clean-motion-v1-read-only-sources-v3` a qualifié les limites machine
et la zone logicielle stock X `68…94 mm`, Y `304,5…306,5 mm`, trajet X `20 mm`
et delta Z `−0,15 mm`, sans exporter le code complet. Ces valeurs ne prouvent
pas la brosse réelle. Le meilleur profil actuel est actif. Thomas a confirmé le
plateau libre, la brosse visible, la buse observable et l'arrêt immédiat
possible. Le préflight frais était vert. La séquence a référencé XYZ, rechargé
le `11 × 11`, commandé `Z=50 mm` et attendu la fin sans chauffe, extrusion, CFS
ou mesure de mesh. Le premier validateur a comparé à tort la position physique
compensée `50,23 mm` à la consigne ; aucun mouvement n'a été rejoué. La
validation corrigée lit `Z=50,00 mm` côté G-code et confirme la machine au repos,
froide, configurations inchangées et `11 × 11` actif. Le statut est
`CHECKPOINT_C_TECHNICAL_OK_AWAITING_HUMAN_VERDICT`. Thomas a ensuite confirmé
`CHECKPOINT C OK`. Le checkpoint ne sera pas rejoué. D1 a ensuite déplacé une
seule fois la tête à froid jusqu'à
`X81 Y280 Z50`, encore `24,5 mm` avant la zone stock déclarée. L'état final
confirme les chauffes à zéro, aucune route CFS, les configurations inchangées et
le `11 × 11` actif. Thomas a confirmé `D1 OK`. D1 n'a pas été rejoué. D2 a
ensuite approché une seule fois jusqu'à `X81 Y300 Z50`, encore `4,5 mm` avant la
zone stock, à froid et sans autre effet. Thomas a confirmé `D2 OK`, puis D3 a approché une
seule fois jusqu'à `X81 Y303 Z50`, encore `1,5 mm` avant la zone stock, à froid
et sans autre effet. Thomas a confirmé `D3 OK`.

Deux captures longues sous conduite manuelle ont ensuite fixé la grande brosse
autour de `X66..99 / Y303..307 / Z2` et la seconde autour de
`X203..206 / Y303..305 / Z32`, avec sortie sûre à `X203 Y273 Z32`. E2 a validé
le balayage de la grande brosse, E3-R2 l'approche resserrée de la seconde et E4
son carré exact `X203..206 / Y304..305`. Le verdict final humain est `E4 OK`.
Les chauffes sont à zéro, aucune route CFS n'est engagée, les configurations
sont inchangées et le `11 × 11` reste actif. La prochaine exigence est le
nettoyage réel borné suivi d'une unique référence Z avec buse propre.

La recette de mesure quotidienne qualifiée reste `6 × 6` Lagrange avec un seul
mesh standard ; cela ne signifie pas que son profil résultant est robuste ni
meilleur aux bords. L'autonomie de calibration quotidienne standard est maintenant
atteinte : la campagne a réussi sans console et le vrai écran corrigé ouvre
depuis Mainsail sans nouvelle authentification ni traduction Codex. Le mode
précision composite est techniquement qualifié, mais sa comparaison physique
a refusé la promotion : il reste caché jusqu'à qualification d'un profil dérivé
qui corrige les bords.

La comparaison V2 a maintenant fourni ce verdict. Avec le Z temporaire
`−0,24 mm` observé pendant l'impression, le composite améliore nettement la
grande zone centrale, mais plusieurs bandes de bord sont beaucoup plus
mauvaises. Il n'est donc pas promu dans l'interface. Le calcul exécuté avec le
`bed_mesh.py` exact borne l'écart bicubique/direct à `0,009877883 mm` ;
l'interpolation n'explique pas seule les défauts. Le profil physique
`k1_p001_t055_r001_n11x11` reste une source immuable et le robuste reste le
repli. L'état distant final après la fin de l'impression n'a pas été
re-préflighté pendant cet audit.

`MESH-EDITOR-OFFLINE-V1` est maintenant close sans action imprimante. Le
paquet local crée `k1_p001_t055_r001_n11x11_tuned_v001`, conserve séparément
source, demande, correction normalisée et matrice finale, puis exporte un
document canonique ou un bloc Klipper déterministe. La normalisation utilise
la surface bicubique exacte `31 × 31` et remet sa moyenne à zéro. La grille
orientée de 121 cellules, l'historique, les gardes, l'aperçu 3D et la fausse API
ont été validés dans le vrai navigateur. Aucun transport K1 n'existe dans ce
paquet.

La mission active reste `MESH-EDGE-DIAGNOSTIC-V1`, mais son premier motif source
est invalide : la tête a bougé et chauffé sans déposer de filament. Le G-code
minimal n'avait ni résolution d'outil CFS, ni chargement, ni purge. La mention
`T0` venait de Codex et n'est pas un fait fourni par Thomas. Ce passage ne prouve
ni une buse bouchée ni le comportement du mesh.

La capture `20260826-090956-mesh-edge-diagnostic-v1` a maintenant obtenu le
rollback exact et `VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK`. Le profil diagnostic
et les quatre G-code sont absents, la base `printer.cfg` exacte est restaurée,
le robuste est actif, les cibles sont à zéro, les axes sont libérés, le runtime
Z est sûr et les deux CFS sont connectés. Aucun nouveau motif ne part avant une
route filament résolue et une purge visible fraîche.

`CFS-READ-ONLY-AUDIT-V1` est ensuite clos OK sous la capture privée
`20260826-final-cfs-read-only-audit-v1`. Les empreintes des cinq fichiers
surveillés sont identiques avant et après la collecte. La K1 est restée
`standby`, cibles zéro, axes libérés, robuste actif, Z `−0,04 mm`, stockage
`ok`, mouvements bas désarmés et deux CFS connectés. Aucun G-code, chauffage,
mouvement, chargement, coupe, purge, restart ou fichier distant n'a été produit.

L'état filament courant est `engaged_unknown` : `filament_sensor` détecte une
présence, mais `box.t_command` est vide et les données persistantes courantes
n'établissent ni outil logique, ni CFS/slot physique actif. L'inventaire des
slots ne prouve pas l'identité du filament engagé. L'historique confirme que le
mapping logique peut être remappé. Aucun débit à la buse n'est prouvé. La
reprise physique reste donc bloquée jusqu'à un nouveau GO, une route résolue et
une purge visible.

Le cycle de production cible est désormais figé par ADR-016,
`docs/25-contrat-cycle-impression-nettoyage-cfs-v1.md` et
`design/job-lifecycle-contract-v1.json`. Orca enverra à terme un unique contrat
`KCTRL_JOB_BEGIN`; K1 Control possédera chauffe, nettoyage, référence Z finale,
mesh/Z, état filament, CFS, purge avec preuve de débit, pause, changement,
runout, reprise et fin. Le bon filament déjà engagé est conservé. Le retrait de
fin devient l'action séparée `Désengager et nettoyer`. Le cœur CFS compilé reste
une frontière à tracer et la bascule Orca avec retrait du `+0,27 mm` reste
fermée et atomique.

La première recette de comparaison V1 est **close KO**. Elle a conservé
l'ancien offset Orca `+0,27 mm` alors que le Z accepté vaut `−0,04 mm`. Le
passage robuste a donc produit une couche trop haute ; le composite n'a pas été
lancé. Les deux fichiers distants ont été supprimés. L'état final conserve le
hash `printer.cfg` exact `f88d6b52…`, le robuste actif, les cibles zéro et les
axes libérés. Toute reprise doit préparer un successeur qui qualifie d'abord le
Z absolu sur un motif court.

L'ADR-013 montre que la limite PRTouch de 36 contacts par séquence ne borne pas
nécessairement la matrice finale : quatre sous-grilles bornées peuvent former
121 mesures physiques `11 × 11` dans la même chauffe et le même référencement.
Le fusionneur hors imprimante est vert. Le composant séparé pour l'unique
sous-grille décalée `5 × 5` a d'abord obtenu le préflight, la pose et deux
validations SSH sous `20260824-113026-g4-k1-control-composite-mesh-subgrid-v1`.
Thomas a ensuite confirmé le plateau libre et `PEI_TEXTURED_A`. La capture
`20260824-113434-g4-k1-control-composite-mesh-subgrid-v1-run` contient exactement
25 contacts et une matrice finie. La qualification a rencontré une course au
restart Klipper, puis le premier delta de reprise a révélé le marqueur persistant
historique `schema: 1` incompatible avec le stockage partagé `version: 1`.
Aucune seconde mesure n'a été lancée. R2 a migré ce seul marqueur atomiquement,
posé les deux composants corrigés et redémarré uniquement Moonraker sous
`20260824-121607-g4-k1-control-composite-mesh-subgrid-recovery-v1-r2`. La reprise
logique a qualifié la matrice existante et la validation indépendante a obtenu
`VALIDATE_RUN_COMPOSITE_SUBGRID_V1_OK`. État final : `standby`, cibles zéro,
axes non référencés, profil robuste actif, Z `−0,04 mm`, stockage `ok` et deux
CFS connectés.

La première recette complète a prouvé qu'une grille rectangulaire `5 × 6`
déclenche elle aussi un `IndexError` propriétaire, après ses 30 contacts. Le
rollback était vert. R2 a remplacé les rectangles par quatre carrés `6 × 6`
recouvrant la ligne et la colonne centrales. La capture
`20260824-131000-g4-k1-control-composite-mesh-v1-r2-run` a obtenu `144/144`
contacts et 121 positions uniques. La fusion initiale a refusé un écart brut
maximal `0,147858 mm` avant toute persistance ; le rollback a de nouveau laissé
la K1 sûre.

Les journaux exacts montrent un biais constant nord/sud ajouté par le
post-traitement local PRTouch. Le delta de reprise posé sous
`20260824-155319-g4-k1-control-composite-mesh-recovery-v1` conserve l'état exact
et aligne un seul biais constant par carré, à moyenne pondérée nulle. L'écart
résiduel maximal vaut `0,043745029 mm` et la moyenne `0,013871331 mm`. La reprise
sans chauffe ni mouvement a persisté `k1_p001_t055_r001_n11x11`, relu sa matrice
exacte, puis rechargé le profil robuste. La validation indépendante a obtenu
`VALIDATE_RUN_COMPOSITE_MESH_V1_OK`. État final : `standby`, cibles zéro, axes
non référencés, profil robuste actif, profils `6 × 6` et `11 × 11` persistants,
Z `−0,04 mm`, stockage `ok` et deux CFS connectés. Voir
`docs/21-g4-k1-control-composite-mesh-v1.md`.

The repository baseline, stock acquisition, complete Orca/G-code intake and
passive P1–P5/PETG trace are complete. Gate G3 is passed for offline design and
simulation only. No further printer mutation is authorised after the completed
gate. The deployed printer-side slices are `G4-SSH-KEY`, the V3 + PATHS-V1
control foundation, the Z/mesh runtime carrying one accepted Z record, the
calibration path and the robust mesh from FIRST-CALIBRATION-V2. Production and
every new physical calibration action remain closed.

Thomas rejected `G4-ZSAFE-START-V1` before deployment. Its fixed `+0.27 mm`,
single `default` mesh and manual clean flow are not a production solution. The
remaining files are historical, marked `rejected_never_deploy`, and fail closed
if loaded accidentally.

The active target is `K1-CONTROL-V1`: one coherent, parameterised product with
a simple daily interface, a Mainsail expert view candidate, persistent accepted
Z calibration, meshes by plate/temperature, safe configurable start/clean/purge,
dynamic two-CFS temperature ownership and one versioned Orca contract. It is
being prepared by reversible slices. The complete offline prototype is now
green. V1 was authorised but stopped before mutation because the required
`logrotate` was absent. V2 reused the bounded stock syslog and reached a working
Mainsail through an SSH tunnel, then was rolled back because Mainsail `v2.18.2`
cannot satisfy the required Moonraker-account gate. V3 moves authentication to
nginx and changes no print behaviour. Les GO V3 exacts renouvelés ont permis de
corriger, avec rollback complet entre les KO, le transport stdin, les droits du
fichier et du dossier parent, puis la transition nginx de la boucle locale vers
le LAN. La capture finale `20260821-015722-g4-control-foundation-v3` est verte :
Moonraker reste sur `127.0.0.1:7125`, Mainsail authentifié écoute sur
`0.0.0.0:4409`, le compte a été vérifié par Thomas, les services Creality sont
intacts, Klipper est `standby`, les chauffes sont à zéro et les deux CFS `1.1.3`
sont connectés. Après ouverture du vrai tableau de bord, deux avertissements ont
prouvé que les racines `config` et `gcodes` dérivées du data path Moonraker sont
distinctes des chemins Creality actifs. La connexion fonctionne, mais
l'intégration du gestionnaire de fichiers reste incomplète. Une inspection
distante bornée et sans mutation a confirmé les deux dossiers Moonraker vides.
Le candidat séparé `G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1` a reçu son GO exact
renouvelé après revue et a été déployé sous la capture
`20260821-111001-g4-control-foundation-v3-paths-v1`. Les deux racines Moonraker
pointent maintenant vers les chemins Creality actifs, `config` est en lecture
seule via l'API et `gcodes` reste en lecture/écriture. Une validation indépendante
a confirmé l'absence d'avertissement, toute la pile verte et aucun changement du
comportement d'impression. L'acceptation durable et ses huit heures d'observation
commencent sur cet état final retenu.

## Confirmed facts

- Passive session `20260820-154056-p123` captured P1, P2, P3, P4, two P5
  attempts and one P1 PETG run. All jobs finished; the trace ended with nozzle
  and bed targets at zero.
- P4 proved that the `+0.27 mm` post-processor correction appears only after
  `START_PRINT`; startup purge and other earlier low operations remain
  unprotected.
- Live Z changes invoke `Z_OFFSET_APPLY_PROBE`, but the end-of-print path applies
  the exact inverse and prepares `0.000` for persistence. The current workflow
  therefore erases the correction it appeared to save.
- P1 PETG required a final visible correction of `+0.38 mm`, `+0.11 mm` above
  the file baseline, after briefly reaching `+0.40 mm`.
- P2 and P3 have the same 639 recorded settings and showed no reported physical
  difference despite separate versus assembled objects. One `+0.010 mm` live Z
  click occurred during P3, so the pair is not entirely untouched; it provides
  no evidence that object count alone explains the historical shifts.
- The second corrected P5 completed without a pause and followed nozzle targets
  `115 -> 220 -> 205 -> 220 -> 0 °C`. The first `220 °C` confirms the startup
  override; the second equals the requested target and cannot prove ownership.
- Every file still receives stock PA `0.044` during startup before its own PA
  becomes active roughly three minutes later.

- The accepted design route is a strengthened stock stack before BTT Eddy or a
  full firmware replacement. It now means one coherent control product, not a
  fixed Z patch followed by unrelated settings. This authorises offline design,
  not deployment.
- The accepted Z rule is explicit: live changes belong to a calibration session;
  only `Enregistrer` creates the persistent record. It survives print end and
  reboot, but a new reference calibration invalidates it.
- Moonraker MIPS is pinned to embedded commit
  `fccffa96c63ed77dc3953e18615e9fe9cd3d69ea`; Mainsail is pinned to `v2.18.2`.
  Their archives, security policy and paths are fixed, but memory and
  coexistence with the screen and two CFS still require the named G4.
- A bounded read-only capacity snapshot found about 209 MiB total RAM, 118 MiB
  available, Python 3.8.2, 4.2 GiB free on `/usr/data`, no Moonraker process and
  no listener on its usual port. No remote mutation occurred.
- A private, Git-ignored intake exists under
  `inventory/raw/user-inputs/20260820-full-system-audit/` for Orca exports,
  existing projects, G-codes, custom scripts, photos and recovery artefacts.
- The first private Orca and test-suite intake is complete: 24 baseline files
  and 13 test-suite files were copied locally and verified by SHA-256 without
  changing their sources. Raw files and manifests remain ignored by Git.
- Six candidate G-codes are now available offline. P2 and P3 have the same 639
  recorded settings, duration, material estimate and two-layer geometry, while
  differing as five separate objects versus one assembled object. They form the
  cleanest current object-structure comparison.
- Ironing is enabled on P1, P2 and P3. Because it is shared and occurs at the
  top surface, it does not invalidate their first-layer comparison; top-surface
  defects must nevertheless remain separate from Z observations.
- The supplied `P5-CFS-ONE-CHANGE` is not a one-change file: it contains eleven
  tool commands and ten automatic changes between PLA targets of 205 and 220
  degrees. It is deferred until a replacement G-code proves exactly one change.
- Every supplied G-code still inserts the temporary `+0.27 mm` correction after
  `START_PRINT`, so none protects a purge or low move executed inside that
  stock macro.
- BTT Eddy is not currently mandatory. Its closest K1 Max `2.3.5.34` + CFS
  integration documents beta Z-offset behaviour, repeated recalibration and
  build-plate risk; it remains a measured fallback if deterministic PR Touch
  still fails.
- Codex has standing authority to manage the complete Git and GitHub lifecycle of this repository, including pull-request fusion into `main`, without another `GO`; printer mutations remain controlled separately by G4.
- Passwordless root SSH is active through the local alias `k1max-root`. The alias selects one dedicated ECDSA P-256 key, refuses password fallback and passed two independent final connections.
- The machine runs Dropbear `2019.78`; Ed25519 public-key authentication is unavailable in this version, so the working key is ECDSA P-256.
- Passive session `20260819-215124-long` completed automatically after a normal long production print returned to standby. Codex performed no printer-side mutation.
- The stock startup applied pressure advance `0.044`; the print file then restored `0.03` at the first layer. The active value remained `0.03` through the automatic CFS refill and to the end.
- The CFS detected runout, selected another slot it classified as equivalent PLA and resumed automatically in about 2 minutes 54 seconds.
- At startup, the CFS reported that it could not read the purge-speed data and then used its fixed `220 °C` purge temperature despite first-layer and normal print targets of `190 °C` and `195 °C`; the compiled implementation prevents proving the exact causal link between those two events.
- During that equivalent-material refill, the temperature sequence was `195 -> 140 -> 220 -> 195 -> 220 °C`. The resumed print stayed at `220 °C` until Thomas manually restored `190 °C` at `23:04`.
- Visible Z homing origin remained `+0.27 mm` for the whole session; no live Z correction was reported.
- After completion and return to standby, the stock runtime briefly requested `150 °C` before returning the nozzle target to zero.
- Thomas judged the finished part broadly correct, with rough/granular ironing areas provisionally attributed to OrcaSlicer settings rather than the observed CFS temperature ownership.

- Target machine: older-generation Creality K1 Max.
- Printer firmware: `2.3.5.34`, Buildroot 2020.02.1, Linux 4.4.94 on MIPS.
- The manufacturing identity partition reports board `CR4CU220812S12`, structure version `0`.
- The startup selector therefore loads the S12 structure-0 stock configuration; the active header and version match it.
- `/etc/ota_info` still reports `CR4CU220812S11`; this is now classified as inconsistent OTA metadata, not the active configuration identity.
- Classic K1 CFS upgrade installed.
- Two CFS units are in use.
- Both CFS units show firmware `1.1.3` on the printer UI; no machine version file has yet confirmed it.
- Active configuration entry point: `/usr/data/printer_data/config/printer.cfg`.
- `printer.cfg` includes `sensorless.cfg`, `gcode_macro.cfg`, `printer_params.cfg` and `box.cfg`.
- `START_PRINT` invokes the CFS, homing, nozzle-cleaning and levelling chains after slicer input.
- `box.cfg` sets `Tn_extrude_temp` to `220`.
- The CFS `BOX_*` implementation is delivered as a compiled `box_wrapper` module; only its small Python loader is readable.
- `CXSAVE_CONFIG`, the principal `CX_*` startup helpers, `G28` and the PR Touch probing path have been captured and mapped from readable Python sources.
- `G28` invokes the PR Touch Z routine, which uses five measurements, selects the median and applies `self_z_offset` when establishing the Z origin.
- The active saved Z offset is `0.000`; one historical snapshot contains `-0.025` before later snapshots return to zero.
- `/usr/data` is persistent ext4 storage; Klipper logs currently account for about 1.6 GiB.
- OrcaSlicer is the usual slicer; Creality Print remains available.
- The Z-offset or Z-reference problem existed before the yellow bed springs were installed.
- The springs improved bed levelling but changed nothing about the Z problem.
- CFS filament changes can override intended nozzle temperatures.
- Startup and calibration sequences can be excessively long and opaque.
- Earlier G-code post-processing successfully removed a redundant tool command and applied a temporary ironing offset, proving that some slicer-side workarounds are useful but insufficient against later firmware macro overrides.
- Session `20260819-185157-g3-aba` completed A1, B and A2 without reboot and without a fourth print.
- B and A2 each exposed multiple Z-establishing phases around nozzle cleaning; A2 reached retry index 7 and contained large internal outliers before converging near the `0.21–0.26` group.
- The stock runtime injected pressure advance `0.044` during B and A2 even though both private G-codes request `0.03` after `START_PRINT`; the final active value was not observable in this capture.
- Thomas changed bed-screw tension between the trials and again around A2. This may have improved the layer but makes the geometry comparison non-qualified.
- A1, B and A2 all completed with broadly usable physical results after manual tuning.

## Reported but not yet verified from the machine

- Exact CFS firmware source and per-unit hardware revision.
- Physical board marking; software selection is S12 structure 0, but physical confirmation remains desirable before firmware recovery.
- Exact Klipper commit/version.
- Recovery image compatibility with this exact machine revision.
- Whether a long print followed by a differently configured or multi-object file triggers the large historical Z shift reported by Thomas.

## Completed

- `G4-ZSAFE-START-V1`, ADR-003 and their former gate are explicitly rejected;
  the historical macro now fails closed if loaded by mistake.
- The durable product need and target behaviour are recorded in
  `docs/10-systeme-pilotage-perenne.md` and ADR-004.
- Mainsail, Moonraker, Creality K1 Series Annex, Creality Helper Script, its CFS
  fork, KAMP and the available calibration approaches were compared against the
  exact captured stack in `docs/11-compatibilite-interfaces-et-calibration.md`.
- A machine-readable `K1-CONTROL-V1` contract now forbids a universal fixed Z,
  requires explicit persistence/invalidation, keys meshes by plate/temperature,
  fixes dynamic temperature ownership and guards every production hazard.
- Offline contract tests were added before any printer-side implementation.
- A dependency-free `K1 Control` web prototype and pure Python Z/mesh/temperature
  state engine now run only on synthetic data under `prototype/`.
- Desktop and narrow-screen browser checks passed. Live adjustment, explicit
  commit, simulated restart persistence and reference-calibration invalidation
  behaved as intended with no JavaScript error.
- The screen now talks to a loopback-only fake Moonraker that applies the Python
  state rules instead of changing browser state directly.
- The executable offline matrix passes all 17 required Z, mesh, sequence,
  temperature, two-CFS, Orca and rollback scenarios.
- The full Orca start/end/tool-change contract and expanded fixtures are ready;
  the active Orca profile and legacy `+0.27 mm` post-processor are unchanged.
- A local bundle containing the three pinned Moonraker/nginx/Mainsail archives
  was built and verified. Binary payloads remain temporary and outside Git.
- V1 had exact paths, first-login tunnel, backup, checksums, no-motion
  validation, resource gates and rollback, but its missing target dependency
  invalidated the package before deployment. V2 preserves these controls.
- The real V1 preflight confirmed standby, zero heater targets, S12 structure
  0, firmware `2.3.5.34`, about 117 MiB available RAM, 340 KiB swap in use,
  stock ports, T1/T2 connected on `1.1.3`, and all V1 targets absent.
- The same preflight proved that neither `logrotate` nor `/etc/logrotate.d`
  exists. V1 performed no mutation and is closed.
- V2 uses the existing `/sbin/syslogd -n` through `/dev/log`; BusyBox reports
  its default 200 KiB limit and one rotated backup. No logging dependency is
  installed.
- The exact V2 GO was received. Real attempts exposed Buildroot transport,
  nginx path, permission, Moonraker provider, service-stop and WebSocket-origin
  gaps. The corrected stack loaded the real Mainsail dashboard through a tunnel.
- Mainsail `v2.18.2` has no Moonraker account workflow. V2 could not remove
  loopback trust and still keep Mainsail working, so every attempt was rolled
  back and V2 is closed.
- Final post-rollback checks found `/usr/data/k1-control-v1` and both project
  services absent, ports `7125`/`4409` closed, stock ports `80`/`8080`/`9999`
  listening and all named Creality processes present.
- Thomas selected nginx authentication. Offline inspection proved the pinned
  MIPS binary contains `auth_basic` and `auth_basic_user_file`. V3 uses a
  masked local prompt, one salted SSHA record, HTTP `401/200` checks, private
  IPv4 source limits and strips credentials before proxying to Moonraker.
- Les GO V3 exacts ont autorisé les reprises après rollback. Les écarts stdin,
  droits du fichier, traversée du dossier parent et transition nginx vers le
  LAN ont été corrigés avec tests de non-régression.
- La capture finale `20260821-015722-g4-control-foundation-v3` a installé la
  fondation, créé et vérifié le compte, ouvert le LAN et obtenu `VALIDATE_OK`.
  Moonraker reste en boucle locale, Mainsail authentifié écoute sur `4409`, les
  ports Creality sont présents et le vrai tableau de bord est fonctionnel.
- Après pose, environ 103 Mio de RAM restent disponibles et la croissance swap
  mesurée est de 36 Kio. Klipper est `standby`, les chauffes sont à zéro, les
  axes ne sont pas homés et les deux CFS `1.1.3` sont connectés.
- La capture `20260821-111001-g4-control-foundation-v3-paths-v1` a aligné les
  racines Moonraker sur les chemins Creality par deux liens, rendu `config`
  accessible seulement en lecture via l'API, conservé `gcodes=rw` et obtenu
  `VALIDATE_PATHS_V1_OK` sans transmettre de G-code. Les avertissements ont
  disparu et seule l'instance Moonraker dédiée a été redémarrée.
- L'observation finale a couvert l'impression normale lancée manuellement à
  12:48. Thomas a confirmé qualité correcte, un seul PLA et aucune intervention.
  Le trou du premier observateur local, de 15:07 à 18:43, a été couvert
  séparément par le journal Klipper persistant : aucun arrêt Klipper/MCU, aucune
  perte de communication, aucune trace Python et aucune erreur interne.
- Le second observateur a atteint sa durée à 20:31:56 et fermé avec `exit_code=0`.
  La validation finale en lecture seule a obtenu `VALIDATE_PATHS_V1_OK` avec les
  axes encore référencés après la calibration manuelle. Le validateur distingue
  désormais correctement une simple vérification de santé d'un préflight de pose.
- Les sources exactes `save_variables.py`, `gcode_macro.py`, `delayed_gcode.py`
  et `bed_mesh.py` ont été copiées en lecture seule dans une capture privée et
  vérifiées par SHA-256.
- Le candidat hors imprimante Z/mesh existe maintenant sous
  `packages/k1-control-v1/z-mesh-runtime-v1/`. Il fournit état Z courant/précédent,
  session provisoire, invalidation, préchauffe, homing guidé, matrices 3–25,
  choix Lagrange/bicubique, commit mesh explicite et garde de mouvements bas.
  Son stockage original utilise validation, SHA-256, `fsync`, remplacement
  atomique et copie précédente. Il ne remplace pas `START_PRINT`, ne contient
  ni CFS, ni extrusion, ni mouvement bas et n'est pas installé.
- Thomas a envoyé le GO exact `G4-K1-CONTROL-Z-MESH-RUNTIME-V1`. Le premier
  préflight a échoué sans mutation parce que deux appels Python avec arguments
  n'indiquaient pas la lecture sur stdin. Le déployeur ajoute maintenant `-`
  avant ces arguments et un test dédié verrouille ce transport.
- Le second préflight en lecture seule est vert sous la capture privée
  `20260821-212431-g4-k1-control-z-mesh-runtime-v1` : `standby`, chauffes à
  zéro, fondation intacte, empreinte initiale conforme, cibles runtime absentes
  et deux CFS `1.1.3` connectés. Aucune copie, sauvegarde distante, inclusion,
  commande Klipper ou relance de service n'a été exécutée.
- Le GO exact renouvelé a ouvert la capture
  `20260821-213732-g4-k1-control-z-mesh-runtime-v1`. Le préflight et le backup
  étaient verts, puis l'état neuf a échoué car `integrity=empty` laissait
  `ready=0`. La garde sans mouvement n'a pas été appelée.
- Le rollback a retiré le runtime mais sa première validation a rencontré T1 en
  reconnexion et une normalisation d'espaces des blocs générés de `printer.cfg`.
  Une complétion bornée a restauré le backup exact sans nouveau restart. Le
  préflight final est vert : runtime absent, hash initial restauré, `standby`,
  axes non homés, chauffes à zéro, T1/T2 `1.1.3` et fondation intacte.
- Le restart a effacé le mesh transitoire `Base`; le profil persistant `default`
  est redevenu actif. Aucun mouvement, chauffe, extrusion, ordre CFS,
  calibration, impression, firmware restart ou reboot n'a été exécuté.
- Le candidat hors imprimante traite maintenant `empty` comme prêt pour une
  calibration mais fermé à la production, attend jusqu'à 60 secondes la
  stabilisation des deux CFS et restaure le backup exact après le restart de
  rollback. Son nouveau hash config est
  `3b0e5215d9bd58a343c57a681668ef1e466465980cceac3b1fd5944fec806f96`.
- Un nouveau GO exact a ouvert la capture
  `20260821-224828-g4-k1-control-z-mesh-runtime-v1`. Préflight et backup étaient
  verts. Après pose, le runtime restait à `ready=0` parce que le parseur exact de
  Creality tronque `K1_CONTROL_LOAD_STATE` en commande `K1` inconnue.
- La source `gcode.py` capturée confirme le découpage
  `([A-Z_]+|[A-Z*/])` : tous les points d'entrée avec un chiffre au milieu sont
  incompatibles. Le candidat emploie désormais `KCTRL_*` pour le runtime, le
  stockage, l'adaptateur et les contrats Orca. Un test rejoue ce parseur exact.
- Le rollback a retiré le runtime, mais un `CXSAVE_CONFIG` Creality tardif a de
  nouveau normalisé seulement les espaces de `bed_mesh default` et `auto_addr`.
  Une complétion bornée a restauré le backup exact sans restart. Le préflight
  final est vert : runtime absent, hash initial, `default`, `standby`, axes non
  homés, chauffes à zéro, deux CFS `1.1.3` et fondation intacte.
- Le rollback offline attend maintenant la reconnexion CFS et une fenêtre
  silencieuse avant sa dernière restauration, puis revérifie l'empreinte après
  trois secondes. Les nouveaux hashes sont
  `1590b918dcdfe70e801c0be40fee4f19ab6b1e2dfa93936975b88aed5d4b1c79`
  pour la configuration et
  `696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede`
  pour le module. La suite locale passe `98/98`; la validation en mémoire sur
  le Python/Jinja exact de la K1 obtient
  `K1_EXACT_RUNTIME_OK templates=17 commands=18`.
- Thomas a renouvelé une troisième fois le GO exact. La capture
  `20260822-004338-g4-k1-control-z-mesh-runtime-v1` a confirmé le préflight et
  le backup, puis chargé les objets `KCTRL_*`. `KCTRL_LOAD_STATE` s'est bien
  exécuté, mais la première affectation texte a échoué : le `shlex` Creality
  transforme `VALUE='empty'` en nom nu `empty`, refusé par `ast.literal_eval`.
- Le rollback automatique renforcé a retiré le runtime, attendu les deux CFS et
  la fenêtre silencieuse, restauré le backup exact et revérifié son empreinte.
  Le préflight final confirme runtime absent, `default`, `standby`, axes non
  homés, chauffes à zéro, deux CFS `1.1.3` et fondation intacte. Aucun mouvement,
  homing, chauffe, extrusion, ordre CFS, calibration, impression, firmware
  restart ou reboot n'a eu lieu.
- Les 24 affectations texte utilisent désormais un littéral protégé comme
  `VALUE='"empty"'`. Le déployeur conserve aussi un snapshot avant rollback si
  `ready` reste à zéro. Le hash courant de la configuration est
  `dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113` ; celui
  du module reste
  `696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede`.
  La suite exécute 99 tests : 98 passent et le contrôle Jinja local ignoré est
  couvert par `K1_EXACT_RUNTIME_OK templates=17 commands=18 string_values=24`
  sur l'environnement exact de la K1.
- Thomas a renouvelé le GO exact pour la capture
  `20260822-011022-g4-k1-control-z-mesh-runtime-v1`. Le préflight frais, le
  backup et la pose sont verts : `DEPLOY_Z_MESH_RUNTIME_V1_OK`.
- La garde `KCTRL_PRODUCTION_ASSERT_ARMED` a refusé l'état vide comme prévu et
  la comparaison avant/après confirme qu'aucune position, origine Z ou cible de
  chauffe n'a changé.
- Un `CXSAVE_CONFIG` différé a ensuite normalisé uniquement l'indentation des
  blocs générés `bed_mesh default` et `auto_addr`. Le diff complet ne contient
  aucun changement de valeur, section ou inclusion, et la comparaison
  normalisée obtient `PRINTER_CFG_NORMALIZED_EQUIVALENCE_OK`.
- Le validateur épingle l'empreinte immédiatement posée et l'unique empreinte
  normalisée observée, tout en exigeant toujours une inclusion et les hashes
  exacts des deux fichiers runtime. La validation indépendante obtient
  `VALIDATE_Z_MESH_RUNTIME_V1_OK`.
- État final retenu : `standby`, axes non homés, chauffes à zéro, `default`,
  deux CFS `1.1.3`, fondation intacte, `ready=1`, `integrity=empty`,
  `accepted_z_valid=0`, `block_reason=no_accepted_z` et `low_moves_armed=0`.
  Le runtime est installé mais ne peut pas encore armer un travail de production.
- La suite courante exécute 131 tests : 129 passent et deux contrôles Jinja
  locaux sont ignorés. Le runtime installé a déjà passé son contrôle exact sur
  la K1 ; l'overlay a également passé son parse exact en mémoire avant sa pose.
- `G4-K1-CONTROL-CALIBRATION-PATH-V1` est installé et validé sous la capture
  `20260822-124207-g4-k1-control-calibration-path-v1` : un fichier, un include,
  un `RESTART` hôte et une validation sans mouvement.
- Le candidat `G4-K1-CONTROL-FIRST-CALIBRATION-V1` est préparé hors imprimante.
  Son contrat fixe `PEI_TEXTURED_A`, `55/140 °C`, `200 s`, nettoyage stock
  borné à `180 °C`, deux meshes `6 × 6` Lagrange et un seuil point par point de
  `0,025 mm`, sans rerun automatique.
- Thomas a validé ces paramètres hors imprimante. Son `GO` générique ne nomme
  pas la gate exacte et précède le commit révisé ; aucune autorisation distante
  n'est donc consommée.
- Le pilote local découpe préparation, chaque mesh, qualification, persistance,
  chaque palier Z, acceptation, annulation et rollback. Son mode par défaut
  `Plan` ne contacte pas la K1. Aucune action distante n'avait été exécutée
  avant le GO exact décrit ci-dessous.
- Thomas a ensuite envoyé le GO exact. La capture
  `20260822-140602-g4-k1-control-first-calibration-v1` a passé le préflight,
  créé et vérifié le backup, préparé la machine puis mesuré exactement deux
  meshes. La qualification est KO : maximum `0,062125 mm`, moyenne
  `0,018049 mm`, seuil `0,025 mm` sur 36 points.
- Le pilote a coupé les chauffes et s'est arrêté sans rerun. Aucun profil cible
  n'a été persisté, aucun stockage Z n'a été créé et aucune session Z n'a été
  ouverte. Le contrôle final en lecture seule a confirmé `printer.cfg` exact,
  profil cible absent, état Z absent, `standby` et cibles de chauffe à zéro ;
  les axes restent référencés après les mesures.

- Complete-system audit, A/B/C comparison, safety invariant, input contract and
  time-bounded roadmap documented in
  `docs/08-audit-systeme-complet-et-trajectoire.md`.
- ADR-002 proposes an analyser-first strengthened stock route and defines the
  later BTT Eddy decision gate.
- Private intake folders and exact deposition instructions created and verified
  as ignored by Git.
- Public repository created.
- Scope, strategy and safety boundary documented.
- Agent rules, gates, roadmap and acquisition protocol prepared.
- Public/private data separation defined.
- Notion project branch created separately as the long-form personal register.
- Gate G1 passed and target identity confirmed.
- Read-only acquisition `20260819-1627-k1max-stock` completed.
- Raw material retained under ignored local storage.
- Redacted manifest, service map, mount map, checksums, include graph, macro index and findings produced.
- Gate G2 passed with explicit limitations.
- Follow-up read-only acquisition `20260819-1726-k1max-targeted-sources` completed.
- S11/S12 runtime configuration identity resolved as S12 structure 0.
- Readable CX, persistence, homing and PR Touch sources mapped; compiled CFS boundary recorded.
- Comparable A1/B/A2 trace protocol completed with fixed conditions, Q1–Q5 qualification and a custom-installation decision matrix.
- Private session, event timeline and comparison templates added under `experiments/g3/`.
- Bounded execution prompt prepared and used; all physical actions were performed by Thomas.
- Private G3 files A/B compared locally: 637 slicer settings and all 34 non-motion control commands are identical.
- Both files apply Z protection `+0.27 mm` and pressure advance `0.03` after `START_PRINT`; B changes only the Y dimension from `200` to `201 mm` and the resulting movements.
- The stock bed check selects four near-corner points randomly, measures each three times and can regenerate and save the mesh when at least two corners exceed its tolerance.
- A1/B/A2 is now the selected first physical sequence; reboot and multi-filament CFS tests are deferred.
- A1/B/A2 session report and cleaned event summary produced. Q1 passed, Q2–Q4 did not pass and Q5 is inconclusive.
- `G4-SSH-KEY` prepared, approved, deployed and validated without any service restart.
- Final `/root/.ssh/authorized_keys` state: one active ECDSA key, root ownership, mode `600`, final recorded SHA-256 `eae61f0314dbcdfaa9a02a42352592e3b175a5d35a0d501cb909b365697eb6af`.
- Local SSH configuration was backed up before adding the tested `k1max-root` alias.
- Read-only production observer added and validated with a six-second subscription probe: one persistent Klipper connection, three state samples, no repeated query traffic and no socket-close errors inside the capture.
- Long production capture `20260819-215124-long` completed with 6,748 state records and an automatic observer shutdown after standby.
- Cleaned findings, event summary and sanitisation report produced for the long capture; raw evidence remains local and ignored.
- Final pressure advance ownership measured: startup `0.044`, then file-requested `0.03` active through the CFS refill and print end.
- Equivalent-PLA CFS refill temperature override measured and confirmed: stock resume returned to `220 °C` instead of preserving the prior print temperature.
- Exact live copies of `printer.cfg`, `gcode_macro.cfg` and `box.cfg` were
  retrieved read-only and matched their recorded SHA-256 hashes.
- The production G-code contains no `M104`/`M109` request for `220 °C`; the CFS
  module and its generic PLA database own that value.
- The static `G4-CFS-TEMP-PLA` candidate was rejected by Thomas before
  deployment because it hard-coded Geeetech PLA and `190/195 °C`.
- Its deployable patch, helper, OrcaSlicer contract, deployment procedure and
  dedicated test were removed from `main`; the rejected ADR remains as history.
- The accepted requirement is dynamic: G-code or Thomas owns every explicit
  phase temperature, equivalent refill preserves the active target, and a true
  material change distinguishes old-material unload, declared transition purge
  and next-tool print targets. The CFS never chooses a hidden fallback.

## Next safe action

Au début de la prochaine session, annoncer explicitement à Thomas :

- autonomie calibration quotidienne standard : **atteinte** ;
- autonomie de création et d'édition **hors ligne** d'un profil dérivé :
  **atteinte** ;
- autonomie du mode Précision réellement installé : **non atteinte** ;
- autonomie production : **non atteinte** ;
- la sous-grille composite `5 × 5` est qualifiée avec 25 contacts ;
- le profil physique `11 × 11` reste une source immuable ; l'éditeur local
  v001 est validé, mais son exposition utilisateur reste fermée jusqu'à la
  qualification physique d'un profil dérivé ;
- l'autonomie production reste non atteinte.

Le rollback de la tentative invalide est clos sous la capture
`20260826-090956-mesh-edge-diagnostic-v1`. La restauration exacte, le retrait
du profil diagnostic et des quatre G-code, le retour au robuste, les cibles
zéro, les axes libérés et la validation finale sont verts. Aucun motif n'a été
relancé.

La reprise ultérieure doit repasser hors imprimante, ne supposer aucun `T0`,
résoudre l'outil logique vers le CFS/slot réel et exiger une purge visiblement
réussie avant chaque variante. La gate doit ensuite seulement prouver le sens
d'une petite correction de `0,010 mm`, sa répétabilité aux bords et l'influence
du PTFE sans dégrader le centre. Le mode Précision reste caché.

Le chemin borné `G4-K1-CONTROL-CALIBRATION-PATH-V1` ajoute ce qui manquait pour
évaluer le premier Z sans console libre ni valeur cachée. Son premier préflight
réel a échoué avant écriture sur une ligne SSH
trop longue. Le transport Jinja corrigé par stdin a ensuite obtenu
`PREFLIGHT_CALIBRATION_PATH_V1_OK` sous la capture `20260822-113503`. La pose
autorisée sous la capture `20260822-115608` a ensuite posé l'overlay, mais sa
validation a interrogé le socket Klipper pendant le `RESTART`. Le rollback
repris sur le backup exact a obtenu `ROLLBACK_CALIBRATION_PATH_V1_OK`, puis le
préflight final a prouvé la base exacte, l'overlay absent et la pleine santé.
Aucune chauffe, homing, mouvement, mesure mesh ou écriture Z n'a eu lieu.

Le déployeur attend maintenant le socket de façon bornée après pose et avant le
`RESTART` du rollback. Le GO renouvelé a ensuite retenu la pose sous la capture
`20260822-124207-g4-k1-control-calibration-path-v1` avec
`DEPLOY_CALIBRATION_PATH_V1_OK` et `VALIDATE_CALIBRATION_PATH_V1_OK`. L'overlay
et son unique include sont installés avec leurs empreintes exactes ; le runtime
reste vide, les axes sont non référencés, les chauffes à zéro et la garde à vide
refuse sans changement physique.

`G4-K1-CONTROL-FIRST-CALIBRATION-V1` a consommé son GO exact sous la capture
`20260822-140602-g4-k1-control-first-calibration-v1`. Les deux meshes ont été
mesurés, mais leur écart maximal `0,062125 mm` dépasse le seuil `0,025 mm`.
L'arrêt KO a laissé la base persistante exacte, sans profil cible et sans état Z.
L'analyse hors imprimante a produit `FIRST-CALIBRATION-V2` : six meshes, deux
médianes indépendantes de trois, qualification moyenne/RMS/maximum et aucun
septième passage. Thomas a donné le GO exact. La capture
`20260822-160948-g4-k1-control-first-calibration-v2` a exécuté les six mesures
et accepté leur répétabilité : moyenne absolue `0,010788694 mm`, RMS
`0,013996452 mm`, maximum `0,034352 mm`. Le profil robuste
`k1_p001_t055_r001_n06x06` est conservé.

L'endpoint `update_mesh` a réellement conservé le homing au lieu de redémarrer,
ce qui a déclenché un faux KO du validateur. Le diff exact ne contenait que la
matrice robuste transitoire. Une reprise bornée a vérifié backup, hashes,
runtime vide et matrice, puis exécuté le commit déjà revu. Le pilote et son test
attendent maintenant ce comportement réel.

Le chemin Z a été repris avec Thomas présent sans refaire les six meshes. Une
pile de dix épaisseurs a évalué la cale à `0,09 mm`. La friction est devenue
nette à `−0,05 mm`; le cran retenu `−0,04 mm` laisse cette cale libre et vise le
jeu final `0,10 mm`. Thomas a confirmé le constat. Le Z a été parqué, persisté
atomiquement et validé. État final observé : `standby`, cibles zéro, profil
robuste présent, stockage `ok`, `accepted_z_valid=1`,
`accepted_z_offset=-0,04`, `session_active=0`, chemin `committed` non armé.

Le premier contrôle final a été un faux KO local : Klipper génère l'en-tête
persistant `#*# [bed_mesh ...]`. Le pilote cherchait sa forme non commentée. Le
contrôle et son test ont été corrigés sans mutation imprimante ; la relance en
lecture seule a obtenu `VALIDATE_FIRST_CALIBRATION_V2_OK`.

À ce stade historique, `CALIBRATION-UI-V1` était préparé hors imprimante. Il fournit un
contrôleur Moonraker serveur et une page réelle avec choix de plaque,
températures, stabilisation, matrice, interpolation, enregistrement, annulation
et restaurations. Sa pose ne devait lancer aucune calibration et devait
redémarrer Moonraker seulement. Il n'était pas encore installé ni validé sur la
machine ; l'autonomie calibration n'était donc pas encore atteinte à cette
étape. La campagne écran close depuis a levé ce blocage pour le mode quotidien
standard.

La revue post-calibration a rendu le candidat compatible avec l'état final réel :
les phases fermées admises sont `idle`, `committed` et `cancelled`; les lectures
Moonraker utilisent le `curl` Creality sans `-fsS` et `+` pour les espaces. Le
préflight compile et importe les sources en mémoire avec le Python Moonraker
`3.8.2` exact, par stdin, et vérifie aussi l'empreinte du déployeur. Le plan local
et le préflight réel en lecture seule sont verts. Aucun fichier distant ou
restart n'a été produit. La pose attend toujours le GO exact UI séparé.

Thomas a ensuite autorisé cette gate. La capture
`20260822-192821-g4-k1-control-calibration-ui-v1` a obtenu le préflight et le
backup exact, puis le premier transfert a échoué avant toute pose parce que
l'OpenSSH Windows a tenté SFTP sur un Dropbear sans `sftp-server`. Le rollback
automatique a restauré la base exacte, retiré les chemins candidats et
redémarré seulement Moonraker. Le préflight final est vert et le staging est
vide. Le transport corrigé utilise `scp -O` et le rollback retire désormais le
staging exact. Ce changement de déployeur exige un nouveau GO exact avant une
seconde tentative. Le paquet corrigé a déjà repassé
`PREFLIGHT_CALIBRATION_UI_V1_OK` en lecture seule.

Thomas a renouvelé le GO exact. La capture
`20260822-202014-g4-k1-control-calibration-ui-v1` a posé le paquet et passé les
contrôles par fichiers/API, mais la recette dans le vrai navigateur a révélé
que le service worker Mainsail masquait `/k1-control/` sur l'origine
`127.0.0.1:4409` et que le dossier UI créé en `0700` était interdit à nginx.
Le journal nginx a confirmé `Permission denied`. Le rollback exact a retiré
l'UI et le composant, restauré la configuration puis obtenu un préflight final
vert. Aucun chauffage, homing, mouvement, mesh ou Z n'a été exécuté.

Le candidat impose et vérifie désormais le mode `0755` du dossier UI. Le
lanceur calibration utilise l'origine isolée
`http://localhost:4409/k1-control/` sur le même tunnel afin d'éviter le service
worker Mainsail. Thomas a renouvelé le GO exact : la capture
`20260822-211633-g4-k1-control-calibration-ui-v1` a obtenu le préflight frais,
la pose et deux validations vertes. L'API est `idle`, le Z accepté vaut
`−0,04 mm`, la K1 reste `standby`, les cibles sont à zéro et les mouvements bas
sont désarmés. Après authentification humaine, le vrai rendu Chrome et un
rechargement complet ont confirmé l'API, les paramètres exacts, le seed
`−0,04 mm` restauré et les confirmations physiques volontairement décochées.
`CALIBRATION-UI-V1` est close.

L'audit de reprise navigateur a ensuite trouvé que le formulaire ne reprenait
pas le Z accepté et qu'une fermeture entre le mesh et le Z rendait la
confirmation « plateau libre » fausse mais désactivée. Le candidat hors
imprimante expose maintenant le Z accepté, réhydrate les paramètres depuis
l'état serveur et laisse les confirmations physiques accessibles ; le bouton Z
les exige explicitement. Les nouvelles empreintes doivent être figées avant GO.

`CALIBRATION-UI-CAMPAIGN-V1` est préparé hors imprimante comme gate séparée de
preuve, dépendante de l'UI posée et rendue. Son protocole couvre désormais les
quatre niveaux physiques : six meshes en `9 × 9`, `11 × 11`, `15 × 15`, puis six
meshes et le parcours Z complet en `6 × 6`. Les niveaux supérieurs sont annulés
depuis l'écran après capture de leur qualification, sans perdre leur profil.
Toute intervention console/Codex, septième passage sur un niveau ou relance
automatique invalide l'autonomie. Le validateur capture chaque niveau et exige
les quatre profils au contrôle final ; son plan local est vert.

Thomas a ensuite signalé l'écart de matrice : l'interface installée était
limitée à `6 × 6` alors que le contrat produit va jusqu'à `15 × 15`. Le GO exact
du delta `CALIBRATION-UI-MATRIX-V1` a été consommé par la capture
`20260822-222005-g4-k1-control-calibration-ui-matrix-v1`. Le préflight, le
déploiement et deux validations indépendantes sont verts. Seuls le core
Moonraker et deux fichiers statiques ont été remplacés après backup exact ; seul
le Moonraker dédié a été redémarré. Aucune calibration, chauffe, référence,
mesure, extrusion, commande CFS, impression ou écriture Z n'a eu lieu.

Le vrai rendu Chrome authentifié expose maintenant `6 × 6` Lagrange, puis
`9 × 9`, `11 × 11` et `15 × 15` bicubiques. Les trois tailles supérieures
forcent le bicubique et désactivent Lagrange. Un rechargement complet restaure
le défaut `6 × 6` Lagrange, le seed `−0,04 mm` et les confirmations physiques
décochées. `CALIBRATION-UI-MATRIX-V1` est close.

Le préflight réel, strictement en lecture seule, de
`CALIBRATION-UI-CAMPAIGN-V1` est vert sous la capture
`20260822-222450-g4-k1-control-calibration-ui-campaign-v1`. Il confirme l'UI
inactive, la K1 au repos, les cibles à zéro, le Z accepté et le profil rapide
présents, ainsi que l'absence attendue des profils `9/11/15`. Le GO de campagne
envoyé avant la correction de matrice n'est pas consommé, car le protocole a
changé depuis. La campagne physique n'est pas autorisée.

Le premier départ humain `9 × 9` a exposé un piège de reprise : après annulation
à `0/6`, `replace_existing=true` restait hydraté dans le formulaire. Une seconde
reprise l'a donc renvoyé. Les deux tentatives ont été annulées avant toute
mesure ; le second arrêt de sécurité a été cliqué par Codex sur une tentative
déjà invalide. Les contrôles ont confirmé `standby`, cibles zéro, stockage Z
`ok`, Z accepté `−0,04 mm`, chemin `committed`, profil `6 × 6` présent et aucun
profil `9 × 9`.

`CALIBRATION-UI-RETRY-SAFETY-V1` est préparé comme correction statique séparée.
Après une reprise incomplète, il réinitialise une seule fois le remplacement et
la confirmation de plateau, tout en permettant ensuite un remplacement
volontaire. Son write-set est le seul `app.js`; aucun service, chauffage,
homing, mouvement, mesh ou Z n'est appelé. Les 179 tests sont verts et le
préflight réel de la capture
`20260822-231240-g4-k1-control-calibration-ui-retry-safety-v1` est vert.
L'autorité globale explicite du goal a couvert sa pose sans nouveau GO. Le même
identifiant a obtenu le déploiement et deux validations vertes. Seul `app.js` a
été remplacé après backup exact ; aucun service n'a été redémarré et aucune
action physique n'a eu lieu. Le vrai rendu reste à valider après authentification
humaine sur le tunnel neuf `127.0.0.1:4410`, isolé du cache Mainsail observé sur
`4409`.

Le tunnel `4410` a ensuite été recréé et son ancien processus en doublon retiré.
Les fichiers distants sont toujours présents et `app.js` porte exactement
l'empreinte du correctif. Le premier nouveau préflight de campagne a exposé un
faux KO local : il exigeait `idle`, alors que les deux arrêts avant toute mesure
laissent légitimement l'API en `cancelled`, `mesh_index=0`, backup disponible et
machine sûre. Le validateur accepte désormais uniquement soit un `idle` neuf,
soit ce cas de reprise borné à zéro mesure ; il refuse toujours une annulation
après le début des meshes. Le test ciblé est vert et la capture
`20260822-233717-g4-k1-control-calibration-ui-campaign-v1` a obtenu
`PREFLIGHT_CALIBRATION_UI_CAMPAIGN_V1_OK`.

Thomas a lancé le niveau `9 × 9` depuis l'écran avec le remplacement décoché.
La chauffe `55/140 °C`, la stabilisation `200 s`, le nettoyage et le homing ont
réussi. La première grille a parcouru la machine puis la tâche s'est arrêtée à
`1/6` avec `Le mesh ne contient pas le nombre de lignes attendu.` L'état privé
contient zéro matrice exploitable. L'arrêt automatique a coupé les chauffes ;
le Z accepté `−0,04 mm`, le profil robuste `6 × 6`, le stockage `ok`, le chemin
`committed`, les deux CFS et le `standby` sont intacts.

L'audit du firmware exact a invalidé l'hypothèse dynamique d'ADR-010 : le module
Creality `prtouch_v3` remplace `BED_MESH_CALIBRATE` et utilise le
`[bed_mesh] probe_count` chargé au démarrage, resté à `6,6`. Son parcours
spiralé exige une matrice carrée impaire, avec le `6 × 6` stock déjà prouvé.
ADR-011 et le paquet séparé
`G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-MATRIX-V1` ajoutent un adaptateur borné :
changement atomique après backup et avant chauffe, restart Klipper, relecture
de la valeur chargée, puis restauration après coupure des chauffes. Sa pose ne
touche pas `printer.cfg` à la pose et redémarre seulement le Moonraker dédié.
La capture `20260823-001724-g4-k1-control-calibration-ui-prtouch-matrix-v1` a
obtenu le déploiement et deux validations vertes. L'essai vide a ensuite été
restauré exactement : phase `rolled_back`, backup reconnu, `printer.cfg` de
base, Z `−0,04 mm`, profil `6 × 6`, runtime et chauffes conformes.

`G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-PRESETS-V1` retire le choix `4 × 4`
incompatible, conserve `3/5/6/9/11/15` et garde le refus serveur des matrices
paires. Le premier transfert a restauré automatiquement les deux fichiers après
un défaut de validation locale. La capture corrigée
`20260823-003755-g4-k1-control-calibration-ui-prtouch-presets-v1` a obtenu le
déploiement et deux validations vertes, sans restart ni action physique. Les 191
tests sont verts, avec 3 ignorés connus. Le préflight de campagne sous
`20260823-002500-g4-k1-control-calibration-ui-campaign-v1` est vert ; à ce stade
historique, la K1 était inactive et attendait le départ écran `9 × 9` avec une
confirmation fraîche du plateau libre.

Le départ `9 × 9` suivant, campagne
`20260823-004305-421-calibration-ui-v1`, a chargé `probe_count=9,9` mais conservé
`algorithm=lagrange`. Klipper a refusé cette combinaison au démarrage avec
XS3002, avant toute chauffe, homing ou mesure. Après la garde bornée, le rollback
automatique a restauré `6,6 + lagrange`. La campagne est `failed` à `0/6`,
Klipper est prêt, les chauffes sont à zéro, le Z `−0,04 mm`, le profil rapide,
le stockage et les deux CFS sont conformes.

Le candidat séparé
`G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-BED-MESH-V2` remplace seulement le
composant prtouch déjà installé. Il commute, vérifie et restaure atomiquement
`probe_count + algorithm`; `9/11/15` utilisent bicubique et `6` revient à
Lagrange. La première validation ne contrôlait pas `failed_components` : elle a
donc laissé passer un composant refusé parce que la K1 omet la ligne
`algorithm` lorsque `lagrange` est implicite. Aucun chauffage ni mouvement n'a
eu lieu. La révision corrigée conserve exactement cette absence au rollback et
vérifie le chargement réel. La capture
`20260823-012755-g4-k1-control-calibration-ui-prtouch-bed-mesh-v2-r2` a obtenu le
préflight, le déploiement et deux validations vertes ; `server/info` donne
`failed_components=[]` et `warnings=[]`. Le préflight complet
`20260823-013151-g4-k1-control-calibration-ui-campaign-v1` est vert. La K1 attend
le nouveau départ écran `9 × 9`.

Le départ suivant a créé la campagne
`20260823-021858-540-calibration-ui-v1`. Le journal exact montre
`g29_cnt=36`, puis `IndexError: list index out of range` dans
`prtouch_v2_wrapper.py` avant le point 37. Le contrôleur a donc échoué à
`mesh_index=1` sans matrice complète. L'arrêt et le rollback API ont restauré
`standby`, cibles zéro, axes non référencés, deux CFS conformes, Z accepté
`−0,04 mm`, stockage `ok` et profil robuste `6 × 6`.

La configuration usine expose trente-six tables de compensation par point. La
correction locale retire donc `9/11/15`, impose `6 × 6 + lagrange` et ramène le
compteur quotidien de six meshes à un seul. FIRST-CALIBRATION-V2 conserve sa
valeur de qualification initiale à six passages. Aucun changement
`pr_version`, retrait de tables usine ou autre contournement communautaire n'est
retenu.

Les tests hors imprimante sont verts : 220 réussites et 3 ignorés connus.
PRTOUCH-BED-MESH-V2, MATRIX-V1, RETRY-SAFETY-V1 et PRTOUCH-PRESETS-V1 ont été
validées séparément sur la K1. Après correction de deux faux KO locaux de chaîne
de manifests, le validateur CAMPAIGN-V1 renforcé a obtenu
`PREFLIGHT_CALIBRATION_UI_CAMPAIGN_V1_OK` sous la capture `20260823-171803`.
CAMPAIGN-V1 reste la seule gate quotidienne non exécutée physiquement.

The Orca cutover remains a later atomic gate. This runtime slice intentionally
keeps the active Orca profile, `START_PRINT` and the legacy `+0.27 mm`
post-processor unchanged.

Le 26 août, Thomas a ensuite choisi explicitement `CFS1 / slot A`, Geeetech PLA
noir. Une première commande sans engagement CFS n'a produit aucun débit. La
séquence CFS suivante a engagé le filament et obtenu une purge visible, mais
elle a imposé `220 °C` malgré une demande `190 °C`, puis référencé X/Y. Le
plateau, resté haut, a bloqué la zone du mécanisme arrière et la purge s'est
faite sur le plateau. Thomas n'a constaté aucun dommage visible.

La récupération a refait le homing proprement, contrôlé les butées X/Y et validé
à froid la position stock de purge `X=185,5 / Y=305 / Z=30 mm`. Thomas a confirmé
que `30 mm` est largement suffisant. Deux essais directs ont ensuite utilisé une
ancienne adresse DHCP et ont faussement fait conclure à une perte du lien.

La connexion canonique `k1max-root` a été requalifiée puis fixée localement sur
la réservation DHCP stable, avec vérification stricte de clé conservée par
`HostKeyAlias`. La relecture fraîche confirme `standby`, cibles zéro, robuste
chargé, Z accepté `−0,04 mm`, axes `xyz` et tête à la position sûre. L'adresse
privée reste dans la configuration locale ignorée ; elle n'est pas publiée.

ADR-017 remplace le problème « température CFS » par une frontière complète à
six invariants : buse, plateau, Z accepté, origine Z, mesh et axes référencés.
Le paquet `CFS-BOUNDARY-GUARD-V1` est validé hors imprimante et refuse la trace
réelle. Il n'autorise aucune pose ni action K1. La joignabilité courante est
verte, mais le Z/mesh transitoire exact pendant l'incident reste inconnu : une
relecture ultérieure de l'état sûr ne recrée pas cet état passé.

`CFS-BOX-WRAPPER-AUDIT-V1` est maintenant clos en lecture seule. Le binaire
capturé correspond à l'empreinte historique et son en-tête confirme un module
partagé ELF 32 bits MIPS little-endian. La fenêtre exacte de 12 800 lignes
prouve l'ordre : géométrie interne, choix matière `220 °C`, cible réelle
`220 °C`, puis purge qui conserve encore son argument `190 °C`. Le plateau est
resté à cible zéro pendant ce passage précis. Aucun G-code, mouvement, chauffage,
ordre CFS, restart ou fichier distant n'a été produit pendant l'audit.

ADR-018 ferme l'adaptateur stock. `BOX_EXTRUDE_MATERIAL` est refusée ;
`BOX_EXTRUDER_EXTRUDE` et `BOX_MATERIAL_FLUSH` restent non qualifiées faute de
preuve isolée. Le contrat hors imprimante conserve une liste de primitives
appelables vide et `deployment_candidate=false`.

`G4-K1-CONTROL-CFS-DYNAMIC-TEMP-ROUTING-V1` est maintenant close hors
imprimante. La base matière reste un filet statique, la réaffirmation post-`T`
une défense et l'interception de `get_material_target_temp` est refusée faute de
point d'extension stable et de séparation géométrique. ADR-020 choisit
`minimal_separate_filament_owner` avec un ticket par phase, une route fraîche
consommable une fois, des cibles distinctes de retrait/chargement/purge et les
six invariants inchangés. Le simulateur obtient `25/25` sur les deux CFS,
first/normal, filament engagé, chargement, changement, refill, runout,
pause/reprise, annulation et arrêts sûrs.

Ce résultat ne contient aucun transport K1 et reste
`deployment_candidate=false`. Il a ouvert uniquement la branche hors imprimante
`G4-K1-CONTROL-CFS-MINIMAL-OWNER-PROTOCOL-V1`. Aucune pose ni reprise physique
n'a été ouverte.

`G4-K1-CONTROL-CFS-MINIMAL-OWNER-PROTOCOL-V1` est maintenant close en KO
borné hors imprimante. Les quatre sources privées gardent leurs empreintes et
le binaire n'a été ni chargé, ni importé, ni exécuté. La carte nettoyée montre
des requêtes sur les adresses 1 et 2, mais une seule route d'effet `T1A` sur
l'adresse 1, slot A.

Retrait, coupe, purge isolée, B/C/D, effets sur le second CFS, intégrité de
trame, resynchronisation et exclusion du propriétaire stock restent non
prouvés. La liste appelable est vide. L'émulateur obtient `25/25` en bloquant
les doublons, pertes, réponses tardives, reconnexions et routes périmées. Ce
vert qualifie le refus, pas un protocole matériel. Aucune connexion K1, aucun
transport et aucun candidat de pose n'ont été créés.

`G4-K1-CONTROL-CFS-MINIMAL-OWNER-EVIDENCE-V1` est ensuite close en KO borné
hors imprimante avec une avancée : un ancien journal contient le retrait stock
`T1A`, ses deux requêtes `0x11`, deux réponses réussies, le timeout de 150
secondes et le capteur local passant de présent à libre. Le journal court étant
le préfixe exact du journal long, une seule observation est comptée.

Le CRC-8 public au polynôme `0x07` correspond à la réponse capturée. La requête
complète sur le fil, l'exclusion du propriétaire constructeur, B/C/D, le second
CFS, coupe, purge, arrêt et reprises après faute restent manquants. La source
publique détaillée utilise une autre table de commandes et n'est pas une preuve
du binaire local. La liste appelable reste vide et le protocole de capture
passive avait alors seulement été préparé ; sa gate réelle est maintenant close
ci-dessous.

`G4-K1-CONTROL-CFS-MINIMAL-OWNER-PASSIVE-CAPTURE-V1` est maintenant close. La
capture elle-même est OK : l'observateur n'a rien écrit sur le bus série, la
route fraîche était `T1A`, la macro constructeur `BOX_QUIT_MATERIAL` a terminé
et les deux phases de retrait ont répondu. Le premier CFS est passé de filament
`A` à aucun filament engagé, et les trois configurations contrôlées sont
restées identiques.

La promotion du protocole reste KO borné. La K1 a demandé `220 °C` puis a laissé
cette cible active après la fin. Une commande `%20` mal encodée a produit un
G-code inconnu malgré la réponse HTTP `ok`; `TURN_OFF_HEATERS` a ensuite ramené
réellement les cibles à zéro. Le capteur de la tête reste actif, donc le segment
après le cutter est encore présent. La coupe n'a pas de confirmation physique
indépendante. Les trames complètes, l'exclusion du propriétaire stock, les
autres routes et les fautes restent non qualifiées. `callable_messages=[]`.

La branche suivante proposée est
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-V1`, hors imprimante seulement. En langage
courant : encadrer la commande Creality avec des vérifications avant/après et
un arrêt systématique des chauffes, sans parler directement aux moteurs du CFS.

`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-V1` est maintenant close hors imprimante.
Le contrôleur refuse sans effet une machine occupée, deux CFS non confirmés, une
commande active ou une route ambiguë. Après une tentative unique de
`BOX_QUIT_MATERIAL`, il exige la fin stock, la route libérée et la commande CFS
vide, puis demande une fois `TURN_OFF_HEATERS` et vérifie les deux consignes à
zéro. La réponse HTTP seule ne suffit jamais et aucun retry automatique
n'existe. Le paquet n'a aucun transport K1 ni candidat de pose.

La branche suivante proposée est
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-LIVE-PREFLIGHT-V1`. En langage courant :
se connecter uniquement pour lire les vrais champs de la K1 et vérifier qu'ils
correspondent au contrat, sans envoyer de G-code, chauffer, retirer du filament
ou installer un fichier. Cette connexion exige un nouveau GO exact.

`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-LIVE-PREFLIGHT-V1` est maintenant close en
lecture seule. Deux états stables montrent Klipper prêt, la machine `standby`,
`T1/T2` connectés, `t_command` vide, les cibles à zéro et aucune route engagée.
Les configurations sont inchangées. Aucun G-code, fichier distant, service ou
effet physique n'a eu lieu.

La K1 n'expose aucun champ direct `stock_unload_state` et la capture historique
montre que `t_command` était resté vide pendant le retrait. Le garde a donc été
corrigé : le succès demande le retour sans erreur de la requête, la route
réellement libérée, `t_command` vide et les chauffes confirmées à zéro. L'état
courant est `BLOCKED_NO_ENGAGED_ROUTE`.

`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-OFFLINE-V1` est maintenant close
hors imprimante. L'adaptateur convertit une réponse K1 déjà nettoyée vers les
huit champs du garde sans réseau, processus ou commande. Une route absente et
un second CFS déconnecté sont traduits pour permettre un refus normal du garde ;
plusieurs routes, une unité incohérente, un champ absent ou une température
invalide sont refusés immédiatement.

Les dix exemples synthétiques ne contiennent aucune identité matérielle. La
matrice obtient `10/10`, les tests ciblés `17/17` et la suite complète `429`
tests exécutés, `426` verts et `3` ignorés connus. Aucun accès K1, G-code,
chauffe, mouvement, retrait, service ou fichier distant n'a eu lieu.

La branche suivante proposée est
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-LIVE-READ-ONLY-V1`. En langage
courant : lire un état K1 frais, retirer les identités avant la traduction et
vérifier uniquement le résultat, sans appeler le chemin d'effet du garde.

Cette gate est maintenant close OK en lecture seule. La capture privée
`20260827-110102-g4-k1-control-cfs-stock-unload-guard-adapter-live-read-only-v1`
contient deux lectures stables. `sn` et `uuid` sont retirés par projection sur
liste blanche avant l'adaptateur ; tout champ nouveau ferme la validation. Les
deux adaptations donnent `T1/T2` connectés, aucune route, commande CFS vide,
cibles zéro et `BLOCKED_NO_ENGAGED_ROUTE`. Les trois configurations gardent
leurs empreintes exactes.

Les tests ciblés obtiennent `61/61` et la suite complète exécute `443` tests,
dont `440` verts et `3` ignorés connus.

La réponse fraîche prouve aussi la valeur texte `None` pour les unités non
provisionnées `T3/T4`. Elle est désormais reconnue comme inactive, sans accepter
d'autres états inconnus. Le garde n'a pas été importé ni appelé. Aucun G-code,
fichier distant, service, chauffage, mouvement ou retrait n'a eu lieu ; aucun
transport ou candidat de pose n'existe.

`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-TRANSPORT-OFFLINE-V1` est maintenant close
OK hors imprimante. La couche simulée accepte uniquement
`BOX_QUIT_MATERIAL` et `TURN_OFF_HEATERS`, chacune au plus une fois. Un timeout,
une coupure ou un retour ambigu rend l'effet inconnu et interdit de renvoyer la
même commande. Les `13/13` scénarios sont verts. Aucun connecteur réel, réseau,
processus, G-code ou candidat de pose n'existe.

`GOAL-P4-OFFLINE-CYCLE-CFS-V1` est maintenant terminé. La machine d'états pure
couvre les `27/27` scénarios canoniques du démarrage à la fin, y compris
filament correct, absent ou incorrect, changements, runout, pause, reprise,
annulation, reboot et action séparée de désengagement. Le plan futur épingle
trois sources, trois destinations, les sauvegardes, le rollback et sept petites
tranches avec présence humaine, mais contient zéro commande distante. Les tests
ciblés du cycle obtiennent `20/20` et la suite complète exécute `476` tests,
dont `473` verts et `3` ignorés connus.

Le prochain Goal unique est `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1`. En langage
courant : se connecter pour comparer des états et délais frais au modèle local,
sans envoyer de commande, écrire de fichier ou provoquer un effet. Cette
connexion exige une autorité séparée ; elle n'est pas ouverte par le Goal 1.

Le pilotage macro est maintenant regroupé dans `GOALS.md`. Quatre grandes
sessions y couvrent successivement le système hors imprimante, sa vérification
réelle sans effet, les qualifications physiques supervisées et la bascule vers
le fonctionnement quotidien. Ce regroupement ne crée aucun Goal Codex et ne
change aucune autorité de connexion, de pose ou d'action physique.

Thomas explicitly rejected further sacrificial print campaigns on 2026-08-21.
The V3 + PATHS-V1 observation remains useful coexistence evidence but no longer
blocks offline product construction. L'autorité globale du Goal couvre la
campagne de calibration dans la tâche active et son préflight est désormais
vert. La production et le Goal 4 restent fermés.

Do not remove or disable the current Orca `+0.27 mm` post-processor. Its
retirement remains atomic with the later proven machine/Orca replacement.

Mise à jour du 28 août 2026 : les Goals 1 et 2 sont clos. Le Goal 3 reste en
cours à `2/7` exigences physiques passées. Le nettoyage automatique est clos
KO et remplacé par le nettoyage manuel obligatoire. Le `11 × 11` est le meilleur
profil actuel, mais aucun profil n'est qualifié robuste.

ADR-032 choisit K1 Control comme propriétaire complet du cycle CFS au-dessus de
petites primitives stock qualifiées séparément. Le préflight S12 a confirmé en
lecture seule le chargeur, le binaire, les commandes, les rappels, les deux CFS
et la valeur stock d'auto-remplacement à `1`, sans paire identique réelle.

`G4-K1-CONTROL-CFS-OWNER-CORE-OFFLINE-V1` est maintenant clos OK. Le moteur pur
obtient `21/21`, les tests ciblés `21/21` et la suite complète exécute `654`
tests, dont `651` verts et `3` ignorés connus. Il modèle un seul propriétaire,
les départs conserver/charger/changer, un remplacement identique entre les deux
CFS, l'absence de retry, le refus des rappels stock et la restitution exacte de
la valeur précédente. Avant une reprise, il compare aussi le contexte complet
de pause au lieu d'accepter un simple indicateur. Toutes ses intentions restent
non exécutables. Aucune connexion K1, commande, chauffe, mouvement, écriture
distante ou action CFS n'a eu lieu.

`G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1` est maintenant clos OK.
Sa matrice obtient `25/25`, ses tests ciblés `15/15` et la suite complète
exécute `669` tests, dont `666` réussis et `3` ignorés connus. Le garde pur
mémorise la valeur stock, borne désactivation et restauration à une tentative, exige deux
lectures stables et ferme toute issue ambiguë sans retry. Toutes les intentions
restent non exécutables. Aucune connexion K1, commande, chauffe, mouvement,
écriture distante ou action CFS n'a eu lieu.

La prochaine mission proposée est
`G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-READ-ONLY-V1`. Elle vérifiera la
forme de deux lectures fraîches et nettoyées sans appeler le garde ni produire
d'effet. Elle exige une autorité distincte de connexion en lecture seule ; le
premier essai réel restera une autre gate avec Thomas devant la K1.

## Not authorised yet

- Helper Script installation.
- `G4-K1-CONTROL-FOUNDATION-V1` forever: preflight KO, never deployed, name closed.
- `G4-K1-CONTROL-FOUNDATION-V2` forever: real attempts rolled back, name closed.
- Any reinstall, correction or extension of the completed
  `G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1` package.
- Any other Mainsail, Fluidd, Moonraker or `K1 Control` installation/change.
- Toute nouvelle pose, correction ou suppression du runtime
  `G4-K1-CONTROL-Z-MESH-RUNTIME-V1` désormais installé.
- Toute commande de calibration Z/mesh, chauffe ou homing du runtime avant une
  gate séparée explicitement approuvée.
- Toute correction, repose ou suppression du chemin installé
  `G4-K1-CONTROL-CALIBRATION-PATH-V1`.
- Toute nouvelle exécution de `G4-K1-CONTROL-FIRST-CALIBRATION-V1`, gate close
  et consommée.
- Toute nouvelle exécution de `G4-K1-CONTROL-FIRST-CALIBRATION-V2`, gate validée,
  consommée et close.
- Toute correction, repose ou suppression de l'interface
  `G4-K1-CONTROL-CALIBRATION-UI-V1` désormais installée.
- Toute correction, repose ou suppression du delta
  `G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1` désormais installé.
- Tout lancement de calibration depuis l'UI avant le préflight CAMPAIGN-V1
  accepté et vert.
- BTT Eddy preparation, installation, firmware or calibration.
- Firmware downgrade or replacement.
- Any SSH write other than the completed `G4-SSH-KEY` deployment.
- Service restart or reboot initiated by an agent.
- Macro or configuration modification.
- Z, mesh, temperature or CFS tuning.
- Any static material-specific CFS temperature candidate.
- Toute pose, tout transport K1 ou tout essai physique issu de
  `G4-K1-CONTROL-CFS-DYNAMIC-TEMP-ROUTING-V1`, qui reste une conception hors
  ligne non déployable.
- Toute utilisation d'une trame de
  `G4-K1-CONTROL-CFS-MINIMAL-OWNER-PROTOCOL-V1` : sa liste appelable est vide
  et sa gate est close en KO borné.
- Toute utilisation des trames observées par
  `G4-K1-CONTROL-CFS-MINIMAL-OWNER-EVIDENCE-V1` : elles restent historiques,
  non isolées et non appelables.
- Toute nouvelle connexion ou répétition de
  `G4-K1-CONTROL-CFS-MINIMAL-OWNER-PASSIVE-CAPTURE-V1`, désormais close et
  consommée.
- Toute connexion K1, pose ou essai physique de
  `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-V1`, désormais clos hors imprimante.
- Toute connexion de
  `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-LIVE-PREFLIGHT-V1` sans son GO exact ;
  cette gate est maintenant close et son GO consommé.
- Toute connexion ou action physique de
  `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-OFFLINE-V1`, désormais close
  hors imprimante et sans transport.
- Toute connexion, tout G-code ou essai réel issu de
  `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-TRANSPORT-OFFLINE-V1` et
  `GOAL-P4-OFFLINE-CYCLE-CFS-V1`, désormais clos hors imprimante.
- Toute connexion, commande, pose ou qualification physique issue de
  `G4-K1-CONTROL-CFS-OWNER-CORE-OFFLINE-V1`, désormais clos hors imprimante ;
  ses intentions ne sont pas exécutables.
- Toute connexion, commande ou action K1 issue de
  `G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1`, désormais clos hors
  imprimante et sans transport.
- Toute connexion de
  `G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-READ-ONLY-V1` sans une nouvelle
  autorité explicite ; même autorisée, cette gate ne pourra envoyer aucune
  commande ni appeler le chemin d'effet.
- Toute répétition ou extension de
  `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1`, désormais clos ; son ancienne
  autorité de lecture seule est consommée.
- Any import or change of Orca fields on the workstation profile.
- `G4-ZSAFE-START-V1` forever: this rejected name cannot receive a GO.
- Any future `K1-CONTROL-V1` deployment until a new exact G4 package exists and
  receives its own explicit approval.
- Toute réutilisation des commandes brutes de la purge CFS du 26 août.
- Toute pose ou tout essai du candidat d'adaptateur CFS tant que sa liste de
  primitives appelables reste vide.

## Current blockers

- Le couple Orca réellement sélectionné est maintenant capturé directement
  depuis OrcaSlicer `2.4.2`, avec les quatre empreintes machine/processus. Le
  départ ancien, le changement vide et le post-traitement actif
  `--start-z-offset 0.27` sont prouvés. La bascule atomique reste à construire,
  mais l'identité du profil actif n'est plus un blocage.
- The PETG G-code has no matching `P1-PETG.3mf` in the intake.
- Recovery artefacts and procedure have not been matched locally to the exact revision.
- The core `BOX_*` state machine is compiled and no readable source matched to
  the exact local binary has been found.
- The literal registration of `ACCURATE_HOME_Z` was not found in readable Python, although the underlying `G28` and PR Touch path is mapped.
- Parts of `ACCURATE_HOME_Z` remain non-observable, although pressure advance ownership is now measured.
- The corrected P5 cannot distinguish temperature ownership after its change
  because both the second filament and the stock CFS request `220 °C`.
- The large historical Z shifts have not been reproduced, although the late
  application and end-of-print erasure mechanisms are now directly proven.
- Long-run memory headroom and per-service use still need proof; the one-shot
  read-only capture confirms only the baseline.
- The exact Creality Klipper commit is unknown; the newly captured exact
  `bed_mesh.py` remains the implementation authority for the mesh adapter.
- The captured `save_variables.py` was rejected for final persistence because it
  rewrites directly. The original atomic store has now completed a real atomic
  write and final validation through FIRST-CALIBRATION-V2.
- Persistent named mesh commit is mapped and proven: the robust deterministic
  profile is retained without `K1_TRANSIENT`, and FIRST-CALIBRATION-V2 is closed.
- Every reference-changing Creality calibration path must be detected or
  wrapped so that an old accepted Z cannot survive a real recalibration.
- The compiled `BOX_*` owner contains or triggers a temperature write that the
  command `BOX_MATERIAL_FLUSH TEMP=190` did not prevent: `220 °C` was observed.
  The same boundary triggered X/Y homing. The exact binary and logs have now
  been inspected statically, but the protocol still lacks unload, cut, isolated
  purge, second-CFS effects, frame integrity and stock-owner exclusion proof.
- The pinned Moonraker/Mainsail package and its file-manager roots completed the
  retained coexistence observation and the final read-only validation.
- The historical transient Mainsail `Base` mesh is no longer current;
  FIRST-CALIBRATION-V2 retained the qualified profile
  `k1_p001_t055_r001_n06x06`.
- The real `K1 Control` adapter and offline Z/mesh guards exist. START_PRINT,
  Orca and CFS integration remain intentionally absent until their atomic
  contracts and rollback are complete.
- Standard daily calibration autonomy is reached. Advanced mesh autonomy is
  still absent until K1 Control can regenerate the composite and create, edit,
  qualify and roll back derived profiles without Codex.
- Production autonomy remains absent until the atomic Orca/START_PRINT cutover,
  removal of the legacy `+0.27 mm`, CFS temperature ownership and G5 proof.

## Exit condition for this phase

P3 has reached its exit condition. The P4 foundation slice is installed,
observed and retained. The three failed Z/mesh attempts are completely rolled
back. The corrected runtime is now installed and independently validated; its
empty state remains fail-closed until a separately authorised calibration.

## Mise à jour 2026-08-28 — exclusion propriétaire CFS live V1

`G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-READ-ONLY-V1` est close avec le
verdict `CLOSED_READ_ONLY_BLOCKED_CONNECTION_EPOCH_AND_EFFECTIVE_Z_SOURCE`.
Exactement deux lectures nettoyées ont montré un état stable, `T1/T2`
connectés, aucune route, chauffes zéro, profil `11 × 11` actif et configurations
inchangées. Aucun effet n'a eu lieu.

La projection ne peut pas ouvrir le garde : l'époque de connexion n'est pas
observable et la vraie valeur Z acceptée n'est pas exposée. `homing_origin` ne
la remplace pas. V1 est consommée et ne doit pas être rejouée. La prochaine
mission unique est
`G4-K1-CONTROL-CFS-OWNER-OBSERVABILITY-ADAPTER-OFFLINE-V2`, hors imprimante.

## Mise à jour 2026-08-28 — observabilité V2 et exclusion réelle

L'adaptateur V2 obtient `12/12` scénarios et distingue une connexion Moonraker
persistante des transitions CFS rapportées. Il lit le vrai Z accepté dans
`KCTRL_STATE` et refuse toute substitution par `homing_origin`.

La capture live
`20260828-194319-g4-k1-control-cfs-owner-observability-live-read-only-v2`
qualifie cette projection sans effet. La capture
`20260828-195248-g4-k1-control-cfs-owner-exclusion-guard-live-effect-v1`
qualifie ensuite une désactivation exacte `1 -> 0` et une restauration exacte
`0 -> 1`, une tentative chacune et deux preuves stables après chaque commande.
Le verdict est `CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED`.

L'état final est `standby`, chauffes zéro, axes libérés, `T1/T2` connectés,
aucune route, Z accepté `−0,04 mm`, mesh `11 × 11` et configurations inchangées.
Aucun filament, mouvement, fichier distant ou service n'a été touché. Les
captures sont consommées. Cette ancienne prochaine tranche a depuis été
installée, puis invalidée physiquement par R5.

## Mise à jour 2026-08-29 — incident R5 et pilotage caméra

Le run `20260829-goal3-thermal-r5-run-6174bcc` est clos KO sans retry. Thomas a
observé la purge hors du bac, l'absence du mouvement de décrochage et une
impression proche de `10 mm` au-dessus du plateau. L'annulation finale est
confirmée : état `cancelled`, cibles buse/plateau à zéro, axes libérés, tête
haute, `11 × 11` actif et aucune route CFS engagée.

ADR-033 remplace la partie « sans brosse » du départ possédé. Le candidat R3
reste hors imprimante et impose : référence grossière, purge dans le bac,
mouvement E4, image caméra propre, référence Z précise, ligne hors plateau,
seconde image, puis modèle. Le document 49 répartit clairement le travail entre
Codex et Thomas et prépare une future calibration Z assistée par image.

La tranche corrective suivante était
`G4-K1-CONTROL-CAMERA-REFERENCE-LIBRARY-AND-R3-COLD-VALIDATION-V1`, hors
imprimante puis à froid seulement. Elle doit construire le pilote caméra simple,
relire le candidat R3 et prouver ses deux pauses sans chauffe, extrusion ni
mouvement physique. Elle est maintenant close dans la mise à jour ci-dessous.
Le LiDAR reste hors périmètre.

## Mise à jour 2026-08-30 — pilote caméra et validation froide R3

`G4-K1-CONTROL-CAMERA-REFERENCE-LIBRARY-AND-R3-COLD-VALIDATION-V1` est close
avec `CLOSED_OK_CAMERA_READ_ONLY_AND_R3_COLD_VALIDATED`. Le pilote a résolu
`k1max-root`, pris une image fraîche `1280 × 720` par un seul `GET`, validé sa
netteté et extrait les zones buse, bac et plateau. Les trois comparaisons avec
`SAFE_IDLE_PARK` restent proches, puis la revue visuelle confirme seulement la
tête haute, le plateau descendu et l'absence d'activité visible. Aucune décision
sémantique automatique n'est produite.

La bibliothèque garde exactement une référence acquise : `SAFE_IDLE_PARK`.
Les cinq autres références restent absentes. La validation froide prouve les
deux blocages caméra, l'usage exclusif de `PAUSE_BASE/RESUME_BASE` et l'arrêt des
chauffes sur timeout sans confirmation d'image. Les `16` blocs Jinja de R3 ont
été parsés sur le Python existant de la K1 via stdin, sans fichier distant ni
G-code.

R3 reste hors imprimante. La prochaine gate chaude est fermée tant que Thomas
n'a pas réellement nettoyé la buse, nettoyé et libéré le plateau, puis réengagé
`T1A` avec la fonction officielle.

## Mise à jour 2026-08-31 — cycle intégré clos KO et confiné

Le candidat de cycle quotidien a été posé avec sélection explicite du G-code,
UI Mainsail, orchestration et fin propriétaire. Deux défauts sans effet ont
d'abord été corrigés : compatibilité du FileManager Moonraker Creality et noms
de macros sans chiffre interne.

Le premier effet réel s'est ensuite fermé KO pendant la réassociation du
filament physique `T1A`. `BOX_EXTRUDE_MATERIAL` a référencé X/Y, annoncé
`flush_temp: 220`, dépassé `220 °C`, vidé le mesh puis échoué sans engager la
route. Aucun chargement qualifié, retrait, nettoyage, palpage, purge ou départ
d'impression n'a suivi ; aucun retry n'a été lancé.

Les cibles sont revenues à zéro, le `11 × 11` a été restauré et la caméra
confirme un état visuel sûr. K1 Control est maintenant confiné avec
`authority_mode: offline`, `effects_enabled: false`, cycle `idle` et macros CFS
neutralisées. La K1 finale est `ready/standby`, buse proche de l'ambiante,
plateau froid, axes libérés, deux CFS connectés, aucune route et Z accepté
`−0,04 mm` intact.

Cette voie ne doit pas être rejouée. L'autonomie complète exige désormais un
propriétaire CFS borné qui ne délègue ni température ni géométrie à la primitive
stock. Une nouvelle gate intégrée est interdite avant une preuve de protocole
hors imprimante puis une qualification unique de chargement et de retrait.

## Mise à jour 2026-08-31 — propriétaire CFS direct vert hors imprimante

ADR-036 remplace la partie d'ADR-032 qui conservait des effets `BOX_*`. K1
Control possède maintenant directement les étapes CFS et ne garde du stock que
`auto_addr` et `serial_485` pour transporter les trames.

Le paquet `cfs-direct-owner-offline-v1` obtient `24/24` scénarios. Les trames
locales exactes de chargement et retrait sont encodées, `T1A..T2D` sont bornés,
les capteurs tête et après-cutter sont exigés, la température appartient à K1
Control, une route `T1A` perdue peut être réassociée sans moteur et deux cycles
complets passent sans retry. Aucun code tiers n'est copié.

Le cycle intégré attend désormais les preuves du propriétaire direct et ne
contient plus d'effet `BOX_*`. Le paquet installé sur la K1 reste cependant
confiné en mode `offline`; le nouveau propriétaire n'est ni posé ni
physiquement qualifié. La prochaine tranche est
`G4-K1-CONTROL-CFS-DIRECT-OWNER-INSTALL-DISABLED-V1`, sans chauffe, mouvement ou
effet filament.

## Mise à jour 2026-08-31 — candidat de pose désactivée prêt hors imprimante

Le paquet `cfs-direct-owner-install-disabled-v1` ajoute l'adaptateur Klipper
réel, la configuration `enabled: false`, six destinations distantes exactes,
un plan de backup/pose/validation/rollback et deux validateurs distants inertes.
Les `13/13` scénarios et `5/5` tests ciblés sont verts hors imprimante.

Dans l'état candidat, aucun objet série n'est pris, aucune commande stock n'est
remplacée et réassociation/chargement/retrait refusent avant leurs arguments.
Le futur mode actif est préparé mais non autorisé : dix-neuf entrées stock sont
alors bloquées, l'auto-remplacement doit déjà être à zéro et les deux CFS doivent
être connectés avant toute trame.

Le script de pose ne contient qu'un ajout de six fichiers, un include, un
`RESTART` Klipper et la remise du meilleur `11 × 11`; son rollback restaure le
`printer.cfg` exact et retire seulement ces fichiers. Le plan local est vert.
Aucune connexion K1, écriture distante, relance, chauffe, mouvement ou trame
CFS n'a eu lieu. La gate de pose reste ouverte et non autorisée.

## Mise à jour 2026-08-31 — propriétaire direct posé mais désactivé

La gate `G4-K1-CONTROL-CFS-DIRECT-OWNER-INSTALL-DISABLED-V1` est close OK sous
la capture `20260831-123137-g4-k1-control-cfs-direct-owner-install-disabled-v1`.
Une première tentative s'est arrêtée avant la copie du premier candidat parce
que le client Windows cherchait un serveur SFTP absent de la K1. Le rollback
automatique a restauré la base exacte, retiré toute destination candidate,
redémarré Klipper et remis le `11 × 11`; le préflight suivant était vert.

La reprise force le mode SCP compatible. Six fichiers et un include sont
maintenant présents. La validation intégrée et deux validations indépendantes
prouvent `enabled=false`, `phase=disabled`, transport série non pris, commandes
stock non remplacées, trois refus d'autotest et zéro trame CFS. Aucun chauffage,
mouvement, extrusion ou effet filament n'a eu lieu.

L'état final est `ready/standby`, cibles zéro, axes libérés, Z accepté
`−0,04 mm`, meilleur `11 × 11` actif, `T1/T2` connectés, commande stock vide et
aucune route logique. La pose est consommée. La prochaine gate unique est
`G4-K1-CONTROL-CFS-DIRECT-OWNER-PHYSICAL-LOAD-UNLOAD-V1`; elle devra activer le
propriétaire sous surveillance et qualifier un seul cycle direct `T1A`, sans
palpage, mesh, purge ou retry.

## Mise à jour 2026-09-02 — le Z accepté s'édite dans l'éditeur de maillage

L'éditeur de maillage (port `7130`) porte désormais le Z accepté du profil
affiché : la valeur enregistrée, la valeur en vigueur sur la machine, un champ
pour taper, un bouton pour reprendre la seconde, un bouton pour écrire.
L'écriture passe par `KCTRL_Z_SAVE`, qui reste l'unique écrivain ; le serveur
refuse d'avance un profil inconnu de Klipper, une valeur hors de ±2 mm ou une
valeur illisible, puis laisse la macro revérifier et répondre.

Chaîne complète prouvée sur la machine pendant l'impression de
`_CORPS_PLA_2h37m.gcode`, sans la perturber : lecture des deux valeurs, refus
d'un `Z=40`, refus d'un profil inconnu, refus lisible de la macro, et une
écriture réelle qui a réenregistré la valeur déjà en place — `0,04` — puis
retrouvée dans `k1-control-saved-vars.cfg`. Empreintes machine identiques au
dépôt. Doc 56, ADR-057.

Défaut corrigé en chemin : le refus d'une macro porte un vrai saut de ligne
dans son enveloppe JSON, que le parseur strict rejetait ; l'opérateur recevait
l'enveloppe entière au lieu de la phrase. L'enregistrement du maillage
bénéficie du même correctif.

La surextrusion à l'arrivée du remplissage sur les parois est diagnostiquée et
n'a rien à voir avec le maillage : `pressure_advance_smooth_time` vaut `0,040 s`
quand les rampes de freinage de la machine durent `0,029 s`, donc la correction
du Pressure Advance arrive en partie après la fin du trait. Le PA est déjà réglé
par filament — `0,03` imposé par le profil du trancheur. Aucune correction n'a
été appliquée : la calibration décisive est une impression. Doc 57.

## Mise à jour 2026-09-02 — les ondulations viennent du maillage

Le maillage `k1_p001_t055_r001_n11x11` en vigueur porte `0,076` à `0,082 mm`
d'ondulation crête à crête sur 60 mm de ligne droite, pour une hauteur de couche
de `0,200 mm` : 40 % de variation d'écrasement le long d'un même trait. 39 % de
ses écarts entre points voisins dépassent `0,030 mm`, la courbure locale monte à
`0,186 mm`. `fade_start: 5.0` applique ce maillage à 100 % jusqu'à 5 mm, donc la
même vague est rejouée sur vingt-cinq couches.

L'interpolation bicubique est hors de cause : la spline cardinale de Klipper a
été rejouée sur ce maillage, dépassement maximal `0,007 mm`.

La période de la vague est celle du maillage, 29 mm, ce qui explique qu'elle
n'apparaisse que sur les longs trajets. Les zones cassantes sont le bord gauche
(`x34`), le bord droit (`x266`) et une tache centrale autour de `x179`–`x208`
entre `y121` et `y208`.

Une plaque n'ondule pas de `±0,04 mm` tous les 29 mm : ce bruit est ajouté par
la mesure, soit par le palpeur — qui est la buse — soit par une feuille
magnétique qui ne repose pas à plat. Rien n'a été corrigé ; l'expérience qui
tranche est un repalpage après nettoyage. Doc 58.

## Mise à jour 2026-09-02 — les ondulations ne viennent pas du maillage

Longueur d'onde mesurée à la règle sur la pièce : **3 à 10 mm**. Les points du
maillage sont espacés de 29 mm, il ne peut rien produire de plus serré. Le
maillage est écarté ; le document 58 se trompait de cause.

L'input shaping en vigueur n'est pas un calibrage complet : `ei` à `57,2 Hz` sur
les deux axes, à 0,1 Hz près. La macro d'usine `inputshaper` ne lance
`SHAPER_CALIBRATE` que sur **Y**, et la macro `autotune_shapers` impose `'ei'`
avant toute mesure. La fréquence de X est une recopie de celle de Y, jamais
mesurée. L'accéléromètre `[adxl345]` est monté en permanence sur `nozzle_mcu` et
`[resonance_tester]` est configuré : la mesure de X ne demande aucun matériel.

Modifier le maillage n'a aucun effet sur l'input shaping — carte d'altitudes en
Z d'un côté, filtre de mouvement X/Y de l'autre. Le décalage du moteur Z non
plus, le Z n'étant pas filtré.

La disparition du défaut à la couche 4 n'est pas expliquée par la vibration :
`bottom_shell_layers: 3` fait qu'il n'y a plus de surface pleine à regarder à
partir de là, et `slow_down_layers: 3` fait de la couche 4 la **première** à
pleine vitesse — un défaut de vitesse y serait pire, pas absent.

Aucune mesure de résonance lancée, impression en cours. Les fréquences réelles
de X et Y restent inconnues. Doc 59.

## Mise à jour 2026-09-02 — input shaping mesuré sur les deux axes

Balayages réels à l'accéléromètre de tête, plateau vide, buse nettoyée.

| | Avant | Après |
| --- | --- | --- |
| X | `ei` à `57,2 Hz` | `ei` à `36,0 Hz` |
| Y | `ei` à `57,2 Hz` | `mzv` à `42,6 Hz` |

X était à 60 % de sa fréquence réelle : la valeur affichée était une recopie de
Y, produite par le code Creality qui annonce lui-même `copy_TestAxis_y_to_x`. À
270 mm/s, 36 Hz donne une ondulation tous les 7,5 mm, ce qui correspond aux 3 à
10 mm mesurés à la règle et au relief senti au doigt.

Le calibrage embarqué n'évalue qu'un seul filtre, `ei`, imposé par
`variable_autotune_shapers` dans `gcode_macro.cfg`. Les cinq filtres ont été
réévalués hors ligne sur les données brutes ; sur Y, `mzv` à `42,6 Hz` fait
mieux qu'`ei` sur tous les critères. Contrôle de méthode : `ei` sur Y retombe
exactement sur les chiffres annoncés par la machine.

Sur X, aucun filtre ne descend sous 14 % de vibrations résiduelles, et Y a perdu
11 % de fréquence depuis l'usine. Les courroies se sont détendues ; le réglage
appliqué améliore l'état actuel mais ne remplace pas une reprise de tension
suivie d'un nouveau balayage.

Piège découvert : `SHAPER_CALIBRATE` écrit dans `printer.cfg` sans qu'aucun
`SAVE_CONFIG` soit demandé. Sauvegarder avant, pas après.

Appliqué à chaud et écrit à la main dans le bloc `#*#`. Aucune impression
d'essai depuis : la preuve que le relief a disparu reste à faire. Doc 60.

## Mise à jour 2026-09-02 — deuxième série : courroies saines, resserrage utile

Après resserrage des vis par Thomas, quatre balayages : les deux axes et chaque
courroie CoreXY séparément.

Les courroies sont identiques à `0,3 Hz` près — `39,8` contre `40,1 Hz`, même
largeur de pic, même répartition d'énergie. Rien à retendre.

Le resserrage a servi : X est passé de `36,0` à `40,2 Hz`, l'énergie parasite
sous 30 Hz de `47,9` à `35,3 %`, et les cinq bosses larges se sont réduites à
une. Y est passé de `50,6` à `46,6 Hz` en `ei` ; la baisse n'est pas expliquée,
la première série était sur machine chaude et la seconde sur machine froide.

Il subsiste sur X un pic net à `14,0 Hz`, absent de Y (4,4 % d'énergie sous
30 Hz) et des deux courroies (1,3 et 1,5 %). Trop bas pour une courroie ou un
rail : une masse entière qui se balance latéralement — support, pieds, CFS,
panneaux. À 270 mm/s il produit des vagues de 19 mm, alors que le défaut mesuré
sur la pièce fait 3 à 10 mm : ce n'est pas lui qu'on voit, c'est le pic à 43 Hz.

En vigueur et dans `printer.cfg` : X `ei` à `40,2 Hz`, Y `mzv` à `39,0 Hz`,
vérifié dans la réponse de Klipper. `SHAPER_CALIBRATE` avait de nouveau écrit
seul dans le fichier (`46,6` recopié sur les deux axes), corrigé après coup.

Accélération conseillée : `3000` sur X, `4500` sur Y, contre `9500` dans le
profil du trancheur. Aucune impression d'essai depuis. Doc 61.
