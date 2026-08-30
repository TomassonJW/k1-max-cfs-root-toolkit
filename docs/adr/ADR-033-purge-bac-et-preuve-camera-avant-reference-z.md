# ADR-033 — Purger dans le bac et voir la buse avant la référence Z précise

> **Supersédée le 30 août 2026 par ADR-034.** R3 reste une preuve froide
> historique et ne doit jamais être posé ni exécuté. Une insertion ou une purge
> précède ici `ACCURATE_G28`, ce qui peut déposer un nouveau résidu et fausser la
> palpation malgré la caméra.

## Contexte

Le run R5 du 29 août 2026 a été arrêté après l'observation d'une purge hors du
bac, de l'absence du mouvement qui décroche la boule et d'une impression
visuellement proche de `10 mm` au-dessus du plateau. La télémétrie indiquait des
valeurs Z ordinaires, mais elle ne pouvait pas voir un morceau de filament sous
la buse pendant la référence.

R2 avait volontairement remplacé le nettoyage chaud par un nettoyage manuel à
froid. Ce choix est insuffisant : du filament peut ressortir pendant la chauffe.
R2 confondait aussi une phase logicielle `visible_purge` avec une preuve physique.

## Décision

La partie « sans brosse » des ADR-031 et ADR-032 est remplacée pour le démarrage
possédé. Le nettoyage stock reste interdit, mais K1 Control doit exécuter sa
petite recette explicite :

- référence Z grossière uniquement pour obtenir une hauteur de déplacement sûre ;
- purge à la position active du bac `X185,5 Y305 Z30` ;
- retour à `140 °C` ;
- mouvement E4 déjà qualifié à `Z32`, sur `X203..206 / Y305`, puis
  `X203..206 / Y304` ;
- image caméra obligatoire montrant la boule décrochée et la buse libre ;
- référence Z précise seulement après cette image ;
- ligne d'amorçage hors plateau à `X-1,7/-1,3` ;
- seconde image obligatoire avant la reprise du modèle.

Les deux arrêts utilisent `PAUSE_BASE` et la reprise finale `RESUME_BASE`. Les
macros stock `PAUSE` et `RESUME`, qui déclenchent des actions CFS, restent
interdites. Un timeout coupe les chauffes et ne confirme jamais l'image.

## Conséquences

Le run R5 est KO et n'est jamais rejoué. Les marqueurs internes ne sont plus une
preuve de purge ni de bonne hauteur. La caméra devient une preuve de sécurité du
pilote de test et, plus tard, une étape visible dans K1 Control.

Décision historique : R3 devait rester hors imprimante jusqu'à la revue caméra
et la remise en état. ADR-034 a depuis fermé définitivement sa pose et tout
essai chaud, indépendamment de cette remise en état.
