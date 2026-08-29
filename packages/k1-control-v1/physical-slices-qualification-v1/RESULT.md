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

L'extinction nocturne a conservé physiquement le filament dans la tête, mais a
effacé la route logique et remis le profil actif à `default`. Deux lectures
fraîches l'ont prouvé sans effet. Le successeur de remise du meilleur `11 × 11`
est préparé. Après la nouvelle `Extrusion T1A`, la projection sûre complète a
prouvé `T1A` unique, `default` actif, les cibles à zéro et une tête parquée très
haut à `X210 / Y291,5 / Z66,8915`. Le seul KO venait de l'ancienne règle qui
refusait tout axe encore connu. R2 accepte désormais soit des axes non
référencés, soit exactement le parc haut borné, sans ajouter le moindre
mouvement. Le préflight R2 est maintenant vert sans effet. La K1 conserve
exactement
`T1A`, `default`, le parc haut, les cibles zéro et toutes les empreintes. La
prochaine gate ne contient donc qu'un chargement du `11 × 11`, avec retour
unique vers `default` si le résultat est ambigu.

Le diagnostic thermique R2 reste ensuite le prochain essai chaud : plateau
stabilisé `200 s` avant création du jeton manuel, puis une seule impression de
deux couches avec purge de bord et fin sûre. Les observateurs passifs des
checkpoints pause/runout/fin et le nouveau motif mesh possédé R2 sont prêts hors
imprimante, mais ne constituent aucune preuve physique.

Le plan d'exécution restant est désormais versionné et vérifié. Il empêche de
quitter `T1A` avant les essais qui dépendent du propriétaire installé, place le
blocage ambigu entre désengagement et réengagement, puis sépare changement
d'outil et runout dans un même futur job long. L'identité réelle de `T2C` et un
slot de secours réellement équivalent restent deux informations humaines
obligatoires avant cette dernière campagne.

Le retour `T2C -> T1A` n'est plus une transition cachée du plan : le paquet
`return-t2c-to-t1a-v1` est prêt hors imprimante. Il ne fait qu'observer une
action humaine unique, vérifie le retour thermique, le mesh, le Z et l'arrêt
final, et n'autorise aucun retry automatique.

Le futur réengagement `aucune route -> T1A`, après le désengagement séparé et
le checkpoint d'ambiguïté, dispose maintenant du même niveau de fermeture. Le
paquet `reengage-t1a-passive-v1` refuse toute route initiale, exige un unique
`T1A`, la chauffe observée avant et après l'engagement, puis le retour complet
à zéro. Il ne déclenche lui-même aucune action.
