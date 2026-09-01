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

## Corriger d'un pas plutôt que retaper la valeur

À l'usage, taper `-0.187` pour un point qui valait `-0.192` n'est pas le geste
juste : l'opérateur ne lit pas une valeur sur son carré imprimé, il lit un
écart. Il décide qu'un point est deux centièmes trop loin, pas qu'il vaut
`-0.187`. Le clavier corrige donc d'un pas : `+` éloigne la buse, `−` la
rapproche, et le pas se choisit entre 0,005 / 0,010 / 0,020 / 0,050 mm.

Trois choix en découlent.

**Un clic simple sélectionne, il n'ouvre plus la saisie.** La version précédente
ouvrait un champ texte au clic, et ce champ avalait la touche `+` : elle
inscrivait un signe plus dans la valeur au lieu de déplacer le point. Taper la
valeur reste à un geste : double-clic, `Entrée`, ou simplement commencer à taper
des chiffres.

**Une rafale élargit le pas, par multiples entiers.** Une touche maintenue se
répète toutes les trente millisecondes ; avancer d'un pas à chaque fois
ramperait. Après six répétitions consécutives sur le même point et dans le même
sens, le pas double ; après seize, il quadruple. Le facteur reste entier pour
qu'un point atterrisse toujours sur les valeurs rondes choisies, jamais sur
0,0175. Changer de sens ou de point remet la rafale à zéro.

**`PagePrec` et `PageSuiv` font la même chose.** Sur un clavier français, `+`
coûte une touche Majuscule. Les deux boutons à l'écran couvrent le même besoin à
la souris, et ils portent le sens écrit en toutes lettres : une valeur de
maillage positive soulève la tête, donc `+` éloigne la buse. Se tromper de signe
après avoir bien lu son carré coûte une plaque.

## Corriger un bord entier d'un seul geste

Un défaut de plateau ne se présente presque jamais point par point : c'est un
bord avant trop loin, une couronne extérieure trop près, un coin qui décroche.
Corriger onze points un par un, c'est surtout la manière la plus sûre de les
corriger inégalement. La sélection est donc multiple, avec les gestes déjà
acquis du tableur : `Maj+clic` étend un rectangle depuis l'ancre, `Ctrl+clic`
ajoute ou retire un point isolé, `Maj+flèches` étend au clavier, `Ctrl+A` prend
le plateau entier. `+` et `−` déplacent alors toute la sélection du pas choisi.

Trois règles rendent la chose sûre.

**L'écriture est atomique.** Si un seul point de la sélection ne peut pas
encaisser la correction — au-delà des `0,15 mm` d'écart avec le mesuré, ou hors
des `±2 mm` — aucun ne bouge, et le message nomme le point qui bloque. Un bord
à moitié déplacé ressemble à un bord corrigé sur la surface : le point resté en
arrière ne se voit qu'à l'impression suivante.

**Le point de référence est sauté, pas bloquant.** `X150 Y150` est le zéro du
profil (ADR-046) et se trouve à l'intérieur de tout rectangle large. Refuser la
correction du plateau entier à cause de lui serait absurde : il est simplement
laissé en place, et le compte rendu le dit.

**Une correction de groupe se défait d'une touche.** La pile d'annulation
enregistre des groupes, pas des points. Défaire quarante points un par un
serait pire que ne pas proposer le geste.

Deux ajouts découlent de l'usage. Le bouton **Garder la couronne** réduit la
sélection à son périmètre : sur `11 × 11`, sélectionner tout le plateau puis
cliquer donne les quarante points du bord, et un rectangle réduit d'un cran
donne la couronne suivante — exactement les deux formes où les défauts se
lisent. Et une valeur tapée au clavier ne s'applique jamais qu'à la cellule
sous le curseur : une valeur est absolue, l'écrire dans quarante points
écraserait le relief que la palpation a mesuré.

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
