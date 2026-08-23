# G4-K1-CONTROL-CALIBRATION-UI-RETRY-SAFETY-V1

Correction statique bornée de l'interface de calibration.

Après une tentative interrompue avant le sixième mesh, la reprise réinitialise
une seule fois les deux confirmations dangereuses :

- `replace_existing=false` ;
- `plate_clear=false`.

Le choix de matrice, l'interpolation, les températures, la stabilisation et le
seed Z restent visibles. L'opérateur doit donc reconfirmer le plateau libre et
peut encore réactiver explicitement un remplacement volontaire.

La pose ne remplace que `app.js`, après backup et empreinte. Elle ne nécessite
aucun restart et ne lance aucune chauffe, référence, mesure, extrusion, commande
CFS, impression ou écriture Z.
