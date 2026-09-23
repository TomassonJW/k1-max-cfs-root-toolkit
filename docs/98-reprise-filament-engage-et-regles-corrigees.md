# 98 — Reprise avec filament engagé : faits, règles et correctif restant

Date : 23 septembre 2026. Mission active, **non terminée**. Aucun nouveau
correctif de départ installé ; la fin `end-rewind-confirm-v3` reste en place.

## Résultat physique

Après rétablissement du courant extrudeur nominal (0,55 A configuré,
0,561526 A relu) et passage explicite du CFS T1B en mode PRINT, une avance
de 5 mm a consommé le tampon. La purge suivante a poussé 120 mm en six
portions à 2 mm/s. Les six lectures du tampon indiquent « milieu ». Thomas
confirme le débit et la boule décrochée.

Cette réussite ne sépare pas l'effet du courant de celui du mode CFS ; elle
ne prouve donc pas à elle seule la cause exacte de la première prise ratée.
La route logique du CFS reste vide : aucune finalisation logicielle de
chargement n'a été inventée à partir du seul capteur.

Aucun homing, restart, retrait ou M112 n'a été envoyé pendant cet essai.
Une palpation précise existe dans le journal avant l'échec, à 09:31 (horloge
K1). Thomas ne sait pas si les références ont pu être affectées ensuite.
La prochaine impression doit donc refaire ses références après nettoyage.

Dernier relevé : tête X210 Y273, Z physique calculé 59,975 / Z G-code 60,
cibles buse et plateau zéro, buse refroidie à environ 36 °C. Ces coordonnées
restent des estimations Klipper, pas une mesure physique indépendante.
Le filament est engagé. La purge a invalidé le nettoyage précédent pour
une nouvelle palpation.

## Corrections explicites demandées par Thomas

- Nettoyage manuel à 150 °C, pince puis brosse tenue à la main. Le filament
  peut rester engagé pendant ce nettoyage et le homing XYZ. Une confirmation
  fraîche de propreté puis la température de contact prévue restent requises.
- Aucun nettoyage automatique sur une brosse fixe. Le trajet latéral exécuté
  pendant l'essai est rejeté ; le décrochage courant utilise l'axe Y du bac.
- Déplacements libres aux vitesses normales vérifiées, sans ralentissement
  arbitraire. Ne pas confondre une vitesse de diagnostic avec la production.
- Plateau descendu d'au moins 30 mm pendant tout le passage au bac ; marge
  commandée de 35 mm et sortie à hauteur constante vers Y273 avant remontée.

Les règles actives d'AGENTS, du pilotage caméra et d'ADR-045/037 sont corrigées.
ADR-034 est signalée comme remplacée sur la condition filament. La suppression
globale d'historique a été refusée par le contrôle automatique ; les comptes
rendus historiques sont conservés et ne doivent plus dicter ces règles.

## Vitesses réellement vérifiées

| Opération | Essai diagnostic | Référence normale vérifiée |
|---|---:|---:|
| Déplacement libre vers le bac | 30 mm/s | 400 mm/s dans le binaire constructeur |
| Entrée dans le bac | 30 mm/s | 100 mm/s dans le binaire constructeur |
| Sortie du bac après purge | 30 mm/s | 250 mm/s dans le binaire constructeur |
| Avance du filament pendant purge | 2 mm/s | 6 mm/s, purge constructeur observée |

Le fichier `2_Athletes_PLA_7h39m.gcode` déclare un diamètre de 1,75 mm et des
limites de 23/24 mm³/s pour ses deux filaments. Son premier filament utilise
23, pas 24. À ce diamètre, 2 mm/s vaut environ 4,8 mm³/s ; 6 mm/s vaut environ
14,4 mm³/s. Le candidat respecte aussi la limite du filament effectivement choisi.

Le fichier déclare 560 mm/s en déplacement et 11000 mm/s² d'accélération.
La configuration machine autorise 800 mm/s et 20000 mm/s², mais le relevé
après l'échec donne encore **500 mm/s²**. Cet héritage explique une partie de
la lenteur et doit être rétabli explicitement au bon moment.

## Périmètre de reprise proposé, à terminer avant installation

1. Garder le déroulement de chauffe et de homing déjà installé, avec buse
   nettoyée, contact à 100 °C, stabilisation du plateau et chargement du profil.
2. Identifier le filament présent avant les effets CFS. Une bobine sélectionnée
   dans le prochain fichier ne prouve pas l'identité du filament déjà en place.
3. Vérifier la fin du homing frais et XYZ avant le moindre mouvement de bac.
   Garder les contrôles thermiques et la garde mécanique indépendante.
4. Avant prise ou purge, rétablir le courant extrudeur configuré et vérifier
   sa valeur ; rétablir les limites de déplacement nécessaires.
5. Si le bon filament est conservé ou sa prise précédente attribuable, établir
   le mode PRINT et vérifier son retour, purger au bac sans cutter/réinsertion,
   vérifier la consommation du tampon, décrocher en Y et sortir avant remontée.
6. Finaliser la route constructeur uniquement après réussite, afin que le Tn
   suivant du fichier ne recoupe pas le même filament. Réarmer les alarmes
   au point prévu et conserver la fin existante.
7. Vérifier les cas d'échec, annulation, nouveau départ et changement ultérieur,
   puis construire le paquet avec empreintes, sauvegarde, restauration exacte,
   validation froide et essai physique après nouveau nettoyage.

Les fichiers présents dans `retained-start-v1` sont des briques candidates,
pas un paquet installable. Les 49 tests couvrent la classification sous garde
XYZ, le dégagement du bac, la sortie avant remontée, les mouvements diagonaux,
les limites de débit et la conservation de la hauteur de retour constructeur.
L'intégration du départ, sa validation complète et son déploiement restent dus.

Le contrôle automatique a refusé un brouillon qui retirait trop tôt le contrôle
XYZ ; ce contrôle est resté intact. Il a ensuite refusé l'ajout du coordinateur
complet, jugé insuffisamment validé même comme candidat local. Cette action
reste bloquée ; aucune exécution indirecte n'a contourné ce refus.

## Preuves

Captures privées : `inventory/raw/20260923-retained-start-v1/`, notamment
`physical-actions.jsonl`, `speed-read-state.json`, `speed-file-read.stdout`,
`isolated-release-and-speed-probe-r2.stdout` et les images de fin de purge.
Les traces du binaire utilisent de faux objets dans un processus isolé : elles
ne sont ni des commandes machine ni une validation mécanique.
