# Tests

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

## Contrôles disponibles

Le paquet `G4-ZSAFE-START-V1` possède une simulation et des contrôles statiques :

```powershell
python -m unittest tests.test_g4_zsafe_offline -v
```

Ils vérifient notamment l'ordre référence finale -> mesh -> correction -> garde,
l'absence des chemins stock dangereux dans le nouveau départ, les gardes avant
CFS/purge, la capture de fin et le chemin de validation haute sans extrusion.
