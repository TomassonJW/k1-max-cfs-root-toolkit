# Résultat — activation stock-derived V1

Statut : **ACTIVÉE ET CORRIGÉE — ESSAI PHYSIQUE BLOQUÉ AVANT RETRAIT PAR LE
CAPTEUR CUTTER**.

Le candidat obtient maintenant `22/22` scénarios hors imprimante. Le
propriétaire Klipper obtient `17/17` scénarios.
Ils couvrent notamment le vrai événement runout, la relève unique T1A vers T2D
à la température G-code, l'absence de cutter sur bobine réellement vide, le
cutter sur changement volontaire, le refus d'une relève ambiguë, l'arrêt froid
sans spare et le non-rejeu d'un ticket retrouvé après restart.

La capture finale
`20260831-205322-g4-k1-control-stock-derived-cycle-activation-v1` contient :

- `DEPLOY_STOCK_DERIVED_CYCLE_ACTIVATION_V1_OK` ;
- `VALIDATE_STOCK_DERIVED_CYCLE_ACTIVATION_V1_OK` obtenu par une lecture
  indépendante après la pose ;
- Klipper `ready`, impression `standby`, chauffes à zéro et axes libérés ;
- mesh `k1_p001_t055_r001_n11x11` et Z effectif `-0,04` ;
- propriétaire direct actif, commandes stock concurrentes bloquées et phase
  Moonraker `idle` ;
- politique stock `auto_refill=0`, runout non armé, compteur d'événement à
  zéro et aucune route engagée ;
- aucun fichier de run ou de sélection, aucune commande d'effet et aucun
  envoi de trame CFS.

Les refus intermédiaires ont tous eu lieu avant chauffe, mouvement, extrusion,
palpage, recalcul de mesh ou action filament. Chaque tentative a déclenché le
rollback automatique. Elles ont permis de corriger quatre écarts réels : le
rechargement du module Python, l'identité publiée du propriétaire direct, la
reconnexion asynchrone des deux CFS et la restauration explicite du Z accepté
après un restart hôte. Une capture séparée,
`20260831-205226-g4-k1-control-stock-derived-cycle-activation-v1`, prouve la
remise immédiate du Z effectif à `-0,04` avec `MOVE=0`.

Le 1er septembre, la lecture des traces a remplacé la purge de reprise de
`30 mm` par le contrat réel : `140 mm` au chargement initial et quantités de
transition issues de la matrice Orca du G-code. Le fichier d'essai courant
publie `266,081080 mm` pour `0→1` et `126,804265 mm` pour `1→0`.

Trois correctifs ont été installés et validés indépendamment : quantité de
purge, conservation de `T1A` pendant la référence d'accès cutter, et suppression
de la réconciliation quand le propriétaire direct possède déjà la route.

Le retrait réel reste fermé. La position stock `X38 Y304,5`, puis les positions
progressives jusqu'à la limite publiée `Y307,5`, n'ont jamais fait passer
`cut_pos` à `1`. Le pilote n'a donc envoyé aucune rétraction. L'état final
confirmé garde `T1A` chargé et les deux capteurs filament actifs ; chauffes à
zéro, axes libérés, `11 × 11` actif et Z `−0,04 mm`. La reprise exige maintenant
une vérification mécanique réelle du levier/cutter ou de son capteur. Voir
ADR-040.

La gate manuelle suivante dispose maintenant d'un moniteur strictement en
lecture seule. Le préflight du 1er septembre a confirmé la buse à `30,65 °C`,
les cibles à zéro, les axes libérés, `cut_pos=0` et les deux capteurs filament
actifs. La caméra était fraîche et nette. Une première fenêtre de `90 s` n'a
vu aucune transition, mais l'appui humain n'a pas été confirmé : ce passage est
**inconclusif** et ne prouve pas une panne du capteur. La preuve attendue reste
exactement `0→1→0` pendant un appui puis un relâchement du levier solidaire de
la tête.
