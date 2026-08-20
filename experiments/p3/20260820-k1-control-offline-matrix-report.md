# Rapport P3 — K1-CONTROL-V1 hors imprimante

Date : 2026-08-20

Résultat : **17/17 scénarios verts ; aucune connexion imprimante**

## Périmètre exécuté

- moteur Z, mesh et température en Python pur ;
- faux Moonraker limité à `127.0.0.1` ;
- interface `K1 Control` reliée à ce faux Moonraker ;
- contrat Orca départ/fin/changement d'outil ;
- simulation du démarrage sûr et des transitions des deux CFS ;
- simulation d'un rollback par inventaire SHA-256 ;
- préparation locale du bundle Moonraker/Mainsail épinglé.

Aucun SSH imprimante, fichier distant, service, port, profil Orca actif, chauffe,
mouvement, calibration, extrusion ou travail n'a été lancé.

## Matrice

| Scénario | Résultat observé |
|---|---|
| `z_live_adjust_then_commit` | valeur provisoire jusqu'à l'enregistrement explicite |
| `z_cancel_calibration` | valeur acceptée précédente conservée |
| `z_print_end_and_restart` | Z accepté conservé |
| `z_new_reference_calibration` | production bloquée, historique conservé |
| `mesh_reference_plate_temperature_match` | profil unique correspondant sélectionné |
| `mesh_reference_mismatch` | production bloquée |
| `mesh_adaptive_job` | limites Orca utilisées, mesh non persisté |
| `safe_start_sequence` | purge précoce refusée ; dangers après armement seulement |
| `cfs_initial_load` | cible T0 du travail conservée |
| `cfs_equivalent_refill` | écrasement 220 détecté, cible 205 restaurée |
| `cfs_intentional_tool_change` | cible T1 220 acceptée |
| `cfs_cross_unit_change` | T0 vers T5, cible 235 restaurée entre deux CFS |
| `pause_resume` | cible et Z acceptés conservés |
| `cancel_and_end` | chauffe arrêtée, calibration inchangée |
| `explicit_operator_temperature_change` | cible opérateur conservée jusqu'au prochain ordre G-code |
| `orca_contract_version_mismatch` | travail refusé avant toute séquence |
| `deployment_slice_rollback` | état initial restauré avec les mêmes SHA-256 |

Commande : `python -m prototype.scenario_matrix`.

La suite complète du dépôt passe également : `49/49` contrôles avec
`python -m unittest discover -s tests -v`. La syntaxe des deux futurs services
Buildroot passe `bash -n`.

## Interface

Contrôles bureau et mobile effectués sur le faux Moonraker :

- ouverture de session à `+0,310` ;
- clic `+0,005`, valeur provisoire `+0,315` ;
- enregistrement explicite, restauration précédente devenue disponible ;
- redémarrage simulé, valeur `+0,315` conservée ;
- nouvelle calibration de référence simulée, production bloquée tout en gardant
  la valeur en historique ;
- aucune erreur ni alerte JavaScript.

## Paquet de fondation

Le bundle local a été réellement préparé avec les trois archives épinglées :

- Moonraker MIPS : SHA-256
  `ca22e35a2773b3159b5023ace15e9abe305f1e5d01a01eef8fa1b6a3f9ce918a` ;
- nginx MIPS : SHA-256
  `586d69ee2b61bf0a6b65e77bcd91bbee28e2b457019a7bcac65898f6f8d7f9f1` ;
- Mainsail `v2.18.2` : SHA-256
  `df2ba7c301f7bfc8ac9f122741a6ba08356d679ecfa1f62f898d0337802d5de5`.

Le résultat temporaire reste hors Git et sera supprimé après la revue. La gate
`G4-K1-CONTROL-FOUNDATION-V1` est préparée mais non autorisée.
