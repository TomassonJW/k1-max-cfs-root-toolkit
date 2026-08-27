# G4-K1-CONTROL-CLEAN-MOTION-V1

Statut : **protocole préparé ; aucune commande candidate ; aucun effet K1**.

Cette gate sera la première tranche physique du Goal 3 après l'activation
réussie du profil robuste. Elle sert uniquement à mesurer humainement la zone de
la brosse et à qualifier une trajectoire à froid sans collision.

Elle ne qualifie pas encore le nettoyage autonome. Elle interdit chauffage,
extrusion, action CFS, palpage de la brosse, mesure de mesh, écriture Z,
configuration distante, restart et répétition automatique.

Le contrat ne contient volontairement aucune coordonnée ni commande de
mouvement. Les limites de la brosse, la hauteur libre, le premier contact et les
directions sûres d'entrée et de sortie sont encore des faits physiques manquants
qui devront être observés avec Thomas devant la K1.

La future session remplira `human-observation-form.json` par checkpoints. Les
commandes candidates ne seront figées qu'après une lecture fraîche des limites
machine et la confirmation humaine des coordonnées. Toute perte de visibilité,
résistance, bruit inhabituel ou état ambigu arrêtera la gate immédiatement.

Voir aussi `docs/42-clean-motion-v1-premiere-tranche-physique.md`.
