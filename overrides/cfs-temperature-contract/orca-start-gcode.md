# Contrat de démarrage OrcaSlicer

Ce paquet n'est pas déployé. Lors d'un futur `G4-CFS-TEMP-PLA`, la ligne de
démarrage OrcaSlicer devra transmettre les deux températures et l'identité du
profil :

```gcode
START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] NORMAL_EXTRUDER_TEMP=[nozzle_temperature] BED_TEMP=[bed_temperature_initial_layer_single] CFS_MATERIAL=GEEETECH_PLA
```

Pour le premier essai autorisé, les substitutions doivent produire exactement :

```gcode
START_PRINT EXTRUDER_TEMP=190 NORMAL_EXTRUDER_TEMP=195 BED_TEMP=55 CFS_MATERIAL=GEEETECH_PLA
```

La valeur du plateau peut varier selon le profil. Le contrat vérifie seulement :

- `CFS_MATERIAL=GEEETECH_PLA` ;
- première couche `190 °C` ;
- température normale `195 °C`.

Un ancien fichier qui ne fournit pas ces paramètres s'arrêtera avant
`BOX_START_PRINT`. C'est un blocage de sécurité voulu, pas une compatibilité
automatique.
