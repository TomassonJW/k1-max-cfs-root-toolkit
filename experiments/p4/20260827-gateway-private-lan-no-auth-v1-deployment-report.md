# G4-K1-CONTROL-GATEWAY-PRIVATE-LAN-NO-AUTH-V1 — rapport de pose

Date : 2026-08-27
Statut : installé et validé

## Résultat

La passerelle Mainsail du port `4409` ne demande plus de nom de compte ni de
mot de passe. Moonraker reste lié uniquement à `127.0.0.1:7125` et nginx reste
la seule entrée LAN, limitée à la boucle locale et aux plages IPv4 privées.

Le fichier `nginx.htpasswd` existe toujours mais la configuration active ne le
référence plus. Il n'a été ni lu dans son contenu sensible, ni modifié, ni
supprimé.

## Déroulement

Le préflight a confirmé la base exacte
`714d6a17756ab101c0845ae683d0f8d9ee9a6c82708c94db8c794d479bbe026d`,
Moonraker et Klipper prêts, l'imprimante en `standby`, les cibles à zéro et les
écoutes attendues.

Le premier `nginx -t` a échoué avant toute mutation parce que le binaire
cherchait `/var/log/nginx/error.log`. La commande a été alignée sur le service
installé avec `-g 'error_log stderr;'`. L'empreinte active est restée identique
avant la reprise.

La première pose sans HTTP Basic a ensuite réussi avec sauvegarde exacte :

`/usr/data/k1-control-v1/backups/20260827-153129-g4-k1-control-gateway-private-lan-no-auth-v1-gateway-no-auth/nginx-active.conf`

Le contrôle LAN a alors révélé une seconde barrière : nginx transmettait
l'adresse du PC dans `X-Real-IP`, et Moonraker la refusait en `401`. La révision
finale présente désormais le proxy local `127.0.0.1` à Moonraker, après le
filtrage privé déjà effectué par nginx. Sa sauvegarde de reprise est :

`/usr/data/k1-control-v1/backups/20260827-153412-g4-k1-control-gateway-private-lan-no-auth-v1-r2-gateway-no-auth/nginx-active.conf`

## Preuves finales

- configuration active :
  `afb3dda29fd0008dfc7cb058bb530f3d3bf9de6578f79ded5bfcd831e7687c0d` ;
- `PREFLIGHT_GATEWAY_PRIVATE_LAN_NO_AUTH_V1_OK` ;
- `VALIDATE_GATEWAY_PRIVATE_LAN_NO_AUTH_V1_OK` ;
- `DEPLOY_GATEWAY_PRIVATE_LAN_NO_AUTH_V1_OK` ;
- appel LAN anonyme de `/server/info` : HTTP 200, Klipper `ready`, aucun
  composant en échec et aucun avertissement ;
- vrai Chrome : tableau de bord Mainsail rendu, état `Standby`, aucune erreur ni
  alerte console ;
- Moonraker reste absent de `0.0.0.0:7125` ;
- seul `S57k1_control_gateway` a été rechargé.

Aucun G-code, chauffe, mouvement, référencement, extrusion, mesure, impression,
changement de profil mesh, restart Moonraker/Klipper ou modification d'une
configuration imprimante n'a eu lieu.
