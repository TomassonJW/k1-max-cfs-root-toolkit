# Transport hors imprimante du garde de retrait CFS V1

Date : 2026-08-27

Mission : `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-TRANSPORT-OFFLINE-V1`

Verdict : **OK hors imprimante ; aucun connecteur réel ; production fermée**.

## Ce qui est maintenant prouvé

Le transport simulé relie le garde à l'adaptateur déjà qualifié sans réseau ni
processus externe. Il accepte seulement :

- `BOX_QUIT_MATERIAL` ;
- `TURN_OFF_HEATERS`.

Chaque commande est tentée au plus une fois. Un délai dépassé ou une coupure
rend son effet inconnu : la même commande n'est jamais renvoyée. Si le retrait
est incertain, l'unique tentative d'arrêt thermique reste permise. Un second
retrait ou un second arrêt thermique est refusé avant le faux endpoint.

Une durée ou une réponse de commande mal formée est journalisée avec un effet
inconnu avant le refus ; l'audit ne perd donc pas la tentative déjà consommée.

Une réponse HTTP positive reste seulement un retour de requête. Le succès du
garde exige toujours la route libérée et les deux cibles réellement à zéro.

## Délais simulés

- lecture : `2 s` ;
- retrait stock : `150 s` ;
- arrêt thermique : `15 s`.

La limite exacte est acceptée ; un dépassement, même petit, produit un timeout
fermé. Le temps est injecté : aucun sommeil réel n'existe dans le paquet.

## Matrice

Treize scénarios couvrent succès, limite exacte, faux succès du retrait, faux
succès de l'arrêt thermique, timeout, coupure, lecture perdue, réponse invalide,
doubles commandes, commande inconnue et arrêt demandé avant retrait.

Résultat ciblé : `13/13`.

## Limites

Le paquet ne connaît ni adresse K1, ni authentification, ni encodage Moonraker,
ni comportement réseau réel. Il ne prouve aucun mouvement, retrait ou arrêt
thermique physique. Ces éléments restent fermés jusqu'aux Goals suivants.
