# Résultat final

Statut : **CLOSED OK — `CLEAN_MOTION_V1_OK`**.

Les sources logicielles stock annonçaient une zone approximative
`X68..94 / Y304,5..306,5`, mais elles n'ont pas été promues en vérité physique.
Thomas a cartographié manuellement les deux brosses sous deux captures GET à
2 Hz :

- brosse principale : `X66..99 / Y303..307`, contact parfait à `Z2` ;
- brosse du bac : `X203..206 / Y304..305`, à `Z32`, avec approche et sortie
  sûres par `X203 Y273 Z32`.

C, D1, D2 et D3 sont humainement acceptés. E1 a été techniquement sûr mais
refusé comme test de nettoyage car sans contact utile. E2 a qualifié un passage
principal de `X99` à `X66` à `Y305 / Z2 / 5 mm/s`. E3 puis E3-R2 ont permis de
préciser la petite brosse. E4 a exécuté le carré exact demandé : aller-retour à
`Y305`, puis à `Y304`, entre `X203` et `X206`, à `Z32 / 3 mm/s`. Thomas a rendu
`E2 OK` et `E4 OK`.

Deux tentatives E3-R2 ont été bloquées avant effet parce que leur départ
versionné était encore celui d'E3. Une lecture fraîche a séparé position logique
et physique ; le candidat a été corrigé puis exécuté une fois. Aucun retry
incertain ni mouvement caché n'a eu lieu.

État final prouvé après E4 :

- `standby` ;
- position G-code `X203 Y273 Z32` ;
- chauffes demandées à zéro ;
- aucune route CFS ni commande CFS active ;
- cinq configurations inchangées ;
- profil `k1_p001_t055_r001_n11x11` actif avec matrice exacte ;
- aucune extrusion, chauffe, mesure de mesh, écriture distante ou restart.

La gate qualifie uniquement le mouvement froid. Elle fournit la géométrie à la
gate suivante `G4-K1-CONTROL-CLEAN-AND-REFERENCE-V1`, qui doit encore qualifier
matière et température explicites, écoulement dans le bac, nettoyage chaud
visible, arrêt thermique et unique référence Z finale avec buse propre.

Vérifications locales finales : `40/40` tests ciblés CLEAN-MOTION et registre,
suite complète de `553` tests dont `550` verts et `3` ignorés connus, et `64`
scripts PowerShell relus sans erreur.
