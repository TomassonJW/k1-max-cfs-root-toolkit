# Diagnostic Z avec stabilisation thermique 200 s

Cette gate compare le Z accepté `−0,04 mm` dans la même fenêtre thermique que
sa calibration. Elle reprend le petit fichier de deux couches déjà qualifié.
Le pilote chauffe le plateau à `55 °C`, attend la cible, stabilise exactement
`200 s`, remet la cible du plateau à zéro, puis seulement après crée le jeton
humain « buse nettoyée » et lance le départ possédé. Le jeton de cinq minutes
ne peut donc plus expirer pendant la stabilisation.

La buse reste froide pendant ces `200 s`. Si l'écran est encore sur un ancien
fichier `complete`, le pilote efface uniquement cet état terminal avant la
chauffe ; il ne rejoue rien. Ensuite, le même départ possédé fait
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

La fin exige chauffes à zéro, plateau descendu à `Z50`, tête parquée à
`X203 Y273`, commandes terminées puis moteurs libérés. T1A reste engagé. Ce
parcage qualifie l'essai borné, pas encore toutes les fins de production.
