# CFS Stock Unload Guard V1

Ce paquet construit hors imprimante une protection autour du retrait officiel
Creality `BOX_QUIT_MATERIAL`.

Il ne contient aucun accès réseau, SSH, série ou Moonraker réel. Le contrôleur
reçoit une API injectée ; cette mission fournit uniquement une fausse API
déterministe pour tester les réussites, les refus et les pannes.

## Ce que le garde fait

Avant tout effet, il vérifie que la K1 est au repos, que les deux CFS sont
présents, qu'aucune commande CFS n'est active et qu'une seule route correspond
à celle demandée.

Après ce contrôle, il peut demander une seule fois le retrait stock. Une réponse
HTTP positive ne suffit jamais : le garde attend le retour sans erreur de la
requête, la libération réelle de la route et l'absence de commande CFS active.
Le préflight live a prouvé que la K1 n'expose aucun champ direct
`stock_unload_state` ; le garde n'en invente donc plus un.

Dès que le retrait a été tenté, il demande une seule fois
`TURN_OFF_HEATERS`, même après une panne. Il ne conclut que lorsque les deux
consignes sont réellement revenues à zéro.

Un refus avant le premier effet n'envoie aucune commande, notamment pour ne pas
couper les chauffes d'une impression déjà en cours.

## Lancer les scénarios

```powershell
python packages\k1-control-v1\cfs-stock-unload-guard-v1\run_scenarios.py
```

Résultat attendu : `CFS_STOCK_UNLOAD_GUARD_V1_OK 9/9`.

## Limites

- aucun transport réel n'est fourni ;
- aucun mapping live Moonraker n'est encore qualifié ;
- aucun retrait réel supplémentaire n'est autorisé ;
- le segment situé après le cutter peut rester dans la tête ;
- une future connexion en lecture seule demande un GO exact distinct.
