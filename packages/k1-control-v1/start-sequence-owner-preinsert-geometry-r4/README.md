# START-SEQUENCE-OWNER-PREINSERT-GEOMETRY-R4

R4 remplace l'ordre rejeté de R3. Il choisit le chemin le plus court encore sûr.

Si les axes, le `11 × 11` et le Z accepté sont toujours valides, Thomas nettoie
la buse, `KCTRL_REUSE_VALID_GEOMETRY_WITH_T1A_R4` garde `T1A` engagé, vérifie et
réarme la géométrie sans mesure, puis ouvre un départ unique de dix minutes. Il
n'y a ni retrait, ni insertion, ni homing, ni palpation.

Si cette géométrie n'est plus valide, la géométrie de contact et l'insertion
deviennent deux phases visibles et séparées :

1. Sans route CFS engagée, Thomas nettoie la buse et confirme ce geste.
2. `KCTRL_PREPARE_GEOMETRY_BEFORE_INSERTION_R4` chauffe à `140/55 °C`, fait
   `G28 X Y`, puis l'unique `ACCURATE_G28`.
3. Le `11 × 11` et le Z `−0,04 mm` sont chargés et relus, les chauffes sont
   coupées et un jeton de dix minutes est ouvert.
4. Thomas insère `T1A` avec le clic officiel dans Mainsail.
5. Le travail Orca appelle `KCTRL_JOB_BEGIN_KEEP_CORRECT_V1`. R4 consomme le
   jeton, recharge le `11 × 11` si l'insertion l'a remplacé, mais ne fait aucun
   homing ni aucune palpation.
6. R4 purge dans le bac, exécute E4, attend la caméra, amorce hors zone utile,
   attend la seconde image, puis rend la main au modèle.

Le paquet ne charge ni ne retire lui-même le filament. Le clic Mainsail n'est
demandé que pour le chemin frais, lorsque la géométrie doit réellement être
refaite. Tout timeout coupe les chauffes, consomme le jeton et désarme les
mouvements bas.

R4 est maintenant installé et validé à froid. La pose a remplacé un fichier
après backup R2 exact, redémarré Klipper, remis le `11 × 11` et validé le
surveillant sans chauffe ni mouvement. Le restart a laissé les deux CFS
connectés mais aucune route logique ; la position physique du filament reste à
résoudre avant la future géométrie fraîche. Aucun essai physique n'est autorisé
par cette pose.
