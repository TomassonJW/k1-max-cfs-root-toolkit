# Essai de retrait coordonné V2 — clos KO pendant le chargement

**Ne pas rejouer ce fichier ni son ancien surveillant.** Le compteur de huit
messages `full` a déclenché l'arrêt d'urgence alors que la tête détectait le
filament depuis 33,449 s et que Klipper commandait encore E à 3 mm/s.
Aucune erreur console avant l'arrêt ; débit physique non confirmé. La pause
et le retrait corrigé n'ont pas été atteints. Lire le document 94.

Récupération du service puis du verrou MCU réalisée sans commande physique.
Machine ready/standby, chauffes zéro, tête détectée chargée mais aucune route
CFS déclarée, références perdues. Les 22 empreintes sont inchangées. Aucune
rétraction ni seconde tentative n'a été faite. Cet état ne permet pas de
palper ou d'inférer une tête vide à partir de la seule table CFS.

## Plan de l'essai clos (historique)

Fichier distinct des essais clos KO. Exige `end-overlap-v2` actif/idle,
22 empreintes conformes, machine froide au repos, tête vide et aucune route,
buse fraîchement nettoyée, plateau libre et opérateur présent. La confirmation
de nettoyage a été reçue ; état et caméra frais vérifiés.

Séquence proposée : `START_PRINT` à 200/55 °C, références avant insertion,
profil existant chargé par le démarrage, chargement T1B et purge dans le bac,
ligne d'amorçage existante, retrait de 5 mm en Z puis pause X150/Y150.
Il n'y a aucun modèle à imprimer. Après confirmation de purge/décrochage et
contrôle caméra, une seule reprise autorise `END_PRINT` corrigé : coupe,
retrait extrudeur coordonné avec CFS, preuve de tête vide et route libérée,
puis stationnement et chauffes coupées. Aucun retry de l'essai.

Surveillance conservée depuis l'essai précédent : températures, console,
capteurs, mouvements et caméra ; arrêt sur première faute ou blocage du
chargement. Un échec de fin déjà arrêté avec chauffes zéro ne déclenche pas
un arrêt d'urgence supplémentaire. Limites : 900 s de départ, pause 180 s,
extrudeur au plus 215 °C et plateau 55 °C.

Le contrôle automatique d'approbation a refusé le script combinant upload et
`/printer/print/start`, jugeant que « c'est bon » confirmait le nettoyage sans
autoriser explicitement le nouvel essai physique. Le script n'a pas été
exécuté. L'upload a été séparé du démarrage. Thomas a ensuite donné une
autorisation explicite du cycle ; état et caméra revérifiés, surveillance
active avant une seule confirmation de départ vers T1B.

Le geste de nettoyage ne doit pas être redemandé tant qu'aucune opération
filament ni autre événement ne l'invalide. La présence et l'état physiques
doivent cependant rester actuels au moment du départ.
