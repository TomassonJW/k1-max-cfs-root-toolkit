# Résultat actuel

Le registre couvre exactement sept exigences du Goal 3 et sépare explicitement
les actions du Goal 4. Il n'ajoute ni mission obligatoire, ni transport, ni
effet sur la K1.

État réel : **une exigence sur sept est close**. CLEAN-MOTION-V1 est qualifié
sur les deux brosses : la géométrie principale et secondaire a été capturée,
les mouvements à froid ont été observés, E2 a validé le contact de la grande
brosse, E3-R2 a validé l'approche resserrée de la seconde, et E4 a validé son
carré exact `X203..206 / Y304..305` à `Z32`. Le retour final est sûr, les
chauffes sont à zéro et le profil actif `11 × 11` est resté inchangé.

Les cinq tranches du cycle impression/CFS ne sont pas encore qualifiées
physiquement. La prochaine est le nettoyage réel borné suivi d'une unique
référence Z avec buse propre. L'éditeur de mesh point par point est prêt hors
ligne, mais aucun profil dérivé n'a encore été qualifié physiquement sur toute
la zone utile.

Le Goal 3 ne pourra passer à `PASSED` qu'après preuves physiques pour les sept
exigences, audit transversal des deux CFS, chauffes, Z, mesh, retours sûrs et
réconciliation du dépôt avec les captures live.

Vérifications finales : `6/6` tests du registre et `40/40` avec CLEAN-MOTION ;
suite complète de `553` tests, dont `550` verts et `3` ignorés connus ; `64`
scripts PowerShell relus sans erreur. Le vérificateur retourne
`GOAL3_LEDGER_OK_IN_PROGRESS` avec `passed=1`, `remaining=6` et zéro effet
déclaré.
