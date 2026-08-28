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

La gate de capture réelle contrôle le retrait officiel `T1A`, la chauffe laissée
active, l'arrêt final des chauffes, l'état du segment restant dans la tête et la
fermeture persistante du protocole série :

```powershell
python -m unittest tests.test_cfs_minimal_owner_passive_capture_v1 -v
```

Le garde hors imprimante du retrait officiel contrôle les refus avant effet,
la tentative unique, la preuve de libération de route, les faux succès HTTP,
l'absence de retry et l'arrêt thermique vérifié :

```powershell
python -m unittest tests.test_cfs_stock_unload_guard_v1 -v
python packages\k1-control-v1\cfs-stock-unload-guard-v1\run_scenarios.py
```

Le préflight live contrôle les empreintes privées, les deux lectures stables,
la correspondance des champs K1, l'absence de G-code et la correction du faux
champ de fin de retrait :

```powershell
python -m unittest tests.test_cfs_stock_unload_guard_live_preflight_v1 -v
python packages\k1-control-v1\cfs-stock-unload-guard-live-preflight-v1\verify_private_capture.py
```

L'adaptateur hors imprimante contrôle la traduction des huit champs du garde,
les routes absente, unique ou ambiguë, le second CFS déconnecté, les données
incomplètes, les températures invalides et l'absence de transport :

```powershell
python -m unittest tests.test_cfs_stock_unload_guard_adapter_offline_v1 -v
python packages\k1-control-v1\cfs-stock-unload-guard-adapter-offline-v1\run_scenarios.py
```

Le transport simulé contrôle les délais, coupures, faux succès et envois
uniques du retrait et de l'arrêt thermique, sans connecteur réel :

```powershell
python -m unittest tests.test_cfs_stock_unload_guard_transport_offline_v1 -v
python packages\k1-control-v1\cfs-stock-unload-guard-transport-offline-v1\run_scenarios.py
```

Le cycle complet hors imprimante contrôle les 27 cas canoniques, le moteur pur,
la composition avec le garde et le plan futur inerte :

```powershell
python -m unittest tests.test_job_lifecycle_offline_v1 -v
python packages\k1-control-v1\job-lifecycle-offline-v1\run_scenarios.py
python packages\k1-control-v1\job-lifecycle-offline-v1\verify_blueprint.py
```

La qualification K1 du Goal 2 vérifie la capture nettoyée, les délais, les
empreintes, l'invalidation du mapping et le KO borné du mesh actif :

```powershell
python -m unittest tests.test_k1_read_only_qualification_v1 -v
python packages\k1-control-v1\k1-read-only-qualification-v1\analyze_capture.py
```

Le garde d'exclusion du propriétaire stock vérifie les doubles lectures, la
tentative unique et la restauration exacte sans transport :

```powershell
python -m unittest tests.test_cfs_owner_exclusion_guard_offline_v1 -v
python -m unittest tests.test_cfs_owner_exclusion_guard_live_read_only_v1 -v
python packages\k1-control-v1\cfs-owner-exclusion-guard-offline-v1\run_scenarios.py
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
