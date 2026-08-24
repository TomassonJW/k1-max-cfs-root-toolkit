# G4-K1-CONTROL-COMPOSITE-MESH-V1

Date : 2026-08-24

Statut : recette de fusion et rendu du profil testés hors imprimante ; campagne,
pose et persistance non préparées tant que SUBGRID-V1 n'est pas qualifiée
physiquement

## But

Construire un profil `k1_p001_t055_r001_n11x11` à partir de 121 contacts
PRTouch réels, sans dépasser 36 contacts par séquence et sans redémarrer
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
| `even_even` | `5..295 mm` | `5..295 mm` | `6 × 6` Lagrange | 36 |
| `odd_even` | `34..266 mm` | `5..295 mm` | `5 × 6` Lagrange | 30 |
| `even_odd` | `5..295 mm` | `34..266 mm` | `6 × 5` Lagrange | 30 |
| `odd_odd` | `34..266 mm` | `34..266 mm` | `5 × 5` Lagrange | 25 |

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
- une valeur absente, dupliquée ou non finie.

Le seul résultat accepté contient quatre passages, 121 valeurs distinctes et
les paramètres finaux `11 × 11`, `5..295 mm`, `mesh_pps=2`, bicubique.

## Pourquoi l'endpoint `update_mesh` ne suffit pas

Le `bed_mesh.py` Creality expose bien `update_mesh`, mais cette méthode remplace
uniquement `probed_matrix` dans le `ZMesh` déjà actif. Elle ne reconstruit pas
ses paramètres `x_count`, `y_count`, bornes et algorithme. Injecter 121 valeurs
après le dernier passage `5 × 5` créerait donc un profil incohérent.

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
- parse Klipper exact du candidat : non exécuté ;
- déployeur et orchestrateur de campagne : non créés ;
- SUBGRID-V1 physique : non exécutée ;
- campagne 121 contacts : non exécutée ;
- profil composite sur la K1 : absent.

## Prochaine action sûre

Clore NAVIGATION-V1, installer SUBGRID-V1, puis exécuter son unique essai
`5 × 5` avec une confirmation fraîche de plateau libre. Aucun fichier de cette
gate complète ne doit être posé avant cette preuve.
