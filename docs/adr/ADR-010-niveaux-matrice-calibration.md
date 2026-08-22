# ADR-010 — Niveaux de matrice de calibration

Date : 2026-08-22

Statut : candidat hors imprimante

## Contexte

Le contrat produit prévoyait quatre niveaux de maillage jusqu'à `15 × 15`, mais
la première interface installée n'exposait que `3 × 3` à `6 × 6` et le serveur
appliquait la même limite. Le runtime Klipper installé accepte déjà de `3` à
`25` points par axe. La limite à six venait donc de l'interface, pas de la K1.

Klipper limite en revanche l'interpolation Lagrange à six points par axe. Une
matrice plus grande doit utiliser l'interpolation bicubique.

## Options examinées

1. Garder uniquement `6 × 6`. Refusé : cela contredit le contrat produit et
   retire à l'utilisateur le niveau de précision attendu.
2. Autoriser librement toutes les tailles jusqu'à `25 × 25`. Refusé : trop de
   choix, campagnes inutilement longues et expérience moins claire.
3. Exposer quatre niveaux nommés jusqu'à `15 × 15`, tout en conservant les
   petites tailles personnalisées et en forçant l'algorithme compatible.
   Retenu.

## Décision

L'interface propose :

- rapide : `6 × 6`, Lagrange ;
- standard : `9 × 9`, bicubique ;
- précis : `11 × 11`, bicubique ;
- expert : `15 × 15`, bicubique.

Les tailles personnalisées `3 × 3`, `4 × 4` et `5 × 5` restent disponibles.
À partir de `9 × 9`, le navigateur sélectionne automatiquement le bicubique et
désactive Lagrange. Le serveur vérifie à nouveau cette règle et refuse toute
combinaison incompatible. `15 × 15` reste la limite de l'interface même si le
runtime interne sait aller plus loin.

## Conséquences

- aucun changement Klipper, mouvement, chauffage, mesh ou Z n'est nécessaire
  pour poser ce correctif ;
- le temps d'une campagne augmente fortement avec la taille choisie, car six
  meshes complets restent obligatoires ;
- les quatre niveaux passent des tests de configuration et d'agrégation hors
  imprimante ;
- la campagne de validation qualifie physiquement six meshes pour chacun des
  quatre niveaux ; les niveaux `9 × 9`, `11 × 11` et `15 × 15` sont capturés
  puis annulés proprement sans refaire le Z ;
- le `6 × 6` est exécuté en dernier et porte seul le parcours Z complet, afin de
  terminer la preuve dans l'état quotidien `accepted` avec les quatre profils
  persistants.
