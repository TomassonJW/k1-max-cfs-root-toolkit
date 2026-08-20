# Rapport P4 — préflight G4-K1-CONTROL-FOUNDATION-V1

Date : 2026-08-20

Résultat : **KO sûr avant mutation ; V1 jamais déployée**

## Autorité et périmètre

Thomas a transmis le texte exact `GO G4-K1-CONTROL-FOUNDATION-V1`. Cette
autorisation couvrait uniquement Moonraker/Mainsail en observation, la création
du compte par tunnel, les contrôles sans G-code et le rollback de ce paquet.

## Contrôles verts

- cible MIPS, carte S12 structure 0, firmware `2.3.5.34` ;
- Klipper `standby`, aucun fichier actif, buse et plateau à `0 °C` cible, axes
  non homés ;
- T1 et T2 connectés, firmware `1.1.3`, quatre emplacements chacun ;
- environ 117 Mio disponibles et seulement 340 Kio de swap utilisés ;
- environ 4,1 Gio disponibles sous `/usr/data` ;
- ports Creality `80`, `8080`, `9999` présents ; ports `7125` et `4409` absents ;
- processus Klipper, MCU, écran, application et web Creality présents ;
- `/usr/data/k1-control-v1` et les deux futurs services absents ;
- `start-stop-daemon`, `tar`, `unzip` et `sha256sum` présents.

## Blocage

`command -v logrotate` a échoué et `/etc/logrotate.d` n'existe pas. V1 exigeait
que cette dépendance accepte sa politique avant toute copie. Continuer aurait
contredit le paquet approuvé et créé une dépendance non documentée.

## Effet réel

Aucun fichier, dossier, lien, service, port ou profil n'a été créé ou modifié
sur l'imprimante. Aucune chauffe, commande G-code, référence, mouvement,
calibration, extrusion, impression, relance ou redémarrage n'a été demandé.

## Remplacement

Le système stock possède `/sbin/syslogd -n` et `/dev/log`. Son BusyBox annonce
une rotation par défaut à 200 Kio avec une sauvegarde. V2 réutilise ce mécanisme
pour nginx, garde la rotation interne de Moonraker et n'installe aucune
dépendance. Elle requiert une nouvelle gate exacte.
