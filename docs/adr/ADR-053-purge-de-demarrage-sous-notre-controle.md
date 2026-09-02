# ADR-053 — La purge de démarrage attend le filament, puis pousse ce qu'elle annonce

Date : 2026-09-02

Statut : **acceptée ; installée ; boule obtenue à `200 mm`, défaut ramené à
`180 mm` à confirmer**

## Contexte

Au démarrage d'une impression, la purge au-dessus du bac laisse un filet mince
accroché à la buse au lieu de former une boule qui se décroche et tombe. Ce
filet est ensuite traîné sur le plateau et finit dans la première couche.

`box.cfg` déclare `box_need_clean_length: 140`, et `140 mm` suffisent — quand
ils sortent effectivement de la buse. Trois raisons pour qu'ils n'en sortent
pas, dont la troisième est qu'ils ne sont même pas poussés.

**La purge partait avant que le filament soit dans la tête.** La séquence
possédée vérifiait le capteur de tête par une assertion — un contrôle unique au
moment où le macro se rend — puis enchaînait sur `BOX_EXTRUDER_EXTRUDE` et la
purge stock. Le CFS continue d'alimenter sur son propre bus après le retour de
la commande. Une purge dimensionnée pour une tête déjà chargée, lancée sur une
zone de fusion vide, ne produit qu'un filet. Aucune longueur supplémentaire ne
répare ça : elle serait dépensée au même endroit.

**Et la buse n'était pas chaude.** Traces du 2 septembre à 00 h 22, au moment
de la purge stock : `extruder: target=220 temp=109.3`. Le CFS pose sa cible et
n'attend pas. À `109 °C` il ne sort quasiment rien.

## Décision

**Rien ne pousse de filament tant que le capteur de tête ne le voit pas.**

`KCTRL_WAIT_FILAMENT SENSOR=filament_sensor_2 TIMEOUT=15` bloque jusqu'à ce que
le capteur voie la matière, relit la broche toutes les `200 ms`, et fait échouer
l'impression si le filament n'arrive jamais. Quinze secondes parce que le CFS
met sept à huit secondes minimum à atteindre la tête et que son propre délai de
déclenchement n'est pas connu ; un sondage toutes les `200 ms` fait qu'un
chargement rapide ne coûte pas quinze secondes mais un cinquième de seconde.

C'est une commande Python, pas un macro qui temporise. La version macro a été
écrite, installée, et elle ne fonctionne pas — silencieusement. Mesures du
2 septembre :

```
un sondage temporisé, appelé directement          0,84 s   la pause a lieu
dix sondages à plat, appelés directement          8,14 s   les dix ont lieu
les mêmes dix à travers un macro                  0,02 s   rien n'a lieu
idem, puis M400 au sommet                         0,02 s   rien n'était en file
```

La dernière ligne tranche : les temporisations n'avaient jamais été mises en
file, donc aucune attente ultérieure ne pouvait les rattraper. Un `G4`/`M400`
dans un macro appelé depuis `START_PRINT` — le seul endroit où cette attente
servirait — est une période de grâce qui n'existe pas, et rien ne le signale :
l'impression continue simplement de purger dans une zone de fusion vide, c'est-
à-dire exactement le défaut recherché.

La commande Python, elle, met en pause le réacteur elle-même et ne dépend pas
de l'endroit d'où elle est appelée. Vérifié sur la machine : `4,01 s` pour un
délai de `4 s` appelée directement, `4,13 s` **appelée depuis un macro**, retour
immédiat sur un capteur déjà plein, refus immédiat sur un capteur inconnu.

**La buse est chaude avant la première poussée.** `M109 S{nozzle}` sur la
température du G-code, attendue, avant `BOX_EXTRUDER_EXTRUDE`.

**La quantité stock est laissée telle quelle, et complétée.** `140 mm`, sans
`LEN=`, plus un complément possédé de `180 mm` juste avant elle. Parce que les
`140 mm` annoncés par `box.cfg` ne sortent pas. Reconstitution depuis les
statistiques de l'impression du 2 septembre à 00 h 23, seule trace de ce que
fait réellement le module compilé :

```
00:23:30 - 00:23:39   print_time figé, buffer 0    le CFS pousse sur son bus,
                                                   rien ne bouge côté tête
00:23:42 - 00:24:00   print_time +32,4 s à 220 °C  la tête extrude
```

Ces `32,4 s` couvrent `BOX_EXTRUDER_EXTRUDE` et la purge ensemble. `box.cfg`
donne `Tn_extrude: 140` à `Tn_extrude_velocity: 360 mm/min`, soit `23,3 s` des
`32,4` — il reste environ `9 s` pour la purge elle-même, de l'ordre de `55 mm`,
pas `140`. L'opérateur avait raison : « ça n'envoie pas du tout 140 mm ».

Le complément vise à ramener la purge réelle près des `140 mm` toujours visés,
pas à ajouter une purge par-dessus une purge complète. Sa longueur n'est pas
calculée, elle est jugée sur la plaque : `200 mm` essayés le 2 septembre ont
donné la boule qui se décroche au lieu du filet qui pend. `180 mm` sont
retenus comme valeur par défaut, choix de l'opérateur pour économiser un peu
de filament à chaque démarrage ; à confirmer sur la prochaine impression.

La longueur n'est pas passée à `BOX_MATERIAL_FLUSH LEN=` : `box.cfg` déclare
`box_need_clean_length_max: 140`, donc une valeur supérieure pourrait être
bornée sans un mot — le pire échec pour une purge, puisque rien ne le signale et
que le défaut ne se voit que sur la plaque.

## Le capteur surveillé est le bon, et il ne dit pas ce qu'on croit

L'hypothèse d'un mauvais capteur était raisonnable. Vérification faite sur la
machine, ce n'est pas ça :

```
filament_sensor    (!PC15, MCU principal)      filament_detected: True
filament_sensor_2  (^!nozzle_mcu:PA10, tête)   filament_detected: False
```

`filament_sensor_2` est bien celui de la tête — câblé sur le MCU de la tête —
et c'est bien celui que la séquence interroge. Il lisait `True` pendant
l'impression et lit `False` une fois l'impression finie, voyant éteint, parce
que `END_PRINT` a déchargé par le cutter. Le capteur fonctionne et il est
correctement lu.

Mais il est placé **après le cutter et avant les galets de l'extrudeur**. Voir
du filament au capteur signifie que le filament est arrivé au capteur, pas que
la buse est amorcée : il reste tout le trajet jusqu'à la zone de fusion, que
`BOX_EXTRUDER_EXTRUDE` couvre avec ses `Tn_extrude: 140`. C'est pour cette
raison que l'assertion seule ne suffisait pas, et pourquoi elle est désormais
précédée d'une attente.

## La mesure annoncée n'a pas fonctionné

`_KCTRL_PURGE_MARK` relève l'axe extrudeur avant l'étape matière et
`_KCTRL_PURGE_REPORT` devait annoncer le total réellement poussé après la purge
stock. Les deux se lisent après un `M400`, ce qui était la bonne précaution mais
pas la seule nécessaire.

Le démarrage du 2 septembre a affiché `-2 mm`. Les routines box émettent des
`G92 E0` à l'intérieur de l'étape matière : l'axe extrudeur repart de zéro sous
le repère, et la différence n'a plus de sens. Une purge qui affiche un chiffre
faux est pire qu'une purge muette, puisque le chiffre sert justement à trancher.

Le rapport garde donc la lecture : au-dessus d'un millimètre il annonce le
parcours mesuré, sinon il dit que le total n'est pas mesurable et rappelle la
seule longueur que ce fichier commande réellement. Le compteur honnête existe —
la position du moteur pas à pas, que `G92` ne touche pas — mais il se lit en
Python, pas en macro. C'est un travail séparé.

## Vérification

Hors machine, l'ordre de l'étape matière est rendu avec l'environnement Jinja
de Klipper (délimiteurs à accolade simple) et non lu : aucune commande qui
pousse du filament n'apparaît avant l'attente, avant l'assertion, ni avant le
`M109`. Le fait que l'attente ne soit pas un macro est verrouillé au même
endroit, parce que c'est précisément le piège dans lequel ce travail est tombé.

Sur la machine : `kctrl_wait.py` déployé dans les extras de Klipper, service
Klipper redémarré — un `FIRMWARE_RESTART` relit la configuration mais pas les
modules Python — `KCTRL_WAIT_FILAMENT` enregistré, blocage réel mesuré y compris
imbriqué dans un macro, sonde de test retirée, configuration relue et empreintes
machine identiques au dépôt. **Le résultat se juge à l'œil sur la plaque** —
c'est le seul juge de « boule » contre « filet ». `200 mm` ont donné la boule
le 2 septembre. `180 mm`, la valeur par défaut retenue depuis, restent à
confirmer au prochain démarrage.

## Conséquences

- Le démarrage s'allonge de l'attente réelle du filament — le temps qu'il met
  vraiment, au plus quinze secondes — et de la montée en température avant
  poussée.
- `kctrl_wait.py` est un module Python de Klipper. Toute modification exige un
  redémarrage du service, pas un simple `FIRMWARE_RESTART`.
- La consommation par démarrage passe d'environ `55 mm` réels à environ
  `235 mm` réels : les `55 mm` de la purge stock plus les `180 mm` du
  complément. Valeur retenue à l'œil sur la plaque, la mesure automatique
  n'étant pas fiable.

- La sauvegarde de la configuration précédente est
  `/usr/data/printer_data/config/.bak-owned-start-v2-prepurge`.
- `Tn_extrude_temp: 220` reste imposé par le CFS sur la purge stock. Le sortir
  de la boucle de température est un travail séparé.

## Alternatives refusées

- **Ajouter `300 mm` de purge à nous** : construit, installé, puis retiré.
  `440 mm` par démarrage compensait à l'aveugle un problème d'ordre, sans le
  corriger. Le complément qui subsiste fait `180 mm`, posé après l'attente du
  filament et jugé sur le résultat imprimé.

- **Passer `LEN=` à `BOX_MATERIAL_FLUSH`** : susceptible d'être borné à `140`
  sans le dire.
- **Se contenter de l'assertion** : elle contrôle une fois, au rendu, et le CFS
  continue d'alimenter après le retour de sa commande.
- **Attendre avec un macro qui temporise** : écrit, installé, mesuré sans effet
  dès qu'il est appelé depuis un autre macro. Une attente qui n'attend pas est
  pire que pas d'attente du tout, puisqu'elle donne le change.

## Voir aussi

- ADR-040 — quantité de purge G-code et garde cutter réel
- ADR-049 — chargement CFS, une poussée ne suffit pas
- ADR-051 — capteur de tête laissé comme le CFS le laisse
