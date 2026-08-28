# ADR-032 — Posséder le cycle CFS au-dessus de primitives stock choisies

Date : 2026-08-28

Statut : **décision acceptée et cœur propriétaire implémenté hors imprimante ;
aucune connexion, pose ou action physique autorisée**

## Contexte

Les captures de cette K1 Max ont déjà prouvé deux choses différentes :

- le matériel CFS et son pilote stock savent charger `T1A` et produire une
  purge visible ;
- les grandes séquences stock prennent aussi des décisions que nous refusons :
  cible cachée à `220 °C`, mouvements internes, brossage, remplacement du
  mesh, nouvelle référence Z et reprise implicite.

Le dernier départ réel a conservé le bon filament, mais `START_PRINT` a
remplacé le `11 × 11` par `default`, brossé une buse encore sale et produit
un décalage uniforme de première couche. ADR-031 a donc déjà retiré
`START_PRINT`, les `Tn`, la brosse et toute recalibration du futur chemin
possédé.

La question restante est plus large : faut-il remplacer tout le pilote CFS,
installer une solution publique, ou garder une partie du système Creality ?

## Sources recoupées

La cartographie publique la plus riche vient de HelixScreen et de la
décompilation documentée par FrederickAlt. Elles confirment la séparation entre
les grandes séquences `T*` et des phases plus petites comme
`BOX_EXTRUDE_MATERIAL`, `BOX_EXTRUDER_EXTRUDE`,
`BOX_CUT_MATERIAL` et `BOX_RETRUDE_MATERIAL`.

Elles montrent aussi des pièges importants :

- `BOX_MATERIAL_FLUSH` finit par un nettoyage de buse et retombe sur une
  température configurée à `220 °C` si la cible n’est pas fournie ;
- `BOX_ERROR_CLEAR` peut jeter un travail de reprise en attente ;
- `BOX_TNN_RETRY_PROCESS` peut aller jusqu’à reprendre une impression ;
- plusieurs phases ne font rien pendant l’état interne de reprise, sans état
  public permettant de le prévoir proprement ;
- l’auto-remplacement stock repose sur le type, la couleur, le capteur du slot
  et une remap interne.

HelixScreen a fait un vrai travail de cartographie du firmware, mais son propre
document précise qu’aucun comportement CFS de cette page n’a été validé sur une
K1 + CFS en fonctionnement. Son chemin K1 courant appelle encore une purge
stock et `BOX_NOZZLE_CLEAN`. Il ne répond donc pas à notre contrat sans
réécriture et validation physique.

Les projets CFSTool et gitstonelabs éclairent le bus RS485 et les machines
d’état, mais aucun ne constitue un pilote de production déjà qualifié pour
cette K1 Max S12. Les configurations SLICK1MAX, Nik-oli et DieDutchman
confirment que d’autres propriétaires rencontrent les mêmes frictions, mais
elles conservent des variantes de `START_PRINT`, `Tn`, KAMP ou des
mouvements que nos preuves ont déjà rejetés.

La carte exacte et les révisions examinées sont figées dans
`design/cfs-control-source-map-v1.json`.

## Options étudiées

### 1. Garder les grandes séquences stock

Rejeté. C’est le chemin le plus court à installer, mais il ne permet pas de
garantir la température, le mesh, le Z, l’absence de brosse ni l’absence de
reprise cachée. Les essais réels ont déjà montré son échec.

### 2. Installer HelixScreen comme propriétaire du cycle

Rejeté comme base directe. Son interface et sa lecture d’état sont utiles, mais
sa séquence K1 appelle encore les opérations que Thomas veut supprimer. Sa
validation CFS sur matériel K1 reste ouverte. Sa licence GPL-3.0 impose en plus
de ne pas copier son code dans ce dépôt sans décision de licence séparée.

### 3. Remplacer immédiatement Creality par un pilote RS485 maison

Reporté. Cela donnerait le contrôle maximal, mais obligerait à requalifier les
trames, les moteurs, les erreurs, les deux unités, les reconnexions et toutes
les sécurités matérielles. Nos anciennes captures ne suffisent pas à rendre les
messages d’effet appelables. Ce serait le chemin le plus long et le plus
risqué pour retrouver rapidement une impression fiable.

### 4. K1 Control au-dessus de primitives stock choisies

Accepté. Le pilote Creality reste chargé pour parler aux deux CFS et exécuter
uniquement des phases matérielles expressément qualifiées. K1 Control possède
le cycle complet : intention du job, températures, ordre des phases, mesh, Z,
purge, pause, reprise, auto-remplacement, journal et rollback.

## Décision

L’architecture cible comporte cinq couches simples :

1. Un profil Orca cloné envoie une seule demande de job versionnée. Il
   n’émet ni `START_PRINT`, ni `Tn`, ni offset Z caché.
2. Le composant Moonraker K1 Control garde l’état du cycle et un verrou
   garantissant qu’un seul propriétaire agit.
3. Une petite couche de macros `KCTRL_*` exécute des actions bornées et
   vérifie l’état avant et après chaque phase.
4. Le `box_wrapper` stock ne sert plus de chef d’orchestre. Il ne peut
   exécuter que les petites phases CFS qualifiées une par une.
5. Les deux CFS gardent leur firmware et leur bus actuels.

La chauffe, le mesh, le Z, la purge et la position de reprise restent des
actions K1 Control/Klipper. Elles ne sont jamais déléguées à une grande macro
CFS.

Les primitives `BOX_EXTRUDE_MATERIAL`,
`BOX_EXTRUDER_EXTRUDE`, `BOX_CUT_MATERIAL` et
`BOX_RETRUDE_MATERIAL` sont seulement des candidates. Cette ADR ne les rend
pas encore appelables. Leur présence et leurs effets exacts doivent d’abord
être recartographiés sur le binaire S12 local, puis chaque phase doit passer une
gate physique unique et bornée.

`BOX_MATERIAL_FLUSH`, `BOX_MATERIAL_CHANGE_FLUSH` et
`BOX_NOZZLE_CLEAN` restent exclus du cycle possédé. La purge sera une recette
`KCTRL` avec température, longueur, vitesse et destination explicites, sans
brosse. Les chemins de runout stock `BOX_CHECK_MATERIAL_REFILL`,
`BOX_EXTRUSION_ALL_MATERIALS` et `BOX_RESUME_EXTRUDE` sont également
exclus tant que K1 Control possède le job.

## Démarrage

ADR-031 reste la règle. Après confirmation du nettoyage manuel :

- le plateau et la buse chauffent sans attente inutile ;
- X/Y sont référencés pendant la montée ;
- une seule référence Z propre est faite à `140/55 °C`, avant tout nouvel
  effet filament ;
- le `11 × 11` et le Z accepté sont chargés puis relus ;
- le filament correct déjà engagé est conservé ;
- la purge propre et l’impression commencent sans autre palpage.

Le démarrage ne mesure jamais un mesh et ne persiste jamais un nouveau Z.

## Auto-remplacement après fin de bobine

La fonction est conservée, mais elle appartiendra à K1 Control, pas au workflow
stock.

Quand le propriétaire personnalisé est actif, l’auto-remplacement stock devra
être désactivé avec une valeur explicite, après lecture et sauvegarde de son
état précédent. Le mode CFS général ne sera pas modifié tant que sa relation
exacte avec les capteurs et le runout S12 n’aura pas été cartographiée.

Un remplacement automatique ne sera possible que si un seul slot disponible
porte la même référence de filament validée par Thomas, le même type, la même
couleur, le même diamètre et une recette thermique compatible. Le capteur
matériau de ce slot doit aussi être actif et la cartographie fraîche.

Le cycle met d’abord l’impression en pause, conserve position, mesh, Z,
températures et outil logique. Il détermine ensuite, avec des capteurs frais, où
se trouve encore la fin de l’ancienne bobine. Une recette physique encore à
qualifier consommera ou retirera ce segment une seule fois, avant le chargement
du remplacement. Le cycle ne fait ni homing, ni palpage Z, ni calibration de
mesh, ni brossage. Il purge à température explicite, revérifie l’état complet
et reprend seulement si tout concorde. Une ambiguïté laisse l’impression en
pause ; elle ne déclenche jamais un retry ou une reprise stock.

Cette décision garantit que la fonction existe dans notre version. Elle ne
prétend pas qu’elle est déjà implémentée ou physiquement qualifiée.

## Interface

Le pilotage quotidien sera ajouté à la page K1 Control déjà ouverte depuis
Mainsail. Mainsail restera disponible pour l’état détaillé et les commandes
expertes `KCTRL_*`. Il n’est pas nécessaire de remplacer l’écran stock, le
firmware CFS ou Moonraker.

## Rollback

La pose future sera additive : noms `KCTRL_*`, include versionné, composant
Moonraker épinglé, extension de la page K1 Control et profil Orca cloné. Les
corps des macros stock ne seront pas réécrits.

Avant activation, le déployeur devra sauvegarder les configurations exactes,
leurs empreintes, le mesh, le Z accepté, l’état de l’auto-remplacement stock et
le profil Orca précédent. Le rollback bloquera d’abord tout nouveau job K1
Control, attendra un état physique sûr, restaurera les fichiers exacts,
redémarrera seulement les services nécessaires, restaurera l’ancien réglage
d’auto-remplacement puis vérifiera les empreintes, chauffes, routes, mesh et Z.

Un rollback fonctionnel signifie revenir exactement au système précédent. Il
réintroduira donc aussi les défauts connus du démarrage stock ; il ne faut pas
le présenter comme une meilleure séquence.

## Conséquences

Cette décision réutilise le travail public et toutes nos captures sans refaire
un pilote complet. Elle réduit fortement le volume à requalifier, garde les
deux CFS, permet une interface Moonraker/Mainsail et conserve un rollback
simple.

Elle impose en contrepartie deux validations avant le développement du chemin
d’effet :

1. une cartographie S12 fraîche en lecture seule des commandes, arguments,
   callbacks de runout, fins de print, états de reprise, nettoyages de mapping
   et empreintes ;
2. des gates physiques séparées pour charger sans flush stock, couper,
   retirer, changer d’un CFS à l’autre et simuler une fin de bobine.

La gate `G4-K1-CONTROL-CFS-S12-OWNER-PREFLIGHT-V1` est maintenant close en
lecture seule. Le document 44 lie le chargeur, le binaire, 66 noms `BOX_*`, les
rappels de runout et de reprise, les états publics et les configurations à
cette S12 exacte. Les signatures d'arguments publiques sont corrélées à cette
surface, mais aucun effet n'est qualifié.

La gate `G4-K1-CONTROL-CFS-OWNER-CORE-OFFLINE-V1` est maintenant close. Son
moteur pur obtient `21/21` scénarios : verrou à un seul propriétaire, décisions
de départ, remplacement strictement identique entre `T1` et `T2`, invalidation
sur reconnexion ou rappel stock, aucune reprise d'un effet incertain et
restauration exacte de la valeur précédente d'auto-remplacement. Toutes les
intentions restent non exécutables et aucun comportement matériel n'est promu.

La gate `G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1` est maintenant
close. Son garde pur obtient `25/25` scénarios : sauvegarde exacte, deux lectures
stables, une tentative maximale, refus d'un acquittement sans effet et
restauration exacte. Toutes ses intentions restent non exécutables et aucun
comportement matériel n'est promu.

La gate live V1 est ensuite close après exactement deux lectures fraîches,
nettoyées, stables et sans effet. Elles ne qualifient pas l'adaptateur : aucune
époque de connexion n'est observable et la vraie valeur Z acceptée n'est pas
présente dans la projection. `homing_origin` ne peut pas lui être substitué.

La prochaine gate proposée est
`G4-K1-CONTROL-CFS-OWNER-OBSERVABILITY-ADAPTER-OFFLINE-V2`. Elle reste hors
imprimante ; elle doit résoudre ces deux sources avant toute nouvelle lecture
live ou tout effet réel.
