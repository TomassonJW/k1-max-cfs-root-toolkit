# CFS Dynamic Temp Routing V1

Statut : **mission hors imprimante close ; architecture choisie ; aucun
transport K1 ; production fermée**.

Ce paquet rend exécutable la règle suivante : avant le premier effet d'un
chargement, retrait, refill ou purge, K1 Control doit déjà connaître la phase,
la cible de buse, la cible séparée du plateau et une route logique fraîche vers
un CFS et un slot. Une donnée absente, incohérente ou périmée arrête le scénario
avant l'effet filament.

L'architecture retenue est `minimal_separate_filament_owner`. Il s'agit d'un
choix de conception, pas d'un pilote installable. Le paquet ne contient ni SSH,
ni série, ni G-code, ni script de pose, ni accès réseau.

## Contenu

- `contract.json` : contrat de phase, preuve de route et six invariants ;
- `architecture-options.json` : comparaison déterministe des quatre voies ;
- `simulator.py` : simulateur pur et sans transport ;
- `scenarios.json` : 25 scénarios synthétiques ;
- `FUTURE-DEPLOYMENT-PLAN.md` : conditions d'une future pose, sans l'exécuter ;
- `RESULT.md` : verdict et limites observées.

## Exécution locale

```powershell
python packages/k1-control-v1/cfs-dynamic-temp-routing-v1/simulator.py `
  packages/k1-control-v1/cfs-dynamic-temp-routing-v1/contract.json `
  packages/k1-control-v1/cfs-dynamic-temp-routing-v1/scenarios.json
```

Un résultat `pass_offline` prouve seulement la cohérence du contrat synthétique.
Il ne prouve ni protocole série, ni capteur, ni cutter, ni débit physique, ni
compatibilité avec la K1 réelle.
