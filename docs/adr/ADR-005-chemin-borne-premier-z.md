# ADR-005 — Séparer la pose du chemin borné et la première calibration Z

Statut : accepté hors imprimante le 2026-08-22.

## Contexte

Le runtime Z/mesh installé sait préparer, mesurer et enregistrer un mesh. Il sait
aussi ouvrir, ajuster, accepter ou annuler un Z provisoire. En revanche, son
verrou de mouvements bas exige déjà un Z accepté. Il ne peut donc pas servir à
évaluer physiquement le tout premier Z sans contourner sa propre sécurité.

La première calibration devra chauffer, référencer les axes, mesurer le plateau
deux fois, comparer les mesures et approcher la buse du plateau. Mélanger
l'installation d'un nouveau chemin de mouvement avec ces opérations rendrait
le diagnostic et le rollback inutilement ambigus.

## Options étudiées

### Utiliser directement la console Mainsail

Simple à court terme, mais elle autorise des commandes non bornées, ne garantit
ni l'ordre des paliers ni la remontée avant acceptation, et ne constitue pas une
interface autonome.

### Réutiliser une valeur Z historique ou le `+0,27 mm`

Refusé. Cette valeur n'est pas une preuve pour la plaque, la température, la
buse, le capteur et le mesh actuels. Elle pourrait masquer le défaut que le
système doit justement supprimer.

### Installer et calibrer dans une seule gate

Refusé. Un défaut de chargement Klipper, de syntaxe ou de parser se confondrait
avec un défaut mécanique et compliquerait le retour exact à l'état précédent.

### Ajouter d'abord un overlay de chemin borné

Retenu. Une gate installe et valide à vide un fichier original séparé. Une gate
ultérieure est seule autorisée à chauffer ou bouger.

## Décision

`G4-K1-CONTROL-CALIBRATION-PATH-V1` ajoute un unique include après le runtime
Z/mesh. Sa pose ne lance aucune macro de calibration. Elle recharge seulement
l'hôte Klipper et vérifie que le nouveau chemin est au repos et refuse toute
action physique sans contexte valide.

Le futur chemin physique impose :

- un mesh persistant déjà qualifié et effectivement chargé ;
- les températures demandées et réelles dans leurs bandes ;
- une session Z provisoire active ;
- le centre `(150, 150)` ;
- la descente `5 → 2 → 1 → 0,5 → 0,3 → 0,2 → 0,15 → 0,1 mm` sans saut ;
- les ajustements Z uniquement à `0,1 mm`, suivis d'un repositionnement physique
  à cette hauteur ;
- une confirmation humaine explicite ;
- une remontée relative de `5 mm` avant acceptation ou annulation.

Aucune valeur Z par défaut n'est fournie.

## Conséquences

La première calibration gagne une voie testable et réversible, mais nécessite
une gate supplémentaire. La console Mainsail reste techniquement disponible
aux experts ; l'interface quotidienne devra exposer seulement les actions
guidées du contrat et non un champ G-code libre.

Cette décision ne rend autonome ni la calibration ni la production. La
calibration autonome exigera encore l'interface réelle. La production exigera
en plus la bascule atomique Orca/`START_PRINT`, le retrait prouvé du `+0,27 mm`,
la propriété des températures CFS et G5.
