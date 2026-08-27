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
physiquement. Le candidat hors imprimante de la prochaine tranche est prêt :
il réutilise le carré E4 exact, sépare chauffe, observation du flux, nettoyage,
refroidissement sans essuyage et unique référence Z. Il reste bloqué avant
effet tant que la matière précédente et sa température de nettoyage ne sont
pas explicites. L'éditeur de mesh point par point est prêt hors ligne, mais
aucun profil dérivé n'a encore été qualifié physiquement sur toute la zone
utile.

Le Goal 3 ne pourra passer à `PASSED` qu'après preuves physiques pour les sept
exigences, audit transversal des deux CFS, chauffes, Z, mesh, retours sûrs et
réconciliation du dépôt avec les captures live.

Vérifications actuelles : `14/14` tests du registre et du candidat
CLEAN-AND-REFERENCE ; suite complète de `561` tests, dont `558` verts et `3`
ignorés connus. Les `64` scripts PowerShell de la clôture CLEAN-MOTION avaient
été relus sans erreur. Le vérificateur retourne
`GOAL3_LEDGER_OK_IN_PROGRESS` avec `passed=1`, `remaining=6` et zéro effet
déclaré.
