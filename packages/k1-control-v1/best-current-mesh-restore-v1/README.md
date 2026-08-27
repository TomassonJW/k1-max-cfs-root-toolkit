# G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1

Cette correction retire l'interprétation erronée selon laquelle le `6 × 6`
serait robuste. Tous les profils actuels ont des défauts de bord. Le composite
`11 × 11` est seulement le meilleur profil observé et le moins mauvais dans la
comparaison physique disponible.

La gate charge au plus une fois ce `11 × 11`, relit sa matrice exacte et revient
au `6 × 6` seulement si l'état après envoi devient ambigu. Elle ne contient
aucun fichier distant, restart, chauffage, mouvement, homing, palpage,
extrusion ou impression.

Le terme `robuste` reste désormais réservé à un futur profil dérivé corrigé
point par point et validé physiquement sur toute la zone utile.
