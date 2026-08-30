# START-SEQUENCE-OWNER-CAMERA-PURGE-R3 — supersédée, ne jamais exécuter

Statut depuis le 30 août 2026 :
`SUPERSEDED_NEVER_DEPLOY_OR_RUN_PROBING_AFTER_INSERTION`.

R3 reste conservée comme preuve froide de l'incident et des arrêts caméra. Elle
exige `T1A` engagé, purge avant `ACCURATE_G28` et peut donc recréer un résidu
avant la palpation. ADR-034 interdit sa pose et son essai chaud.

Ce successeur hors imprimante ferme le défaut physique observé le 29 août 2026.
R2 traçait une ligne au bord du plateau, mais ne purgeait pas dans le bac CFS et
n'exécutait pas l'aller-retour qualifié qui décroche la boule. Il lançait aussi
la référence Z précise avant tout nettoyage du filament ressorti à chaud.

L'ordre historique de R3 était :

1. référence X/Y puis référence Z grossière à `140/55 °C` ;
2. chauffe à `190 °C` et purge de `20 mm` à la position active du bac
   `X185,5 Y305 Z30` ;
3. retour à `140 °C`, puis cycle qualifié à `Z32` : `X203↔206` à `Y305`, puis
   `X203↔206` à `Y304` ;
4. pause brute, sans action CFS, jusqu'à ce qu'une image caméra montre la boule
   décrochée et la buse libre ;
5. seulement ensuite, référence Z précise, recharge du `11×11` et du Z accepté ;
6. ligne rapide entièrement hors plateau entre `X-1,7` et `X-1,3`, de `Y20` à
   `Y150` ;
7. seconde vérification caméra bloquante, puis reprise brute du modèle.

Les confirmations caméra sont des commandes techniques du contrôleur. Thomas
n'a rien à copier-coller : lors d'un futur essai, Codex capture l'image, la
contrôle et continue ou annule lui-même.

Le paquet n'est pas un candidat de pose. Il ne contient ni déployeur, ni
commande réseau, ni autorisation d'essai. La machine reste arrêtée et le run R5
est définitivement KO sans retry.
