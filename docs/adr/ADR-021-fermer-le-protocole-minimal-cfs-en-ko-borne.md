# ADR-021 — Fermer le protocole minimal CFS en KO borné

Date : 2026-08-26

Statut : accepté

## Contexte

ADR-020 choisit un propriétaire filament minimal séparé, car le chemin stock
possède la température et la géométrie. Avant toute implémentation, il fallait
qualifier le plus petit protocole nécessaire depuis les captures privées déjà
disponibles, sans connexion à la K1 et sans exécuter le module compilé.

Les journaux montrent plusieurs requêtes d'état sur deux adresses et une
séquence `EXTRUDE_PROCESS` sur `T1A`. Ils ne montrent ni retrait, ni coupe
isolée, ni purge isolée, ni effet sur le second CFS. Le mécanisme qui exclurait
le propriétaire constructeur n'est pas observable.

## Options

### 1. Déduire les trames manquantes par symétrie

Refusé. Une adresse ou un slot voisin peut changer le payload, l'état, la
séquence ou la sécurité physique. La symétrie n'est pas une preuve.

### 2. Traduire les noms Cython en commandes supposées

Refusé. Un symbole prouve qu'une méthode existait dans le binaire, pas son
identifiant, son payload, son checksum ni ses effets.

### 3. Rendre appelables les seules requêtes vues

Refusé pour V1. Même une lecture doit avoir une réponse définie, une politique
de timeout, une règle de reconnexion et une coexistence sûre avec le wrapper
stock. Ces éléments ne sont pas complets.

### 4. Fermer la gate en KO borné et garder la liste vide

Retenu. La carte de preuve est versionnée sans données d'identité. Un émulateur
hors ligne vérifie les ambiguïtés et bloque par défaut. La liste appelable reste
vide jusqu'à l'acquisition de preuves exactes supplémentaires.

## Décision

`G4-K1-CONTROL-CFS-MINIMAL-OWNER-PROTOCOL-V1` est close avec
`gate_verdict=KO_BOUNDED` et `callable_messages=[]`.

Une requête et une réponse ne peuvent être rapprochées hors ligne que par la
clé observée `(adresse, commande)`. Un doublon est bloqué. Après timeout ou
reconnexion, aucune réponse tardive ne peut valider une nouvelle opération sans
protocole de resynchronisation prouvé. Toute route changeante ou reconnectée
est invalidée.

La mention d'un heartbeat désactivé n'est pas reconnue comme exclusion du
propriétaire stock.

## Conséquences

- aucun transport, déployeur ou paquet installable n'est créé ;
- aucune commande, même de lecture, n'est qualifiée comme appelable ;
- les deux CFS sont modélisés pour les risques de corrélation, pas pour les
  effets physiques ;
- le propriétaire minimal de l'ADR-020 reste la bonne architecture cible, mais
  il n'a pas encore de protocole d'exécution ;
- la production et la reprise du diagnostic de bord restent fermées ;
- une gate suivante devra apporter source exacte ou captures séparément
  autorisées, puis créer une nouvelle ADR avant tout transport.
