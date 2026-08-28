# ADR-031 — Posséder le démarrage sans brossage ni recalibration

Date : 2026-08-28

Statut : **décision acceptée par verdict physique ; candidat hors imprimante
préparé et vérifié structurellement, aucune pose autorisée**

## Contexte

Le second essai réel `KEEP_CORRECT_T1A` a retiré les anciens `G28` et `T0`
placés avant `START_PRINT`, mais il a conservé `START_PRINT` lui-même. La
capture passive `20260828-goal3-cfs-keep-correct-t1a-r5` montre alors :

- `T1A` conservé sans retrait, rechargement ni commande CFS active ;
- aucune cible cachée à `220 °C` sur ce chemin, avec un maximum observé de
  `190 °C` ;
- le profil actif passé de `11 × 11` à vide, puis `default`, avant la ligne de
  purge basse stock ;
- le `11 × 11` réarmé seulement après le retour complet de `START_PRINT`, donc
  trop tard pour protéger le nettoyage, les références et la purge stock ;
- des configurations inchangées.

Le nettoyage constructeur a laissé du filament sur la buse. Thomas a dû le
retirer manuellement pendant le cycle. La première couche n'est devenue à
peine acceptable qu'avec une origine Z temporaire à `−0,19 mm`, alors que le Z
accepté stocké reste `−0,04 mm`. L'écart uniforme de `−0,15 mm` est cohérent
avec une référence Z faussée par un résidu, sans constituer à lui seul une
preuve métrologique absolue de la cause.

La politique canonique ADR-030 interdit déjà le nettoyage automatique. La
séquence stock la contredit encore en appelant `CX_NOZZLE_CLEAR`, une nouvelle
référence Z, un contrôle de nivellement et une purge basse avant que
`KCTRL_PRODUCTION_ARM` puisse agir.

## Décision

K1 Control utilisera un point d'entrée distinct de `START_PRINT`. La première
version installable couvrira uniquement le cas quotidien déjà prouvé : le bon
filament `T1A` est engagé et doit être conservé.

Le démarrage suit exactement cet ordre :

1. Thomas nettoie la buse à la main et émet une confirmation consommable une
   seule fois.
2. Le contrat vérifie `T1A`, l'absence de commande CFS, le Z accepté, le profil
   demandé et des températures explicites.
3. Le plateau et la buse commencent à chauffer immédiatement. Le référencement
   X/Y se fait pendant cette montée afin de ne pas ajouter une attente vide.
4. La buse propre et le plateau atteignent ensuite l'unique fenêtre de
   référence déjà liée au Z accepté, `140/55 °C`. Une seule commande
   `ACCURATE_G28` établit alors la référence Z. Il n'y a ni référence Z
   grossière, ni second palpage Z.
5. Le profil persistant demandé et le Z accepté sont chargés puis relus avant
   tout mouvement bas.
6. `T1A` est revérifié et conservé. Aucun `Tn`, retrait, coupe ou chargement
   n'est appelé sur cette branche.
7. La buse atteint la température de première couche déclarée, puis une purge
   déterministe s'exécute seulement après une seconde vérification mesh/Z.
8. Le G-code du modèle commence sans offset caché.

Une route absente, différente ou ambiguë bloque la V1 avant tout effet CFS. Les
branches de chargement et de changement seront ajoutées au même propriétaire
seulement lorsqu'un ticket thermique aura une cible effective avant son
premier effet. Elles ne retomberont jamais silencieusement sur `220 °C`.

## Interdits

Le nouveau point d'entrée ne peut appeler :

- `START_PRINT`, `BOX_START_PRINT` ou `BOX_START_PRINT_EXTRUDE_MATERIAL` ;
- `CX_ROUGH_G28`, `CX_NOZZLE_CLEAR` ou une recette de brosse ;
- un `G28` contenant Z, ou plus d'un appel `ACCURATE_G28` ;
- `CX_PRINT_LEVELING_CALIBRATION`, `CHECK_BED_MESH`, `G29` ou
  `BED_MESH_CALIBRATE` ;
- un `Tn`, une température CFS implicite ou l'ancien offset Orca `+0,27 mm`.

Le mesh reste une calibration explicite séparée. Le démarrage ne mesure ni ne
persiste un nouveau mesh et ne modifie jamais le Z accepté.

## Conséquences

La V1 rend le chemin `KEEP_CORRECT_T1A` court, observable et fermé par défaut.
Elle ne prétend pas encore automatiser un chemin vide ou un changement de
matière. Cette limite est volontaire : bloquer est préférable à charger à une
température ou avec une géométrie non maîtrisée.

Le démarrage ne sera pas entièrement autonome, puisque Thomas doit nettoyer la
buse et confirmer sa propreté. Cette contrainte est la politique produit
acceptée, pas une dette à masquer.

Le profil physique `11 × 11` et le Z accepté pourront être recalibrés dans une
campagne séparée. Leur optimisation ne fait pas partie de ce correctif et ne
doit pas retarder la reprise de contrôle du démarrage.

## Gate future

Le candidat hors imprimante est
`G4-K1-CONTROL-START-SEQUENCE-OWNER-V1`. Sa préparation n'autorise aucune
connexion, pose, chauffe, référence, extrusion ou impression. Une future pose
exigera une revue figée du fichier de macros, de l'include, du profil Orca, des
backups, du rollback et des commandes exactes.
