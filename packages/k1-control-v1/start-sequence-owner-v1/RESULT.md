# Résultat — candidat qualifié, pose non autorisée

`G4-K1-CONTROL-START-SEQUENCE-OWNER-V1` produit maintenant un candidat de pose
fermé par défaut pour le seul chemin `KEEP_CORRECT_T1A` :

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

## Preflight réel

La capture privée
`20260828-203739-g4-k1-control-start-sequence-owner-v1` est verte en lecture
seule :

- treize templates Jinja parsés dans l'environnement K1 exact ;
- ligne de purge incluse dans les courses réelles ;
- `11 × 11` actif, Z accepté `−0,04 mm`, cibles zéro et axes libérés ;
- empreintes des configurations et composants inchangées ;
- aucune écriture distante, aucun restart, aucune chauffe, aucun mouvement,
  aucune extrusion et aucune action CFS.

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

- vérificateur du candidat :
  `START_SEQUENCE_OWNER_V1_PREFLIGHT_QUALIFIED_OK` ;
- scénarios du surveillant : `8/8` ;
- tests ciblés : `9/9` ;
- suite complète : `703` tests exécutés, `700` réussis et `3` ignorés connus ;
- parse PowerShell du déployeur : OK ;
- plan local avec empreintes figées : OK.

## Verdict et suite

Verdict : `PREFLIGHT_QUALIFIED_DEPLOYMENT_CANDIDATE_NOT_AUTHORIZED`.

Le GO reçu a été consommé par le préflight, puis le paquet a été corrigé. Rien
n'est installé. Un nouveau GO exact sur le paquet figé devra autoriser seulement
l'ajout du fichier et de son include, le restart Klipper et le test froid du
surveillant. Une gate distincte devra ensuite charger et relire `T1A`. Le
premier démarrage physique restera encore une troisième gate, avec Thomas
présent devant la K1.
