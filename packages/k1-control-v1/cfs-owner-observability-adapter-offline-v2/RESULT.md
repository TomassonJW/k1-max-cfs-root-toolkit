# Résultat — observabilité propriétaire CFS V2 hors imprimante

Statut : `CLOSED_OFFLINE_12_OF_12`

Les `12/12` scénarios sont déterministes. L’adaptateur refuse une reconnexion
de l’observateur, toute transition CFS notifiée, une fenêtre périmée, une forme
inconnue, un Z invalide et toute substitution par `homing_origin`.

La limite reste explicite : une reconnexion interne du pilote CFS qui ne
produirait absolument aucun changement Moonraker n’est pas prétendue
observable. Le chemin propriétaire exige donc une connexion continue et se
ferme sur toute interruption réellement visible.
