# Prochaine étape proposée — garde du retrait officiel CFS

Nom technique proposé : `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-V1`.

## En langage courant

On ne cherche plus, pour l'instant, à parler directement aux moteurs du CFS.
On laisse le logiciel Creality faire la coupe et le retrait qu'il sait déjà
faire, mais on l'entoure de contrôles pour éviter un état dangereux ou ambigu.

Le futur garde devra :

1. vérifier que la K1 est au repos et identifier le slot réellement engagé ;
2. refuser si la route est inconnue ou si une autre opération est active ;
3. lancer une seule fois le retrait officiel ;
4. suivre les deux étapes jusqu'à leur vraie fin ;
5. vérifier que le CFS ne considère plus le slot comme engagé ;
6. couper les chauffes même si le retrait échoue ou si l'API répond de façon
   trompeuse ;
7. expliquer clairement que le morceau après le cutter reste dans la tête ;
8. produire un résultat OK ou KO lisible, sans relancer automatiquement.

## Portée de la prochaine mission

La première version doit être construite et testée hors imprimante avec une
fausse API. Elle ne se connecte pas à la K1 et ne lance aucun nouveau retrait.
Une future pose ou validation réelle demandera un autre GO exact après revue.
