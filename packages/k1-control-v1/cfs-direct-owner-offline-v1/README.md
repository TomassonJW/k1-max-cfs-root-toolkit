# Propriétaire CFS direct hors imprimante V1

Ce paquet remplace le choix raté des primitives `BOX_*` par une machine d'état
K1 Control qui possède chaque étape de chargement et de retrait. Il conserve
uniquement le transport série déjà présent sur la K1.

Il ne contient aucun connecteur réseau, aucune pose, aucune macro Klipper et
aucune commande physique. `runtime_adapter.py` fixe seulement la signature de
l'appel local futur vers `serial_485`; rien ne l'instancie contre une machine.

## Ce qui est qualifié

- les trames exactes relevées dans les journaux de cette K1 ;
- les routes `T1A..T2D` sur deux CFS ;
- le chargement borné par le capteur de tête ;
- le retrait en deux phases avec une seule traction locale ;
- la distinction entre la route CFS libérée et le petit segment coupé qui peut
  rester dans la tête ; ce segment n'autorise que le chargement possédé suivant
  dans le même runtime, jamais une extrusion avant arbitraire ;
- la température appartenant exclusivement à K1 Control ;
- l'arrêt au premier timeout, statut CFS ou capteur incohérent ;
- aucune répétition automatique d'un effet incertain ;
- plusieurs cycles normaux avec des identifiants d'effet consommables une fois.

## Vérification

Depuis la racine du dépôt :

```powershell
python -S packages\k1-control-v1\cfs-direct-owner-offline-v1\run_scenarios.py
```

Le résultat attendu est :

```text
CFS_DIRECT_OWNER_OFFLINE_V1_OK 24/24
```

## Ce qui reste fermé

La pose, l'exclusion physique du propriétaire stock et le moindre mouvement de
filament restent fermés. La prochaine gate installe d'abord le composant en
mode désactivé et prouve son rollback. Une qualification physique unique de
chargement/retrait viendra seulement ensuite, sous caméra.
