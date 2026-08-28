# Observabilité V2 et exclusion réelle du propriétaire CFS

Date : 2026-08-28

Missions closes :

- `G4-K1-CONTROL-CFS-OWNER-OBSERVABILITY-ADAPTER-OFFLINE-V2` ;
- `G4-K1-CONTROL-CFS-OWNER-OBSERVABILITY-LIVE-READ-ONLY-V2` ;
- `G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-EFFECT-V1`.

## Résultat

L'adaptateur V2 obtient `12/12` scénarios hors imprimante. Il prend le vrai Z
accepté dans `gcode_macro KCTRL_STATE.accepted_z_offset` et utilise une seule
connexion WebSocket Moonraker persistante. Une reconnexion de l'observateur ou
une transition CFS rapportée invalide immédiatement la paire de lectures.
`homing_origin` ne remplace jamais le Z accepté.

La lecture live V2 est close avec
`CLOSED_READ_ONLY_OBSERVABILITY_V2_QUALIFIED_EFFECTS_CLOSED`. Une seule session
SSH et une seule connexion Moonraker ont produit deux lectures stables : Z
accepté `−0,04 mm`, `T1/T2` connectés, aucune route, chauffes zéro, mesh
`k1_p001_t055_r001_n11x11` et configurations inchangées. Aucun effet n'a eu
lieu.

La gate d'effet a ensuite sauvegardé la valeur stock `1`, envoyé une seule fois
`BOX_ENABLE_AUTO_REFILL ENABLE=0`, prouvé deux fois la valeur `0`, puis envoyé
une seule fois `BOX_ENABLE_AUTO_REFILL ENABLE=1` et prouvé deux fois la
restauration exacte à `1`. Le même observateur et la même époque ont été
conservés, sans transition CFS. La machine termine au repos, froide, sans route,
avec le `11 × 11`, le Z accepté et les configurations inchangés.

Verdict : `CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED`.

## Ce que cette preuve autorise techniquement

Le futur propriétaire K1 Control peut désormais exiger l'exclusion stock avant
de prendre la main, puis restituer exactement la valeur précédente. Un simple
retour `ok` ne suffit toujours pas ; seules les lectures d'état ouvrent et
ferment le verrou.

Cette gate n'installe aucun propriétaire, ne déplace aucun filament et
n'autorise aucun démarrage quotidien. Les deux captures live sont consommées et
ne doivent pas être rejouées.

## Limite honnête

Une reconnexion interne du pilote qui ne produit absolument aucun changement
d'état Moonraker reste indétectable. La preuve couvre la connexion de
l'observateur et les transitions CFS réellement rapportées, pas un événement
entièrement silencieux.

## Suite

La tranche `G4-K1-CONTROL-START-SEQUENCE-OWNER-V1` est depuis installée et
validée à froid avec son surveillant borné, son parse K1 exact, ses coordonnées
de purge relues, son backup et son rollback. Le restart attend une vraie
transition du socket, puis restaure et relit le `11 × 11`. Aucune route n'est
engagée. Le chargement de `T1A` et l'essai physique restent deux gates séparées.
