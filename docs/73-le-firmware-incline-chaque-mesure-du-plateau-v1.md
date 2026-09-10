# 73 — Le firmware incline chaque mesure du plateau de 0,10 mm avant de l'enregistrer

Date : 2026-09-10, 11:50 à 12:15. Analyse à froid, en lecture seule, du
journal `klippy.log` et des profils enregistrés dans `printer.cfg` pour les
cinq mesures du matin (vis à 09:08, quatre quarts de 09:35 à 09:52). Demandée
par Thomas sur le cube de 11:15 : « le fond de la plaque est trop proche de la
buse, et l'avant trop loin ! Ou le maillage n'est pas bien respecté ? ».
Reconstruction et matrices dans `experiments/2026-09-10-mesh-brut-sans-rampe/`.

## Résultat en une phrase

Le maillage est respecté ; c'est le maillage qui est faux. Entre le contact
mesuré (ligne `probe at X,Y is z=` du journal) et le profil enregistré, le
micrologiciel ajoute à chaque mesure une correction constante sur une rangée et
décroissante d'une rangée à la suivante, **0,10 mm au total du premier rang au
dernier**, quelle que soit la taille de la grille. Les quatre quarts sont
mesurés dans le même sens (avant vers arrière) ; recollés, ils empilent deux
rampes : l'avant est remonté de 0,10 et l'arrière abaissé de 0,10 par rapport
au centre. Le profil en service dit « avant −0,18, arrière −0,17 » ; le plateau
réel dit « avant −0,28, arrière −0,07 ». La buse imprime donc **0,10 trop loin
à l'avant et 0,10 trop près à l'arrière** : le symptôme de Thomas, dans le bon
sens et dans la bonne taille.

## Ce qui est mesuré : enregistré moins brut, rangée par rangée

| Mesure | Rangs | Correction par rang (mm), du premier au dernier | Pas |
|---|---|---|---|
| `K1_SCREWS` 09:08, 5×5 | 5 | +0,140 · +0,115 · +0,090 · +0,065 · +0,040 | 0,025 |
| `K1_SUB_SW` 09:35, 6×6 | 6 | +0,299 · +0,279 · +0,259 · +0,239 · +0,219 · +0,199 | 0,020 |
| `K1_SUB_SE` 09:40, 6×6 | 6 | +0,263 · +0,243 · +0,223 · +0,203 · +0,183 · +0,163 | 0,020 |
| `K1_SUB_NW` 09:44, 6×6 | 6 | +0,157 · +0,137 · +0,117 · +0,097 · +0,077 · +0,057 | 0,020 |
| `K1_SUB_NE` 09:48, 6×6 | 6 | +0,184 · +0,164 · +0,144 · +0,124 · +0,104 · +0,084 | 0,020 |

À l'intérieur d'une rangée la correction ne varie pas (écart sous 0,001 sur
les 169 points). La constante de départ change d'une mesure à l'autre (de
+0,140 à +0,299) : elle est retirée par le recollage des quarts et par la mise
à zéro au point de référence, elle ne fait pas de mal. La pente, elle, reste
dans le profil.

**Le dernier contact de chaque mesure est enregistré tel quel**, sans
correction, et dans trois mesures sur cinq il est lui-même faux :

| Mesure | Dernier contact | Brut | Contact précédent | Même point, autre mesure |
|---|---|---|---|---|
| `K1_SUB_SW` | X5 Y150 | +0,155 | −0,077 | −0,039 (NW, 5 min plus tard) |
| `K1_SUB_SE` | X150 Y150 | +0,141 | +0,016 | −0,009 / −0,004 / −0,026 (SW, NW, NE) |
| `K1_SUB_NE` | X150 Y295 | +0,016 | −0,085 | −0,074 (NW) |
| `K1_SUB_NW` | X5 Y295 | −0,022 | −0,035 | sans double |
| `K1_SCREWS` | X277 Y274 | −0,110 | −0,099 | sans double |

Ce dernier contact arrive 13 à 17 s après le précédent, contre 5 à 6 s entre
deux points ordinaires : le micrologiciel fait autre chose entre les deux
(`Start Step Lost Check` dans le journal, puis le dernier point).

## Le plateau réel et le profil en service

Moyenne par rangée, zéro au point de référence X150 Y150 (ADR-046) :

| Y | Contacts bruts recollés | Profil `k1_p001_t055_r001_n11x11` en service | Écart |
|---|---|---|---|
| 5 (avant) | −0,283 | −0,184 | −0,099 |
| 34 | −0,206 | −0,127 | −0,079 |
| 63 | −0,140 | −0,081 | −0,059 |
| 92 | −0,078 | −0,039 | −0,039 |
| 121 | −0,039 | −0,020 | −0,019 |
| 150 (centre) | −0,010 | −0,012 | +0,001 |
| 179 | +0,009 | −0,013 | +0,022 |
| 208 | +0,005 | −0,037 | +0,042 |
| 237 | −0,022 | −0,084 | +0,062 |
| 266 | −0,054 | −0,136 | +0,082 |
| 295 (arrière) | −0,065 | −0,171 | +0,106 |

Les colonnes, elles, ne bougent pas (écart sous 0,006 sur les onze moyennes
par X) : la rampe suit l'ordre de mesure, rangée après rangée, et l'ordre de
mesure suit Y.

## Pourquoi les valeurs brutes sont les bonnes

- Les dix-neuf points partagés par deux quarts sont mesurés deux fois, à
  quatre à dix minutes d'écart et à des rangs différents de leur mesure ; les
  contacts bruts s'y retrouvent à 0,039 mm près au pire, 0,015 en général. Une
  dérive réelle de 0,10 sur la durée d'une mesure les ferait diverger d'autant.
- La première couche du cube de 11:15 a été imprimée sur le profil en service,
  Z réglé en direct au centre : Thomas a vu la buse trop loin à l'avant et trop
  près à l'arrière. L'écart entre le profil et le brut vaut −0,10 à l'avant et
  +0,10 à l'arrière.
- Le rapport `KCTRL_BED_SCREWS` du matin lisait la grille enregistrée, donc
  plate de 0,10 : il a vu 0,077 mm d'écart entre vis quand les contacts bruts
  en montrent 0,177 (avant −0,26 / −0,24, arrière −0,08 / −0,10). Les trois
  passes de vis de la matinée se sont arrêtées sur un plateau encore incliné de
  près de 0,18 mm, l'arrière plus haut que l'avant.

## Où c'est, et où ce n'est pas

- Pas dans Python : `probe.py` (`_probe`, `run_probe`, `_move_next`) et
  `bed_mesh.py` (`probe_finalize`, `save_profile`, `ZMesh.build_mesh`) sont le
  code Klipper d'origine, sans correction, et `probe_finalize` reçoit déjà les
  valeurs corrigées.
- Dans le module compilé `prtouch_v2_wrapper` : il contient les noms
  `bed_mesh_post_proc`, `correct_bed_mesh_data`, `_correct_bed_mesh_one_data`,
  et journalise par point `[RDY_POS]` et `[GET_BEST_RDY_Z] Src=RDY … cal_z=…`,
  puis `Start Step Lost Check` après le dernier point.
- L'origine du 0,10 n'est pas isolée. `[prtouch_v2]` porte `noz_ex_com: 0.09`
  et `tilt_corr_dis: 0.05` ; la deuxième chaîne n'apparaît pas dans le `.so`
  v2. Un total fixe quelle que soit la durée (2 min 30 pour les vis, 4 min par
  quart) exclut une dérive mesurée à chaque fois.
- Attendu, non vérifié : le profil `default` de Creality, mesuré en une seule
  passe de 6×6, porte la même rampe (arrière abaissé de 0,10 par rapport à
  l'avant).

## Ce qui est prêt

`experiments/2026-09-10-mesh-brut-sans-rampe/reconstruire.py` relit les 169
contacts bruts, écarte le dernier contact d'un quart quand un autre quart
couvre le point, recolle les quarts comme `KCTRL_MESH_MERGE` (décalages
+0,018 / −0,002 / +0,017, résidus sous 0,035), met le centre à zéro et écrit
la matrice en deux fichiers, parce que `KCTRL_MESH_APPLY` refuse un déplacement
de plus de 0,15 mm par point et que l'avant en demande 0,158 :

```
k1_p001_t055_r001_n11x11.etape1.json   moitié du chemin, plus grand pas 0,079
k1_p001_t055_r001_n11x11.etape2.json   profil reconstruit, plus grand pas 0,079
```

Application, sur accord de Thomas, machine à l'arrêt (`print_stats.state`
autre que `printing`), sans contact matériel : copier les deux fichiers dans
`/usr/data/printer_data/config/`, puis à la console

```
KCTRL_MESH_APPLY FILE=/usr/data/printer_data/config/k1_p001_t055_r001_n11x11.etape1.json
KCTRL_MESH_APPLY FILE=/usr/data/printer_data/config/k1_p001_t055_r001_n11x11.etape2.json
```

Chaque appel garde une sauvegarde de la matrice précédente et
`KCTRL_MESH_UNDO` revient en arrière. Ensuite, carré 280×280, Z réglé en
direct, `KCTRL_Z_SAVE` après l'impression : le zéro Z réglé sur le cube est
perdu (remis à zéro par l'interface à 11:43:08) et un nouveau profil demande de
toute façon un nouveau Z.

## Suite structurelle

Toute mesure future refaite par `BED_MESH_CALIBRATE` portera la même rampe.
La correction durable est que `KCTRL_MESH_ACQUIRE` et `KCTRL_BED_SCREWS`
capturent les lignes `probe at … is z=` pendant la mesure (un
`register_output_handler` dans `kctrl_mesh.py`) et que `KCTRL_MESH_MERGE` et
`KCTRL_SCREWS_REPORT` travaillent sur ces contacts bruts, plus jamais sur les
profils enregistrés. Mission distincte, à ouvrir après validation du carré sur
le profil reconstruit.
