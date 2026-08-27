# GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1

Ce paquet ferme le Goal 2 en lecture seule. Il contient la liste exacte des
lectures autorisées, le nettoyage exécuté sur la K1 avant tout retour local, la
traduction vers les faits du cycle hors imprimante et le validateur de preuve.

## Ce qui est réellement exécutable

- `capture_live_read_only.ps1` ouvre une connexion SSH et lance uniquement des
  requêtes HTTP `GET` vers Moonraker ;
- le script calcule les empreintes sur la K1 et ne renvoie jamais le contenu des
  configurations ;
- les numéros de série, UUID, nom du fichier d'impression et valeurs non
  autorisées ne sont pas exportés ;
- `read_only_connector.py` est un traducteur pur, sans réseau, processus,
  fichier, G-code ou contrôle de service ;
- `analyze_capture.py` vérifie la capture privée épinglée par son empreinte.

## Résultat

La forme et les délais des lectures sont qualifiés. L'état de contrôle est
stable et sans effet, mais le système hors imprimante n'est pas prêt pour une
gate physique : la K1 a chargé le mesh `default`, différent du profil robuste
requis. Le profil robuste existe encore avec sa matrice attendue.

Statut : `CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT`.

## Limite volontaire

Le paquet ne contient aucun connecteur de commande, script de pose, manifeste
exécutable, redémarrage de service ou changement Orca. La reconnexion CFS n'a
pas été provoquée. Le futur composant devra invalider son mapping sur une époque
de connexion issue des notifications Moonraker, car deux sondages identiques ne
peuvent pas détecter une reconnexion très courte entre eux.

## Vérification locale

```powershell
python packages\k1-control-v1\k1-read-only-qualification-v1\analyze_capture.py
python -m unittest tests.test_k1_read_only_qualification_v1
```
