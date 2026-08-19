# Montages et persistance

## Faits mesurés

| Zone | Type | État | Taille | Utilisé | Rôle observé |
|---|---|---|---:|---:|---|
| `/rom` | squashfs | lecture seule | 155,9 MiB | 100 % structurel | système constructeur immuable |
| `/overlay` | ext4 | lecture-écriture | 96,8 MiB | 2,6 MiB | couche de modifications du système |
| `/` | overlay | lecture-écriture | 96,8 MiB | 2,6 MiB | vue système active |
| `/usr/data` | ext4 | lecture-écriture | 6,5 GiB | 1,8 GiB | données persistantes, configurations, G-code et journaux |

`/usr/data/printer_data` contient environ :

- `logs` : 1,6 GiB ;
- `gcodes` : 13,1 MiB ;
- `config` : 628 KiB.

Les journaux Klipper représentent donc l’essentiel de l’espace utilisé. Les fichiers rotatifs observés atteignent chacun plusieurs centaines de mégaoctets. Aucun nettoyage n’a été exécuté.

## Carte de persistance

- configuration active : `/usr/data/printer_data/config/printer.cfg` ;
- fichiers inclus : même répertoire persistant ;
- G-code : `/usr/data/printer_data/gcodes` ;
- journaux Klipper : `/usr/data/printer_data/logs` ;
- données et journaux Creality : `/usr/data/creality/userdata` ;
- configuration Wi-Fi : présente sous `/usr/data`, retenue exclusivement en privé.

Le système de démarrage peut recopier ou migrer des configurations constructeur vers ce répertoire. La présence dans `/usr/data` confirme la persistance du support, mais pas la stabilité de chaque fichier face aux migrations de firmware.
