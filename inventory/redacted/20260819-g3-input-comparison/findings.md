# Comparaison locale des entrées G3

Date : 2026-08-19

Mode : analyse locale uniquement, sans connexion à l’imprimante

## Fichiers privés comparés

| Identifiant | Géométrie | SHA-256 | Taille |
|---|---|---|---:|
| A | carré `200 × 200 × 0,20 mm` | `50b54577a4b8a76a0bb5fb2b48e915d1dc6ea9e5bb87aa1f32404c559a54f856` | 70 731 octets |
| B | rectangle `200 × 201 × 0,20 mm` | `d8c1b625649a816398c2034fc573b825548d1b1899b79809fdd2c9b0fafa59a1` | 70 797 octets |

Les G-code complets restent sous `inventory/raw/` et ne sont pas publiés.

## Ce qui est identique

- les 637 réglages enregistrés par OrcaSlicer ;
- un seul filament Geeetech, sans changement de filament ;
- buse `190 °C`, plateau `55 °C`, couche unique de `0,20 mm` ;
- la suite complète des 34 commandes de contrôle hors mouvements ;
- `G28`, sélection de l’outil, puis `START_PRINT` ;
- protection Z `+0,27 mm`, appliquée après la fin de `START_PRINT` ;
- pression du filament fixée explicitement à `0,03` après `START_PRINT` ;
- absence de commande explicite `G29`, `BED_MESH_*` ou `BOX_*` dans le fichier.

## Ce qui change

- le contour déclaré avant `START_PRINT` : A couvre `200 × 200 mm`, B couvre `200 × 201 mm` ;
- les coordonnées des mouvements nécessaires à ce millimètre supplémentaire ;
- quatre mouvements supplémentaires dans B ;
- environ `0,05 g` et six secondes estimées supplémentaires.

Aucun réglage de Z, pression, température, vitesse de contrôle ou calibration ne change entre A et B.

## Comportement stock pertinent

La source privée déjà capturée montre que la préparation normale appelle le contrôle du nivellement après le homing et le nettoyage.

Ce contrôle :

- choisit aléatoirement un point proche de chacun des quatre coins de la zone de nivellement ;
- décale chaque point de deux à cinq millimètres à chaque exécution ;
- effectue trois mesures à chaque point ;
- compare ces mesures au nivellement enregistré ;
- peut relancer un nivellement complet puis le sauvegarder si au moins deux coins dépassent la tolérance.

La source lisible utilise par défaut une tolérance de `0,20 mm`; aucun remplacement de cette valeur n’a été trouvé dans la configuration capturée.

Ce comportement aléatoire ne dépend pas directement des dimensions A/B dans le code lisible. Il peut toutefois faire varier le chemin de préparation, surtout près des bords, et peut coïncider avec un changement de fichier ou un redémarrage. Le journal d’exécution doit donc distinguer corrélation et causalité.

Le seul renseignement géométrique transmis avant `START_PRINT` est le contour de l’objet. Les macros lisibles de démarrage et de contrôle du nivellement ne l’utilisent pas. Une sensibilité réellement reproductible à A/B désignerait donc une couche non lisible, une intervention de l’interface ou un état externe au G-code.

## Conséquences pour la pression du filament et le CFS

Dans ces deux fichiers, la pression est fixée à `0,03` après le retour de `START_PRINT`. Les opérations CFS de démarrage connues ont donc déjà eu lieu lorsque cette valeur est appliquée. Aucun autre changement d’outil ou de pression n’apparaît ensuite.

Ces fichiers conviennent pour isoler Z et nivellement avec un seul filament. Ils ne constituent pas encore un test CFS multi-filament.

## Séquence retenue

1. **Essai A1** : fichier A.
2. **Essai B** : fichier B, sans redémarrage.
3. **Essai A2** : fichier A de nouveau, toujours sans redémarrage.

A1 et A2 forment la paire strictement identique. B teste l’effet du seul millimètre de géométrie supplémentaire. Un test après redémarrage sera décidé seulement après analyse de cette première séquence.

La protection Z `+0,27 mm` reste identique. Comme des corrections jusqu’à `+0,60 mm` ont déjà été nécessaires selon l’opérateur, chaque début de couche doit être surveillé et arrêté immédiatement en cas de contact avec la plaque.

## État de la preuve

- entrées locales : validées ;
- isolement de la géométrie : validé ;
- comportement aléatoire du contrôle du nivellement : confirmé dans la source capturée ;
- effet réel pendant A1/B/A2 : non mesuré ;
- Gate G3 : reste ouverte.
