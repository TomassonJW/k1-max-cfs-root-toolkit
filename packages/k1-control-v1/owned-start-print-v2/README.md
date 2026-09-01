# Owned Start Print V2

Cible exacte : Creality K1 Max, S12 structure 0, firmware 2.3.5.34, kit CFS,
deux unités chaînées.

Ce paquet installe une séquence de démarrage d'impression appartenant à
K1 Control. Il remplace `START_PRINT` en s'appuyant sur le fait que Klipper
analyse sa configuration avec `strict=False` : la dernière définition d'une
section gagne, donc l'inclusion doit rester après `gcode_macro.cfg`.

## Ce que la séquence garantit

1. Le profil de mesh est choisi par la **température de plateau du G-code**.
   `START_PRINT EXTRUDER_TEMP=190 BED_TEMP=55` résout
   `k1_p001_t055_r001_n11x11`. Aucun repli silencieux sur un profil voisin :
   si la bande n'existe pas, la séquence s'arrête en nommant le profil manquant.
2. Le décalage Z vient du **même profil**, lu dans `save_variables`. Un profil
   sans Z accepté refuse de lancer une impression.
3. Une seule référence géométrique. `CX_PRINT_LEVELING_CALIBRATION` est retiré :
   c'est lui qui repalpait le plateau à chaque départ.
4. `CX_NOZZLE_CLEAR` est retiré. Le nettoyage automatique n'a jamais fonctionné
   sur cette machine ; la buse se nettoie à la main avant de lancer.
5. La cible de buse est reprise et **vérifiée** après l'étape CFS, donc aucune
   température de table matière ne peut fuir dans l'impression.

## Contournement stock documenté

`homing_override` se termine par `BED_MESH_PROFILE LOAD="default"`. Tout `G28`
remplace donc silencieusement le mesh actif. C'est la raison pour laquelle le
profil est chargé **après** le dernier référencement, et vérifié ensuite.

## Dépendance Orca restante

Le post-traitement Orca injecte `SET_GCODE_OFFSET Z=... MOVE=1` juste après
`START_PRINT`. Cette ligne écrase le Z du profil. Elle doit être retirée du
profil Orca, sinon le décalage par profil est annulé à chaque impression.

## Commandes ajoutées

| Commande | Rôle |
|---|---|
| `KCTRL_PROFILE_NAME BED=55` | montre le profil et le Z que cette température résout |
| `KCTRL_Z_SAVE [PROFILE=] [Z=]` | enregistre le Z accepté du profil ; sans paramètre, prend le profil actif et le décalage courant |
| `KCTRL_Z_LIST` | liste chaque profil de mesh avec son Z enregistré |
| `KCTRL_START_CONF` | rappelle la famille de profils utilisée |

## Campagne de calibration associée

1. Retirer le filament, plateau à la température visée.
2. Construire le mesh de la bande par sous-grilles de 36 points maximum, puis
   `BED_MESH_PROFILE SAVE=k1_pXXX_tXXX_rXXX_nYYxYY` et `SAVE_CONFIG` (ADR-013).
3. Recharger le filament, imprimer un carré `280 × 280`, régler le Z à la main
   pendant la première couche, puis `KCTRL_Z_SAVE`.
