# Résultat actuel

Statut : **V1 KO physique ; brosse du bac condamnée ; candidat V2 sur la grande
brosse préparé et préflighté en lecture seule, encore non exécuté**.

Le premier cycle a fini avec les chauffes à zéro et les configurations exactes,
mais il n'a pas nettoyé la buse. Sa lenteur et son refroidissement au contact de
la brosse du bac ont recollé le filament sur la buse. Thomas a nettoyé la buse à
la main. Ce passage n'est pas promouvable et ne valide pas la deuxième exigence
du Goal 3.

Le candidat V2 abandonne complètement cette brosse et le frottement pendant le
refroidissement. Il prévoit six allers-retours à `F6000` sur la grande brosse,
puis coupe la chauffe, remonte immédiatement de `5 mm`, sort de la brosse et
refroidit au parc sûr. La référence finale reste une action séparée après le
verdict visuel.

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

Le candidat V2 et ses empreintes sont revérifiés hors imprimante. Le second
nettoyage reste verrouillé jusqu'au GO humain demandé.
