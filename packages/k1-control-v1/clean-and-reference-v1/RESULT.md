# Résultat actuel

Statut : **nettoyage automatique clos KO ; nettoyage manuel obligatoire**.

Le premier cycle a fini avec les chauffes à zéro et les configurations exactes,
mais il n'a pas nettoyé la buse. Sa lenteur et son refroidissement au contact de
la brosse du bac ont recollé le filament sur la buse. Thomas a nettoyé la buse à
la main. Ce passage n'est pas promouvable et ne valide pas la deuxième exigence
du Goal 3.

Le V2 a abandonné cette brosse et le frottement pendant le refroidissement,
mais sa buse était déjà propre et aucune préparation filament ne l'avait
précédé : ce passage est non probant. Après chargement, petite purge et retrait
manuels par Thomas, le V3 a exécuté huit allers-retours diagonaux à `F12000`, à
`Z2,5`, puis une remontée immédiate à `Z7,5`, une sortie et un refroidissement
au parc sûr. La référence finale prévue n'a pas été exécutée et la voie est
maintenant fermée.

Le runner physique refuse chaque
effet sans verdict humain exact, présence devant la K1, plateau libre, brosses
et buse visibles et arrêt immédiat possible. Il ne contient aucune extrusion,
commande CFS, écriture distante ou relance automatique.

Avant le second essai, du filament pourra être chargé, légèrement purgé puis
retiré manuellement avec les fonctions stock sous observation. Aucune commande
CFS non qualifiée n'est ajoutée au runner. Le second nettoyage attend le GO
explicite de Thomas après cette préparation. Le préflight frais est déjà vert :
aucun G-code, mouvement ou chauffage ; cibles zéro, configurations exactes et
profil `11 × 11` actif.

Un premier passage s'est arrêté après la chauffe faute de verdict reçu dans la
fenêtre interactive. Aucun nettoyage n'a été exécuté. La coupure de sécurité a
confirmé les deux cibles à zéro, les configurations exactes et aucun mouvement.
La chauffe séparée est supprimée du nouveau programme : le cycle suivant finit
obligatoirement chauffes à zéro sans attendre un message.

Le cycle V3 est techniquement vert, sans retry, avec cibles zéro, tête à
`X81 Y280 Z35`, buse à `141,07 °C`, configurations exactes et profil `11 × 11`
inchangé. Thomas a toutefois jugé le nettoyage visible non convaincant. Aucun
V4 et aucune référence Z finale ne sont autorisés par cette gate. La procédure
retenue est le nettoyage manuel de la buse par Thomas.
