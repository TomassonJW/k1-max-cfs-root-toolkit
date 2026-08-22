# CALIBRATION-UI-MATRIX-V1

Statut : candidat hors imprimante, non autorisé.

Ce delta étend l'interface de calibration déjà installée aux matrices
`3×3`, `4×4`, `5×5`, `6×6`, `9×9`, `11×11` et `15×15`.

- Lagrange reste limité à six points par axe.
- Toute matrice supérieure à `6×6` utilise automatiquement l'interpolation
  bicubique.
- Le runtime Klipper existant accepte déjà ces tailles ; aucun fichier Klipper,
  mesh, Z, profil Orca ou composant CFS n'est modifié.

La pose future remplacera uniquement le contrôleur de calibration et deux
fichiers statiques, après backup exact, puis redémarrera seulement Moonraker.
Elle ne lance aucune calibration.

Après revue du commit figé, la seule autorisation de pose recevable est :
`GO G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1`.
