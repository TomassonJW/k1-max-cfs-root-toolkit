# Dérive réelle du mesh à 55 °C, mesurée le 1er septembre 2026

## Protocole

Filament retiré par le cycle stock, tête vide prouvée par
`filament_switch_sensor filament_sensor_2` à faux — lecture physique valide,
puisque Klipper met `filament_present` à jour depuis le gestionnaire de bouton
même lorsque le capteur est désactivé. Buse nettoyée à la main par Thomas avant
tout contact, conformément à ADR-045.

Plateau `55 °C`, buse `140 °C`, trempe `200 s`, puis `G28` et un maillage
`6 × 6` Lagrange sur `5,5 → 295,295`, comparé point à point au profil
enregistré `k1_p001_t055_r001_n06x06`.

## Résultat

| Grandeur | Valeur |
|---|---|
| points comparés | 36 |
| écart moyen | `−0,034468 mm` |
| écart RMS | `0,040285 mm` |
| pire écart | `−0,071157 mm` |
| amplitude du profil de référence | `0,518500 mm` |
| amplitude de la mesure fraîche | `0,571637 mm` |

Écart-type autour de la moyenne : `0,0209 mm`. Pire écart une fois la moyenne
retirée : `0,0367 mm`.

## Lecture

ADR-013 donne le bruit de mesure de cette machine entre deux médianes
indépendantes : `0,0108 mm` en moyenne, `0,0140 mm` RMS, `0,0344 mm` au pire.

La dérive observée se décompose donc en deux parties très différentes :

- **une translation globale de `−0,034 mm`**, trois fois le bruit moyen : elle
  est réelle ;
- **un changement de forme d'écart-type `0,021 mm` et de pire écart
  `0,037 mm`**, soit l'ordre de grandeur du bruit de mesure : il n'est pas
  distinguable du bruit.

## Décision

Le profil `k1_p001_t055_r001_n11x11` **n'est pas à reconstruire**. Sa forme
reste valide ; ce qui a bougé est un décalage global, qui est précisément ce
qu'absorbe la calibration Z par profil.

La campagne de reconstruction composite `11 × 11` en sous-grilles de 36 points
est donc reportée : elle coûte plusieurs heures et ne corrigerait rien de
mesurable aujourd'hui. Elle redeviendra nécessaire si un contrôle ultérieur
montre un changement de forme au-dessus du bruit.

La suite est le carré `280 × 280`, Z réglé à la main pendant la première
couche, puis `KCTRL_Z_SAVE` pour attacher ce Z au profil.
