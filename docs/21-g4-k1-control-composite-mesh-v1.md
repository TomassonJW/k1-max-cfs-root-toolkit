# G4-K1-CONTROL-COMPOSITE-MESH-V1

Date : 2026-08-24

Statut : **qualifiée sur la K1 réelle** ; quatre quadrants carrés, `144/144`
contacts, 121 positions uniques et profil persistant `11 × 11` validés ;
comparaison de premières couches en attente

## But

Construire un profil `k1_p001_t055_r001_n11x11` à partir de 121 positions
PRTouch réelles, sans dépasser 36 contacts par séquence et sans redémarrer
Klipper entre les quatre acquisitions.

Cette gate reste séparée de l'installation SUBGRID-V1, de son essai `5 × 5`,
des impressions comparatives et de l'exposition du mode dans l'interface.

## Dépendance fermée

La campagne complète est interdite tant que l'état privé de SUBGRID-V1 et sa
capture indépendante ne prouvent pas tous les points suivants :

- phase terminale `qualified` ;
- matrice finie `5 × 5` et 25 contacts ;
- positions impaires `34, 92, 150, 208, 266 mm` sur X et Y ;
- aucun redémarrage avant la capture ;
- chauffes à zéro, axes libérés, profil robuste `6 × 6`, Z accepté et deux CFS
  conformes à la fin ;
- `printer.cfg` identique à la base quotidienne revue.

Un échec de cette preuve ferme la campagne complète. Il ne déclenche pas une
seconde sous-grille avec une autre méthode.

## Recette physique candidate

Une seule chauffe `55/140 °C`, une stabilisation `200 s`, un nettoyage stock et
un seul homing précèdent les passages suivants :

| Passage | X | Y | Matrice | Contacts |
| --- | --- | --- | --- | ---: |
| `north_west` | `5..150 mm` | `5..150 mm` | `6 × 6` Lagrange | 36 |
| `north_east` | `150..295 mm` | `5..150 mm` | `6 × 6` Lagrange | 36 |
| `south_west` | `5..150 mm` | `150..295 mm` | `6 × 6` Lagrange | 36 |
| `south_east` | `150..295 mm` | `150..295 mm` | `6 × 6` Lagrange | 36 |

Les quatre carrés produisent 144 contacts et 121 positions uniques. La ligne
et la colonne centrales sont volontairement reprises : 23 contacts répétés sur
21 positions. Ils sont moyennés et leur divergence maximale doit rester sous
ou à `0,05 mm`.

La fusion corrige uniquement un biais constant par quadrant, estimé par les
positions communes. Les quatre corrections sont recentrées à moyenne pondérée
nulle. Aucun ajustement local libre n'est autorisé.

Les quatre passages gardent le même identifiant de campagne, la même référence
XYZ et les mêmes cibles. La présence de `xyz` est revérifiée avant et après
chaque passage. Toute déconnexion Klipper, perte de référence, cible thermique
différente, forme de matrice inattendue ou annulation coupe les chauffes et
interdit la persistance.

## Fusion

`packages/k1-control-v1/composite-mesh-v1/compose_mesh.py` impose maintenant la
recette exacte, dans cet ordre. La fusion refuse :

- une cinquième sous-grille ou un ordre différent ;
- une borne, taille, interpolation ou liste d'indices différente ;
- plus de 36 contacts dans un passage ;
- un contexte physique différent ou un redémarrage déclaré ;
- une valeur absente ou non finie ;
- une divergence de recouvrement supérieure à `0,05 mm`.

Le seul résultat accepté contient quatre passages carrés, 144 contacts, 121
positions distinctes et les paramètres finaux `11 × 11`, `5..295 mm`,
`mesh_pps=2`, bicubique.

## Pourquoi l'endpoint `update_mesh` ne suffit pas

Le `bed_mesh.py` Creality expose bien `update_mesh`, mais cette méthode remplace
uniquement `probed_matrix` dans le `ZMesh` déjà actif. Elle ne reconstruit pas
ses paramètres `x_count`, `y_count`, bornes et algorithme. Injecter 121 valeurs
après le dernier passage créerait donc un profil incohérent.

La persistance candidate est un bloc Klipper généré complet, préparé seulement
après la fusion des 121 valeurs. `render_profile.py` exige :

- un unique marqueur `SAVE_CONFIG` ;
- un unique profil robuste `k1_p001_t055_r001_n06x06` ;
- l'absence du profil cible ;
- exactement onze lignes de onze valeurs finies ;
- les paramètres `11 × 11`, bicubique, `5..295 mm`.

Ce module ne fait aucune écriture. La future transaction devra encore être
testée avec le parseur Python `3.8.2` exact, précédée d'un backup vérifié, écrire
atomiquement, couper les chauffes avant le premier restart, puis charger et
relire le profil exact. Sur tout écart, elle restaurera le backup bit à bit,
redémarrera Klipper et rechargera le profil robuste.

## État des preuves hors imprimante

- recette stricte et fusion : tests ciblés verts ;
- rendu en mémoire du bloc `11 × 11` : tests ciblés verts ;
- absence de mutation dans ces deux modules : vérifiée par conception ;
- parse Klipper exact du candidat : vert au préflight réel ;
- composant carré R2 installé et validé sans action physique ;
- SUBGRID-V1 physique : qualifiée avec 25 contacts ;
- campagne initiale : arrêtée après le premier `6 × 6` réussi ; le passage
  rectangulaire `5 × 6` a atteint ses 30 contacts puis
  `prtouch_v2_wrapper.bed_mesh_post_proc` a levé `IndexError` ;
- rollback : vert, chauffes zéro, axes libérés, profil robuste actif, Z
  `−0,04 mm`, stockage OK et deux CFS connectés ;
- campagne carrée : quatre passages `6 × 6` et `144/144` contacts capturés ;
  persistance refusée avant écriture sur l'écart brut des recouvrements ;
- état final après refus : rollback vert, profil robuste actif, cibles zéro,
  axes libérés, Z et deux CFS conformes ;
- reprise logique exacte : candidat `121` positions, écart brut maximal
  `0,147858 mm`, écart aligné maximal `0,043745029 mm`, moyenne alignée
  `0,013871331 mm`, empreinte de matrice
  `9d975c32512b840cf06c0b942af6e4713f7f69c62ce35e140c41941540153100` ;
- reprise logique posée et validée deux fois sous
  `20260824-155319-g4-k1-control-composite-mesh-recovery-v1` ;
- profil `k1_p001_t055_r001_n11x11` persistant : présent et validé, onze lignes
  de onze valeurs ;
- profil robuste `k1_p001_t055_r001_n06x06` : toujours chargé après la reprise ;
- état final : `standby`, cibles zéro, axes non référencés, Z `−0,04 mm`,
  stockage `ok` et deux CFS connectés.

## Prochaine action sûre

Préparer et exécuter une comparaison bornée de premières couches entre le
profil robuste `6 × 6` et le profil composite `11 × 11`, à matériau, plaque,
températures et G-code identiques. Cette gate ne demande aucun nouveau palpage.
Le mode Précision reste caché dans l'interface jusqu'à un gain observable.
