# Diagnostic Z avec stabilisation thermique 200 s

Cette gate compare le Z accepté `−0,04 mm` dans la même fenêtre thermique que
sa calibration. Elle reprend le petit fichier de deux couches déjà qualifié et
insère seulement trois commandes avant le départ possédé : plateau à `55 °C`,
attente de cette cible, puis stabilisation `200 s`.

La buse reste froide pendant ces `200 s`. Ensuite, le même départ possédé fait
une seule référence Z propre à `140/55 °C`, recharge le mesh `11 × 11`, purge
visiblement puis imprime le même motif. Aucun Z n'est enregistré et aucun mesh
n'est mesuré.

Interprétation :

- couche bonne à `−0,04` sans réglage : la stabilisation thermique explique le
  décalage et le départ possédé devra intégrer cette attente ;
- couche encore trop haute : la piste thermique est rejetée et une
  recalibration Z bornée devient justifiée ;
- réglage humain avant le verdict ou état ambigu : diagnostic non concluant,
  arrêt sans retry.

La fin reste celle du fichier d'essai : chauffes à zéro et moteurs libérés,
sans prétendre qualifier le futur parcage de production. T1A reste engagé.
