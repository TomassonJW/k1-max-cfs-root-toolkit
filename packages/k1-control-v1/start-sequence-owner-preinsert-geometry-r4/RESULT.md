# Résultat

Statut :
`CLOSED_OK_OFFLINE_AND_EXACT_K1_JINJA_VALIDATED_DEPLOYMENT_CANDIDATE_READY`.

Le candidat choisit désormais entre deux chemins. Une géométrie encore valide
garde `T1A` engagé et ne fait aucune mesure. Une géométrie perdue impose le
cycle frais qui sépare la référence de contact et l'insertion officielle. Dans
les deux cas, le bloc exécuté avec filament engagé contient zéro `G28`, zéro
`ACCURATE_G28` et zéro calibration de mesh. Le mesh et le Z sont réarmés sans
mesure avant toute purge ou trajectoire basse.

Le vérificateur dédié est vert. Le parse Jinja exact dans le Python déjà présent
sur la K1 est vert sur les `20` blocs, sans fichier distant, G-code, chauffe,
mouvement, extrusion, CFS ou service. Le déployeur remplace un seul fichier,
fait un backup exact, observe le vrai redémarrage Klipper, remet le `11 × 11`,
fait seulement un autotest froid du surveillant et restaure l'ancienne version
au premier écart.

Le paquet est prêt pour une pose séparée. Cette préparation n'autorise ni la
pose, ni l'essai physique, ni la production.

Vérifications finales : `18/18` tests ciblés verts sur R4, ADR-034 et le
tombstone R3 ; suite complète `811` tests, soit `808` verts et `3` ignorés
connus ; `git diff --check` vert.
