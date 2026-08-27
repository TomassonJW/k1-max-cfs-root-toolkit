# G4-K1-CONTROL-GATEWAY-PRIVATE-LAN-NO-AUTH-V1

Ce correctif retire l'authentification HTTP Basic de la passerelle Mainsail
dédiée au port `4409`.

Les autres frontières restent inchangées :

- Moonraker écoute seulement sur `127.0.0.1:7125` ;
- nginx écoute sur `0.0.0.0:4409` ;
- nginx accepte seulement la boucle locale et les trois plages privées IPv4 ;
- Moonraker voit uniquement le proxy local déjà approuvé, jamais le client LAN ;
- les services web constructeur restent intacts ;
- aucune commande G-code, chauffe, référence, mesure ou impression n'est lancée.

Le fichier `nginx.htpasswd` n'est ni lu ni supprimé. Il reste disponible pour
un retour arrière exact, mais la configuration active ne l'utilise plus.

La pose sauvegarde `nginx-active.conf`, valide le candidat avec `nginx -t`,
remplace uniquement ce fichier puis recharge `S57k1_control_gateway`. En cas
d'échec, elle restaure la sauvegarde et recharge la même passerelle.
