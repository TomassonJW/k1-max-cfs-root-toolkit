# MESH-EDITOR-OFFLINE-V1

Statut : **gate hors imprimante validée le 25 août 2026**.

Ce paquet permet de créer et manipuler en mémoire un profil dérivé du composite
physique 11 × 11. Il ne contient aucun transport K1, aucune pose distante,
aucune écriture de configuration et aucune commande de mouvement.

Nomenclature corrigée par ADR-029 : tous les profils actuels ont des défauts de
bord. Le `11 × 11` est le meilleur profil observé et le moins mauvais, pas un
profil robuste. Le mot `robuste` reste réservé à un futur dérivé validé sur
toute la zone utile.

L'édition point par point est déjà opérationnelle : choisir `Un point`, cliquer
la cellule voulue, puis appliquer `Rapprocher` ou `Éloigner` par pas de
`0,005 mm` ou `0,010 mm`. La source reste inchangée ; seule la dérivation
versionnée reçoit la correction.

## Lancer la démonstration locale

Depuis la racine du dépôt :

    python packages\k1-control-v1\mesh-editor-offline-v1\server.py --port 8765

Puis ouvrir :

    http://127.0.0.1:8765/

Le serveur écoute uniquement sur la boucle locale. Toutes les données restent
en mémoire et disparaissent à son arrêt.

## Contrat

- source physique : k1_p001_t055_r001_n11x11, immuable ;
- profil dérivé : k1_p001_t055_r001_n11x11_tuned_v001 ;
- source publique nettoyée : 121 valeurs persistées, orientation Y croissant
  de la première à la dernière ligne et X croissant de gauche à droite ;
- empreinte canonique publique de cette matrice :
  bee530fb9738773d1f2ccb63d47743e15776690f1bcdf92a3daac7661f0f50bf ;
- actions : Rapprocher applique un delta négatif, Éloigner un delta positif ;
- pas : 0,005 mm ou 0,010 mm ;
- sélections : point, ligne, colonne ou zone de 3 × 3 points maximum ;
- avertissement au-delà de 0,050 mm ;
- refus au-delà de 0,100 mm ou pour un saut voisin supérieur à 0,080 mm ;
- aucun lissage et aucune correction automatique cachée ;
- le Z global est absent du modèle et de l’export.

## Normalisation

Le moteur reproduit la surface bicubique cardinale 31 × 31 du profil Klipper
11 × 11, avec deux points interpolés entre deux mesures et une tension de 0,2.
Il calcule la moyenne arithmétique des 961 valeurs de cette surface, puis
retire cette moyenne à toute la correction demandée.

La correction normalisée a donc une moyenne nulle sur la surface réellement
utilisée pour le fade Klipper, et pas seulement sur les 121 points de mesure.
La correction demandée et la correction normalisée restent toutes deux
présentes dans le profil versionné.

## Contenu

- source-profile.json : fixture publique nettoyée et empreintes de provenance ;
- mesh-editor-contract.json : limites exécutables de la gate ;
- mesh_editor_core.py : moteur pur, normalisation, gardes et historique ;
- klipper_profile.py : rendu et parse déterministes du bloc Klipper ;
- fake_api.py : flux futur simulé, entièrement en mémoire ;
- server.py : serveur statique et fausse API sur 127.0.0.1 seulement ;
- www/ : grille 2D orientée, vue source/deltas/final, aperçu 3D et scénarios ;
- tests/test_mesh_editor_offline.py : tests métier, isolation et export ;
- tests/mesh_editor_ui.test.mjs : tests d’orientation et de projection.

## Fausse API

La simulation expose uniquement des chemins relatifs sous
/api/mesh-editor/v1/ :

- création de la dérivation v001 ;
- correction locale ;
- annulation, rétablissement et restauration de la source ;
- export JSON ou bloc Klipper ;
- scénarios prêt, chargement, erreur de validation et source restaurée.

Ces routes sont un contrat de travail pour la future intégration. Elles ne
doivent pas être confondues avec une API Moonraker installée.

## Exports

L’export JSON conserve séparément :

- la référence et l’empreinte de la source ;
- la matrice source ;
- les deltas demandés ;
- les deltas normalisés ;
- la matrice finale ;
- l’historique et son curseur ;
- les gardes, avertissements et états de qualification ;
- une empreinte SHA-256 du document canonique.

L’export Klipper contient exactement 121 valeurs, bicubic, tension 0,2,
limites X/Y de 5 à 295 mm et métadonnées d’origine. Pour une même entrée, le
résultat est identique bit à bit. L’arrondi à six décimales doit conserver une
moyenne de surface dans la tolérance de 0,000001 mm.

## Vérifier

    python -m unittest tests.test_mesh_editor_offline
    "C:\Program Files\nodejs\node.exe" --test tests\mesh_editor_ui.test.mjs
    python -m unittest discover -s tests

La gate s’arrête ici. Le paquet ne prépare pas le G-code de diagnostic, ne
joint pas l’imprimante, n’installe pas le profil dérivé et n’expose pas le mode
Précision.
