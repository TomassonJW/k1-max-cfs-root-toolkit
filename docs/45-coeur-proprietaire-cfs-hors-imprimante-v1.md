# Cœur propriétaire du cycle CFS — hors imprimante V1

Date : 2026-08-28

Statut : **clos OK hors imprimante ; effets, pose et production fermés**

## Résultat en langage courant

K1 Control possède maintenant un moteur logique spécialisé pour le cycle CFS.
Ce moteur ne parle pas à l’imprimante. Il décide ce qui devrait se passer,
refuse les situations dangereuses et garde un journal ordonné, mais ne sait pas
transformer une décision en commande réelle.

Le travail ne remplace pas le moteur complet du Goal 1. Il précise la partie qui
manquait après la cartographie S12 : comment garantir un seul propriétaire,
comment choisir une bobine de remplacement identique et comment empêcher les
retries ou reprises cachés du système stock.

## Un seul propriétaire

Avant qu’un travail puisse devenir actif, le moteur mémorise la valeur de
l’auto-remplacement Creality et exige une preuve qu’elle vaut ensuite `0`. Le
réglage général CFS reste inchangé. À la fin, le moteur exige le retour exact à
la valeur précédente : `1` redevient `1`, et une valeur déjà à `0` reste `0`.

Cette logique est seulement simulée ici. Le paquet émet une intention non
exécutable et ne contient aucun nom de commande stock, connecteur ou script de
pose. La désactivation réelle et sa restauration devront passer une autre gate.

Pendant la possession, un rappel stock de fin de bobine, retry, reprise ou fin
d’impression crée un conflit de propriétaire et bloque le cycle. Un changement
de cartographie ou d’époque de connexion invalide aussi le verrou, les plans en
cours et toute reprise possible.

## Démarrage et changement

Le moteur distingue trois chemins :

- filament correct déjà engagé : aucune coupe ni aucun chargement ; seulement
  la purge visible K1 Control reste à faire ;
- chemin vide : un chargement unique puis une purge visible ;
- mauvais filament engagé : coupe, retrait, chargement et purge, chacun sous une
  intention séparée et consommable une fois.

Une route seule ne prouve jamais l’identité matière. Si cette identité n’est
pas confirmée, si plusieurs routes paraissent engagées ou si un segment reste
présent sans route attribuable, le moteur s’arrête avant une nouvelle intention.

## Fin de bobine entre les deux CFS

La fonction d’auto-remplacement demandée est conservée. Le moteur met d’abord le
travail en pause et exige un contexte structuré : position de retour, modes de
mouvement, extrusion, mesh, Z, cibles thermiques, ventilateurs, facteurs de
vitesse et de débit, pressure advance, outil logique, route, capteurs et
fraîcheur de cartographie. Il cherche ensuite un seul emplacement disponible dont la
référence approuvée, le type, la couleur, le diamètre et la recette thermique
sont identiques. Le capteur de cet emplacement doit voir du filament et la
cartographie doit rester fraîche.

Dans la matrice synthétique, `T1A` épuisé choisit uniquement `T2A`, puis le
modèle vérifie le traitement de la fin restante, le chargement et la purge
visible. La reprise appartient à K1 Control et reste interdite tant que le
contexte fourni ne correspond pas exactement à celui de la pause et que toutes
les protections ne concordent pas. Un simple booléen « état complet » ne suffit
pas. Aucun homing, aucune référence Z et aucune mutation du mesh ne sont admis.

Zéro candidat, deux candidats ou une simple couleur proche laissent le travail
en pause. Le moteur ne choisit jamais arbitrairement.

## Incertitude et journal

Chaque intention a un identifiant unique, un ordre strict et une seule tentative
possible. Si l’effet est inconnu, la suite est fermée et l’intention ne peut pas
être rejouée. Une intention déjà observée avec succès est également refusée au
second passage. Le journal mémoire est numéroté et permet d’expliquer chaque
décision sans présenter une simulation comme une action physique.

## Preuves et limites

La matrice obtient `21/21`, les tests ciblés `21/21` et la suite complète
exécute `654` tests, dont `651` verts et `3` ignorés connus. Le paquet relit la
preuve S12 nettoyée et vérifie ses empreintes. Il conserve donc les deux faits exacts
de la capture : l’auto-remplacement stock valait `1`, et les six groupes observés
ne formaient aucune paire identique.

Les paires utilisées dans les tests sont fictives. Aucune primitive de coupe,
retrait, chargement, purge ou fin de bobine n’est qualifiée par ce vert. Aucune
connexion K1, commande, chauffe, mouvement, écriture distante ou pose n’a eu
lieu.

## Suite historique

La tranche suivante était
`G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1`. Elle devait préparer,
toujours sur le PC, le garde exact qui encadrerait une future désactivation puis
restauration de l’auto-remplacement stock : une tentative maximum, lecture avant
et après, refus de tout écart et aucun effet filament. La connexion et l’essai
réel restaient une gate différente. Cette tranche est désormais close ; voir le
document 46 et la passation actuelle.
