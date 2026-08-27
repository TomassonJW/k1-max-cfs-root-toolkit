# Résultat actuel

Le registre couvre exactement sept exigences du Goal 3 et sépare explicitement
les actions du Goal 4. Il n'ajoute ni mission obligatoire, ni transport, ni
effet sur la K1.

État réel : **deux exigences sur sept sont closes**. CLEAN-MOTION-V1 conserve les
deux géométries observées à froid. La grande brosse est la seule candidate au
nettoyage automatique. La brosse du bac est désormais condamnée : le cycle
chaud ultérieur a montré qu'elle recollait le filament sur la buse. Sa
géométrie reste une preuve historique, pas une validation fonctionnelle.

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

Une première fenêtre `EMPTY_LOAD` destinée au chargement manuel de `T1A` n'a vu
aucune action stock pendant 120 secondes. Elle est non probante et attend la
clarification humaine avant reprise.

Le Goal 3 ne pourra passer à `PASSED` qu'après preuves physiques pour les sept
exigences, audit transversal des deux CFS, chauffes, Z, mesh, retours sûrs et
réconciliation du dépôt avec les captures live.

Le registre est à `passed=2`, `remaining=5`. L'identifiant automatique
historique reste visible, mais ADR-030 et la politique versionnée prouvent sa
résolution : voie automatique rejetée, nettoyage manuel obligatoire et actions
automatiques techniquement bloquées.
