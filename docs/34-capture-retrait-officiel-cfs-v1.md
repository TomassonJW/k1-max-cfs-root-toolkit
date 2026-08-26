# Capture du retrait officiel CFS V1

Date : 2026-08-27

Statut : **capture réussie ; solution série indépendante toujours fermée**.

## Résultat en langage courant

La K1 sait bien couper puis retirer le filament avec son propre système. Ce
passage réel a fonctionné sur le premier CFS, slot A.

En revanche, la commande constructeur a laissé la buse chauffée à `220 °C`
après avoir terminé. Il a fallu envoyer séparément l'arrêt global des chauffes
et vérifier que la cible était réellement revenue à zéro.

Le prochain logiciel ne devra donc pas remplacer le cerveau du CFS. Il devra
d'abord encadrer la commande Creality existante et garantir le retour à un état
sûr.

## Passage observé

État initial :

- K1 au repos ;
- cibles de buse et plateau à zéro ;
- deux CFS connectés ;
- filament engagé depuis `T1A` ;
- écoute locale active, sans écriture distante ni envoi série.

Action unique : `BOX_QUIT_MATERIAL`, lancée après autorisation explicite de
Thomas.

Résultat :

- la séquence constructeur contient contrôle, coupe, retrait et déplacement ;
- deux phases de retrait ont obtenu leur réponse réussie ;
- le cycle a duré environ 106 secondes ;
- le premier CFS est passé du slot engagé `A` à aucun slot engagé ;
- la cible thermique est passée automatiquement de `0` à `220 °C` ;
- le capteur de la tête reste actif après le retrait côté CFS ;
- `TURN_OFF_HEATERS` a ramené les deux cibles à zéro ;
- les trois configurations contrôlées sont restées identiques.

## Point de sécurité découvert

Le retour HTTP `ok` ne suffit pas. Une tentative utilisant `M104%20S0` a été
reçue littéralement comme une commande inconnue, tout en laissant l'API répondre
`ok`. L'effet réel doit toujours être relu après une commande.

Le futur garde utilisera un transport validé et vérifiera la cible thermique.
Il devra exécuter l'arrêt des chauffes même si le retrait échoue.

## Limites honnêtes

- aucun capteur dédié ni retour humain ne confirme directement le mouvement du
  cutter ; seule sa présence dans la séquence constructeur est prouvée ;
- la trame sortante complète reste absente ;
- la propriété exclusive du bus n'est pas démontrée ;
- les autres slots, le second CFS, le chargement et la purge restent à tester ;
- les messages d'arrière-plan `auto_addr` sans réponse existaient avant le
  retrait et continuent après ; ils nécessitent un diagnostic séparé.

## Suite proposée

Préparer hors imprimante `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-V1`.

En pratique, cela veut dire créer un petit contrôleur qui vérifie l'état de la
K1, lance une seule fois le retrait officiel, surveille sa vraie fin, coupe
toujours les chauffes et refuse de déclarer un succès si le slot ou les capteurs
restent incohérents.

Cette préparation ne se reconnectera pas à la K1. Une installation ou un nouvel
essai réel demanderont un GO séparé après revue.

Voir ADR-023 et
`packages/k1-control-v1/cfs-minimal-owner-passive-capture-v1/`.
