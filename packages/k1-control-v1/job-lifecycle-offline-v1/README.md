# Cycle complet K1 Control hors imprimante V1

Ce paquet rend exécutable le contrat figé dans
`design/job-lifecycle-contract-v1.json`, sans parler à la K1.

Il sépare clairement :

- le contrat de travail et les recettes matière ;
- l'état initial de la machine et du filament ;
- la machine d'états du démarrage à la fin ;
- les preuves synthétiques de chaque frontière CFS ;
- le transport simulé du retrait stock ;
- la future pose, qui reste absente et fermée.

## Ce qui est couvert

La matrice reprend les 27 scénarios canoniques : mesh et Z, nettoyage,
filament correct, incorrect ou absent, changement voulu, deux CFS, runout,
pause, reprise, annulation, reboot, fin, retrait séparé, délais, preuves de
route fraîches, réécriture tardive de température et rollback.

Chaque effet CFS possède un identifiant unique, une preuve de route consommable
une fois, une cible explicite avant le premier effet, un délai et une preuve de
sortie. Un timeout, un doublon, une route périmée ou un faux succès coupe les
deux cibles simulées et interdit la reprise automatique.

## Ce que le vert ne prouve pas

- aucune trajectoire réelle autour d'une pièce ;
- aucune position ou pression réelle de brosse ;
- aucun débit visible à la buse ;
- aucun comportement réel des autres slots ou du second CFS ;
- aucun connecteur Moonraker d'effet ;
- aucune installation ni production.

Le futur paquet de pose est seulement décrit par un plan inerte. Il ne contient
ni commande distante, ni script de déploiement, ni activation de composant.

## Vérifier localement

```powershell
python packages\k1-control-v1\job-lifecycle-offline-v1\run_scenarios.py
python -m unittest tests.test_job_lifecycle_offline_v1 -v
```

Le Goal 2 a maintenant comparé ce modèle à une lecture K1 fraîche sans effet.
La lecture est qualifiée, mais la suite physique reste bloquée parce que le
mesh actif `default` diffère du profil robuste requis. Voir le paquet
`../k1-read-only-qualification-v1`.
