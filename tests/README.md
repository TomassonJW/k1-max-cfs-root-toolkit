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

Le contrat actif `K1-CONTROL-V1` possède des contrôles statiques :

```powershell
python -m unittest tests.test_production_control_contract -v
```

Ils vérifient l'absence de Z fixe, la sauvegarde explicite, la persistance et
l'invalidation, les meshes plaque/température, les gardes avant CFS/purge, la
propriété dynamique des températures et le contrat Orca atomique.

Le moteur d'état et l'interface locale ont leurs contrôles dédiés :

```powershell
python -m unittest tests.test_k1_control_prototype -v
```

Le candidat de première calibration, ses paramètres figés, l'absence de rerun
automatique, la distinction annulation/rollback et le comparateur `6 × 6` se
contrôlent ainsi :

```powershell
python -m unittest tests.test_k1_control_first_calibration -v
```

Le premier paquet de fondation, le contrat Orca et la matrice complète se
contrôlent ainsi :

```powershell
python -m unittest tests.test_control_foundation_package -v
python -m unittest tests.test_control_foundation_paths_deployer -v
python -m unittest tests.test_orca_control_contract -v
python -m prototype.scenario_matrix
```

La gate de preuves du propriétaire minimal CFS contrôle la nouvelle séquence de
retrait, le non-double-comptage des journaux, le CRC de réponse et la fermeture
de toute surface appelable :

```powershell
python -m unittest tests.test_cfs_minimal_owner_evidence_v1 -v
```

La suite complète doit être lancée avec un dossier de découverte explicite :

```powershell
python -m unittest discover -s tests -v
```

L'ancien paquet rejeté `G4-ZSAFE-START-V1` conserve ses tests historiques et un
contrôle qui prouve qu'il échoue volontairement s'il est chargé :

```powershell
python -m unittest tests.test_g4_zsafe_offline -v
```

Ces tests ne rendent pas ce paquet déployable.
