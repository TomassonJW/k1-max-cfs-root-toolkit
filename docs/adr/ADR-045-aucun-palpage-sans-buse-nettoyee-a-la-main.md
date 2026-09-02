# ADR-045 — Aucun palpage Z ni calibration sans buse nettoyée à la main

Date : 2026-09-01
Statut : accepté, contraignant, sans dérogation
Cible matérielle : Creality K1 Max, S12 structure 0, kit CFS.

## Règle

Toute opération qui met la buse en contact avec le plateau est interdite tant
que Thomas n'a pas nettoyé la buse à la main et confirmé qu'il l'a fait.

Sont concernés, sans exception :

- `G28` incluant l'axe Z, `CX_ROUGH_G28`, `ACCURATE_G28`, `_HOME_Z` ;
- `BED_MESH_CALIBRATE` et toute acquisition de sous-grille ;
- `CX_PRINT_LEVELING_CALIBRATION` ;
- toute séquence de démarrage d'impression qui contient l'un des précédents.

Le nettoyage manuel implique que le filament soit **rétracté** au préalable :
une buse ne peut pas être nettoyée proprement avec du filament engagé, et du
filament en bord de buse fausse les mesures.

## Pourquoi

Le palpage de cette machine est un contact buse contre plateau via PRTouch.
Une trace de matière sur la buse décale le point de contact et contamine :

- la référence Z, donc toutes les premières couches ;
- chaque point du mesh, donc le profil enregistré et tout ce qui s'en sert.

Une mesure faite sur une buse sale n'est pas une mesure dégradée, c'est une
mesure fausse qui a l'air valide. Elle se propage ensuite dans un profil
persistant et coûte des jours à diagnostiquer.

Le nettoyage automatique de brosse n'a jamais fonctionné sur cette machine.
`CX_NOZZLE_CLEAR` est retiré de la séquence de démarrage possédée (ADR-044 et
paquet `owned-start-print-v2`). Il n'existe donc **aucun** substitut automatique.

## Conséquences opérationnelles

1. Ordre imposé avant toute calibration : retrait du filament, puis nettoyage
   manuel, puis seulement la chauffe et le palpage.
2. Un agent ne lance jamais une calibration ou un palpage de sa propre
   initiative. Il annonce l'opération, attend la confirmation explicite de
   nettoyage, et seulement ensuite exécute.
3. Une séquence déjà lancée qui n'a pas encore atteint son premier contact peut
   être laissée en trempe le temps du nettoyage. Une séquence qui a déjà palpé
   avec une buse non confirmée est jetée, pas exploitée.
4. La confirmation ne se déduit pas d'un capteur. Aucun capteur de cette
   machine ne prouve qu'une buse est propre.

## Portée

Cette règle s'applique aussi aux impressions ordinaires, puisque la séquence de
démarrage possédée contient une référence géométrique. En pratique : buse
nettoyée avant de lancer un travail.
