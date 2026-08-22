# État réel avant bascule production

Date : 2026-08-22

Périmètre : lecture seule de la K1 et du profil Orca local, puis préparation
hors imprimante. Aucune commande G-code, chauffe, homing, extrusion, sélection
CFS, impression ou écriture distante n'a été exécutée.

## Orca réellement actif

La configuration locale OrcaSlicer indique la version `2.4.2` et sélectionne la
machine `Creality K1 Max (0.4 nozzle) - Copie`. Son association courante utilise
le processus `0.20mm - SpeedClassics - MultiMaterials`.

Les quatre fichiers exacts ont été copiés dans la capture privée ignorée
`20260822-210332-production-readiness-v1`. Empreintes :

| artefact privé | SHA-256 |
|---|---|
| machine JSON | `5fba496f37ad2a77c25204e9c6c7ed153baf801e29c308d76ff40b265e15eee3` |
| machine info | `0a68160d41f98466f6ea1f0a8f5d604dd3fa8ef0ef429864ec864461ff44a3c7` |
| processus JSON | `ad1afc98e4b6c3369837d4bcc461dd5f276c3a52c6e5b0cab71b1ac03006f84d` |
| processus info | `0c4ba839732bb59bec08fd4e5134942a12fce4188e76326a04b95eed868a7ce` |

Le départ actif exécute encore `G28`, sélectionne l'outil avant `START_PRINT`,
puis ajoute des consignes thermiques et des mouvements Z. Les champs fin et
changement de filament sont respectivement hérité/absent et vide. Le processus
actif appelle encore le post-traitement historique avec
`--start-z-offset 0.27`. Le retrait atomique de ce script est donc maintenant
fondé sur le profil réellement sélectionné, pas sur l'ancien export du 20 août.

## Points d'accroche CFS réels

L'objet Klipper `box` expose actuellement les indicateurs non secrets
`state`, `t_command`, `auto_refill`, `filament_useup` et `filament`. Deux unités
sont connectées et le refill automatique est actif. Ces champs permettent de
dater un chargement, un refill équivalent et un changement volontaire pendant
une impression utile.

La liste `gcode/help` n'expose toutefois comme commandes lisibles que les cinq
macros `BOX_CHECK_MATERIAL`, `BOX_INFO_REFRESH`,
`BOX_LOAD_MATERIAL_WITH_MATERIAL`, `BOX_LOAD_MATERIAL_WITHOUT_MATERIAL` et
`BOX_QUIT_MATERIAL`. Les commandes de départ, de sélection `Tn` et le cœur du
refill restent fournis par le module compilé. Cette observation confirme qu'un
propriétaire de température ne peut pas être déclaré fiable par simple wrapper
théorique.

Le traceur passif suit désormais les cinq indicateurs `box` en plus des
températures, positions et états d'impression. Il ne collecte ni inventaire de
bobines, ni couleur, ni identifiant CFS.

## État de décision

- le blocage « profil Orca actif non capturé » est levé ;
- les champs atomiques à remplacer et le `+0,27 mm` actif sont prouvés ;
- les gardes Z/mesh existent déjà côté machine, mais aucune macro
  `KCTRL_JOB_*` ou `KCTRL_TOOL_CHANGE_*` n'est installée ;
- le comportement CFS compilé reste la frontière réelle : la future gate doit
  d'abord observer `box.t_command` et la cible thermique pendant une impression
  utile, puis accepter ou refuser le propriétaire proposé ;
- aucune bascule production n'est autorisée avant la pose UI, sa campagne écran
  réussie et un paquet production séparé avec backup et rollback exacts.
