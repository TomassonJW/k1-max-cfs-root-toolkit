# K1 Control — prototype local

Statut : **simulation hors imprimante uniquement**.

Ce dossier montre le fonctionnement quotidien validé par ADR-004. L'écran parle
à `prototype/moonraker_simulator.py`, un faux Moonraker lié au moteur d'état
Python. Ce serveur reste sur `127.0.0.1`, ne connaît aucune adresse d'imprimante
et n'expose qu'une poignée de commandes de simulation. L'interface utilise
uniquement HTML, CSS et JavaScript natifs afin de rester statique en production.

## Ce que le prototype démontre

- état global prêt/bloqué avec raison lisible ;
- calibration Z ouverte explicitement ;
- clics Z provisoires tant que `Enregistrer` n'est pas choisi ;
- annulation sans modification de la valeur acceptée ;
- redémarrage et fin d'impression sans perte de la valeur ;
- invalidation visible après une nouvelle calibration système ;
- mesh identifié par plaque/température et adaptation non persistante ;
- températures demandée/réelle et propriétaire affichés ;
- ordre sûr visible avant CFS et purge.

Toutes les données de `mock-state.json` sont synthétiques. La valeur `+0,31 mm`
sert à la démonstration visuelle ; ce n'est pas un réglage de l'imprimante ni
une valeur par défaut du produit.

## Lancer localement

Lancer le faux Moonraker depuis la racine du dépôt :

```powershell
python -m prototype.moonraker_simulator --port 8765
```

Puis ouvrir `http://127.0.0.1:8765`. Cette commande ne contacte pas
l'imprimante. Les boutons utilisent les routes Moonraker simulées
`/server/info`, `/printer/objects/query` et `/printer/gcode/script`.

## Suite

Le futur branchement réel conservera cette interface d'adaptateur, ajoutera
l'authentification et les événements WebSocket, puis traduira uniquement les
commandes autorisées vers les macros originales du projet. La logique
persistante reste dans la couche d'état/macros testée, pas dans le navigateur.
