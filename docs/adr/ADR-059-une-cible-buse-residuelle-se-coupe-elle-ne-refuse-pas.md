# ADR-059 — Une cible buse résiduelle se coupe, elle ne refuse pas

Date : 2026-09-05

Statut : **accepté**. Amende le plafond de température au palpage installé le
1er septembre ; posé sur la machine et prouvé à froid.

## Contexte

Le plafond de palpage existe pour une raison mesurée : une buse plus chaude
que la température de contact coule sur le plateau et fausse chaque contact
qui suit. La macro qui ouvre la fenêtre traitait deux situations de façon
opposée, sans que rien ne justifie l'écart :

- une **température** au-dessus du plafond était acceptée, la cible coupée et
  l'attente tenue jusqu'à la redescente ;
- une **cible** au-dessus du plafond interrompait toute la séquence.

Le 5 septembre, trois départs se sont arrêtés au même octet, à `16:21`, `16:43`
et `17:47`, sur le second cas : le fichier tranché chargeait un outil et
purgeait à `220 °C` avant `START_PRINT`, et la cible tenait encore quand la
fenêtre s'ouvrait. Un correctif du profil de tranchage a été tenté le matin. Il
ne pouvait rien : tout fichier déjà tranché gardait le préfixe fautif, et la
copie corrigée n'a pas été celle relancée.

Un refus qu'aucune action de l'opérateur ne lève n'est pas une garde, c'est une
impasse — le même raisonnement qu'ADR-058.

## Décision

Une cible au-dessus du plafond est **coupée et annoncée**, jamais un motif
d'arrêt. La fenêtre est ouverte avant la coupure, pour que le plafond
s'applique aussi à elle.

Ce que cela suppose, et qui est vrai : la fenêtre n'est ouverte que par trois
séquences — le démarrage d'impression, l'acquisition de maillage, la mesure du
plan — toutes propriétaires de ce qu'elles s'apprêtent à palper, et toutes
reposant la température d'impression après le contact. Une cible encore debout
à cet instant est un reste, pas une intention.

La protection ne bouge pas : `M104` et `M109` au-dessus du plafond restent
refusés pendant toute la fenêtre, la buse est toujours ramenée sous le plafond
avant le contact, et un plafond hors bornes reste refusé.

## Conséquences

Un fichier tranché par n'importe quel profil, y compris ceux qui chargent un
outil avant notre départ, démarre. Le prix est une purge inutile et un
référencement de plus quand le profil n'est pas corrigé ; le correctif de
profil reste donc recommandé, mais il n'est plus une condition.

Ce que cela n'apporte pas : la buse peut arriver au palpage avec de la matière
dedans, laissée par une purge que nous n'avons pas demandée. Le plafond limite
l'écoulement, il n'enlève pas une bavure figée. Le nettoyage manuel avant
relance (ADR-045) reste la règle après un départ avorté.

Voir `docs/63-depart-tolere-buse-deja-chaude-v1.md`.
