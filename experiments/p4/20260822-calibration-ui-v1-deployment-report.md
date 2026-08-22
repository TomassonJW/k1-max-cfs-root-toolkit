# Déploiement CALIBRATION-UI-V1

Date : 2026-08-22

Capture privée ignorée :
`20260822-211633-g4-k1-control-calibration-ui-v1`.

## Résultat confirmé côté machine

Le GO exact `G4-K1-CONTROL-CALIBRATION-UI-V1` a été consommé pour cette pose.
Le préflight frais a obtenu `PREFLIGHT_CALIBRATION_UI_V1_OK`. Le déployeur a
créé le backup exact, transféré les deux composants Python et les trois fichiers
statiques, ajouté l'unique section Moonraker revue, puis redémarré seulement le
Moonraker dédié. Il a obtenu successivement :

- `VALIDATE_CALIBRATION_UI_V1_OK` ;
- `DEPLOY_CALIBRATION_UI_V1_OK` ;
- un second `VALIDATE_CALIBRATION_UI_V1_OK` indépendant.

Le dossier statique distant est en mode `0755`. L'API métier répond en phase
`idle`, sans campagne active, avec le Z accepté valide à `−0,04 mm`. La K1 est
restée `standby`, les cibles buse et plateau sont à zéro, la session Z est
fermée et les mouvements bas sont désarmés.

Aucune chauffe, référence des axes, mesure de mesh, extrusion, commande CFS,
impression ou écriture Z n'a été lancée par cette gate.

## Contrôle navigateur

L'origine isolée `http://localhost:4409/k1-control/` demande sa propre
authentification HTTP. Le premier accès automatisé a été refusé avec des
identifiants navigateur invalides ; aucune donnée d'authentification n'a été
lue ou saisie par Codex. Le lanceur officiel a ouvert la page dans le navigateur
système pour authentification humaine. Thomas s'est authentifié lui-même.

Le vrai rendu Chrome affiche `Interface réelle`, `API connectée`, la plaque
`PEI_TEXTURED_A`, `55/140 °C`, `200 s`, `6 × 6` Lagrange et le seed
`−0,04 mm`. Les confirmations physiques sont décochées, la progression est
`0 / 6`, le Z est verrouillé et aucune action n'est en cours. Après rechargement
complet, les mêmes paramètres et le seed sont revenus depuis l'état serveur ;
les confirmations physiques sont restées volontairement décochées.

`CALIBRATION-UI-V1` est donc close et validée. La campagne physique séparée
`G4-K1-CONTROL-CALIBRATION-UI-CAMPAIGN-V1` n'est pas autorisée par ce GO.
