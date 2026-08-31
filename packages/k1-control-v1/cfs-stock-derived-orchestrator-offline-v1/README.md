# Orchestrateur stock-derived hors imprimante V1

Ce paquet fait la couture entre la géométrie R4 réalisée avant filament et les
primitives directes cutter, retrait, chargement, purge, ligne de départ,
changement, refill et fin. Il ne contacte pas la K1 et n'exécute aucune des
commandes qu'il encode.

La différence essentielle avec l'ancien cycle intégré est le journal de
tickets : chaque opération est enregistrée avec sa commande et son empreinte
avant le premier effet. Si Moonraker redémarre ou si le résultat devient
inconnu, le ticket passe en blocage manuel et n'est jamais renvoyé.

## Roulement entre bobines

Le roulement automatique est conservé sous K1 Control. Une bobine de secours
est acceptée uniquement si elle est disponible, approuvée et strictement
identique sur la référence, le matériau, la couleur, le diamètre et la recette
thermique. Il doit y avoir exactement une candidate. Le contexte complet de la
pause et la température active sont comparés avant la reprise.

Le groupe « même matériau » du firmware ne suffit donc pas à lui seul. Pendant
le job, son auto-refill est désactivé pour éviter deux propriétaires concurrents
et sa valeur précédente est remise exactement à la fermeture.

## Limite actuelle explicite

R4 ne qualifie aujourd'hui que le contexte `55 / 140 / 190`, le mesh
`k1_p001_t055_r001_n11x11` et le Z `-0,04`. Tout autre profil thermique est
refusé avant émission d'une commande. Le paquet définit le jeton de handoff
`geometry_ready_for_stock_cycle`, mais l'overlay Klipper qui le produit et le
composant Moonraker qui persiste puis envoie les tickets ne sont pas encore
installés.

## Vérifications

```powershell
python packages\k1-control-v1\cfs-stock-derived-orchestrator-offline-v1\run_scenarios.py
python packages\k1-control-v1\cfs-stock-derived-orchestrator-offline-v1\verify_candidate.py
python -m unittest tests.test_cfs_stock_derived_orchestrator_offline_v1 -v
```
