# ADR-051 — Le capteur de tête reste éteint, comme le CFS le laisse

Date : 2026-09-01

Statut : **accepté**, après un défaut constaté en production le soir même

## Contexte

L'ADR-049 relevait que le CFS désactive le capteur de filament de tête pour
charger et ne le restaure jamais, et en concluait que les impressions
tournaient sans détection de fin de bobine. Le démarrage propriétaire le
réactivait donc après la purge.

La première impression menée jusqu'au bout avec cette activation s'est terminée
ainsi :

```
23:28:19  [box] cut sensor state:1      coupe de fin d'impression
23:28:21  flush_temp: 220
23:28:32  filament_sensor_2 pause       le capteur se vide -> pause runout
23:28:59  Printer not homed             le rechargement s'enlise
```

`END_PRINT` retire le filament par le cutter. Le capteur se vide donc à **chaque
fin d'impression normale**, son `runout_gcode` se déclenche, et la machine se
met en pause après la dernière couche, buse tenue à `140 °C`, sans rien à
reprendre. Il faut une intervention manuelle pour en sortir.

Mesure faite après redémarrage : le capteur revient à `enabled: True` par
défaut, et c'est le chargement CFS qui l'éteint. Autrement dit, en
fonctionnement d'origine il est **toujours** éteint au moment du retrait final.
Ce que l'ADR-049 lisait comme un oubli du CFS est une précaution.

## Décision

L'activation est retirée. Le capteur est laissé dans l'état où le CFS le met.

Le désarmer juste avant le retrait final n'a pas de point d'accroche propre :
`END_PRINT` appartient à Creality, et le fichier propriétaire remplace des
sections entières au lieu de les envelopper — Klipper fusionne les sections
homonymes, ce qui interdit `rename_existing` sur une macro déjà déclarée. En
prendre le contrôle signifierait recopier tout son corps et en assumer la
maintenance.

La détection de fin de bobine attend donc cette reprise en main, faite
délibérément et à froid. Jusque-là, la machine se comporte comme depuis
toujours : une bobine qui s'épuise en cours d'impression n'est pas rattrapée.

## Conséquences

- Une impression ne peut plus se terminer par une pause fantôme.
- Le point 4 du cahier des charges — rechargement automatique en fin de bobine —
  reste non tenu, et sa dépendance est identifiée : posséder `END_PRINT`.
- Règle générale retenue : **armer une protection sans posséder la séquence qui
  doit la désarmer transforme une fin normale en incident.** Le garde de
  filament du démarrage échappe à cette règle parce qu'il n'observe rien de
  lui-même ; il est interrogé à un instant choisi.

## Voir aussi

- ADR-049 — chargement CFS, une poussée ne suffit pas
- ADR-040 — cutter : aucun rejeu automatique
