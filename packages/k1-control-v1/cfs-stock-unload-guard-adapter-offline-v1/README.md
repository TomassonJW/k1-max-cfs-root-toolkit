# CFS Stock Unload Guard Adapter Offline V1

Ce paquet traduit une réponse K1 déjà nettoyée vers les huit champs attendus
par le garde de retrait. Il n'a aucun moyen de se connecter à l'imprimante,
d'envoyer une commande ou de démarrer un processus externe.

## Règles de traduction

- `print_stats.state` devient `print_state` ;
- `box.state` devient `box_state` ;
- `box.t_command` devient `active_cfs_command` ;
- chaque `T1/T2.state=connect` devient une unité connectée ;
- un slot `A..D` d'une unité connectée devient une route comme `T1A` ;
- les cibles buse et plateau doivent être des nombres finis positifs ou nuls ;
- le capteur actif devient un booléen, et un capteur désactivé devient `null`.

Une route absente est un état valide à transmettre au garde. Un second CFS
déconnecté est également traduit : le garde pourra alors refuser l'action avant
toute commande. En revanche, plusieurs routes, un slot actif sur une unité
déconnectée, une unité `T3/T4` connectée, un champ manquant ou une température
invalide sont refusés immédiatement. Un état d'unité autre que `connect` ou
`disconnect` est également refusé au lieu d'être assimilé à une déconnexion.

Les exemples sous `fixtures/` sont entièrement synthétiques. Ils ne contiennent
aucun numéro de série, UUID, adresse ou réponse privée.

## Exécution locale

```powershell
python packages\k1-control-v1\cfs-stock-unload-guard-adapter-offline-v1\run_scenarios.py
python -m unittest tests.test_cfs_stock_unload_guard_adapter_offline_v1 -v
```

Cette gate ne crée ni transport ni candidat de pose. La prochaine lecture live,
si elle est un jour autorisée comme mission distincte, devra nettoyer les
données avant l'adaptateur et ne devra pas appeler le chemin d'effet du garde.
