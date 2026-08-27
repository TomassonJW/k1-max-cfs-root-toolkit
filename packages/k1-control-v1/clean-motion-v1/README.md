# G4-K1-CONTROL-CLEAN-MOTION-V1

Statut : **clos OK ; deux brosses qualifiées à froid ; meilleur profil observé
`11 × 11` toujours actif**.

Cette gate est l'exigence 1 sur 7 du Goal 3. Elle a qualifié les coordonnées,
les hauteurs et les mouvements froids nécessaires à une future recette de
nettoyage. Elle ne qualifie pas encore la chauffe, l'extrusion, la purge visible,
l'efficacité du nettoyage à chaud ni la référence Z finale.

## Géométrie physique qualifiée

- Brosse principale : `X66..99`, `Y303..307`, contact à `Z2`.
- Sortie sûre de la brosse principale : remontée verticale avant tout mouvement
  hors de la zone.
- Brosse du bac de purge : carré utile `X203..206`, `Y304..305`, à `Z32`.
- Approche et sortie sûres de la seconde brosse : `X203 Y273 Z32`.
- La seconde brosse impose `Z >= 30` pendant toute approche.

Ces valeurs proviennent de captures manuelles GET à 2 Hz. Codex n'a envoyé
aucun mouvement pendant leur acquisition. Thomas a placé la buse sur chaque
point, confirmé le contact `Z2`, la remontée sûre et les quatre limites de la
seconde brosse.

## Qualifications de mouvement

- C, D1, D2 et D3 : acceptés humainement.
- E1 : techniquement sans collision, mais refusé comme test de nettoyage car
  volontairement trop loin des brosses.
- E2 : un balayage de la brosse principale de `X99` à `X66`, à `Y305 / Z2` et
  `5 mm/s` ; verdict `E2 OK`.
- E3 puis E3-R2 : affinage de la marge Y de la brosse du bac.
- E4 : un aller-retour `X203 ↔ X206` à `Y305`, puis un autre à `Y304`, toujours
  à `Z32` et `3 mm/s` ; verdict `E4 OK`.

Après chaque effet, la K1 est restée en attente, chauffes à zéro, sans route CFS,
avec les configurations inchangées et le profil
`k1_p001_t055_r001_n11x11` actif. La position finale est
`X203 Y273 Z32`.

## Limite et suite

La géométrie peut maintenant alimenter une recette versionnée, mais cette gate
n'autorise aucun nouveau mouvement. La suite est
`G4-K1-CONTROL-CLEAN-AND-REFERENCE-V1` : choisir explicitement la matière et la
température, chauffer au-dessus du réceptacle, vérifier le débit visible,
qualifier un nettoyage borné, couper les chauffes puis exécuter une seule
référence Z finale avec buse propre.

Les preuves exactes sont dans `evidence-map.json`; les décisions humaines et
coordonnées sont dans `human-observation-form.json`.
