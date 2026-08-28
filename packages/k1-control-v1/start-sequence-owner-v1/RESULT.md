# Résultat — installé et validé à froid

`G4-K1-CONTROL-START-SEQUENCE-OWNER-V1` est installé et validé à froid pour le
seul chemin `KEEP_CORRECT_T1A` :

- `T1A` doit être l'unique route engagée et aucune commande CFS ne doit être en
  cours ;
- le nettoyage manuel est confirmé par un jeton valable cinq minutes et
  consommable une seule fois ;
- X/Y sont référencés pendant la chauffe ;
- `ACCURATE_G28` est appelé exactement une fois à `140/55 °C` ;
- le `11 × 11` et le Z accepté sont chargés et relus avant tout mouvement bas ;
- `T1A` n'est ni coupé, ni retiré, ni rechargé ;
- la cible de première couche `190 °C` est explicite ;
- un surveillant toutes les cinq secondes coupe les chauffes si l'état
  d'impression disparaît ou si une phase dépasse son délai ;
- la purge visible ne commence qu'après une nouvelle preuve du mesh et du Z ;
- aucun repli vers `START_PRINT`, brossage, `Tn`, `220 °C`, recalibration de mesh
  ou offset `+0,27 mm` n'existe.

## Pose réelle corrigée

La capture privée
`20260828-220525-g4-k1-control-start-sequence-owner-v1` est verte :

- treize templates Jinja parsés dans l'environnement K1 exact ;
- ligne de purge incluse dans les courses réelles ;
- `11 × 11` actif, Z accepté `−0,04 mm`, cibles zéro et axes libérés ;
- empreintes des configurations et composants inchangées ;
- backup exact de `printer.cfg`, ajout d'un fichier et d'un include, puis un
  seul restart Klipper ;
- transition réelle du socket exigée avant toute validation du nouveau runtime ;
- profil `11 × 11` restauré une seule fois puis relu ;
- propriétaire et surveillant chargés, phase finale `idle` ;
- test froid du surveillant et validation indépendante terminés ;
- aucune chauffe, aucun mouvement, aucune extrusion et aucune action CFS.

La lecture montre toutefois `route_count=0`. La précondition physique `T1A`
est donc fausse et tout essai est bloqué avant effet.

## Export Orca sacrificiel

Une copie privée du petit projet `P1-SINGLE.3mf` a été exportée avec OrcaSlicer
2.4.2. L'ancien `START_PRINT`, l'ancien post-traitement et le G-code filament
ont été retirés de cette copie ; `manual_filament_change=1` empêche Orca
d'ajouter son `T0` automatique. L'export final fait deux couches, monte à
`0,4 mm`, appelle une seule fois le propriétaire et ne contient aucun ordre
interdit. Il n'a pas été envoyé à la K1 et n'a pas été imprimé.

## Vérifications du 28 août 2026

- vérificateur du payload installé :
  `START_SEQUENCE_OWNER_V1_INSTALLED_PAYLOAD_OK` ;
- scénarios du surveillant : `8/8` ;
- tests ciblés : `11/11` ;
- suite complète : `705` tests exécutés, `702` réussis et `3` ignorés connus ;
- parse PowerShell du déployeur : OK ;
- plan local avec empreintes figées : OK.

## Verdict et suite

Verdict : `INSTALLED_VALIDATED_COLD_BLOCKED_NO_T1A`.

La pose est close et son autorisation est consommée. La prochaine gate devra
charger puis relire une route unique `T1A`, car la K1 est actuellement sans
filament engagé. Le premier démarrage physique restera une gate encore séparée,
avec Thomas présent devant la K1.
