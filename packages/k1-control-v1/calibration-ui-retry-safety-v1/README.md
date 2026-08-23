# G4-K1-CONTROL-CALIBRATION-UI-RETRY-SAFETY-V1

Correction statique bornée de l'interface de calibration.

Statut : installée et validée sous la capture
`20260823-164558-g4-k1-control-calibration-ui-retry-safety-v1`.

Après toute fin non acceptée du mesh quotidien unique (`cancelled`, `failed`,
`mesh_rejected` ou `rolled_back`), la reprise réinitialise une seule fois les
deux confirmations dangereuses :

- `replace_existing=false` ;
- `plate_clear=false`.

Le choix de matrice, l'interpolation, les températures, la stabilisation et le
seed Z restent visibles. L'opérateur doit donc reconfirmer le plateau libre et
peut encore réactiver explicitement un remplacement volontaire.

La règle ne compare plus `mesh_index` à `mesh_target_count` : dans le protocole
à un passage, un mesh rejeté peut déjà exposer `1 / 1` sans résultat accepté.

La pose ne remplace que `app.js`, après backup et empreinte. Elle ne nécessite
aucun restart et ne lance aucune chauffe, référence, mesure, extrusion, commande
CFS, impression ou écriture Z.
