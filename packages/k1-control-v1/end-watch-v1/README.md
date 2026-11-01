# End watch V1 - surveillance de fin d'impression depuis le PC

Statut : **versionnée et testée hors imprimante, jamais lancée sous cette
forme**. Sa version brute de la nuit du 1er novembre 2026 (sha256 `4e989918…`,
gardée hors Git) a coupé par arrêt d'urgence la routine stock « extrude all
material » à 07:14:08, après 0,13 mm poussés (ADR-076, document 104). Elle doit
surveiller la première fin sous la V5 (`end-no-stock-flush-v5`).

- `watch_end.py` : la surveillance, lancée sur le PC, jamais sur la K1.
  `decide()` porte toutes les règles sur une lecture, sans réseau ; `watch()`
  lit, journalise, attend et arrête.

## Lancer

L'essai à blanc d'abord, puis la surveillance, avant la fin du fichier :

    python packages/k1-control-v1/end-watch-v1/watch_end.py HOST --dry-run
    python packages/k1-control-v1/end-watch-v1/watch_end.py HOST > inventory/raw/<capture>/watch_end.log 2>&1

`HOST` est l'adresse locale de la K1 : en argument seulement, jamais dans un
fichier suivi. Le repli passe par l'alias SSH `k1max-root` des autres paquets.
Le journal reste sous `inventory/raw/`, hors Git : ses rapports recopient les
champs `box` de la K1. `--keep-on-pause` garde la surveillance pendant une
pause de plus de 2 min avant la fin. La ligne `start` dit si le PC est tenu
éveillé (`awake=True`, Windows seulement) ; sinon, l'empêcher de dormir
autrement. Lancée après la fin du fichier, elle prend sa première lecture comme
référence des gardes et compte sa fenêtre depuis son lancement.

L'essai à blanc lit les deux requêtes et le rapport, envoie un POST de lecture
(`objects/query`) par la passerelle et une requête `info` au socket Klipper. Il
n'arrête rien et sort en 0 seulement si les deux requêtes, le POST et le socket
ont répondu, Klipper `ready` ; sinon en 1.

## Rythme

- Pendant l'impression ou la pause : une lecture toutes les 30 s, toutes les
  5 s après 97 % ou en pause. Aucune action.
- Après la fin du fichier (`print_stats` en `complete`, `error`, `cancelled`
  ou `standby`, et `virtual_sdcard.is_active` faux) : toutes les 2 s pendant
  15 min, puis toutes les 5 s jusqu'à 45 min, et jusqu'à 90 min tant que la fin
  K1 Control reste dans une phase active.
- Une PAUSE stock après la fin ne termine pas la surveillance : seul un nouveau
  fichier qui imprime la termine.

## Déclencheurs

Après la fin du fichier seulement, un seul arrêt d'urgence, puis sortie,
quand :

- `kctrl_purge_guard.cold_refused` augmente : la garde à froid a refusé une
  poussée ;
- `kctrl_purge_guard.denied` augmente : la garde du bac a refusé un mouvement ;
- E avance de plus de 1 mm hors des phases actives de la fin K1 Control
  (`waiting`, `heating`, `cutting`, `rewinding`, `finalizing`, où tournent
  `BOX_CUT_MATERIAL` et `END_PRINT_NO_M84`) : la référence garde le minimum
  vu, un recul l'abaisse, une phase active ou un E illisible l'efface ;
- la cible de la buse reste à 170 °C ou plus pendant 15 min sans phase active.

Les refus des gardes comptent aussi pendant une phase active, E et la cible
non. Un champ absent ou inconnu ne déclenche aucun arrêt et, avant la fin,
passe pour une impression en cours.

L'arrêt part d'abord vers Moonraker (POST `/printer/emergency_stop`), puis, si
Klipper n'est pas en `shutdown` 6 s plus tard, droit au socket Klipper par
`ssh k1max-root python3 -`. Les deux passent à côté de la file G-code, qu'une
boucle stock peut tenir. L'arrêt est confirmé (20) quand `shutdown` est lu,
dans les 6 s après Moonraker ou dans les 10 s après le socket ; sinon 21.

## Codes de sortie

| Code | Sens |
| --- | --- |
| 0 | fin propre : fenêtre close, fin K1 Control `complete` |
| 10 | fin en échec mais calme : `failed`, aucun déclencheur |
| 11 | aucune fin K1 Control vue : phase ni `complete` ni `failed` |
| 12 | un nouveau fichier imprime |
| 20 | arrêt d'urgence confirmé |
| 21 | arrêt d'urgence non confirmé |
| 30 | pause de 2 min avant la fin, sans `--keep-on-pause` |
| 40 | Klipper pas prêt (`webhooks.state` autre que `ready`) |
| 50 | lecture ratée au terme des 90 min après la fin |
| 60 | 10 h de surveillance écoulées : fin du fichier jamais vue, ou lecture ratée à ce terme |

Chaque sortie de la surveillance écrit une dernière ligne `exit N: sens` : un
journal qui s'arrête sans elle veut dire un processus tué ou interrompu.
L'essai à blanc sort en 0 ou 1 ; une ligne de commande fausse (option inconnue,
adresse absente) sort en 2 sans rien lire.

## Lecture ratée

Une lecture ratée n'arrête jamais la surveillance : elle est dite une fois,
puis relue toutes les 5 s, sans action.

- `unreachable HTTPError 503` : Moonraker répond mais Klipper n'y est plus
  connecté (arrêté ou en redémarrage) ;
- `unreachable HTTPError 502`, `URLError ...` ou `TimeoutError` : passerelle
  ou réseau coupés ;
- `unreadable ...` : réponse illisible, dont un statut qui n'est pas un
  ensemble d'objets.

Tant que dure la coupure, elle est aveugle : aucun déclencheur ne peut partir.

## E prévu, poussée réelle

E (`toolhead.position[3]`) est la position prévue : il avance dès qu'un
mouvement est mis en file, pas quand l'extrudeur le fait. Le 1er novembre, la
poussée stock prévoyait 80 mm ; 0,13 mm seulement sont sortis avant l'arrêt.

La poussée réelle se lit dans `klippy.log`, par une fenêtre bornée en octets,
jamais par `tail -n` :

1. `Requested toolhead position at shutdown time T: ...` donne l'instant
   d'arrêt T ;
2. le bloc `Dumping trapq 'extruder'` liste les segments
   `move N: pt=... mt=... sv=... a=... sp=(...) ar=(...)` : début `pt`, durée
   `mt`, vitesse de départ `sv`, accélération `a`, position de départ `sp` ;
3. sur le segment en cours à T, avec t = min(mt, T - pt), la position réelle
   vaut sp + ar × (sv + 0,5 × a × t) × t, la formule de Klipper pour la tête.
   La poussée réelle est cette position moins le `sp` du premier segment de la
   poussée. Le 1er novembre, un seul segment à vitesse constante :
   (T - pt) × sv = 0,13 mm.

## Limites connues

- Arrêter la surveillance avant toute chauffe ou poussée à la main dans la
  fenêtre : elle ne distingue pas un geste de Thomas d'une routine stock.
- Une coupure longue après la fin la rend aveugle jusqu'à sa sortie en 50.
- Une poussée déjà en file quand E prend sa référence - à la deuxième lecture
  après la fin (la première ne lit pas E), puis à la sortie de chaque phase
  active - n'est pas vue : seuls un refus des gardes ou la chauffe tenue la
  rattrapent.
- Klipper qui redémarre la fait sortir en 40 : la relancer si la fenêtre n'est
  pas finie. Un redémarrage pendant une coupure remet les compteurs des gardes
  à 0, sous l'ancienne référence : un refus n'y compte qu'au-delà.
- 21 peut vouloir dire que Klipper a quitté avant d'être lu en `shutdown` (le
  1er novembre, il a quitté seul 6 s après l'arrêt, bogue TMC Creality) : lire
  `klippy.log` avant de conclure.
- Après un arrêt d'urgence, ne redémarrer ni Klipper ni la K1 : Thomas rallume.
  Vérifier ensuite qu'aucun processus `python` ou `ssh` de la surveillance ne
  reste sur le PC.

## Différences avec la version de la nuit

- Mêmes requêtes, seuils, cadences, arrêt et codes : les deux versions donnent
  les mêmes lectures, arrêts, rapports et codes sur 3 000 chronologies tirées
  au hasard (comparaison hors dépôt, qui détecte cinq mutants sur cinq).
- La décision est une fonction pure, `decide()`, testée sans réseau.
- Une réponse 200 dont un objet vaut `null` arrêtait la version de la nuit sur
  une exception, sans arrêt d'urgence possible ensuite ; elle est maintenant
  refusée et dite, et la surveillance continue.
- Le journal ne peut plus faire tomber la surveillance : une sortie perdue
  avant l'arrêt empêchait l'arrêt d'urgence de partir.
- Les codes 50 et 60 sortaient sans un mot : chaque sortie finit par
  `exit N: sens`.
- Le code HTTP figure dans la ligne d'une lecture ratée (`HTTPError 503`).
- La ligne d'arrêt sur refus à froid citait `cold_last`, que la requête de fin
  ne lit pas : elle disait toujours `None`. Elle ne le cite plus ; le rapport
  qui suit l'arrêt le donne.
- La ligne de commande est stricte : `--dryrun` mal tapé lançait la vraie
  surveillance ; il sort maintenant en 2.
- L'essai à blanc continue après une lecture ratée et sort en 1 si une voie
  d'arrêt ne répond pas.

Validation : **104 tests ciblés verts** (`tests/test_end_watch.py`) : fausse
K1 sur horloge simulée, aucun réseau, aucun SSH. Chacun des cinq mutants de la
comparaison en fait échouer au moins un.
