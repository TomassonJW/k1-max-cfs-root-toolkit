# ADR-007 — Maillage robuste sur PR Touch V2

Date : 2026-08-22

## Contexte

FIRST-CALIBRATION-V1 a comparé deux maillages `6 x 6` à `55/140 °C`. L'écart
moyen était `0,018049 mm`, mais le maximum atteignait `0,062125 mm`, donc V1
s'est arrêté avant toute persistance ou calibration Z.

L'analyse du journal exact et du module actif `prtouch_v2` montre 209 contacts
pour 72 points. Cinquante points ont reçu deux contacts ; les autres en ont reçu
de trois à treize. Des faux contacts dépassant largement un millimètre sont
filtrés, mais le résultat point par point garde un bruit résiduel incompatible
avec une comparaison maximale stricte de seulement deux passages.

## Options examinées

1. Augmenter la stabilisation thermique. Le motif mesuré alterne les signes et
   reste dispersé ; il ne ressemble ni à une dérive uniforme ni à une pente du
   plateau. Cette option augmente le temps sans traiter la cause observée.
2. Modifier le module PR Touch constructeur compilé. Cela rendrait la mise à
   jour et le rollback plus fragiles, pour un comportement interne opaque.
3. Relâcher simplement le seuil V1. Cela accepterait un passage bruité comme
   référence sans améliorer le maillage enregistré.
4. Agréger un nombre fixe de passages et séparer qualification et candidat.
   Cette option utilise les interfaces déjà présentes et ne modifie pas le
   code constructeur.

## Décision

V2 exécute exactement six maillages dans le même cycle thermique. Deux groupes
indépendants de trois sont réduits par médiane point par point. Ils sont
qualifiés si la moyenne absolue est au plus `0,020 mm`, le RMS au plus
`0,025 mm` et le maximum au plus `0,060 mm`. Le candidat enregistré est la
médiane point par point des six passages.

Le nombre de passages et les trois limites sont figés avant l'exécution. Un KO
arrête la campagne ; il ne déclenche aucun passage supplémentaire. Le candidat
n'est chargé et persisté qu'après qualification, avec relecture exacte et
rollback vers le `printer.cfg` sauvegardé.

## Conséquences

- La campagne dure plus longtemps qu'un maillage stock, mais reste bornée.
- Le maillage persistant est moins sensible à un contact isolé.
- Le code PR Touch constructeur et les overlays installés restent inchangés.
- La preuve porte sur deux estimateurs indépendants, pas sur deux mesures brutes.
- La calibration Z et la production restent des validations distinctes.
