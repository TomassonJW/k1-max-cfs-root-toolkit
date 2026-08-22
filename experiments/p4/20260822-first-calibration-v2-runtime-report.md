# FIRST-CALIBRATION-V2 — rapport d'exécution

Date : 2026-08-22

Gate : `G4-K1-CONTROL-FIRST-CALIBRATION-V2`

Capture privée : `20260822-160948-g4-k1-control-first-calibration-v2`

Résultat : **VALIDÉE ET CLOSE**

## Périmètre exécuté

- plaque `PEI_TEXTURED_A` ;
- plateau `55 °C`, buse `140 °C`, stabilisation `200 s` ;
- exactement six meshes `6 × 6` Lagrange, sans septième passage ;
- qualification robuste par deux médianes indépendantes de trois mesures ;
- chemin Z central borné jusqu'à `0,10 mm`, sans extrusion ;
- confirmation humaine obligatoire avant persistance.

## Résultat du mesh

Les deux médianes sont acceptées sur 36 points :

- moyenne absolue : `0,010788694 mm` ;
- RMS : `0,013996452 mm` ;
- maximum : `0,034352 mm`.

Le profil `k1_p001_t055_r001_n06x06` est persisté. Aucun septième mesh n'a été
lancé.

## Résultat du Z

La première session Z a été annulée sans observation humaine, sans perdre le
mesh. La reprise n'a refait aucune mesure de mesh.

Thomas a évalué la cale disponible par une pile de dix épaisseurs : `0,90 mm`,
soit environ `0,09 mm` par épaisseur. Les ajustements provisoires de `−0,01 mm`
ont produit une friction nette à `−0,05 mm`. Le retour d'un cran à `−0,04 mm` a
laissé la cale libre, ce qui vise le jeu final de `0,10 mm`. Thomas a confirmé
ce constat avant acceptation.

`ACCEPT_FIRST_CALIBRATION_V2_OK` a persisté atomiquement l'offset `−0,04 mm`,
fermé la session et coupé les chauffes.

## Validation et faux KO corrigé

Le premier `Validate` a confirmé l'état accepté mais a refusé le contrôle textuel
du profil. La cause est locale : Klipper persiste les profils générés sous la
forme `#*# [bed_mesh ...]`, alors que le pilote cherchait `[bed_mesh ...]`.

Le pilote compte désormais la forme réellement générée, au préflight comme à la
validation. Un test dédié verrouille les deux contrôles. Ce correctif n'a envoyé
aucune commande de mutation et n'a changé aucun fichier sur la K1.

La relance en lecture seule a obtenu `VALIDATE_FIRST_CALIBRATION_V2_OK`.

## État final vérifié

- `standby` ;
- cibles buse et plateau à zéro ;
- stockage Z `ok` ;
- `accepted_z_valid=1` ;
- `accepted_z_offset=-0,04` ;
- `session_active=0` ;
- chemin `committed`, mouvements bas non armés ;
- profil robuste présent ;
- deux CFS connectés et fondation conforme ;
- `printer.cfg` :
  `36cfb7e71180268841ab5cedd31628c8d9953ba437c47662ced16df18bb1bacd`.

## Limites et prochaine gate

Cette réussite qualifie la première calibration. Elle ne valide ni l'autonomie
calibration, ni l'autonomie production. La prochaine gate unique est la revue,
puis un éventuel GO séparé pour `G4-K1-CONTROL-CALIBRATION-UI-V1`. Une campagne
complète depuis cette interface, sans console ni aide Codex, restera nécessaire
avant de déclarer l'autonomie calibration.

La production reste fermée jusqu'à la bascule atomique Orca/`START_PRINT`, au
retrait prouvé du `+0,27 mm`, à la propriété des températures CFS et à G5.
