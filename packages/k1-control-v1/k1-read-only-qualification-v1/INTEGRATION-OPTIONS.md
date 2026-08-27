# Points d'intégration Moonraker observés, sans activation

La configuration installée charge déjà des composants séparés : `k1_control`,
`k1_control_probe_count`, `k1_control_composite_subgrid` et
`k1_control_composite_mesh`. Leurs empreintes correspondent aux versions
revues. Aucun composant du cycle complet n'a été ajouté pendant le Goal 2.

## Option recommandée pour la future préparation physique

Créer un composant Moonraker séparé pour le cycle, avec :

- une lecture interne des objets Klipper déjà qualifiés ;
- une époque de connexion alimentée par les notifications, afin d'invalider le
  mapping même si une reconnexion retrouve le même état ;
- des sorties strictement nettoyées vers l'interface ;
- aucune route d'effet tant que la tranche physique correspondante n'a pas sa
  propre gate et sa présence humaine.

Cette option garde la calibration séparée du cycle d'impression, limite le
risque de casser l'interface déjà installée et permet de tester le propriétaire
filament indépendamment.

## Options non retenues à ce stade

- étendre directement `k1_control.py` : moins de fichiers, mais mélange la
  calibration et le cycle quotidien et augmente le risque de régression ;
- ajouter un service séparé : isolation forte, mais service et maintenance
  supplémentaires trop tôt ;
- piloter uniquement depuis Orca : ne voit pas assez finement les reconnexions,
  le CFS et les reprises après faute.

Ce document est une recommandation pour préparer le Goal 3, pas une décision
d'architecture activée. Aucune configuration, écriture ou pose ne l'accompagne.
