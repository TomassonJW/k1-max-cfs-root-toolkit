# Garde d’exclusion du propriétaire stock — hors imprimante V1

Ce paquet prépare uniquement sur le PC le verrou qui devra empêcher le système
Creality de reprendre le cycle CFS pendant qu’un futur propriétaire K1 Control
est actif.

Le garde pur :

- exige deux lectures identiques et successives d’un état nettoyé ;
- mémorise la valeur `stock_auto_refill` avant tout effet ;
- prépare au plus une intention non exécutable de désactivation ;
- ne donne le verrou qu’après deux nouvelles lectures prouvant la valeur `0` ;
- prépare au plus une intention non exécutable de restauration exacte ;
- refuse tout changement du mesh, du Z, des chauffes, des axes, des routes, de
  l’époque de connexion, de la cartographie ou de la politique d’impression ;
- ne rejoue jamais un résultat incertain.

Les seules chaînes présentes sont les signatures déjà revues dans S12 :
`BOX_ENABLE_AUTO_REFILL ENABLE=0` et la restauration de la valeur sauvegardée.
Elles sont toujours rendues avec `dispatchable=false`. Le paquet n’a aucun
connecteur, transport, G-code, accès réseau, fichier distant, service ou script
de pose.

Vérification locale :

```powershell
python packages\k1-control-v1\cfs-owner-exclusion-guard-offline-v1\run_scenarios.py
python -m unittest tests.test_cfs_owner_exclusion_guard_offline_v1 -v
```

La prochaine gate proposée relira deux captures fraîches et nettoyées sans
envoyer la moindre commande. Un essai réel de désactivation/restauration restera
une gate humaine ultérieure et distincte.
