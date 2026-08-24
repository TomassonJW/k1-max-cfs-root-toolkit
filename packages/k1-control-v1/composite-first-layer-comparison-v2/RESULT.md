# Résultat — COMPOSITE-FIRST-LAYER-COMPARISON-V2

Date : 2026-08-24

Statut : **close — gain central réel, bords KO, aucune promotion du mode
Précision**

## Exécution

- profil testé : `k1_p001_t055_r001_n11x11` ;
- motif : carré première couche `260 × 260 × 0,20 mm` ;
- Z temporaire observé pendant l'impression : `−0,24 mm` ;
- Z persistant accepté : `−0,04 mm`, non modifié ;
- `RESUME` stock a montré qu'il peut restaurer une origine antérieure ; Thomas a
  réappliqué le Z temporaire après la reprise ;
- aucun Z n'a été persisté depuis cet essai.

## Verdict humain et photographique

- centre et grande surface intérieure : clairement meilleurs que le robuste ;
- bords : plusieurs zones froissées, arrachées ou mal compensées ;
- défaut spatial, pas seulement un Z global ;
- résultat insuffisant pour un usage quotidien autonome.

## Contrôle mathématique hors imprimante

Calculé avec le `bed_mesh.py` exact de la K1 :

- reproduction du profil robuste actif : erreur max `0,000000499 mm` ;
- bicubique composite contre surface directe : écart max
  `0,009877883 mm` ;
- même écart dans la bande extérieure de 29 mm : `0,009712808 mm` ;
- dépassement local maximal : `0,000689867 mm` ;
- différence locale de forme composite/robuste après retrait de la constante :
  environ `−0,086850 .. +0,085271 mm`.

Conclusion : l'interpolation est secondaire. Les valeurs spatiales mesurées,
la composition résiduelle et les efforts mécaniques dépendant de la position
sont prioritaires.

## Décision

- conserver le profil physique composite comme source immuable ;
- conserver le robuste comme repli actif ;
- ne pas exposer le mode Précision ;
- ne pas rejouer V2 telle quelle ;
- construire `MESH-EDITOR-OFFLINE-V1`, puis un motif `5..295 mm` et un profil
  dérivé versionné ;
- garder le Z global séparé des corrections locales.

L'état final de la K1 après la fin de l'impression n'a pas été re-préflighté
pendant la rédaction de ce résultat. Aucun état distant final n'est donc
affirmé ici.
