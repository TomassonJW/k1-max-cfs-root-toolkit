# Résultat actuel

Le registre couvre exactement sept exigences du Goal 3 et sépare explicitement
les actions du Goal 4. Il n'ajoute ni mission obligatoire, ni transport, ni
effet sur la K1.

État réel : **deux exigences sur sept sont closes**. CLEAN-MOTION-V1 conserve les
deux géométries observées à froid. La grande brosse avait été la dernière
candidate automatique ; son essai chaud a lui aussi été rejeté. La brosse du
bac avait déjà recollé le filament sur la buse. Les deux géométries restent des
preuves historiques, pas des recettes fonctionnelles.

Les cinq tranches du cycle impression/CFS ne sont pas encore qualifiées
physiquement. Après le KO de la brosse du bac, le V2 non probant et un V3 à huit
allers-retours diagonaux `F12000`, Thomas a jugé le résultat non convaincant.
Le nettoyage automatique est fermé ; Thomas nettoiera la buse à la main avant
chaque référence ou impression sensible. Aucune V4 ni référence automatique
n'est autorisée par cette gate. L'éditeur de mesh point par point est prêt hors ligne,
mais aucun profil dérivé n'a encore été qualifié physiquement sur toute la zone
utile.

L'observateur passif CFS de l'exigence 3 est également prêt : `8/8` scénarios
hors imprimante et baseline live de huit lectures verte, sans route, commande,
chauffe, mouvement ni écriture. Il pourra enregistrer la préparation manuelle
du filament puis les futurs checkpoints CFS, sans jamais les déclencher ni les
valider à la place de Thomas.

La reprise `EMPTY_LOAD/T1A` est close OK : chargement unique, purge visible,
cible `220 °C`, retour des chauffes à zéro et configurations inchangées. La
seconde reprise `KEEP_CORRECT_T1A` a ensuite conservé `T1A` sans transition ni
commande CFS et n'a jamais demandé la cible cachée `220 °C`. Le chemin CFS
« garder le bon filament » est donc techniquement prouvé pendant ce départ
observé.

Le départ stock historique reste KO. `START_PRINT` a vidé ou remplacé le `11 × 11`
pendant ses mouvements bas, puis son brossage a laissé du filament sur la buse.
Thomas a nettoyé manuellement et a dû passer temporairement de `−0,04` à
`−0,19 mm` pour une première couche à peine correcte. Le `11 × 11` exact était
bien actif lors de cette lecture et le Z accepté stocké était resté à `−0,04` :
la forme du mesh n'explique pas à elle seule ce décalage uniforme. Le résidu
pendant la nouvelle référence Z est l'explication principale, sans être promu
en preuve métrologique absolue. ADR-031 et START-SEQUENCE-OWNER-V1 préparent
donc hors imprimante le remplacement atomique du départ stock : nettoyage
manuel, une seule référence Z propre, aucun brossage, aucune mesure de mesh,
températures explicites et purge après armement mesh/Z.

Le départ possédé a ensuite été exécuté une fois. L'automatisation est verte,
la purge est confirmée et les deux couches sont bonnes après intervention
humaine à `−0,19 mm`. `KEEP_CORRECT_T1A` passe donc comme checkpoint CFS, mais
le Z `−0,04 mm` ne passe pas sans intervention. La différence entre les `200 s`
de stabilisation de la calibration et l'absence de stabilisation du départ est
une hypothèse plausible, pas encore une preuve.

Le Goal 3 ne pourra passer à `PASSED` qu'après preuves physiques pour les sept
exigences, audit transversal des deux CFS, chauffes, Z, mesh, retours sûrs et
réconciliation du dépôt avec les captures live.

Le registre est à `passed=2`, `remaining=5`. L'identifiant automatique
historique reste visible, mais ADR-030 et la politique versionnée prouvent sa
résolution : voie automatique rejetée, nettoyage manuel obligatoire et actions
automatiques techniquement bloquées.

## Reprise actuelle au 29 août 2026

`T1A` est engagé et l'état sûr a été restauré. Le petit fichier de deux couches
a terminé sans `END_PRINT`, `BOX_END` ni `BOX_END_PRINT`. Sa fin minimale a bien
coupé les chauffes et libéré les moteurs, mais n'a ni parqué la tête ni présenté
le plateau. Ce constat alimente l'exigence 6 sans la faire passer. Le filament
est volontairement resté engagé ; son retrait appartient au bouton séparé
`Désengager et nettoyer`.

La gate passive `T1A → T2C` est déjà préparée hors imprimante, sans commande
d'effet et sans retry. Avant de l'utiliser, le prochain verrou est un diagnostic
Z avec la même stabilisation thermique que la calibration.
