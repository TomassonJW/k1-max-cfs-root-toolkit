# 16 — Préparation de `G4-K1-CONTROL-Z-MESH-RUNTIME-V1`

Date : 2026-08-21

Statut : **deuxième essai réel rollbacké, baseline exacte restaurée ; candidat renommé et rollback renforcé hors imprimante, nouveau GO requis**

## État d'exécution du 2026-08-21

Thomas a envoyé le GO exact. Le premier préflight s'est arrêté sans mutation :
le Python distant recevait `0` comme nom de fichier au lieu de lire le programme
fourni sur stdin. Les deux appels concernés utilisent maintenant explicitement
`python -` avant leurs arguments. Un test de non-régression couvre ces deux
formes.

Le second préflight, toujours en lecture seule, est vert sous la capture privée
`20260821-212431-g4-k1-control-z-mesh-runtime-v1` : machine `standby`, chauffes
demandées à zéro, fondation intacte, empreinte `printer.cfg` conforme, cibles
runtime absentes et deux CFS `1.1.3` connectés. Les axes étaient référencés et le
mesh transitoire `Base` actif ; ce sont des états acceptés avant le redémarrage
hôte prévu par la pose.

Aucune sauvegarde distante, copie, inclusion, donnée runtime, commande Klipper
ou relance de service n'a été exécutée. La correction modifie une commande revue
après le premier GO : le déploiement attend donc un nouveau GO exact.

## Essai et rollback de la capture `20260821-213732`

Le GO renouvelé a ouvert une pose réelle. Le préflight et le backup étaient
verts. Après l'installation et le restart hôte, la validation a refusé l'état
initial : un stockage neuf `integrity=empty` suivait la branche invalide et
laissait `ready=0`. La garde sans mouvement n'a pas été appelée.

Le rollback a retiré les cibles puis redémarré Klipper. Son contrôle immédiat a
rencontré T1 encore en reconnexion. Le restart a aussi normalisé les espaces des
blocs générés `bed_mesh default` et `auto_addr`, sans changer leurs valeurs. Une
complétion bornée a restauré une dernière fois le backup exact sans autre
restart. Le préflight final confirme le hash initial, le runtime absent,
`standby`, axes non homés, chauffes à zéro, T1/T2 `1.1.3` et fondation intacte.

Le mesh actif `Base` était transitoire et a été perdu au restart ; le profil
persistant `default` est redevenu actif. Aucun mouvement, homing, chauffe,
extrusion, ordre CFS, calibration, impression, firmware restart ou reboot n'a
été exécuté.

La correction distingue maintenant l'état `empty` : le stockage devient prêt
pour commencer une calibration, tout en gardant `accepted_z_valid=0`,
`low_moves_armed=0` et `block_reason=no_accepted_z`. Le déployeur attend la
stabilisation complète de Klipper et des CFS, puis restaure une seconde fois le
backup exact après le restart du rollback. Les 96 tests sont verts à 95 + un
skip local ; les 17 templates et le rendu `empty` passent sur le Python/Jinja
exact de la K1.

## Essai et rollback de la capture `20260821-224828`

Un nouveau GO exact a ouvert la pose renforcée. Le préflight et le backup
étaient verts. Après pose et restart hôte, les objets runtime existaient mais
`ready` restait à zéro pendant tout le délai. Le journal Klipper a donné la
cause exacte : `K1_CONTROL_LOAD_STATE` était reçu comme commande inconnue `K1`.

La source `gcode.py` de cette machine utilise le découpage
`([A-Z_]+|[A-Z*/])`. Un chiffre au milieu d'une commande étendue termine donc le
nom : toutes les commandes prévues `K1_*`, y compris la commande Python de
sauvegarde, étaient incompatibles. Elles portent désormais le préfixe sans
chiffre `KCTRL_*`. Un test rejoue le découpage exact de Creality sur chaque nom
du runtime et sur `KCTRL_STATE_SAVE`.

Le rollback automatique a bien retiré le runtime et son inclusion, mais a
restauré le backup exact avant la fin d'un `CXSAVE_CONFIG` différé du démarrage
Creality. Seuls les espaces des blocs générés `bed_mesh default` et `auto_addr`
ont de nouveau changé. Après vérification de la copie temporaire et du backup,
une complétion bornée a restauré l'empreinte exacte sans restart. Le préflight
final est vert : runtime absent, profil `default`, `standby`, axes non homés,
chauffes à zéro, deux CFS `1.1.3` et fondation intacte.

Le rollback attend maintenant le déchargement du runtime, la reconnexion des
deux CFS et une fenêtre silencieuse bornée avant la restauration finale. Il
attend encore trois secondes puis revérifie l'empreinte exacte pour détecter une
écriture tardive. Aucun mouvement, homing, chauffe, extrusion, ordre CFS,
calibration, impression, firmware restart ou reboot n'a été exécuté.

La suite locale passe désormais `98/98`. Une validation uniquement en mémoire
avec le Python/Jinja exact de la K1 compile le module, parse les 17 templates et
valide 18 noms de commandes : `K1_EXACT_RUNTIME_OK templates=17 commands=18`.
Les commandes et les deux empreintes ayant changé, ce candidat reste strictement
hors imprimante jusqu'à une nouvelle revue.

## Décision opérateur

Une impression utile réussie ne suffit pas à exclure les défauts aléatoires
rapportés. Thomas refuse une nouvelle campagne d'impressions sacrificielles et
demande la mise en œuvre des protections. L'observation de la fondation peut
continuer comme preuve de coexistence, mais elle ne bloque plus la construction
hors imprimante.

Le prochain lot fonctionnel traite ensemble la propriété du Z, le choix du
mesh et l'ordre sûr de démarrage. Le retrait de l'actuel post-traitement Orca
`+0,27 mm` reste interdit tant que son remplacement complet n'est pas prouvé et
prêt à être activé atomiquement.

## Fait nouveau issu de Mainsail

Thomas a lancé manuellement une calibration depuis Mainsail après avoir référencé
les axes. La lecture Moonraker postérieure a confirmé :

- état machine `standby`, axes `xyz` référencés et chauffes à zéro ;
- profil actif `Base` couvrant `5–295 mm` sur X et Y ;
- matrice mesurée `6 × 6`, interpolation Lagrange et `mesh_pps=2,2` ;
- amplitude des 36 points mesurés d'environ `0,446 mm` ;
- profil `Base` absent de `printer.cfg`, donc non persistant ;
- seul l'ancien profil `default` reste enregistré dans `printer.cfg`.

Ce résultat prouve que le bouton générique de Mainsail ne fournit ni orchestration
Creality sûre, ni choix explicite de densité, ni qualification, ni persistance
compréhensible du profil.

## Contrat du planificateur mesh

Le premier composant codé est volontairement hors imprimante. Il transforme un
contexte explicite en plan borné et ne transmet aucun G-code.

Presets :

| Nom | Matrice | Points | Usage |
|---|---:|---:|---|
| `quick` | `6 × 6` | 36 | équivalent à la configuration capturée |
| `standard` | `9 × 9` | 81 | compromis courant |
| `precise` | `11 × 11` | 121 | référence complète recommandée |
| `expert` | `15 × 15` | 225 | diagnostic ou besoin local confirmé |

Le mode expert accepte de `3` à `25` points par axe. La zone reste obligatoirement
dans la plage revue `5–295 mm`. Jusqu'à `6 × 6`, l'algorithme reste Lagrange ;
au-delà, il devient bicubique pour éviter la limite d'oscillation documentée de
Lagrange.

Un profil de référence est identifié par plaque, plage de température, révision
de la référence capteur et matrice. Un mesh adaptatif reçoit une zone de travail,
reste transitoire et ne peut jamais être réutilisé comme profil global.

## Qualification avant acceptation

Une matrice plus dense ne suffit pas. Deux mesures comparables doivent avoir les
mêmes dimensions et rester dans une tolérance point par point. La tolérance
initiale hors imprimante est `0,025 mm` ; elle devra être confirmée pour le PR
Touch exact avant la gate de déploiement. Une matrice vide, non rectangulaire,
non finie, hors zone ou trop dense est refusée.

## Suite de construction

1. ~~raccorder le planificateur au vrai adaptateur Moonraker en lecture seule~~ ;
2. ~~ajouter l'état persistant Z/mesh et les macros originales de garde~~ ;
3. ~~comparer le stockage `save_variables` minimal au coût d'une écriture
   atomique originale, puis figer le choix~~ ;
4. produire le contrat Orca atomique et son contrôle sans extrusion ;
5. préparer sauvegardes, empreintes, installation et rollback ;
6. seulement alors présenter tous les fichiers et commandes pour un GO exact
   `G4-K1-CONTROL-Z-MESH-RUNTIME-V1`.

Le lot suivant, séparé pour le rollback, portera la propriété dynamique des
températures pendant les opérations des deux CFS.

## Sources exactes et candidat runtime

Les modules réellement présents sur le firmware ont été copiés en lecture
seule dans une capture privée ignorée et vérifiés par SHA-256 :
`save_variables.py`, `gcode_macro.py`, `delayed_gcode.py`, `gcode.py` et
`bed_mesh.py`.
Ils confirment le chargement différé de l'état, les littéraux Python des
variables, les paramètres dynamiques du mesh et le redémarrage imposé par
`SAVE_CONFIG`.

Le candidat public est sous
`packages/k1-control-v1/z-mesh-runtime-v1/`. Il ne remplace pas `START_PRINT`,
ne contient aucun appel CFS, aucune extrusion et aucun mouvement bas. Il ajoute :

- un enregistrement Z composite versionné, avec contexte et précédent complet ;
- les actions explicites démarrer, ajuster, accepter, annuler, restaurer et
  invalider ;
- le préchauffage plateau/buse et la stabilisation bornés ;
- un homing explicite avant mesh, ce qui évite l'erreur « Must home axis first » ;
- une matrice 3–25 points par axe avec Lagrange limité à 6 et bicubique au-delà ;
- une mesure transitoire, un nom de profil déterministe et une acceptation mesh
  séparée qui retire le profil transitoire avant `SAVE_CONFIG` ;
- une garde qui reste fermée tant que le profil et le Z effectifs n'ont pas été
  relus et comparés.

Le `save_variables.py` constructeur a été écarté : une coupure au mauvais moment
pourrait laisser un fichier tronqué et empêcher Klipper de charger la
configuration. Le candidat utilise maintenant `k1_control_store.py`, un module
original ciblé qui valide les 17 champs, ajoute une somme SHA-256, écrit en
`0600`, synchronise, remplace atomiquement et garde une copie précédente.
L'intégrité douteuse bloque la production ; la copie précédente n'est jamais
réactivée silencieusement.

## Pose candidate exacte

La nouvelle pose corrigée n'est pas encore autorisée. Son plan est figé par
`deployment-manifest.json` et
`scripts/deploy-k1-control-z-mesh-runtime-v1.ps1`.

État initial obligatoire :

- carte S12, structure `0`, firmware `2.3.5.34` ;
- Klipper `standby`, fichier vide, chauffes demandées à zéro, deux CFS `1.1.3` ;
- fondation V3 + PATHS-V1 intacte ;
- `printer.cfg` SHA-256
  `272640237e20659cf01f3268ed4cb0282b098c3d613e94bf84a3b80caac3c3b0` ;
- aucune cible, inclusion ou donnée runtime déjà présente.

Écritures prévues :

1. sauvegarder `printer.cfg` et vérifier son empreinte ;
2. ajouter `/usr/share/klipper/klippy/extras/k1_control_store.py` ;
3. ajouter `/usr/data/printer_data/config/k1-control-z-mesh.cfg` ;
4. insérer exactement `[include k1-control-z-mesh.cfg]` après
   `[include box.cfg]` ;
5. exécuter le `RESTART` hôte Klipper exact, sans firmware restart.

Le `printer.cfg` attendu après insertion a pour SHA-256
`fa8c25b0bc79f94bcdf1c1bca2c48c3d892ca42854cf277962580680d5767f05`.
Le fichier runtime corrigé a pour SHA-256
`1590b918dcdfe70e801c0be40fee4f19ab6b1e2dfa93936975b88aed5d4b1c79`.
Le module de stockage corrigé a pour SHA-256
`696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede`.
Le profil Orca, son post-traitement `+0,27 mm`, `START_PRINT`, les fichiers
constructeur, le CFS et la fondation ne sont pas modifiés par ce gate.

## Validation sans extrusion

Après le redémarrage hôte : Klipper doit être prêt, au repos, chauffes à zéro,
axes non référencés, deux CFS connectés, état atomique `empty`, aucun Z accepté
et garde basse fermée. Le déployeur appelle ensuite uniquement
`KCTRL_PRODUCTION_ASSERT_ARMED`. Le refus est obligatoire et les températures,
la position et l'origine G-code sont comparées avant/après. Aucune chauffe,
homing, calibration, extrusion, sélection CFS ou impression n'est exécutée.

## Rollback exact

Le rollback vérifie d'abord le backup, archive avec empreintes toute donnée Z
`current`, `previous` ou temporaire, restaure le `printer.cfg` original, retire
les deux fichiers ajoutés et les données runtime, puis recharge Klipper. Si la
socket Klipper est indisponible, le seul secours est le restart du service exact
`S55klipper_service`. L'état final exige les empreintes initiales, l'absence du
runtime, les services/ports de fondation et les deux CFS conformes. Le rollback
attend aussi la fin des écritures de démarrage Creality avant la dernière
restauration et revérifie ensuite que l'empreinte reste exacte.

Le seul texte d'approbation renouvelé valable après revue de la correction est :

`GO G4-K1-CONTROL-Z-MESH-RUNTIME-V1`
