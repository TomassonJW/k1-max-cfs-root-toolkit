# ADR-052 — Éditeur de maillage point par point, servi par l'imprimante

Date : 2026-09-01

Statut : **accepté**, chaîne complète vérifiée sur la machine réelle

## Contexte

L'ADR-050 a livré une retouche par zone : un bord, un coin, une couronne. La
demande réelle était autre :

> Faut que je puisse éditer point par point. Je clique sur un des points, et je
> modifie la valeur à la main direct. Rapidement, avec fluidité, visualisés sur
> l'éditeur 3D, et un bouton enregistrer.

La correction par zone reste juste pour un défaut qui suit un bord. Elle ne
convient pas à quelqu'un qui sait lire son carré imprimé point par point et
veut poser chaque valeur lui-même.

## Décision

Une page servie par l'imprimante, sur le port `7130`, par un serveur qui ne
dépend que de la bibliothèque standard.

**La page et son API sortent du même processus.** Moonraker écoute sur un autre
port ; une page servie ailleurs serait en origine croisée et exigerait
d'ouvrir CORS sur l'API de la machine — une modification permanente pour faire
marcher un outil local.

**Aucune écriture ne passe par le serveur.** Il dépose la matrice éditée dans un
fichier JSON et laisse `KCTRL_MESH_APPLY` valider, sauvegarder et persister.
La copie en mémoire de Klipper et `printer.cfg` ne peuvent donc pas diverger.

**Chaque enregistrement laisse la matrice précédente sur disque**, horodatée, à
côté de `printer.cfg`. Un maillage retouché à la main est un jugement, pas une
mesure : il ne se repalpe pas. Le fichier de sauvegarde est lui-même un
argument valide de `KCTRL_MESH_APPLY`, donc revenir en arrière est la même
opération que retoucher.

Les deux invariants sont tenus des deux côtés — la page et l'imprimante — parce
qu'une règle que l'interface laisse enfreindre et que la machine refuse ensuite
fait perdre une soirée : `X150 Y150` reste à zéro (ADR-046), et aucun point ne
s'écarte de plus de `0,15 mm` du mesuré.

## Trois pièges rencontrés, tous silencieux

**Le profil est stocké en tuples.** `config.getlists` produit un tuple de
tuples : une matrice fraîchement chargée est immuable. Les lignes sont promues
en listes dans le dictionnaire vivant, une fois, à la première ouverture.

**L'abonnement console exige un `response_template`.** Sans lui Klipper
enregistre l'abonnement et n'envoie plus jamais rien. Et la charge utile arrive
en dictionnaire `{"response": "..."}`, pas en liste : la parcourir naïvement
rend le mot `response`.

**La cellule affiche trois décimales, la mesure en porte six.** Quitter un champ
sans rien taper ne doit pas réécrire le point à son propre arrondi, sinon
traverser une ligne repeint le plateau d'un demi-centième.

## Conséquences

- La retouche par zone (ADR-050) et la retouche par point coexistent : la
  première pour un défaut de bord, la seconde pour le jugement fin.
- Le serveur est lancé à la main et ne survit pas à un redémarrage de
  l'imprimante. Le rendre persistant est une décision séparée, qui touche à
  l'init de la machine.
- Vérifié de bout en bout : édition, enregistrement, écriture dans
  `printer.cfg`, sauvegarde horodatée, restauration depuis cette sauvegarde, et
  matrice finale identique bit à bit à celle issue de la calibration.

## Voir aussi

- ADR-046 — profil de maillage référé au point de palpage
- ADR-050 — retouche du maillage par zone
