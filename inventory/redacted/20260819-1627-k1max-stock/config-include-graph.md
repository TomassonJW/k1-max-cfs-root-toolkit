# Graphe de configuration active

## Point d’entrée

```text
/usr/data/printer_data/config/printer.cfg
├── sensorless.cfg
├── gcode_macro.cfg
├── printer_params.cfg
└── box.cfg
```

## Rôles

- `printer.cfg` : matériel, MCU, axes, extrudeur, lit, capteurs, PR Touch, mesh et bloc `SAVE_CONFIG` ;
- `sensorless.cfg` : homing sans contacteur et commandes associées ;
- `gcode_macro.cfg` : démarrage, fin, homing précis, nivellement, pause, reprise, chargement et retrait ;
- `printer_params.cfg` : températures par défaut et paramètres de macros ;
- `box.cfg` : liaison série CFS, coupe, chargement, retrait, nettoyage, purge et RFID.

## Chaîne de démarrage observée

```text
START_PRINT
├── BOX_START_PRINT                         [commande du module CFS]
├── WAIT_TEMP_END
├── si préparation nécessaire
│   ├── PRINT_PREPARE_CLEAR
│   ├── CX_ROUGH_G28
│   ├── CX_NOZZLE_CLEAR
│   ├── ACCURATE_G28
│   │   └── ACCURATE_HOME_Z
│   └── CX_PRINT_LEVELING_CALIBRATION
├── M140 / M104
├── BOX_START_PRINT_EXTRUDE_MATERIAL
├── M109 si le CFS est activé
└── CX_PRINT_DRAW_ONE_LINE
```

Cette chaîne explique pourquoi un G-code déjà corrigé côté trancheur peut encore être modifié par des macros exécutées ensuite dans le firmware.

## Nivellement explicite

```text
G29
├── désactivation temporaire des capteurs de filament
├── G28
├── BED_MESH_CLEAR
├── NOZZLE_CLEAR
├── ACCURATE_G28
├── BED_MESH_CALIBRATE
├── BED_MESH_OUTPUT
├── CXSAVE_CONFIG
└── réactivation des capteurs de filament
```

`G29` est potentiellement persistant à cause de `CXSAVE_CONFIG`. Il n’a pas été exécuté pendant l’acquisition.

## Contradiction de révision

- `/etc/ota_info` déclare `CR4CU220812S11` ;
- l’en-tête du `printer.cfg` actif déclare `CR4CU220812S12` ;
- le script de démarrage contient des branches séparées pour S11 et S12.

La révision exacte et l’origine du fichier actif doivent être résolues avant toute préparation de patch.
