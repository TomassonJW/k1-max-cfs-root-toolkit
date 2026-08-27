# Préflight live du garde de retrait CFS V1

Date : 2026-08-27

Mission : `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-LIVE-PREFLIGHT-V1`

Verdict : **mapping OK avec correction du garde ; K1 actuellement non prête
pour un retrait faute de route engagée ; aucune action physique**.

## Autorité utilisée

Le GO exact autorisait seulement une connexion en lecture seule. Deux requêtes
d'état ont été effectuées à deux secondes d'intervalle, encadrées par les
empreintes des trois configurations principales.

Aucun G-code, chauffage, mouvement, service, restart, fichier distant ou
retrait n'a été demandé.

## État réel observé

Les deux instantanés concordent :

- Klipper `ready` ;
- aucun composant Moonraker échoué et aucun avertissement ;
- impression `standby` ;
- `box.state=connect` ;
- `T1` et `T2` connectés ;
- `T3` et `T4` absents ;
- `box.t_command` vide ;
- aucun slot CFS engagé ;
- consignes buse et plateau à zéro ;
- capteur de la tête actif, cohérent avec le segment restant après le cutter ;
- configurations inchangées avant/après.

L'état actuel est sûr mais ne remplit pas la précondition “exactement une route
engagée”. Le garde doit donc répondre `BLOCKED_NO_ENGAGED_ROUTE` et ne rien
envoyer.

## Correspondance des champs

- machine au repos : `print_stats.state` ;
- état global CFS : `box.state` ;
- unités connectées : chaque `box.T1..T4.state` égal à `connect` ;
- route engagée : pour chaque unité connectée, `filament=A..D` devient par
  exemple `T1A` ;
- commande CFS active : `box.t_command` ;
- chauffe : `extruder.target` et `heater_bed.target` ;
- segment dans la tête : capteur `filament_sensor.filament_detected`.

Les réponses complètes de `box` restent privées car elles contiennent les
numéros de série et d'autres identités matérielles.

## Correction imposée au garde

Aucun champ direct `stock_unload_state` n'existe dans l'objet `box`. La capture
historique du retrait officiel prouve en outre que `box.t_command` est resté
vide pendant tout le cycle.

Le garde hors imprimante ne suppose donc plus cet état fictif. Après la
tentative unique, il qualifie le retrait seulement si :

1. la requête revient sans erreur de transport ;
2. la route demandée a réellement disparu ;
3. `box.t_command` est vide ;
4. le nettoyage thermique est ensuite demandé et les deux cibles sont à zéro.

HTTP `ok` seul reste insuffisant. Si la route reste engagée, le garde attend de
façon bornée puis retourne KO sans retry.

## Première capture rejetée

Le premier collecteur utilisait les options `curl -sS`, incompatibles avec le
`curl` Creality. La commande a signalé ces options et la capture n'a pas été
acceptée comme autorité, même si elle contenait encore des réponses. Aucun effet
distant n'a eu lieu. Le collecteur corrigé utilise le `curl` exact de la K1 et
la seconde capture est l'unique preuve live retenue.

## Étape suivante réalisée hors imprimante

L'étape suivante a construit sur l'ordinateur le petit traducteur qui convertit
une réponse K1 nettoyée en données comprises par le garde. Il est testé sur une
route absente, unique ou ambiguë, un CFS déconnecté et des valeurs invalides.

Mission close :
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-OFFLINE-V1`.

Cette clôture reste hors imprimante. Elle n'autorise aucune connexion ni aucun
retrait réel. Le résultat est publié dans
`docs/37-adaptateur-hors-ligne-garde-retrait-cfs-v1.md`.
