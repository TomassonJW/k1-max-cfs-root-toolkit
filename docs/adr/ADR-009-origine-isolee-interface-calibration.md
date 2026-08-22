# ADR-009 — Isoler l'origine navigateur de l'interface de calibration

Date : 2026-08-22

Statut : accepté après observation réelle

## Contexte

Les fichiers de `CALIBRATION-UI-V1` ont été posés sous
`/usr/data/k1-control-v1/current/www/mainsail/k1-control/` et son API Moonraker
est verte. Pourtant, deux navigateurs ont affiché la coque Mainsail en ouvrant
`http://127.0.0.1:4409/k1-control/`. Le script chargé était l'asset principal
de Mainsail et non `k1-control/app.js`.

La cause est la portée d'origine du service worker Mainsail : une navigation
sous la même origine `127.0.0.1:4409` peut être interceptée avant nginx, même si
le fichier statique demandé existe.

## Options

1. Supprimer le service worker ou les données du navigateur. Refusé : action
   locale destructive, non durable et à répéter pour chaque navigateur.
2. Ajouter un second port nginx. Refusé : nouvelle écoute, nouvelle surface
   réseau et mutation imprimante inutile.
3. Réutiliser le tunnel et le port `4409` avec une origine navigateur distincte.
   Retenu.

## Décision

Le lanceur de calibration ouvre
`http://localhost:4409/k1-control/`, tandis que Mainsail conserve
`http://127.0.0.1:4409/`. Les deux noms atteignent le même tunnel
`127.0.0.1:4409:127.0.0.1:4409`, le même nginx et la même authentification.
L'origine différente suffit à séparer les service workers.

Le contrôle de disponibilité continue d'interroger `127.0.0.1:4409` et exige
HTTP `401` avant l'ouverture. Aucun secret, port, service ou fichier de la K1
n'est ajouté par ce correctif poste.

## Conséquences

- un raccourci `Ouvrir-Calibration-K1-Max.cmd` devient l'entrée quotidienne ;
- le compte nginx existant peut être demandé une première fois pour l'origine
  `localhost` ;
- l'écran de calibration ne dépend plus du cache applicatif Mainsail ;
- une campagne réelle reste obligatoire avant de déclarer l'autonomie.
