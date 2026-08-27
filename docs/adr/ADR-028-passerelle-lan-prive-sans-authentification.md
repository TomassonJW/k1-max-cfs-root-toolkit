# ADR-028 — Passerelle du LAN privé sans authentification HTTP

## Contexte

La passerelle experte de la K1 Max utilise HTTP Basic sur le port `4409`.
Après redémarrage, cette frontière a de nouveau bloqué Mainsail alors que nginx,
Moonraker et Klipper étaient sains. Une navigation Chrome neuve a retourné
`ERR_INVALID_AUTH_CREDENTIALS`. Le compte persistant était toujours présent et
la configuration installée correspondait exactement au dépôt.

Cette authentification a créé des délais, des états de cache difficiles à
comprendre et plusieurs blocages d'accès sur un réseau local privé administré
par Thomas.

## Options

1. Conserver HTTP Basic et réinitialiser le mot de passe.
2. Remplacer HTTP Basic par un autre système de comptes.
3. Retirer l'authentification applicative tout en conservant les limites réseau.

## Décision

L'option 3 est retenue à la demande explicite de Thomas.

Moonraker reste lié à `127.0.0.1:7125`. La seule entrée LAN reste nginx sur
`4409`, limitée par `allow` aux adresses privées IPv4 et à la boucle locale.
Nginx présente ses requêtes à Moonraker comme venant de `127.0.0.1`, seule
adresse déjà approuvée par Moonraker. L'adresse cliente n'est donc pas utilisée
comme une seconde barrière d'authentification.
Le fichier de compte existant reste inutilisé afin de permettre un retour
arrière immédiat.

## Conséquences

- aucun mot de passe n'est demandé sur le LAN privé ;
- tout appareil déjà présent sur ce LAN peut ouvrir Mainsail et appeler les API
  exposées par la passerelle ;
- cette configuration ne doit jamais être exposée par une redirection de port,
  une DMZ, un Wi-Fi invité non maîtrisé ou un tunnel public ;
- une utilisation depuis un réseau non fiable doit passer par un accès réseau
  privé maîtrisé ;
- le retour arrière restaure la configuration sauvegardée avec HTTP Basic.

## Alternatives refusées

La réinitialisation du mot de passe est refusée parce qu'elle conserve la cause
des blocages répétés. Un nouveau système de comptes est refusé car il ajouterait
une autre dépendance et une autre source de panne pour un besoin strictement
local.
