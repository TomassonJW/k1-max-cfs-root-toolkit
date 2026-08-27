# ADR-015 — Profils mesh dérivés et corrections locales

Date : 2026-08-24

Statut : retenue et implémentée hors imprimante. Sa terminologie `robuste 6 × 6`
est corrigée par ADR-029 ; aucune correction dérivée n'est encore appliquée à
la K1.

## Contexte

Le profil composite `k1_p001_t055_r001_n11x11` a été construit à partir de
quatre acquisitions physiques `6 × 6`, soit 144 contacts et 121 positions
uniques. Sa comparaison de première couche V2 montre un gain net sur une grande
partie centrale, mais des défauts sévères et localisés près de plusieurs bords.
Le profil ne peut donc pas encore être exposé comme mode Précision quotidien.

L'hypothèse d'une déformation principalement créée par l'interpolation a été
testée contre le `bed_mesh.py` exact de la K1. Le calcul local reproduit la
matrice active stock avec une erreur maximale de `0,000000499 mm`. Sur le profil
composite, la différence maximale entre le bicubique actif et une interpolation
directe sans points intermédiaires est `0,009877883 mm`, dont
`0,009712808 mm` dans la bande extérieure de 29 mm. Le dépassement local de
l'enveloppe des quatre sommets d'une cellule ne vaut que `0,000689867 mm`.

Ces valeurs sont trop petites pour expliquer à elles seules les plis,
arrachements et variations visibles. Le profil mesuré ou sa reconstruction
physique reste donc la piste principale. La configuration exacte utilise quatre
canaux de pression PRTouch et le cœur de calcul est dans un module compilé. Une
force dépendant de la position — tube PTFE/CFS, câble, contrainte du plateau ou
capteur de charge — peut ainsi produire une erreur spatiale répétable sans que
la visualisation « mesuré / calculé » paraisse incohérente.

Mainsail `v2.18.2` ne fournit pas d'éditeur de points. Son composant de carte
convertit seulement `probed_matrix` et `mesh_matrix` en surfaces ECharts ; la
liste des profils permet de charger, renommer ou supprimer. Modifier Mainsail
directement créerait en plus une divergence fragile avec son bundle et son
service worker.

## Décision

K1 Control recevra un éditeur de **profils dérivés**. Il ne modifiera jamais le
profil physique source.

Chaque profil dérivé contient :

- l'identité et l'empreinte du profil source immuable ;
- une matrice de corrections locales en millimètres ;
- la matrice finale effectivement persistée ;
- la plaque, la température, la recette composite et l'orientation physique ;
- l'auteur, la date, le motif de test et la version ;
- le résultat du test de première couche et l'état `draft`, `qualified` ou
  `rejected`.

Le profil source `k1_p001_t055_r001_n11x11` reste intact. Il est le meilleur
profil actuellement observé, tout en gardant des défauts de bord. Le premier profil
éditable portera un autre nom, par exemple
`k1_p001_t055_r001_n11x11_tuned_v001`. Le `6 × 6` reste un repli historique,
pas un profil robuste. Aucun profil actuel n'est qualifié robuste.

## Séparation entre correction locale et Z global

Le `bed_mesh.py` exact ajoute la valeur calculée du mesh au Z commandé pendant
la première couche. Une correction positive augmente donc la compensation
locale et éloigne la buse du plateau ; une correction négative la rapproche.
L'interface emploiera d'abord les mots **Éloigner** et **Rapprocher**, puis
affichera le delta signé en complément.

Le même fichier utilise la moyenne du mesh comme cible de disparition lorsque
`fade_target` n'est pas configuré. Une constante ajoutée à toute la matrice
agirait donc aussi comme un Z global. Pour empêcher ce mélange :

- la matrice de corrections appliquée est normalisée à moyenne pondérée nulle ;
- l'interface affiche la correction demandée et la correction réellement
  normalisée ;
- le Z accepté reste un objet distinct et n'est jamais réécrit par l'éditeur ;
- aucune commande « corriger tous les points » ne remplace le réglage Z.

## Interface V1

La V1 sera ajoutée à K1 Control, accessible depuis le bouton Mainsail déjà
validé. Elle ne modifiera pas le composant Heightmap de Mainsail.

Elle comportera :

1. une grille 2D `11 × 11` orientée comme la plaque réelle, avec repères avant,
   arrière, gauche et droite ;
2. la valeur source, le delta et la valeur finale de chaque point ;
3. des actions `Rapprocher` / `Éloigner` par pas de `0,005` et `0,010 mm` ;
4. la sélection d'un point, d'une ligne, d'une colonne ou d'une petite zone ;
5. quatre vues : source, corrections seules, résultat brut et surface
   calculée ;
6. annuler, rétablir, dupliquer, comparer, rejeter et restaurer ;
7. un historique complet des versions et des essais physiques associés.

Le glisser-déposer vertical en 3D est repoussé. Il est séduisant mais ambigu :
la perspective, le zoom et l'orientation rendent une correction de quelques
centièmes de millimètre difficile à contrôler. La vue 3D reste interactive pour
inspecter et sélectionner ; la valeur est modifiée numériquement.

## Gardes V1

Les limites initiales sont volontairement conservatrices :

- pas par clic : `0,005` ou `0,010 mm` ;
- avertissement à partir de `|delta| > 0,050 mm` ;
- refus V1 au-delà de `|delta| > 0,100 mm` sur un point ;
- refus si une correction crée un saut voisin supérieur à `0,080 mm` ;
- aucun lissage automatique silencieux ;
- aucune écriture pendant une impression, une calibration, une chauffe ou une
  reprise CFS ;
- création et activation séparées ;
- backup exact, parse du bloc Klipper, relecture de la matrice, profil source
  toujours présent et rollback bit à bit.

Ces bornes ne prétendent pas décrire la mécanique idéale. Elles couvrent
l'échelle réellement observée : résidu composite maximal `0,043745029 mm` et
différence locale de forme `6 × 6 / 11 × 11` d'environ `±0,087 mm`. Si elles ne
suffisent pas, la gate s'arrête sur une cause mécanique ou une mesure à refaire
au lieu d'autoriser une surface arbitraire.

## Protocole d'apprentissage du signe et de l'amplitude

La première campagne ne corrigera pas tous les bords à l'œil. Elle utilisera un
motif peu consommateur couvrant la zone utile jusqu'aux bords, avec cellules et
coordonnées lisibles. Une seule petite région problématique sera corrigée,
d'abord de `0,010 mm`, puis réimprimée dans les mêmes conditions.

Critères :

- amélioration au bon endroit sans déplacer le défaut vers les voisins ;
- centre inchangé ;
- même plaque, même profil source, même filament et même Z effectif ;
- tube PTFE/CFS dans la même disposition ;
- aucun changement de vis ou de ressort entre les deux passages.

Une fois le signe prouvé, les autres régions peuvent être ajustées par petits
lots. Le profil n'est `qualified` qu'après une feuille complète sans défaut
grave et un second passage de confirmation.

## Causes à isoler avant de multiplier les corrections

L'éditeur compense une erreur stable ; il ne doit pas masquer une erreur qui
change à chaque passage. Avant sa promotion, il faut mesurer :

- la répétabilité de quelques points de bord dans une seule session chaude ;
- l'effet d'un tube PTFE soutenu avec assez de mou vers les quatre coins ;
- l'assise exacte de la plaque et l'absence de débris ;
- les contraintes des ressorts, entretoises, câbles et capteurs sous le plateau ;
- la stabilité des biais de quadrants déjà alignés ;
- l'absence de changement de Z introduit par `PAUSE` / `RESUME`.

Si le défaut suit la position du tube ou varie au-delà de la tolérance de
répétabilité, la correction manuelle est refusée jusqu'à la correction
mécanique.

## Persistance et activation

Le composant Moonraker K1 Control construit hors ligne un bloc de profil complet
et le valide avec le parseur exact. Il ne réutilise pas l'endpoint Creality
`update_mesh` pour modifier le profil actif en place. Cet endpoint remplace la
matrice courante, l'enregistre sous le profil courant et lance `CXSAVE_CONFIG`,
ce qui ne fournit ni source immuable ni transaction métier complète.

La pose d'un profil dérivé se fait uniquement au repos : backup exact,
écriture atomique du nouveau bloc, restart Klipper borné, relecture de ses 121
valeurs, puis rechargement du meilleur profil courant `11 × 11`. L'activation du profil dérivé est une
action séparée et réversible depuis l'interface.

## Conséquences

### Positives

- Thomas peut corriger une erreur spatiale stable sans console ni Codex ;
- la mesure d'origine, le meilleur profil courant et le repli `6 × 6` restent
  toujours récupérables ;
- chaque essai est attribuable et comparable ;
- le Z global, le mesh et l'interpolation ne sont plus confondus ;
- le futur mode Précision peut rester caché tant qu'aucun profil dérivé n'est
  qualifié.

### Négatives

- plusieurs petites impressions de diagnostic restent nécessaires ;
- une correction locale peut masquer temporairement un défaut mécanique ;
- la V1 demande un nouveau composant d'édition, une persistance versionnée et
  des tests de sécurité ;
- l'édition 3D directe n'est pas incluse.

## Alternatives refusées

### Remplacer seulement le bicubique par du bilinéaire

Refusé comme solution principale : le calcul exact borne son effet à environ
`0,01 mm` sur ce profil. Il pourra rester une option de comparaison hors ligne.

### Modifier directement `probed_matrix` dans Mainsail

Refusé : Mainsail `v2.18.2` ne l'implémente pas et un patch du bundle ne fournit
ni transaction, ni historique, ni rollback du profil physique.

### Écraser le profil composite source

Refusé : toute erreur humaine détruirait la seule référence physique qualifiée.

### Optimiser automatiquement depuis une photo

Refusé en V1 : l'apparence dépend aussi du débit, du filament, du Z global et
de la lumière. La correction doit rester explicite, bornée et validée par une
comparaison physique.

## Références

- [Klipper — Bed Mesh](https://www.klipper3d.org/Bed_Mesh.html)
- [Mainsail v2.18.2 — rendu de la carte](https://github.com/mainsail-crew/mainsail/blob/v2.18.2/src/components/charts/HeightmapChart.vue)
- [Mainsail v2.18.2 — actions sur les profils](https://github.com/mainsail-crew/mainsail/blob/v2.18.2/src/components/panels/Heightmap/HeightmapProfilesPanelRow.vue)
- [Moonraker — composants](https://moonraker.readthedocs.io/en/latest/components/)
- [Creality — configuration PRTouch K1 Max](https://github.com/CrealityOfficial/K1_Series_Klipper/blob/main/config/K1_MAX_CR4CU220812S12_1/printer.cfg)
- [Retour communautaire K1 Max + CFS sur la tension PTFE](https://github.com/DieDutchman/K1-Max-KAMP-CFS-Fix)
- [Retour communautaire sur les capteurs de charge K1](https://github.com/cryoz/K1_tenso_manual/blob/main/README_ENG.md)
