# Résultat actuel

Le registre couvre exactement sept exigences du Goal 3 et sépare explicitement
les actions du Goal 4. Il n'ajoute ni mission obligatoire, ni transport, ni
effet sur la K1.

État réel : **une exigence sur sept est close**. CLEAN-MOTION-V1 conserve les
deux géométries observées à froid. La grande brosse est la seule candidate au
nettoyage automatique. La brosse du bac est désormais condamnée : le cycle
chaud ultérieur a montré qu'elle recollait le filament sur la buse. Sa
géométrie reste une preuve historique, pas une validation fonctionnelle.

Les cinq tranches du cycle impression/CFS ne sont pas encore qualifiées
physiquement. Le premier nettoyage chaud est KO et Thomas a nettoyé la buse à
la main. Le candidat V2 utilise seulement la grande brosse : six allers-retours
à `F6000`, coupure de chauffe, remontée immédiate de `5 mm`, sortie de la brosse
puis refroidissement au parc sûr. Son préflight frais en lecture seule est vert
et il attend la préparation manuelle du filament puis le GO explicite de
Thomas. L'éditeur de mesh point par point est prêt hors ligne,
mais aucun profil dérivé n'a encore été qualifié physiquement sur toute la zone
utile.

L'observateur passif CFS de l'exigence 3 est également prêt : `8/8` scénarios
hors imprimante et baseline live de huit lectures verte, sans route, commande,
chauffe, mouvement ni écriture. Il pourra enregistrer la préparation manuelle
du filament puis les futurs checkpoints CFS, sans jamais les déclencher ni les
valider à la place de Thomas.

Le Goal 3 ne pourra passer à `PASSED` qu'après preuves physiques pour les sept
exigences, audit transversal des deux CFS, chauffes, Z, mesh, retours sûrs et
réconciliation du dépôt avec les captures live.

Le candidat V2 est revérifié, réépinglé et préflighté en lecture seule. Le
registre reste à `passed=1`, `remaining=6` tant que le nettoyage réel et sa
référence finale ne sont pas acceptés.
