# Résultats — propriété de la température CFS

Date : 2026-08-20
Mode : lecture seule sur la machine, préparation locale uniquement

## Faits confirmés

- Le fichier de production privé observé a été récupéré sans modifier sa source.
  Son SHA-256 est
  `eafb9b2ed394ac33883091867c32210a0a0932f1776eba1ddd5c98518ede807`.
- Il demande `190 °C` au démarrage, puis `195 °C` en impression normale. Il ne
  contient aucune commande `M104` ou `M109` demandant `220 °C`.
- La configuration active `box.cfg` fixe `Tn_extrude_temp` à `220`.
- Les données persistantes de chaque emplacement CFS enregistrent notamment le
  type, la couleur et la quantité restante, mais aucune température ni pression
  d'avance propre à la bobine.
- La base interne de matériaux associe l'entrée PLA générique à une température
  de buse de `220 °C` et une pression d'avance de `0.04`.
- Le module CFS compilé contient des chemins nommés pour lire la température de
  purge et la température cible du matériau. Son interface visible ne permet
  pas de modifier à chaud `Tn_extrude_temp`.
- Au démarrage, les journaux montrent la sélection PLA, puis le calcul d'une
  prochaine température à `220 °C` et une purge à `220 °C`.
- Lors du remplacement automatique, la macro de reprise restaure d'abord
  `195 °C`. La lecture du fichier reprend ensuite, rejoue le nouvel outil
  physique et le module CFS réapplique `220 °C` après cette restauration.
- La pression d'avance est restée à la valeur demandée par le fichier pendant
  ce remplacement. Elle n'est pas corrigée dans ce lot.

## Fichiers actifs vérifiés

| Fichier | SHA-256 |
|---|---|
| `printer.cfg` | `272640237e20659cf01f3268ed4cb0282b098c3d613e94bf84a3b80caac3c3b0` |
| `gcode_macro.cfg` | `864fedde88fbb345c220ae5658f7b04779b3981bd78d68eda6fa63c59c79a04f` |
| `box.cfg` | `e7a6b26df58a9fa8e49d3af6845f5a0937a790c8ef494b96ec72fd7392abc7a7` |

Les trois copies privées locales ont exactement ces empreintes. Elles servent
uniquement de fixtures de test ignorées par Git.

## Conclusion

Le saut à `220 °C` vient de la propriété de température du CFS, pas d'une
commande du fichier OrcaSlicer. Le premier correctif raisonnable est un contrat
PLA très étroit autour du pilote d'origine, pas un remplacement complet du
pilote ni une campagne de milliers d'impressions.

Le candidat local `G4-CFS-TEMP-PLA` :

- remplace la température fixe CFS `220` par `195 °C` ;
- exige `GEEETECH_PLA`, première couche `190 °C`, impression `195 °C` ;
- mémorise la cible lors d'un épuisement avec remplacement automatique ;
- remet une éventuelle cible manuelle `190 °C` juste après la relecture cachée
  du nouvel outil ;
- refuse les autres matériaux et températures avant le premier appel au CFS.

Il est préparé et testé localement, mais pas déployé.
