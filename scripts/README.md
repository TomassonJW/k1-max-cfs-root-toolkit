# Scripts

Planned script classes:

- local read-only acquisition helpers;
- redaction and secret scanning;
- manifest and checksum generation;
- configuration call-graph extraction;
- local validation and tests;
- later, gated deployment and rollback tooling.

The first gated deployment helper is `install-ssh-public-key.ps1`. It is limited
to the named `G4-SSH-KEY` change and requires all private target, key and evidence
paths as explicit runtime parameters.

`start-passive-production-trace.ps1` performs read-only observation around a
normal production job. It writes only to an ignored local session directory and
never sends printer-control or configuration commands.

`deploy-control-foundation.ps1` prépare la pose V3 en cinq actions séparées.
Par défaut, `Plan` ne contacte pas la machine. Toute action réelle exige à la
fois `-Execute` et `-Gate G4-K1-CONTROL-FOUNDATION-V3`. `InstallBootstrap`
répète le préflight, vérifie le bundle, sauvegarde l'état, installe seulement la
fondation locale et rollback automatiquement sur KO. `SetGatewayAccount` est
appelée par `set-control-foundation-account.ps1` : le mot de passe est saisi
deux fois en mode masqué et n'entre jamais dans la ligne de commande. Ces deux
scripts exigent PowerShell 7 ou plus récent.
`ActivateLan` exige ensuite `-AccountVerified`. `Validate` ne transmet aucune
commande G-code et `Rollback` ne touche que les nouveaux chemins de cette
fondation.

`deploy-control-foundation-paths-v1.ps1` est séparé du déployeur V3 initial. Il
ne sait modifier que les deux racines vides `state/config`, `state/gcodes` et le
`moonraker.conf` épinglé. Il sauvegarde et vérifie l'état, ne redémarre que le
Moonraker dédié, valide les permissions API sans écriture et rollbacke au premier
KO. Toute action distante exige `-Execute` et le gate exact
`G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1`.

`deploy-k1-control-calibration-path-v1.ps1` prépare cinq actions pour l'overlay
borné du premier Z. `Plan` reste purement local. Les quatre actions distantes
exigent `-Execute` et le gate exact
`G4-K1-CONTROL-CALIBRATION-PATH-V1`. Le préflight parse le candidat en mémoire
avec le Python/Jinja exact de la K1 ; la pose ajoute un fichier et un include,
fait uniquement un `RESTART` hôte, puis vérifie à vide que la garde refuse sans
changer position, origine ou chauffe. Le script n'appelle aucune macro de
chauffe, homing, mesh, mouvement, ajustement ou commit.

`Ouvrir-Mainsail-K1-Max.cmd`, à la racine du dépôt, se lance par double-clic.
Il appelle `launch-control-dashboard.ps1`, réutilise le tunnel local s'il répond
correctement ou en démarre un nouveau en arrière-plan, exige HTTP `401` avant
d'ouvrir Mainsail et ne contient aucune adresse privée ni aucun secret.

During P0/P1, scripts must default to no remote write and fail closed on ambiguity.

A future remote-mutating script must:

- require an explicit change ID;
- refuse to run without a verified backup;
- show the exact diff and target paths;
- support dry-run where meaningful;
- validate after deployment;
- provide a tested rollback path;
- never accept or print credentials through tracked configuration.
