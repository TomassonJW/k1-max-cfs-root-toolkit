# Tests

## Contrat de température CFS

`Test-CfsTemperatureContract.ps1` vérifie localement :

- les empreintes des trois fichiers actifs copiés en lecture seule ;
- l'application exacte du patch sans approximation ;
- le remplacement unique de `220` par `195 °C` ;
- l'ordre des protections au démarrage, à la pause, à la reprise et à la fin ;
- la présence du refus explicite des profils autres que Geeetech PLA `190/195`.

Les fichiers de test proviennent du dossier brut ignoré. Le test ne contacte pas
l'imprimante et supprime son dossier temporaire local après exécution.

The test suite will grow with the project.

Initial priorities:

- secret/redaction fixtures;
- manifest schema validation;
- detection of remote-write command patterns;
- G-code tool-command post-processing fixtures;
- macro call-graph parsing;
- configuration patch idempotence;
- deployment dry-run and rollback checks;
- recorded Z and temperature timeline analysis.

Fixtures must be synthetic or fully redacted. Do not use raw printer backups as test data in Git.
