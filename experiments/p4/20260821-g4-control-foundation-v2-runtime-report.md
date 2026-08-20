# G4-K1-CONTROL-FOUNDATION-V2 — rapport d'exécution réelle

Date : 2026-08-20 au 2026-08-21

Résultat : **V2 rollbackée et fermée ; aucune fondation laissée active**

## Autorité et périmètre

Thomas a fourni le texte exact `GO G4-K1-CONTROL-FOUNDATION-V2`. Les actions
sont restées limitées à Moonraker, nginx et Mainsail en observation. Aucun
G-code, mouvement, chauffe, calibration, extrusion, impression, redémarrage ou
changement Orca/Z/mesh/CFS/macro n'a été demandé.

## Résultats confirmés

Chaque préflight réel a retrouvé la K1 Max S12 structure 0 attendue, le firmware
`2.3.5.34`, Klipper au repos, les chauffes à zéro, les axes non homés, les ports
et processus Creality, ainsi que les deux CFS connectés en `1.1.3`.

Les essais ont mis en évidence, puis permis de corriger dans les sources :

1. Dropbear `2019.78` ne fournit pas SFTP : SCP doit forcer le protocole
   classique avec `-O` ;
2. le tag syslog nginx n'accepte pas le tiret et utilise `k1_control` ;
3. les chemins compilés `/var/tmp/nginx` et `/var/log/nginx/error.log` sont
   absents ; les fichiers temporaires sont isolés sous le projet et le journal
   initial est envoyé sur stderr ;
4. Moonraker doit utiliser le fournisseur Buildroot `none` et un `usb.ids`
   local pour éviter toute tentative de téléchargement ;
5. les droits du chemin statique doivent permettre à `www-data` de traverser
   jusqu'au site sans rendre l'état privé lisible ;
6. l'arrêt nginx doit attendre la fin réelle du processus et retirer son PID ;
7. nginx doit transmettre `$http_host`, port compris, pour satisfaire la
   protection d'origine WebSocket de Moonraker.

Après le septième correctif, Mainsail a réellement chargé le tableau de bord et
les données de la machine par le tunnel local. La validation a alors prouvé le
blocage structurel : Mainsail `v2.18.2` ne contient pas de mécanisme de compte
Moonraker. Une confiance locale retirée coupe Mainsail ; une confiance locale
conservée après ouverture LAN rend tous les clients nginx fiables.

## Arrêt sûr

Le critère « compte vérifié avant LAN » étant impossible dans V2, le port LAN
n'a jamais été ouvert. Chaque essai installé a été rollbacké. Après le dernier
rollback :

- `/usr/data/k1-control-v1` absent ;
- les deux services V2 absents ;
- ports `7125` et `4409` fermés ;
- ports Creality `80`, `8080` et `9999` présents ;
- Klipper, `klipper_mcu`, `master-server`, `app-server`, `display-server`,
  `web-server` et `Monitor` présents.

Les captures brutes restent uniquement sous `inventory/raw/`, ignorées par Git.
Elles ne sont pas reproduites dans ce rapport.

## Décision suivante

Thomas a choisi `CHOIX AUTH — NGINX`. Le remplacement
`G4-K1-CONTROL-FOUNDATION-V3` utilise l'authentification HTTP nginx et attendra
sa propre gate exacte après préparation et revue hors imprimante.
