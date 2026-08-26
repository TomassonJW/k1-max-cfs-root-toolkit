# Plan futur de pose, backup et rollback

Statut : **plan de contrôle seulement ; aucune pose préparée ni autorisée**.

## Blocages avant de figer un paquet installable

Le propriétaire minimal n'a encore aucun transport. Il faut d'abord fermer une
mission hors imprimante distincte qui :

1. cartographie le sous-ensemble série minimal depuis les preuves déjà
   capturées, sans charger le binaire ;
2. sépare adresse CFS, slot, avance, retrait, cutter et accusés de réception ;
3. démontre qu'un seul propriétaire peut tenir la frontière sans concurrence
   avec le propriétaire stock ;
4. simule timeout, doublon, réponse retardée, reconnexion et deux CFS ;
5. laisse toute commande non comprise hors de la liste appelable.

Tant que ces cinq points ne sont pas verts, le write-set exact, les commandes,
les hashes et le service à redémarrer restent volontairement **non fixés**. Un
document qui les inventerait maintenant ne serait pas révisable honnêtement.

## Forme obligatoire d'une future gate de pose

Une future gate devra être séparée en trois étapes qui ne se confondent pas.

### A. Pose inactive

- préflight frais : K1 au repos, chauffes demandées à zéro, aucun CFS en
  transition, deux unités cohérentes, production fermée ;
- manifeste épinglant chaque octet local et chaque baseline distante ;
- backup vérifié avant la première écriture ;
- nouveaux chemins versionnés uniquement ; aucune réécriture dynamique de
  `material_database.json` et aucun remplacement global de `box_wrapper` ;
- composant posé inactif, sans chauffe, homing, mouvement, coupe, avance, purge
  ou impression ;
- validation indépendante : service chargé, aucun échec ni avertissement,
  hashes hors write-set inchangés et état machine identique.

### B. Essai de protocole borné

Cette gate devra recevoir une autorisation fraîche et une confirmation physique
de présence de Thomas et de plateau libre. Elle ne couvrira qu'une seule famille
d'effet déjà simulée, avec route fraîche, cible explicite, timeout, preuve
capteur et arrêt sûr. Elle ne couvrira pas une impression.

### C. Qualification thermique et géométrique

Chaque frontière devra prouver avant, pendant et après : cible buse, cible
plateau, Z accepté, origine Z, mesh et axes référencés. Le débit visible reste
une preuve séparée. Une dérive coupe les deux cibles, bloque la reprise et ne
restaure jamais le Z à l'aveugle.

## Backup exigé

Avant toute future écriture, le paquet devra capturer et vérifier :

- chaque fichier exact du write-set et son mode ;
- l'absence explicite de chaque nouveau chemin ;
- les includes et composants actifs ;
- les six invariants et les cibles thermiques ;
- l'état des deux CFS, sans le transformer en preuve de route ou de débit ;
- un manifeste privé horodaté avec SHA-256.

## Rollback exigé

Le rollback devra être automatique après tout KO de pose et manuel mais borné
après un KO physique :

1. demander les deux cibles thermiques à zéro ;
2. interdire toute nouvelle action filament et toute reprise ;
3. désactiver uniquement le nouveau propriétaire ;
4. restaurer les octets et modes exacts depuis le backup vérifié ;
5. redémarrer seulement le service réellement touché, après attente bornée ;
6. relire les hashes, les listes d'échec et d'avertissement et les six invariants ;
7. conserver le Z observé en cas d'écart et arrêter sans restauration aveugle ;
8. produire un marqueur final de rollback seulement après deux validations
   indépendantes.

Ce plan n'est pas une recette exécutable. La prochaine mission canonique est
`G4-K1-CONTROL-CFS-MINIMAL-OWNER-PROTOCOL-V1`, toujours hors imprimante.
