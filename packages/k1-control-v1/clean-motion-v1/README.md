# G4-K1-CONTROL-CLEAN-MOTION-V1

Statut : **sources live qualifiées en lecture seule ; aucune commande
candidate ; aucun effet physique**.

Cette gate est la première tranche physique du Goal 3. Son préalable est
maintenant satisfait : le profil robuste `k1_p001_t055_r001_n06x06` a été
activé et revérifié sous `G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1`. Elle sert
uniquement à mesurer humainement la zone de la brosse et à qualifier une
trajectoire à froid sans collision.

Elle ne qualifie pas encore le nettoyage autonome. Elle interdit chauffage,
extrusion, action CFS, palpage de la brosse, mesure de mesh, écriture Z,
configuration distante, restart et répétition automatique.

Le contrat ne contient volontairement aucune coordonnée ni commande de
mouvement. Les limites de la brosse, la hauteur libre, le premier contact et les
directions sûres d'entrée et de sortie sont encore des faits physiques manquants
qui devront être observés avec Thomas devant la K1.

La capture privée `20260827-clean-motion-v1-read-only-sources-v3` a néanmoins
qualifié les limites logiques et la zone déclarée par le logiciel stock :
X `68…94 mm`, Y `304,5…306,5 mm`, trajet X `20 mm`, delta Z `−0,15 mm`.
Ces nombres restent des indications logicielles, pas une preuve de la brosse
réelle. Voir `RESULT.md` et `evidence-map.json`.

La future session remplira `human-observation-form.json` par checkpoints. Les
commandes candidates ne seront figées qu'après une lecture fraîche des limites
machine et la confirmation humaine des coordonnées. Toute perte de visibilité,
résistance, bruit inhabituel ou état ambigu arrêtera la gate immédiatement.

La suite attend donc Thomas devant la K1, plateau libre et brosse visible. Le
cadre `$session-tas` ne remplace pas ces observations physiques.

Voir aussi `docs/42-clean-motion-v1-premiere-tranche-physique.md`.
