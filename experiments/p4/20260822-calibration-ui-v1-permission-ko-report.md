# CALIBRATION-UI-V1 — rapport du second déploiement KO

Date : 2026-08-22

Gate : `G4-K1-CONTROL-CALIBRATION-UI-V1`

Capture locale privée : `20260822-202014-g4-k1-control-calibration-ui-v1`

## Pose technique

Le préflight frais a obtenu `PREFLIGHT_CALIBRATION_UI_V1_OK`. Le transfert
historique corrigé a réussi. Le script a ensuite obtenu :

```text
VALIDATE_CALIBRATION_UI_V1_OK
DEPLOY_CALIBRATION_UI_V1_OK capture=20260822-202014-g4-k1-control-calibration-ui-v1
```

Une validation indépendante a aussi obtenu
`VALIDATE_CALIBRATION_UI_V1_OK`. L'API métier répondait en phase `idle`, sans
campagne ni backup actif. La machine restait en `standby`, cibles à zéro, mesh
robuste actif, Z accepté `−0,04 mm`, stockage `ok`, session fermée et deux CFS
connectés.

## Validation navigateur KO

La première URL testée sur le port stock `80` a logiquement répondu `404` ; la
passerelle du projet écoute sur `4409`. L'accès anonyme au vrai port a répondu
`401`, comme prévu.

Après authentification, deux défauts distincts ont été prouvés :

1. sur `127.0.0.1:4409`, le service worker de Mainsail intercepte
   `/k1-control/` et affiche la coque Mainsail ;
2. sur l'origine isolée `localhost:4409`, nginx répond `403` parce que le dossier
   posé `k1-control` est en mode `0700`.

Le syslog exact confirme :

```text
.../www/mainsail/k1-control/index.html is forbidden (13: Permission denied)
```

Le fichier `index.html` est en `0644`, mais son dossier parent créé par
`mkdir -p` est en `0700`. Le validateur vérifiait le fichier et son hash, pas le
mode du dossier ni le rendu navigateur.

## Rollback

La capture a ensuite obtenu :

```text
ROLLBACK_CALIBRATION_UI_V1_OK capture=20260822-202014-g4-k1-control-calibration-ui-v1
PREFLIGHT_CALIBRATION_UI_V1_OK
```

La base Moonraker exacte et l'état sûr de la K1 sont restaurés. Aucun chauffage,
homing, mouvement, mesh, réglage Z, extrusion, impression ou action CFS n'a été
exécuté.

## Corrections hors imprimante

- le déployeur applique explicitement `chmod 0755` au dossier UI ;
- `Validate` exige maintenant le mode exact `755` via le `stat` BusyBox prouvé ;
- le lanceur quotidien ouvre la calibration sur
  `http://localhost:4409/k1-control/`, origine séparée du service worker
  Mainsail, sans nouveau port ni service ;
- `Ouvrir-Calibration-K1-Max.cmd` fournit cette entrée dédiée ;
- ADR-009 documente le choix d'origine.

Le GO est consommé. Le paquet et son déployeur ayant changé, une nouvelle pose
exige un nouveau GO exact après intégration du correctif.
