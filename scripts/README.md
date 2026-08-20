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

`deploy-control-foundation.ps1` prépare la pose V2 en quatre actions séparées.
Par défaut, `Plan` ne contacte pas la machine. Toute action réelle exige à la
fois `-Execute` et `-Gate G4-K1-CONTROL-FOUNDATION-V2`. `InstallBootstrap`
répète le préflight, vérifie le bundle, sauvegarde l'état, installe seulement la
fondation locale et rollback automatiquement sur KO. `ActivateLan` exige en
plus `-AccountVerified`. `Validate` ne transmet aucune commande G-code et
`Rollback` ne touche que les nouveaux chemins de cette fondation.

During P0/P1, scripts must default to no remote write and fail closed on ambiguity.

A future remote-mutating script must:

- require an explicit change ID;
- refuse to run without a verified backup;
- show the exact diff and target paths;
- support dry-run where meaningful;
- validate after deployment;
- provide a tested rollback path;
- never accept or print credentials through tracked configuration.
