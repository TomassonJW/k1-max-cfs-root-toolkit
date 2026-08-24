# MESH-EDITOR-OFFLINE-V1 — résultat

Date : 25 août 2026

Verdict : **OK, gate hors imprimante close**.

## But

Créer le premier éditeur sûr de profils mesh dérivés sans toucher à la K1 :
source physique immuable, corrections locales traçables, moyenne de surface
nulle, historique, gardes, aperçu et export reproductible.

## Périmètre réellement exécuté

La mission est restée entièrement locale :

- aucune connexion SSH ;
- aucun tunnel ;
- aucun appel Moonraker ou Creality ;
- aucun chauffage, homing, mouvement, palpage ou impression ;
- aucune écriture de printer.cfg ;
- aucune écriture Z ;
- aucun déploiement et aucune exposition du mode Précision.

Le serveur de démonstration a écouté seulement sur 127.0.0.1, puis a été arrêté
après la recette.

## Source publique minimale

Les trois artefacts privés indiqués par la passation ont été relus et leurs
empreintes concordent :

| Preuve privée | SHA-256 |
|---|---|
| printer.cfg.composite | f88d6b52477592805384fca2b4d7abd00298deecd82227af2fa580085fe26fa2 |
| composite-mesh-state.json | 09fe8333dd1708dc781091e367efef7220d8056d40dab7ffefee26e55de9d8eb |
| final-printer-status.json | 24490c6efc9f2d315a6772f62af20864d5ed8e492f92cb36076213cf7abbc9e |

Seuls les 121 nombres persistés et les métadonnées strictement nécessaires ont
été copiés dans source-profile.json. Aucun chemin privé, journal, adresse
réseau, configuration complète ou photo n’a été publié.

L’empreinte canonique de la matrice publique à six décimales vaut :

bee530fb9738773d1f2ccb63d47743e15776690f1bcdf92a3daac7661f0f50bf

Elle est distincte de l’empreinte de la matrice candidate de composition, qui
portait encore sa précision de calcul interne. La source persistée reste
l’autorité pour l’export Klipper.

## Décisions réalisées

### Source et dérivation

La source k1_p001_t055_r001_n11x11 n’est jamais modifiée. Le moteur crée
k1_p001_t055_r001_n11x11_tuned_v001 et conserve séparément source, demande,
normalisation et résultat final.

Le document dérivé contient une empreinte canonique et refuse :

- une autre source ;
- une matrice source altérée ;
- une incohérence entre demande, normalisation et matrice finale ;
- l’inclusion du Z global ;
- une empreinte documentaire invalide.

### Moyenne réellement nulle

Le code reproduit la forme cardinale-Hermite bicubique du maillage qualifié :
11 × 11 points, deux points intermédiaires par intervalle, tension 0,2, soit
une surface 31 × 31.

La moyenne retirée est celle des 961 valeurs interpolées. Cette définition
reste cohérente avec la moyenne de surface utilisée par le fade Klipper. La
tolérance interne est de 10 puissance moins 12 mm. Après l’arrondi Klipper à
six décimales, la tolérance contractuelle est de 0,000001 mm.

### Gardes et historique

- Rapprocher : delta négatif ;
- Éloigner : delta positif ;
- pas autorisés : 0,005 et 0,010 mm ;
- sélection : point, ligne, colonne ou petite zone limitée à 3 × 3 ;
- avertissement au-dessus de 0,050 mm ;
- refus au-dessus de 0,100 mm ;
- refus d’un saut voisin supérieur à 0,080 mm ;
- l’état reste identique après un refus ;
- undo, redo, branche d’historique et restauration sont déterministes ;
- aucune correction automatique ou aucun lissage implicite.

### Interface

La grille affiche l’arrière Y 295 en haut, l’avant Y 5 en bas, X 5 à gauche et
X 295 à droite. Les 121 cellules sont utilisables au clic et au clavier.

Les vues Source, Deltas et Final partagent la même orientation. Le mode
Comparer affiche les valeurs source et finale. L’aperçu 3D autorise seulement
la sélection par clic : aucune traînée verticale n’existe en V1.

Les scénarios de chargement, refus de validation et restauration sont simulés
par la fausse API. La puissance avancée reste repliée par défaut.

## Vérifications obtenues

- tests ciblés Python : 21 verts ;
- tests JavaScript de géométrie : 5 verts ;
- suite complète du dépôt : 294 tests verts, 3 ignorés connus ;
- source compatible avec la grammaire Python 3.8 ;
- rendu réel dans le navigateur intégré :
  - 121 cellules ;
  - profil v001 visible ;
  - moyenne 0,000000000000 mm ;
  - correction centrale à 0,005 mm ;
  - undo et redo conformes ;
  - grille et aperçu 3D mutuellement exclusifs ;
  - refus simulé sans mutation ;
  - aucune erreur ou alerte navigateur.

Le test visuel a découvert puis fait corriger un conflit CSS avec l’attribut
hidden. La page a été rechargée et la correction a été revérifiée sur le même
flux.

## Ce que cette gate rend autonome

Thomas peut désormais créer, examiner, corriger, annuler, rétablir, comparer,
restaurer et exporter un profil dérivé dans un laboratoire local sans
traduction Codex et sans risque pour la K1.

Cela ne rend pas encore autonome le mode Précision réel : l’éditeur est une
simulation, et aucun profil dérivé n’est installé.

## Gate suivante

La prochaine gate unique est MESH-EDGE-DIAGNOSTIC-V1. Elle doit préparer puis
exécuter un motif physique borné à X/Y 5..295 mm afin de prouver le sens d’une
seule correction locale de 0,010 mm, sa répétabilité aux bords et l’influence
du PTFE, sans dégrader le centre.

Cette gate exigera un état K1 frais, la présence de Thomas et une confirmation
factuelle du plateau avant toute action physique. Elle ne doit pas être
anticipée par le paquet hors ligne.
