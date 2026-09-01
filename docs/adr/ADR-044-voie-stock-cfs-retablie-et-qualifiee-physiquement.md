# ADR-044 — La voie CFS stock est rétablie et qualifiée physiquement

Date : 2026-09-01
Statut : accepté
Contexte matériel : Creality K1 Max, kit CFS, deux unités chaînées.

## Contexte

ADR-041 a montré que la garde qui bloquait le retrait lisait `box.cut_pos`, un
champ qui ne reflète jamais le capteur du cutter. ADR-043 a posé la règle : une
garde qui retire une capacité doit livrer son remplaçant qualifié dans la même
tranche. Les trois inclusions propriétaires ont été basculées en variante
`disabled` dans `printer.cfg`, puis `FIRMWARE_RESTART`.

Il restait à prouver que la voie stock, une fois débloquée, exécute réellement
un cycle complet retrait puis chargement sur cette machine.

## Ce qui a été observé

Séquence de retrait lancée depuis l'écran, capturée par
`gcode/subscribe_output` :

```
[box] cut sensor state:1
[box] cut to return OK
Cut sensor triggered.
T0 monte de 31 à 220 °C
capteur après-cutter -> faux
[box] cut sensor state:0
```

`BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1A`, envoyé ensuite buse à 220 °C, rend la
main en trois secondes sans mouvement : le CFS avait déjà rembobiné. Le capteur
`filament_sensor` restait vrai à cause d'un tronçon resté dans la tête, hérité
d'un rembobinage sans coupe antérieur. Ce n'était pas un bourrage bloquant.

Séquence de chargement lancée depuis l'écran, même capture :

```
buffer_state: 0x0
capteur après-cutter -> vrai
box.T1.filament -> A
```

Le chemin filament est donc libre de bout en bout. Un second cycle complet
retrait puis chargement a produit une purge visible et un filament correctement
inséré, confirmé par l'opérateur.

État final mesuré : `box.state connect`, `box.T1.filament A`, `T1.mode 2`, les
deux capteurs filament vrais, cibles de chauffe à zéro, `print_stats standby`.

## Décision

La voie CFS stock est déclarée physiquement qualifiée pour le retrait et le
chargement sur ce matériel. Elle devient la voie de production par défaut tant
qu'aucun remplaçant propriétaire n'est qualifié dans les mêmes conditions.

Aucune garde ne doit être réinstallée sur `BOX_CUT_MATERIAL`,
`BOX_RETRUDE_MATERIAL`, `BOX_EXTRUDE_MATERIAL` ni sur leurs macros enveloppes
`BOX_QUIT_MATERIAL` et `BOX_LOAD_MATERIAL_*` sans une capture équivalente à
celle-ci pour le remplaçant.

## Défaut réel resté ouvert

La capture montre le parasitage de température annoncé par Thomas. Pendant le
premier chargement, la cible passe à `0 °C` juste après l'arrivée du filament,
remonte à `200 °C`, puis la purge annonce `flush_temp: 220`. La valeur `220`
provient de `Tn_extrude_temp` codé en dur dans `box.cfg` et ne vient d'aucun
G-code. C'est la cause directe du « quasi rien extrudé » du premier essai.

Ce défaut est réel, reproductible et documenté ici ; il n'est pas corrigé par
cette décision. Sa correction appartient à la tranche « températures » et doit
faire dériver la température de purge du G-code, pas d'une constante.

## Conséquences

- Le point de blocage de trois semaines est levé et prouvé levé.
- La machine peut produire immédiatement avec le comportement CFS d'origine.
- Le retour à la variante `active` des trois inclusions reste possible et reste
  décrit dans `HANDOFF.md`.
- La suite de travail reste celle d'ADR-042, sans la sortie de secours filament
  qui n'est plus nécessaire.
