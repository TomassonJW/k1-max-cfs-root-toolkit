# G4-K1-CONTROL-CLEAN-MOTION-V1

Statut : **checkpoint C techniquement vert ; meilleur profil `11 × 11` actif ;
verdict visuel humain attendu avant tout mouvement suivant**.

Cette gate est la première tranche physique du Goal 3. Son préalable corrigé
est satisfait : `G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1` a remis actif le
meilleur profil observé `k1_p001_t055_r001_n11x11`. Tous les profils actuels ont
des défauts de bord ; aucun n'est qualifié robuste. Elle sert
uniquement à mesurer humainement la zone de la brosse et à qualifier une
trajectoire à froid sans collision.

Elle ne qualifie pas encore le nettoyage autonome. Elle interdit chauffage,
extrusion, action CFS, palpage de la brosse, mesure de mesh, écriture Z,
configuration distante, restart et répétition automatique.

Le contrat de départ ne contenait volontairement aucune coordonnée ni commande
de mouvement. Les limites physiques de la brosse, la hauteur libre, le premier contact et les
directions sûres d'entrée et de sortie sont encore des faits physiques manquants
qui devront être observés avec Thomas devant la K1.

La capture privée `20260827-clean-motion-v1-read-only-sources-v3` a néanmoins
qualifié les limites logiques et la zone déclarée par le logiciel stock :
X `68…94 mm`, Y `304,5…306,5 mm`, trajet X `20 mm`, delta Z `−0,15 mm`.
Ces nombres restent des indications logicielles, pas une preuve de la brosse
réelle. Voir `RESULT.md` et `evidence-map.json`.

Thomas a maintenant confirmé le plateau libre, la brosse visible, la buse
observable et l'arrêt immédiat possible. `human-observation-form.json` enregistre
ces quatre faits. Les commandes restent séparées par checkpoints : toute perte de visibilité,
résistance, bruit inhabituel ou état ambigu arrêtera la gate immédiatement.

Le premier mouvement a tenu compte du comportement stock : `G28` recharge
`default`, puis le checkpoint a rechargé explicitement le `11 × 11`, commandé
`Z=50 mm` et attendu l'arrêt. Il n'a ni chauffé, ni extrudé, ni agi sur le CFS,
ni mesuré un mesh.

Le premier validateur a lu `50,23 mm` sur la position physique compensée par le
mesh et a produit un faux KO malgré la consigne `Z=50`. La récupération a
seulement envoyé `TURN_OFF_HEATERS` et rechargé le `11 × 11`, sans mouvement.
Le validateur corrigé lit la position G-code `50,00 mm` et borne séparément la
compensation physique. La validation R2 est verte. Le checkpoint n'a pas été
rejoué et ne doit pas l'être.

Voir aussi `docs/42-clean-motion-v1-premiere-tranche-physique.md`.
