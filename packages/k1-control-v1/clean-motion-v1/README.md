# G4-K1-CONTROL-CLEAN-MOTION-V1

Statut : **checkpoint D1 techniquement vert ; verdict visuel de Thomas attendu ;
D2 verrouillé ; meilleur profil `11 × 11` actif**.

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
compensation physique. La validation R2 est verte. Thomas a confirmé
`CHECKPOINT C OK`. Le checkpoint n'a pas été rejoué et ne doit pas l'être.

Le rapprochement D1 a ensuite été exécuté une seule fois. La tête est passée de
`X156,657 Y142,271 Z50` à `X81 Y280 Z50` à `20 mm/s`. Ce point reste
`24,5 mm` avant le début Y de la zone stock déclarée. La lecture finale confirme
la consigne G-code exacte, le Z physique compensé `50,23 mm`, les chauffes à
zéro, aucune route CFS, les configurations inchangées et le `11 × 11` actif.
Le statut est `D1_TECHNICAL_OK_AWAITING_HUMAN_VERDICT`.

D1 ne doit pas être rejoué. D2, prévu vers `X81 Y300 Z50` à `10 mm/s`, est
interdit tant que Thomas n'a pas confirmé visuellement l'absence de bruit,
contact, obstacle ou perte de visibilité pendant D1.

Voir aussi `docs/42-clean-motion-v1-premiere-tranche-physique.md`.
