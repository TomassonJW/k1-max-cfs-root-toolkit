# ADR-064 — Un maillage sert à ±5 °C de sa température ; une nouvelle bande part d'un maillage existant

Date : 2026-09-14

Statut : **acceptée ; écrite, testée et installée le 14 septembre à 17:58,
machine à l'arrêt** (voir `STATE.md`).

Répond au point 6 du flux quotidien (`GOALS.md`) : tout se déroule aux bonnes
températures, calibré, sans intervention.

## Contexte

`START_PRINT` choisissait le maillage par la température exacte du plateau
du G-code : `k1_p001_t055_r001_n11x11` pour 55 °C, et un refus pour tout
autre degré. Seul le 55 existe. Chaque nouvelle bande coûte une calibration
complète, dont cinq cubes imprimés. Thomas, le 14 septembre : dupliquer le
55 pour 50, 60 et 65, « ou alors accepter une tolérance de ±5 degrés », et
partir d'une copie pour 70 plutôt que de tout refaire.

## Décision

1. **Tolérance de bande.** `START_PRINT` et `KCTRL_PROFILE_NAME` prennent,
   dans la famille `k1_p<plaque>_t<NNN>_r<rev>_n<X>x<Y>`, le profil le plus
   proche à `band_tolerance_c` près (5, dans `_KCTRL_START_CONF`) ; à écart
   égal, le plus froid. Le 55 imprime de 50 à 60 °C, le 70 de 65 à 75 °C.
   Hors bande, refus avant toute chauffe, avec les maillages mesurés et la
   commande à lancer. La tolérance 0 rend la règle exacte.
2. **Pas de copies 50, 60, 65.** Des profils identiques au 55 ne mesurent
   rien et masqueraient qu'aucune bande n'a été calibrée à ces degrés ; la
   tolérance couvre 50 et 60, et 65 relève du 70.
3. **`KCTRL_MESH_COPY BED_TEMP=<t> [SOURCE=<profil>]`** crée le profil d'une
   autre température depuis un maillage existant : points et paramètres
   recopiés dans le bloc autosave, profil enregistré à chaud (pas de
   `SAVE_CONFIG`), Z `z_<source>` recopié. N'écrase jamais un profil. Le Z
   copié est un point de départ : à affiner sur le carré, puis `KCTRL_Z_SAVE`.

## Conséquences

- Le 70 est une copie du 55, pas une mesure : un plateau plus chaud gondole
  un peu plus. Si la première couche le montre, calibrer la bande 70 pour de
  vrai ; la copie aura servi en attendant.
- Trou volontaire de 61 à 64 °C : aucun profil ne le couvre, le refus le dit.
  Un fichier à 62 °C demande `KCTRL_MESH_COPY BED_TEMP=62` ou un changement
  de température dans le trancheur.
- Les profils `default`, `_tuned_v…`, d'autre plaque ou d'autre grille ne
  sont jamais retenus.

Tests : `tests/test_mesh_band_tolerance_v1.py` (30).
