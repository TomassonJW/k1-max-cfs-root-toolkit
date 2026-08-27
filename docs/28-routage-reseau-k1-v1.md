# Routage réseau K1 V1

Date : 2026-08-27
Statut : routage appliqué ; passerelle LAN sans mot de passe validée

## Résultat

La panne apparente venait de deux contrôles qui avaient visé directement une
ancienne adresse DHCP. La K1 répondait normalement par l'alias canonique
`k1max-root`. Après réservation stable de l'adresse par Thomas, la configuration
SSH locale a été sauvegardée puis corrigée pour viser directement cette
réservation.

La vérification stricte de la clé hôte reste active. `HostKeyAlias` conserve le
nom sous lequel la clé de la K1 était déjà connue : le changement d'adresse ne
contourne donc pas le contrôle d'identité.

L'adresse privée exacte n'est pas publiée. Elle est conservée dans le fichier
SSH de l'utilisateur et dans `machine/local/network-endpoint.yml`, répertoire
ignoré par Git conformément à la politique du dépôt.

## Mainsail et K1 Control

Aucune correction distante n'était nécessaire :

- les scripts et lanceurs appellent seulement `k1max-root` ;
- le tunnel transporte `127.0.0.1:4409` vers `127.0.0.1:4409` ;
- Mainsail s'ouvre sur `http://127.0.0.1:4409/` ;
- K1 Control s'ouvre sur `http://localhost:4409/k1-control/` ;
- `navi.json` utilise le chemin relatif `/access-k1-control/` ;
- les configurations distantes Mainsail, Moonraker et nginx ne contiennent ni
  ancienne adresse, ni adresse réservée, ni nom `.lan`.

Le changement DHCP reste ainsi limité à la couche locale qui établit la
connexion SSH.

Depuis `G4-K1-CONTROL-GATEWAY-PRIVATE-LAN-NO-AUTH-V1`, le tunnel reste
disponible mais n'est plus obligatoire sur le LAN privé. Le port `4409` répond
sans HTTP Basic, après filtrage des sources privées par nginx. Moonraker reste
sur `127.0.0.1:7125` et voit uniquement le proxy local approuvé.

## Preuves du 26 août

- résolution SSH effective : endpoint réservé, port 22, utilisateur root ;
- identité de clé conservée et contrôle strict actif ;
- connexion réelle : `K1_FIXED_ENDPOINT_OK` ;
- tunnel Mainsail neuf : HTTP `401` attendu au 26 août, avant retrait de HTTP
  Basic ;
- vue Calibration sur le tunnel existant : HTTP `401` attendu au 26 août,
  avant retrait de HTTP Basic ;
- audit distant des trois configurations réseau : aucune référence trouvée ;
- aucune chauffe, mouvement, extrusion, commande CFS, écriture distante ou
  restart.

## Règle durable

Ne jamais introduire une adresse RFC 1918 précise dans un script ou un document publié.
Si l'adresse réservée change, modifier uniquement l'endpoint de `k1max-root`,
préserver l'identité de clé, puis rejouer les deux préflights de tunnel.
