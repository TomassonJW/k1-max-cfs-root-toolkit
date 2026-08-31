# Résultat — orchestrateur stock-derived hors imprimante V1

Statut : **orchestrateur pur et persistable, sans connecteur, non installable**.

La matrice déterministe obtient `19/19` scénarios verts.

Le chemin complet est maintenant encodé autour des primitives revues : retrait
au cutter avant nettoyage si nécessaire, géométrie R4 sans filament, chargement
et purge au bac, contrôle caméra, ligne stock exacte, impression, changements,
roulement équivalent et fin complète.

Le roulement `T1A -> T2D` est accepté dans la matrice uniquement lorsque les six
champs d'identité concordent et qu'il n'existe qu'une seule bobine disponible.
Une couleur proche, un second spare identique, une température modifiée ou un
contexte de reprise différent ferment le cycle.

Chaque effet possède un ticket à tentative unique. Une reprise du processus
avec un ticket seulement revendiqué donne `blocked_uncertain`; elle ne réémet
pas le cutter, le retrait, le chargement ou la purge.

La seule couture encore absente avant un candidat installable désactivé est
l'overlay qui transforme la fin de géométrie R4 en jeton consommable par ce
cycle, puis le vrai composant Moonraker qui persiste l'état et distribue les
commandes. Les profils thermiques autres que `55 / 140 / 190` restent fermés
tant que leur mesh 11x11 et leur Z canonique ne sont pas qualifiés.
