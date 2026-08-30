# CALIBRATION-BEFORE-INSERTION-V1

Ce paquet fige la règle issue du constat physique de Thomas : une insertion de
filament laisse un résidu sous la buse et peut fausser une palpation suivante.

Il sépare donc deux chemins :

- géométrie déjà valide : relire mesh et Z, ne pas palper, conserver le bon
  filament si sa route est cohérente ;
- nouvelle géométrie : aucun filament engagé, nettoyage manuel, toutes les
  palpations, chargement et relecture de la géométrie, puis seulement insertion
  et purge.

Le paquet ne contient ni G-code exécutable, ni connecteur K1, ni déployeur. Il
ferme R3 et conserve son fichier seulement comme preuve de l'ordre rejeté.

Le préflight réel du 30 août est resté en lecture seule. Il a confirmé la K1 au
repos et `T1A`, puis a fermé la suite parce que le mesh actif est `default` en
`6 × 6`, pas `k1_p001_t055_r001_n11x11`.

Validation locale :

```powershell
python.exe packages\k1-control-v1\calibration-before-insertion-v1\verify_contract.py
```
