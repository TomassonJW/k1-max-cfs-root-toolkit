# K1 Control — prototype local

Statut : **simulation hors imprimante uniquement**.

Ce dossier montre le fonctionnement quotidien validé par ADR-004 sans appeler
Moonraker, Klipper, Orca ou la K1 Max. Il utilise uniquement HTML, CSS et
JavaScript natifs afin de ne pas ajouter un second service lourd sur une machine
qui ne possède qu'environ 209 Mio de RAM.

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

Le navigateur doit recevoir les fichiers par HTTP pour charger le JSON :

```powershell
python -m http.server 8765 --directory prototype/k1-control
```

Puis ouvrir `http://127.0.0.1:8765`. Cette commande ne contacte pas
l'imprimante. Elle ne doit pas être utilisée comme service de production.

## Suite

Le branchement futur remplace seulement `mock-state.json` par un adaptateur
Moonraker limité et versionné. La logique persistante reste dans la couche
d'état/macros testée, pas dans le navigateur. La sélection des versions et la
sécurité réseau doivent encore passer la matrice de compatibilité avant G4.
