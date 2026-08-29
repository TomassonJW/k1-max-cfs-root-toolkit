# MESH-EDGE-DIAGNOSTIC-OWNED-START-R2-V1

Ce successeur hors imprimante remplace uniquement le chemin de motif invalide
qui avait chauffé et bougé sans déposer de filament. Il conserve la géométrie,
la source immuable `11 × 11` et la correction locale historique, mais place
chaque motif derrière le propriétaire R2 réellement installé.

Chaque fichier commence donc par le départ possédé `KEEP_CORRECT` : route
logique `T1A` relue, référence propre, `11 × 11` armé et purge visible sur le
bord stock. Aucun `T0`, `START_PRINT`, `END_PRINT` ou outil physique supposé
n'est présent.

La fin ne recharge plus l'ancien `6 × 6`. Elle désarme le propriétaire, remet
le meilleur profil actuel `11 × 11`, coupe les chauffes, monte à `Z50`, parque
à `X203 Y273`, attend la fin des commandes puis libère les moteurs, sans homing
de fin.

Le générateur est seulement local. Il ne contient aucun transport K1 et ne
constitue ni l'autorisation d'installer le profil dérivé, ni celle d'imprimer.
Le passage corrigé reste interdit tant que la source n'a pas donné un motif
physiquement exploitable.

Prévisualisation locale dans un nouveau dossier sous `.codex-work` :

```powershell
python.exe packages\k1-control-v1\mesh-edge-diagnostic-owned-start-r2-v1\build_owned_patterns.py .codex-work\mesh-edge-owned-r2-preview
```
