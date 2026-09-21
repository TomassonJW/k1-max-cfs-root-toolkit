# Retrait coordonné V2 — candidat hors imprimante

Corrige l'attente fautive du candidat end-separated-v1. La primitive
constructeur Tn_Extrude attend la fin des 20 mm rapides ; les 15 mm lents
suivants sont en revanche seulement mis en file avant les appels CFS. Le
candidat V1 attendait aussi leur fin, supprimant ce chevauchement.

V2 garde la coupe, le relâchement local sans X/Z ni bac et la résolution fraîche
T1B. Il attend après E-20, programme E-15, lance les primitives CFS une fois,
puis attend la fin des mouvements avant les preuves de retrait et le parc.
Les ACK, les capteurs, les températures et les refus restent exigés.

170 tests ciblés verts, dont trois délais d'ACK sous une file de mouvements
simulée et trois témoins négatifs utilisant le code V1. Ces tests refusent
l'ancien ordre. Ils ne constituent pas une qualification physique.

**Non installé, désactivé par défaut, aucun paquet de pose dans cette révision.**
Ne pas substituer le fichier manuellement : préparer un delta épinglé et un
rollback avant pose, après récupération confirmée du filament. La cause exacte
du blocage matériel ne peut pas être prouvée par une file simulée ; le défaut
de coordination logiciel est confirmé par les commandes et traces réelles.
