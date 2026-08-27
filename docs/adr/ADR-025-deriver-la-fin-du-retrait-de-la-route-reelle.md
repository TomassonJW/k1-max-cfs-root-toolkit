# ADR-025 — Dériver la fin du retrait de la route réelle

Date : 2026-08-27

Statut : accepté

## Contexte

Le premier garde hors imprimante modélisait un champ abstrait
`stock_unload_state`. Le préflight live prouve que la K1 n'expose aucun champ de
ce nom ni d'équivalent direct. La capture historique montre aussi que
`box.t_command` reste vide pendant le retrait officiel.

## Options

### 1. Inventer un état “terminé” dans l'adaptateur

Refusé. Cela transformerait une supposition en preuve et pourrait valider un
faux succès.

### 2. Utiliser seulement `box.t_command`

Refusé. Ce champ est resté vide avant, pendant et après le passage réel.

### 3. Utiliser le retour de requête et la disparition réelle de la route

Retenu. Le contrôleur connaît localement la tentative unique. Il exige ensuite
que la route fraîchement engagée disparaisse et que `t_command` soit vide. La
coupure thermique reste une preuve séparée et obligatoire.

## Décision

Le champ abstrait `stock_unload_state` est retiré du contrat du garde. La fin
est une preuve composée : requête revenue sans erreur de transport, route
attendue libérée, absence de commande CFS active et nettoyage thermique
confirmé.

Le résultat HTTP n'est pas une preuve suffisante. Une route encore engagée
conduit à un timeout KO sans second retrait.

## Conséquences

- le modèle correspond aux champs réellement présents sur la K1 ;
- la preuve de retrait repose sur un effet CFS observable ;
- `t_command` reste une garde contre une activité étrangère, pas un témoin du
  cycle stock ;
- le futur adaptateur devra redacter les identités de `box` ;
- l'état actuel sans route engagée refuse correctement toute tentative ;
- aucune pose ou action physique n'est autorisée par cette décision.
