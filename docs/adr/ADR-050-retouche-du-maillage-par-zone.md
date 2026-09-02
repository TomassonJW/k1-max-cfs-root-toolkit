# ADR-050 — Retouche du maillage par zone, pas point par point

Date : 2026-09-01

Statut : **accepté** ; testé hors machine (37 cas), pas encore exercé sur une
retouche réelle

## Contexte

Le maillage `11 × 11` est descendu à `0,353 mm` d'amplitude et le centre est
jugé impeccable sur un carré imprimé. Ce qui reste est en périphérie, et Thomas
le décrit ainsi :

> le coin avant droit est vraiment un peu trop loin, le bord avant juste un peu
> trop loin de 0.01 environs, le bord droit un peu trop près de 0.02, le coin
> arrière droit 0.025 trop près, le bord du fond aussi

Trois choses se lisent dans cette phrase et elles dictent l'outil.

**Il raisonne par zone, pas par point.** Un éditeur point par point demanderait
soixante-douze commandes pour la couronne extérieure et la première intérieure.
Par bord et par coin, il en faut huit par couronne.

**Il exprime un écart observé, pas une valeur de maillage.** « trop près de
0,02 » est une observation de première couche. La convention du maillage est
inverse et non évidente : une valeur positive lève la tête, donc éloigne la buse
du plateau. Exiger de lui la traduction, c'est garantir une inversion de signe
un soir de fatigue — et une inversion double le défaut au lieu de le corriger,
sans rien signaler.

**Les corrections ne sont pas constantes le long d'un bord.** Le coin avant
droit et le bord droit qui le touche vont dans des sens opposés. Un bord et son
coin se jugent séparément.

## Décision

`KCTRL_MESH_EDIT` désigne une zone et lui applique une correction.

La zone se nomme par `EDGE` (`avant`, `fond`, `gauche`, `droit`, ou leurs
équivalents anglais), par `CORNER` (`avant_droit`, `arriere_gauche`, …), par
`COL`+`ROW`, ou par `X`+`Y` en millimètres. `RING` choisit la couronne : `0`
pour le périmètre, `1` pour la suivante. **Un bord exclut ses deux coins**,
`WITH_CORNERS=1` les réintègre. Les quatre bords et les quatre coins d'une
couronne la pavent exactement une fois, sans recouvrement.

La correction s'écrit `CLOSER=` ou `FURTHER=` — comme elle a été observée sur la
plaque — ou `DELTA=` en valeur de maillage pour qui sait ce qu'il fait. Une
seule des trois à la fois. `CLOSER` est toujours négatif quel que soit le signe
tapé : un signe en trop ne peut pas inverser l'intention.

Garde-fous : `0,15 mm` maximum par commande, valeur résultante bornée à
`± 2 mm`, `PREVIEW=1` pour lister les points sans rien écrire, `KCTRL_MESH_UNDO`
pour annuler la dernière commande.

**Le point de référence `X150 Y150` est refusé à l'édition.** Le profil vaut zéro
en ce point et chaque impression en dépend (ADR-046) ; le déplacer décalerait
tout le plateau au lieu d'une zone. Le levier prévu pour ça est le décalage Z.

L'édition modifie la matrice en mémoire **et** le fichier, puis recharge le
profil s'il est actif. C'est ce qui permet d'enchaîner plusieurs retouches puis
de juger, sans redémarrage entre chacune. Écrire seulement le fichier aurait
fait perdre toutes les corrections sauf la dernière, chaque commande relisant
l'état d'avant.

## Conséquences

- La couronne extérieure se corrige en huit commandes, seize avec la première
  intérieure.
- Une inversion de signe reste possible avec `DELTA`, jamais avec
  `CLOSER`/`FURTHER`. Le compte rendu de chaque édition dit en clair dans quel
  sens la buse a bougé.
- L'invariant « zéro au point de palpage » est préservé par construction,
  puisque la seule cellule qui pourrait le rompre est interdite.
- Le module doit être rechargé par un redémarrage du service Klipper pour que
  les commandes existent ; un `FIRMWARE_RESTART` ne recharge pas les modules
  Python.

## Voir aussi

- ADR-013 — maillage composite et limite de trente-six contacts
- ADR-046 — profil de maillage référé au point de palpage
- ADR-047 — plateau voilé et plancher mécanique
