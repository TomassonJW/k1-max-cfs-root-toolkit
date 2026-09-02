# ADR-047 — Le plateau est voilé : plancher mécanique et fin du réglage aux vis

Date : 2026-09-01

Statut : **accepté, mesuré trois fois sur la machine réelle**

## Contexte

Le réglage du plateau se faisait jusqu'ici en imprimant un maillage `11 × 11`
puis en lisant les valeurs des quatre coins. Chaque itération coûtait vingt-cinq
minutes pour un ajustement mécanique qui ne demande qu'un plan.

Le passage à une mesure dédiée a produit trois faits nouveaux.

### Les vis ne sont pas aux coins et leur position devait être mesurée

Les coordonnées publiées par la communauté mélangent K1 et K1 Max. La position
réelle a été relevée sur la machine : plaque retirée, buse amenée au-dessus de
chaque vis, position signalée par un mouvement d'un millimètre en Z pendant
l'enregistrement de la trajectoire de la tête.

| vis | X | Y |
| --- | --- | --- |
| avant-gauche | 18,5 | 23,7 |
| avant-droit | 276,5 | 23,7 |
| arrière-gauche | 48,5 | 273,7 |
| arrière-droit | 246,5 | 273,7 |

La paire avant couvre 258 mm, la paire arrière seulement 198 mm et décalée vers
la droite. Une position devinée à 20 mm près coûte 0,05 mm de correction sur un
plateau incliné de 0,7 mm de bout en bout, soit l'ordre de grandeur de l'erreur
recherchée : deviner n'était pas acceptable.

### Le plan ajusté ne désigne pas les vis d'un plateau voilé

La première version évaluait la hauteur de chaque vis sur le plan ajusté aux
moindres carrés. Sur un plateau plan, c'est équivalent. Sur celui-ci, le plan
passe loin des coins et **inversait le classement des deux vis avant** : il
désignait l'avant-droit comme la vis à serrer le plus alors que la grille
palpée place l'avant-gauche 0,10 mm plus haut. Agir dessus aurait accentué
l'inclinaison.

La hauteur d'une vis se lit désormais par interpolation bilinéaire de la grille
réellement palpée. Le plan ne sert plus qu'à quantifier le voile.

### Le voile est dans la tôle, pas dans la précontrainte

L'hypothèse d'un bombement induit par un serrage excessif des quatre coins a
été formulée puis **réfutée par la mesure** : après desserrage différentiel, le
voile est resté identique en amplitude comme en forme.

| passage | inclinaison entre vis | écart au plan |
| --- | --- | --- |
| avant réglage | 0,262 | 0,151 |
| après première correction | 0,214 | 0,146 |
| après desserrage | 0,114 | 0,152 |

La forme est stable sur les trois mesures : centre haut d'environ `+0,11` à
`+0,15`, quatre bords bas de `−0,04` à `−0,15`. C'est un bombement de la plaque.

## Décision

Le réglage aux vis vise l'inclinaison entre vis et **s'arrête là**. Le voile
d'environ `0,15 mm` est le plancher mécanique de cette machine ; aucune vis ne
le corrige, et le maillage `11 × 11` existe précisément pour l'absorber.

Un agent ne renvoie pas Thomas aux vis pour une erreur qu'aucune vis ne peut
atteindre. Le rapport de mesure affiche l'écart au plan et le dit explicitement
quand il dépasse `0,05 mm`.

Le sens de rotation est établi sur cette machine : **visser éloigne le plateau
de la buse**. Le rapport présente donc la variante « tout visser » en premier.

## Conséquences

- `KCTRL_BED_SCREWS` remplace le cycle « maillage complet puis lecture des
  coins » : vingt-cinq contacts, environ six minutes au lieu de vingt-cinq.
- Toute correction inférieure à un demi-huitième de tour est annoncée comme du
  bruit plutôt que comme une action.
- Une vis arrivée en butée n'est pas forcée ; la correction équivalente se fait
  en desserrant les trois autres.
- Le plancher mécanique retenu est `0,15 mm` d'écart au plan. En dessous, le
  travail se fait au maillage et à l'édition point par point, pas à la clé.

## Voir aussi

- ADR-013 — maillage composite et limite de trente-six contacts
- ADR-045 — aucun palpage sans buse nettoyée à la main
- ADR-046 — profil de maillage référé au point de palpage
- ADR-048 — perte de pas Z isolée, risque matériel ouvert
