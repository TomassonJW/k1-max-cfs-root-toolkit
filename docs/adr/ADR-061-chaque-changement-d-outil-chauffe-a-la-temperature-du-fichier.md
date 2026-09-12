# ADR-061 — Chaque changement d'outil chauffe à la température du fichier

Date : 2026-09-10

Statut : **acceptée ; écrite et testée ; pas encore déployée** (déploiement sur
accord explicite du propriétaire, machine à l'arrêt, redémarrage du service
Klipper).

Prolonge ADR-059 et le document 67 (alignement de la fiche matière au
démarrage) à tous les changements d'outil d'une impression. Répond au point 4
du flux quotidien dicté le 10 septembre (`GOALS.md`) : « le multi-filament en
cours d'impression est bien géré ».

## Contexte

Le changement de filament en cours d'impression est le `T{n}` du fichier
tranché, et ce `T{n}` est une commande du module compilé du CFS : coupe,
retrait, alimentation de la nouvelle bobine, tirage jusqu'à la buse, purge
dans le bac, retour du Z. Ses températures viennent de la fiche matière de
l'emplacement visé (`material_database.json`), c'est-à-dire de la valeur du
cloud Creality pour cette matière, réécrite par le firmware à chaque
démarrage. Le fichier tranché n'est jamais lu pour ça.

Depuis le 10 septembre 11:15, `START_PRINT` aligne la fiche du filament de
départ sur la température du fichier avant de charger (`KCTRL_MATERIAL_ALIGN`,
document 67). Tout `T` suivant passait par la commande stock intacte : un
travail à deux filaments changeait de bobine à la température du cloud, pas à
celle du profil de filament que Thomas a réglé dans Orca.

Ce que le fichier sait, et où : Orca écrit son profil complet en fin de
fichier, entre `; CONFIG_BLOCK_START` et `; CONFIG_BLOCK_END`, avec une ligne
par clé et les valeurs par filament en liste, dans l'ordre du trancheur :

```
; nozzle_temperature = 195,220
; nozzle_temperature_initial_layer = 190,220
; filament_type = PLA;PLA
; filament_colour = #000000;#8080FF
; initial_layer_print_height = 0.2
```

Cube du 10 septembre : ligne 2079 d'un fichier de 2750 lignes ; fichier de
13 h : ligne 1 799 345. Le bloc se lit par la fin.

Ce que fait la commande stock quand ça se passe mal : `return False`, sans
erreur Klipper. Un filament qui pointe sur un emplacement vide, sur une unité
absente, ou une fiche qui refuse, c'est une impression qui continue à vide.

## Décision

**Un module Klipper, `kctrl_tool_change.py`, reprend T0..T15 au chargement**
(section `[kctrl_tool_change]` dans le fichier du démarrage possédé, inclus
après `box.cfg`, comme le ferait un `rename_existing`). Autour de chaque
commande stock :

1. **Résolution.** Le filament `n` du fichier est le nom logique `T1A`..`T4D`
   de même rang ; la table `tnn_map` (celle que la commande stock lit, via
   `kctrl_slot_map`) donne l'emplacement réel ; l'objet `box` dit si l'unité
   est connectée et si l'emplacement est garni. Un filament qui pointe nulle
   part, sur une unité absente ou un emplacement vide, ou que le fichier ne
   déclare pas, est un **refus net avant la commande stock**, avec le message
   qui dit quoi faire (`KCTRL_SLOT`, `KCTRL_SLOTS`).
2. **Alignement.** La température que le fichier donne à ce filament —
   première couche tant que la position Z est sous la deuxième couche ou
   pendant `START_PRINT`, courante ensuite — est écrite dans la fiche matière
   de l'emplacement visé, par la même méthode que `KCTRL_MATERIAL_ALIGN`.
   Une fiche qui ne peut pas être alignée est un refus : le chargeur
   chaufferait à une valeur que personne n'a choisie.
3. **La commande stock**, telle quelle.
4. **Après, hors démarrage** : `M400`, puis si le firmware a lui-même mis en
   pause (erreur cutter, `key841`), rien de plus qu'un message ; sinon, si le
   capteur de tête ne voit pas de filament, **pause** et message (« charger à
   la main puis RESUME »), jamais une pièce finie à vide ; sinon la cible
   buse est remise à la valeur du fichier, parce que la purge stock la laisse
   à `max(fiche, 200)`.
   Dans `START_PRINT`, l'enveloppe se limite à l'alignement : le démarrage
   garde son attente du capteur avec grâce, son `M109` et ses contrôles.

Un `T` tapé à la console sans fichier en cours, ou avec le CFS désactivé,
passe à la commande stock sans rien d'autre.

**`KCTRL_TOOLS`** montre, pour le fichier en cours ou `FILE=…`, chaque
filament déclaré : type, couleur, températures, emplacement visé, état de
l'emplacement, fiche et sa température actuelle, et « sera alignée au
changement » quand elle diffère. Il liste aussi les commandes T reprises et
celles que le module compilé n'avait pas enregistrées.

**`kctrl_slot_map`** publie désormais ce que le fichier dit de ses filaments
(`job_count`, `job_temps`, `job_initial_temps`, `job_types`, `job_colours`,
`job_names`), lu en queue de fichier et mis en cache tant que le fichier ne
change pas. C'est aussi la matière première du point 2 du flux (appariement
automatique des bobines depuis Mainsail).

## Ce que ça change pour Thomas

Un fichier à plusieurs filaments change de bobine à la température de son
profil Orca, première couche comprise. Un changement impossible s'arrête tout
de suite avec la raison, au lieu d'imprimer de l'air. `KCTRL_TOOLS` avant de
lancer dit ce qui va se passer.

## Preuve

- `tests/test_kctrl_tool_change_v1.py` (24 tests) : prise en main des seize
  commandes sans faire échouer Klipper quand une manque ; fiche écrite
  **avant** l'appel stock ; première couche contre courante ; dans
  `START_PRINT`, alignement seul ; refus avant la commande stock pour
  emplacement vide, unité absente, filament non déclaré, table sans entrée,
  fichier sans températures, fiche illisible ; pause après un changement
  fini sans filament, pause du firmware non doublée, erreur stock remontée
  telle quelle ; `KCTRL_TOOLS`.
- `tests/test_kctrl_slot_map_v1.py` : le bloc de configuration du cube réel
  (`tests/fixtures/k1-control-v1/orca-2.4.2-cube-2026-09-10-tail.gcode`) se
  lit ; lecture en queue d'un gros fichier ; rien d'inventé sans bloc ou avec
  une valeur illisible ; `align` partagé et cache invalidé.
- Observation attendue au premier `T` réel en cours d'impression : dans le
  journal, `get next material temp: <température du fichier>` puis
  `flush_temp: max(<fichier>, 200)`, et la ligne « K1 Control: T1 -> … » avant
  `cmd_T vtnn=`.

## Conséquences

- Le plancher de purge à 200 °C du module compilé reste (document 67 § 8) :
  un filament à 195 est purgé à 200, puis la cible revient à 195.
- Deux bobines de la même matière partagent une fiche : chaque changement la
  réécrit à la température du filament qui arrive, ce qui est exactement ce
  qu'il faut, puisque la commande stock la relit à chaque chargement.
- La détection de première couche en cours d'impression se fait sur la
  position Z du G-code, sous la hauteur de la deuxième couche ; un saut Z de
  changement d'outil en première couche prend la température courante, écart
  de 5 °C sur les profils actuels.
- L'accumulateur Z du module compilé (audit 70, P1) n'est pas touché : sur
  les deux démarrages du 10 septembre au soir, `z_down` et `z_restore` se
  compensent exactement (20,036 / 20,036) ; le `0,8` laissé par la routine de
  fin d'impression est remis à zéro par `virtual_sdcard` au fichier suivant
  (« Move z not clear, move_z:0.8 », sans effet).
