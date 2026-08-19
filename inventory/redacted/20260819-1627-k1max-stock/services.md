# Services et processus

## Architecture observée

La machine utilise Buildroot et des scripts d’initialisation dans `/etc/init.d`, pas `systemd`.

| Composant | État observé | Entrée principale | Rôle |
|---|---|---|---|
| Klipper | actif | Python + `klippy.py` | moteur d’impression, configuration active sous `/usr/data` |
| Klipper host MCU | actif | `klipper_mcu` | GPIO et fonctions MCU côté Linux |
| Dropbear | actif | `dropbear` | serveur SSH root |
| Creality master | actif | `master-server` | orchestration constructeur |
| Interface applicative | active | `app-server`, `display-server`, `web-server`, `Monitor` | écran, application et interface web |
| Réseau | actif | `wifi-server`, DHCP, Wi-Fi supplicant, mDNS | connexion et découverte locale |
| Audio | actif | `audio-server` | notifications audio |
| Caméra | active | `cam_app`, `mjpg_streamer` | caméra et flux local |
| IA caméra | active | `cx_ai_middleware` | traitement caméra constructeur |
| Vidéo distante | active | `webrtc` | service vidéo, identifiant privé retiré |
| Mise à niveau | actif | `upgrade-server` | gestion constructeur des mises à jour |
| Moonraker | non observé | aucun processus trouvé | version et présence non confirmées |

## Démarrage et dépendances

- `S55klipper_service` sélectionne une configuration constructeur à partir du modèle, de la carte et de la version de structure.
- Il peut créer, sauvegarder ou migrer `printer.cfg` au démarrage lorsque les versions diffèrent.
- Il lance Klipper avec `/usr/data/printer_data/config/printer.cfg` et écrit le journal sous `/usr/data/printer_data/logs`.
- `S57klipper_mcu` gère le MCU Linux utilisé par Klipper.
- `S99start_app` lance la pile applicative Creality après Klipper.

## Limite de l’inventaire réseau

La commande de liste des ports n’a produit aucune sortie exploitable. Les processus actifs sont confirmés, mais la carte complète des ports reste non vérifiée. Aucun second accès SSH n’a été demandé pour corriger cette limite.
