# ADR-023 — Encadrer le retrait stock avant un propriétaire série

Date : 2026-08-27

Statut : accepté

## Contexte

Le protocole série minimal reste incomplet. Une capture réelle vient toutefois
de montrer que la macro constructeur `BOX_QUIT_MATERIAL` réalise correctement
un retrait `T1A` en deux phases et met à jour l'état du CFS.

Elle révèle aussi deux risques : la cible de buse reste à `220 °C` après la fin,
et une réponse HTTP `ok` peut masquer une commande G-code mal encodée.

## Options

### 1. Construire maintenant notre propre propriétaire série

Refusé. La trame sortante complète, la prise exclusive du bus, les autres
routes et les scénarios de faute restent inconnus.

### 2. Appeler directement la macro constructeur sans contrôle

Refusé. Ce passage laisserait la chauffe active et pourrait déclarer un succès
sur la seule réponse HTTP.

### 3. Encadrer la macro constructeur avec des gardes

Retenu pour le prochain incrément. Le logiciel laisse Creality contrôler le CFS
mais vérifie la route et l'état initial, surveille la fin réelle, contrôle le
slot après retrait et coupe toujours les chauffes.

## Décision

Le propriétaire série indépendant reste différé et sa liste appelable reste
vide. La prochaine mission prépare hors imprimante un garde étroit autour de
`BOX_QUIT_MATERIAL`.

Ce garde ne sera pas encore un système complet de changement de filament. Il
qualifiera uniquement le retrait officiel, son nettoyage thermique et ses
conditions de refus.

## Conséquences

- la voie immédiate réutilise un comportement constructeur réellement observé ;
- aucune trame série n'est inventée ;
- `TURN_OFF_HEATERS` devient une obligation de fin, succès ou échec ;
- chaque réponse doit être confirmée par son effet réel ;
- le segment restant dans la tête est affiché comme tel ;
- chargement, purge, autres slots et second CFS restent des gates séparées ;
- toute pose ou nouvelle action physique demandera un GO exact distinct.
