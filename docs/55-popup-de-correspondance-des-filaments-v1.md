# 55 — Le popup de correspondance des filaments : où il est passé

Date : 2026-09-02
Statut : cause établie, correctif posé et vérifié à froid ; un vrai print reste
à faire par Thomas

Le popup d'origine — les filaments du G-code avec leurs couleurs d'un côté, les
bobines du CFS de l'autre, et on les met en face — n'a jamais disparu. Il n'a
simplement jamais été appelé, et quand il l'aurait été, la séquence de démarrage
possédée n'aurait pas lu sa réponse.

## 1. Le popup est vivant, et il travaille déjà

Le firmware analyse chaque fichier tranché, en extrait les couleurs et les
matières, et propose une correspondance. C'est dans `master-server.log`, sans
qu'on ait rien fait :

```
Parse file path:3DBenchy_C2.gcode
types  : PLA;PLA;PLA;PLA
colors : #000000;#ffffff;#ff0000;#0080ff
the multicolor match info is (T1A=T1A T1B=T1D T1C=T2A T1D=T2B)
```

Quatre couleurs dans le G-code, quatre bobines proposées, choisies sur la
couleur déclarée de chaque emplacement. L'opérateur corrige à l'écran, et le
firmware applique par `BOX_MODIFY_TN`, qui écrit la table `tnn_map` dans
`tn_data.json`. Le texte du popup est dans `display-server` :

> Undefined filament-to-CFS slot mappings. Place matching filaments in CFS or
> manually specify mapping.

## 2. Pourquoi il ne s'est jamais montré

Le popup appartient aux surfaces Creality : l'écran tactile, l'application
Creality, la page web Creality. `master-server` distingue explicitement ses
sources de lancement (`dis set start print`, `web control start print local
gcode`, `app control start print local gcode`, `fluidd start print file`).

Sur les journaux conservés, tous lancements confondus :

| Source | Lancements |
|---|---|
| Fluidd / Mainsail | 19 |
| Page web Creality | 1 |
| Écran tactile | 0 |
| Application Creality | 0 |

Chaque impression est partie de Fluidd ou de Mainsail, qui n'ont pas ce popup et
ne l'appellent pas. La correspondance est restée à l'identité, et l'identité
envoie le premier filament sur `T1A`.

## 3. Le deuxième verrou : la réponse n'était pas lue

Même le popup utilisé, l'impression serait partie sur `T1A`. `START_PRINT`
possédé charge le CFS par `BOX_EXTRUDE_MATERIAL TNN=<emplacement>`, qui adresse
un emplacement physique et ne consulte pas `Tnn_map`. Et `Tnn_map` n'est **pas**
publiée dans l'objet `box` de Klipper : une macro ne pouvait pas voir la réponse
que l'opérateur venait de donner.

## 4. Ce qui a été posé

`kctrl_slot_map.py`, un objet Klipper en lecture seule, déployé dans
`/usr/share/klipper/klippy/extras/`. Il lit le fichier que le firmware écrit et
publie la table sous `printer["kctrl_slot_map"].map`. Il ne relit que si le
fichier a changé, et il n'écrit jamais.

`START_PRINT` résout maintenant l'emplacement par `map["T1A"]` — l'entrée du
premier filament du trancheur. Si la table est illisible, il refuse de démarrer
au lieu de repartir sur `T1A` en silence.

`Tnn_map` devient la seule réponse à « quelle bobine ». Trois écrivains, une
table : le popup de l'écran, `BOX_CHECK_MATERIAL_REFILL` quand une bobine
s'épuise, et `KCTRL_SLOT` quand il n'y a pas d'écran dans la boucle. La variable
persistante `kctrl_slot` est supprimée : deux vérités divergent dès que l'une
des deux autres écrit.

Deux commandes de lecture : `KCTRL_MAP` montre la correspondance complète avec
matière et couleur de chaque emplacement visé, `KCTRL_SLOTS` montre les bobines
et celle qui partira.

## 5. Preuve faite sur la machine, à froid

Le 2 septembre, machine au repos, plateau bas, aucun mouvement ni chauffe :

| Question | Preuve |
|---|---|
| L'objet lit la vraie table | `printer["kctrl_slot_map"]` renvoie les seize entrées de `tn_data.json`, `loaded: 1`, `error: ""` |
| Il suit une écriture du firmware | `BOX_MODIFY_TN T1A=T2C` puis relecture : `T1A -> T2C` |
| `KCTRL_MAP` le dit lisiblement | `filament 1 (T1A) -> T2C   matiere 000003, couleur 0ffffff   <- remappe` |
| `KCTRL_SLOTS` suit la même source | `-> T2C` en face de l'emplacement retenu |
| Restauration exacte | `BOX_MODIFY_TN T1A=T1A`, table revenue à l'identité |

## 6. Les purges du G-code

Elles sont déjà prises en compte, et elles l'ont toujours été. Les volumes de
purge d'un G-code décrivent des **changements de couleur**, et chaque changement
de couleur passe par le `cmd_T` stock, qui lit ces volumes dans le fichier
tranché lui-même — `get_flush_length_from_gcode`, `flush_volumes_matrix`,
`get_purge_in_prime_tower`, tous présents dans le module CFS et tous alimentés
par le fichier.

`START_PRINT` ne touche qu'au premier chargement, qui n'a aucune couleur à
chasser : il n'y a pas de volume de purge du trancheur à respecter là. La purge
de démarrage reste celle réglée ici, `120 mm`, plafond retenu par Thomas.

## 7. Ce qui n'est pas prouvé

Aucune impression n'a été lancée. La chaîne est vérifiée pièce par pièce à
froid ; ce qui reste à voir tourner, c'est un vrai départ depuis l'écran avec le
popup, et un multi-filament complet avec ses changements de couleur.

## 8. Sauvegarde laissée sur la machine

```
/usr/data/printer_data/config/k1-control-owned-start-print-v2.cfg.kctrl-bak-20260902b
```
