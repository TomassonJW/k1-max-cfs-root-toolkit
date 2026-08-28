# Handoff — propriétaire K1 Control du cycle CFS

Date de clôture : 2026-08-28

Mise à jour : cette passation est historique. Le cœur propriétaire qui y était
proposé est maintenant clos ; la passation courante est
`docs/HANDOFF-CFS-OWNER-CORE-2026-08-28.md`.

État de reprise : **ATTENDRE_GO**

Nouvelle tâche créée : non

Goal Codex créé : non

## État livré

La mission `G4-K1-CONTROL-CFS-S12-OWNER-PREFLIGHT-V1` est close avec le statut
`CLOSED_READ_ONLY_S12_SURFACE_CONFIRMED_EFFECTS_CLOSED`. Elle a relié notre
cartographie au matériel et au logiciel exacts de cette K1 Max, sans envoyer de
commande à l'imprimante.

La collecte unique a duré environ six secondes. Au moment de cette lecture, la
K1 était au repos, les deux chauffes demandaient `0 °C`, aucune commande CFS
n'était active, les deux CFS classiques en version `1.1.3` étaient connectés et
le profil `k1_p001_t055_r001_n11x11` était sélectionné. Les fichiers contrôlés
sont restés identiques entre le début et la fin. Les numéros de série et UUID
ont été retirés sur la K1 avant le retour de la réponse vers le PC.

Le chargeur et le binaire CFS ont les mêmes empreintes que les captures déjà
conservées : l'ancienne cartographie n'a donc pas été jetée ni recommencée. Le
binaire exact contient les 66 noms `BOX_*`, les 11 commandes nécessaires à
notre futur propriétaire et les 13 rappels internes obligatoires. Les 17
marqueurs contrôlés sont tous présents. La configuration active confirme aussi
la température stock de repli à `220 °C` et 31 appels `BOX_*`.

La décision structurante reste celle d'ADR-032 : K1 Control deviendra l'unique
propriétaire du démarrage, du changement de filament, de la fin de bobine, de
la pause, de la reprise et de la fin d'impression. Il pourra appeler de petites
primitives stock qualifiées séparément, mais jamais déléguer le cycle complet
aux grosses séquences Creality. Celles-ci peuvent déclencher notamment `G28`,
`M104`, `M109`, `BED_MESH_CLEAR`, `PAUSE` et `RESUME`, donc reprendre le
contrôle du Z, du mesh, des températures ou de la reprise à notre insu.

Le démarrage cible reste celui demandé par Thomas : nettoyage manuel de la
buse, une seule référence Z avec buse propre avant tout effet filament, montée
des températures, chargement ou conservation du filament correct, purge
visible, puis impression. Aucun brossage automatique et aucune recalibration
après l'introduction du filament. L'auto-remplacement d'une bobine vide par une
bobine de même référence reste prévu dans notre propriétaire. La capture S12
montre que les interfaces nécessaires existent, mais elle ne contenait aucune
paire alors reconnue comme identique : chaque groupe observé n'avait qu'un seul
emplacement.

Documents canoniques à relire : `GOALS.md`,
`docs/44-preflight-proprietaire-cfs-s12-v1.md`,
`docs/43-cartographie-canonique-pilotage-cfs-k1-max-v1.md`,
`docs/adr/ADR-032-proprietaire-cycle-cfs-sur-primitives-stock.md`,
`design/cfs-control-source-map-v1.json` et
`packages/k1-control-v1/cfs-s12-owner-preflight-v1/RESULT.md`.

## Limites réelles

Cette mission n'a qualifié aucun chargement, retrait, cutter, purge, runout,
retry, reprise ou fin d'impression. Elle n'a créé aucun candidat de pose et
n'autorise aucune action physique. Le Goal 3 reste en cours avec `2/7`
exigences closes ; le Goal 4 n'est pas commencé. Les défauts de bord du mesh et
le Z physique ne sont pas résolus par ce travail. L'état de la K1 indiqué plus
haut est celui de la capture, pas une garantie permanente pour une reprise
future.

## Git et vérifications

Le résultat fonctionnel est contenu dans le commit
`3ac29682128f9f8984df259d81aaaaa469ef2c0f`. Avant le commit documentaire de
cette passation, `main` et `origin/main` étaient alignés sur ce SHA, avec une
divergence `0/0`, un checkout propre et un seul worktree. Aucune ressource
étrangère n'a été trouvée ni modifiée. Le SHA final de la passation est à
communiquer dans le compte rendu de clôture.

- Préflight live nettoyé : **OK**, lecture seule et fichiers inchangés.
- Surface S12 attendue : **OK**, commandes, rappels et `17/17` marqueurs.
- Tests ciblés du préflight et de la cartographie : **OK**, `20/20`.
- Action sur la K1 pendant cette clôture : **non exécutée**.
- Validation physique des primitives CFS : **non exécutée**, hors périmètre.
- Suite complète du dépôt : **non exécutée**, inutile pour ce handoff
  documentaire ; les tests ciblés couvrent l'état livré.

## Prochaine mission unique

La reprise proposée est `G4-K1-CONTROL-CFS-OWNER-CORE-OFFLINE-V1`. Elle
construira uniquement sur le PC le moteur qui décide quoi faire à chaque étape,
à partir de la capture S12 nettoyée, des cartes publiques épinglées et des
preuves historiques. Elle conservera l'auto-remplacement vers une bobine
identique, refusera les états ambigus et n'utilisera aucun retry ou `RESUME`
stock automatique. Elle ne se connectera pas à la K1 et ne préparera encore
aucune pose.

Un nouveau GO exact est obligatoire : le GO du préflight est consommé.
Concrètement, ce GO autorisera seulement la conception, le code et les tests
hors imprimante de ce moteur. Toute installation et chaque primitive physique
resteront des gates séparées, avec Thomas devant la machine.

Modèle conseillé : `gpt-5.6-sol`, raisonnement `max`, car le graphe combine les
deux CFS, le runout, les erreurs, le retour arrière et l'exclusion stricte du
propriétaire stock. Option plus économique acceptable : `gpt-5.6-terra` en
`high`, avec davantage de relecture avant de figer le contrat.

Ce clavardage source est conservé et ne doit pas être archivé.
