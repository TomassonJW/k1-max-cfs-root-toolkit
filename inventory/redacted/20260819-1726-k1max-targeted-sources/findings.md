# Résultats de l’acquisition ciblée P2

## Conclusion sur S11/S12

La variante utilisée par le système de démarrage est maintenant établie : **K1 Max S12, structure 0**.

Éléments concordants :

- l’outil constructeur `/usr/bin/get_sn_mac.sh board` renvoie `CR4CU220812S12` ;
- `structure_version` renvoie `0` ;
- cet outil lit la partition matérielle dédiée `sn_mac`, et non `/etc/ota_info` ;
- `S55klipper_service` utilise ce même outil pour sélectionner `K1_MAX_CR4CU220812S12` ;
- la configuration active porte la version `v1.0.5`, identique à la variante usine S12 structure 0 ;
- les fichiers actifs `gcode_macro.cfg` et `printer_params.cfg` ont les mêmes empreintes que ceux de cette variante S12.

La valeur S11 dans `/etc/ota_info` est donc une métadonnée firmware incohérente avec l’identité de fabrication et la sélection réellement faite au démarrage. Elle ne doit plus être utilisée seule pour choisir une configuration.

La marque physique de la carte n’a pas été inspectée. Pour une récupération firmware, la contradiction OTA reste une raison de vérifier l’image exacte avant flash, même si la sélection logicielle S12 est désormais solidement établie.

## Cartographie des commandes internes

| Commande ou domaine | Implémentation observée | Résultat utile |
|---|---|---|
| `CXSAVE_CONFIG` | `klippy/configfile.py` | réécrit le bloc `SAVE_CONFIG`, crée une sauvegarde datée et remplace le fichier actif sans redémarrer Klipper |
| `CX_PRINT_LEVELING_CALIBRATION` | `extras/custom_macro.py` | appelle `CHECK_BED_MESH AUTO_G29=1` |
| `CX_ROUGH_G28` | `extras/custom_macro.py` | calcule une température de homing, chauffe la buse et le lit, puis lance `G28` |
| `CX_NOZZLE_CLEAR` | `extras/custom_macro.py` | appelle `NOZZLE_CLEAR` avec les températures calculées |
| `G28` avec PR Touch v2 | `extras/homing.py` puis `extras/prtouch.py` | appelle `run_G28_Z`, mesure cinq fois, prend la valeur médiane et rétablit l’origine Z avec `self_z_offset` |
| `BOX_*` | chargeur `box.py` puis module compilé `box_wrapper...so` | le cœur CFS n’est pas livré en Python lisible sur cette machine |
| `ACCURATE_HOME_Z` | aucune définition littérale dans les sources Python lisibles | la macro l’appelle, mais son enregistrement reste dans une couche dynamique ou compilée non publiée |

## Conséquences pour le Z

`CXSAVE_CONFIG` est un mécanisme de persistance, pas la source directe d’une nouvelle valeur Z. Il enregistre les valeurs que d’autres modules ont placées dans l’état de sauvegarde.

Le chemin `G28` est maintenant explicite : `homing.py` appelle `prtouch.py::run_G28_Z`, qui utilise la médiane de cinq mesures et soustrait `self_z_offset` lors de la remise à zéro de la position Z.

La dernière opération de référence dans `START_PRINT` ne peut toutefois pas encore être déclarée avec certitude, car `ACCURATE_HOME_Z` est appelé après le premier `G28` et sa définition n’existe pas dans le Python lisible. Le futur protocole de traces devra donc observer ce point d’exécution au lieu de supposer son comportement.

## Conséquences pour la température CFS

`Tn_extrude_temp` vaut `220` dans les variantes usine examinées et dans la configuration active. Le chargeur `box.py` de 129 octets correspond octet pour octet à un chargeur public qui délègue au module compilé `box_wrapper` ; son SHA-256 est identique.

Le consommateur réel de `Tn_extrude_temp` est donc la machine d’état CFS compilée. Son code source n’est pas présent sur l’imprimante et son binaire n’est pas publié dans le dépôt. La valeur `220` est un paramètre d’entrée confirmé, mais son moment exact d’application et sa restauration doivent être mesurés pendant une transition CFS.

## Limites et prochaine preuve

- aucune impression, chauffe, calibration, homing ou transition CFS n’a été déclenchée ;
- aucun fichier distant n’a été modifié ;
- le code lisible des commandes CX, de la sauvegarde et du homing a été capturé en privé ;
- les frontières compilées `BOX_*` et `ACCURATE_HOME_Z` sont maintenant explicites ;
- une comparaison de deux exécutions identiques reste nécessaire pour Gate G3.
