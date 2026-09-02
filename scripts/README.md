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

`run-k1-control-first-calibration-v1.ps1` est le pilote découpé de la première
calibration. `Plan` reste purement local. Le futur GO exact ouvre seulement la
liste figée d'actions : préflight, backup et préparation thermique, deux meshes
séparés, qualification locale sans rerun automatique, commit mesh, chemin Z par
palier, acceptation/annulation, validation et rollback. Chaque action exige la
capture privée et les checkpoints précédents ; aucun nouveau fichier n'est
installé sur la K1.

`run-k1-control-first-calibration-v2.ps1` conserve les checkpoints, le backup
et le rollback de V1, mais mesure exactement six meshes. Il compare deux
médianes indépendantes de trois avec trois limites, sans septième mesure, puis
charge et relit la médiane des six avant toute persistance. Toute action physique
exige la gate exacte `G4-K1-CONTROL-FIRST-CALIBRATION-V2`.

`deploy-k1-control-calibration-ui-v1.ps1` prépare la pose séparée de l'interface
réelle. `Plan` est local. `Preflight` et `Validate` sont en lecture seule ;
`Deploy` et `Rollback` exigent `-Execute` et
`G4-K1-CONTROL-CALIBRATION-UI-V1`. Le script sauvegarde `moonraker.conf`, pose
deux composants et trois fichiers statiques, redémarre seulement Moonraker et
rollbacke automatiquement sur KO. Il n'envoie aucun G-code de calibration.

`Ouvrir-Mainsail-K1-Max.cmd`, à la racine du dépôt, se lance par double-clic.
Il appelle `launch-control-dashboard.ps1`, réutilise le tunnel local s'il répond
correctement ou en démarre un nouveau en arrière-plan, exige HTTP `401` avant
d'ouvrir Mainsail et ne contient aucune adresse privée ni aucun secret. Tous les
lanceurs et scripts utilisent l'alias `k1max-root` ; son endpoint réel appartient
à la configuration SSH locale et non au dépôt public.

`Ouvrir-Calibration-K1-Max.cmd` réutilise exactement le même tunnel et la même
authentification, mais ouvre `http://localhost:4409/k1-control/`. Cette origine
distincte empêche le service worker de Mainsail, enregistré sur
`127.0.0.1:4409`, d'intercepter l'écran de calibration. Aucun nouveau port ni
service n'est créé.

`Ouvrir-Editeur-Maillage-K1-Max.cmd` ouvre l'éditeur de maillage point par
point sur `http://127.0.0.1:7130/`, par un tunnel dédié vers le même alias
`k1max-root`. Le lanceur réutilise le tunnel existant plutôt que d'en empiler un
— Windows laisse deux `ssh` écouter le même port local sans erreur — et, si le
port répond mais que la page ne vient pas, relance à distance le serveur de
l'éditeur, qui ne survit pas à un redémarrage de l'imprimante. Aucune adresse
privée ni secret dans le script.

`deploy-k1-control-mesh-editor-v1.ps1` pose l'éditeur de maillage et le service
qui le rallume au démarrage de l'imprimante, `/etc/init.d/S58k1_control_mesh_editor`.
`Status` lit sans rien écrire, `Deploy` copie les quatre fichiers du paquet,
installe le service, redémarre et vérifie que l'API répond, `Rollback` retire le
service en laissant le paquet en place. La syntaxe de `app.mjs` est vérifiée
avant la pose : un module cassé laisse le serveur répondre `200` sur une page
qui ne démarre jamais.

`validate-k1-control-calibration-ui-campaign-v1.ps1` prépare puis contrôle en
lecture seule la campagne d'autonomie opérée depuis l'écran. `Preflight` exige
l'UI exacte et l'état sûr avant chauffe ; `Validate` exige la phase `accepted`,
exactement six meshes, les paramètres revus et les gardes finales fermées. Le
script n'expose aucune action de calibration et conserve ses preuves dans la
capture privée ignorée.

During P0/P1, scripts must default to no remote write and fail closed on ambiguity.

A future remote-mutating script must:

- require an explicit change ID;
- refuse to run without a verified backup;
- show the exact diff and target paths;
- support dry-run where meaningful;
- validate after deployment;
- provide a tested rollback path;
- never accept or print credentials through tracked configuration.
