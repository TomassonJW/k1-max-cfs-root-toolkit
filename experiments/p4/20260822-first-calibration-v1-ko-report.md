# FIRST-CALIBRATION-V1 — rapport KO

Date : 2026-08-22

Capture privée : `20260822-140602-g4-k1-control-first-calibration-v1`

Autorité : GO exact reçu sur le commit figé `7fab3b8`.

## Résultat

Le préflight réel a confirmé la K1 S12 structure `0`, le firmware `2.3.5.34`,
la base persistante exacte, le runtime vide, le chemin Z fermé, les chauffes à
zéro, les axes non référencés, deux CFS `1.1.3` et le profil cible absent.

`Prepare` a créé et vérifié le backup avant chauffe, stabilisé le plateau à
`55 °C` et la buse à `140 °C` pendant `200 s`, puis terminé le nettoyage et le
homing. Le premier mesh `6 × 6` a été capturé. Le second a été capturé une seule
fois puis comparé localement au premier.

| Mesure | Résultat |
|---|---:|
| points comparés | `36` |
| écart moyen | `0,018049 mm` |
| écart maximal | `0,062125 mm` |
| seuil | `0,025 mm` |
| qualification | `KO` |

## Arrêt et état final

Le pilote a coupé les chauffes et s'est arrêté immédiatement. Il n'a lancé ni
troisième mesh, ni `CommitMesh`, ni `BeginZ`, ni mouvement bas, ni acceptation
Z. Aucun profil `k1_p001_t055_r001_n06x06` n'a été écrit dans `printer.cfg` et
aucun fichier d'état Z n'a été créé.

Un contrôle final en lecture seule a confirmé, dans cet ordre, les empreintes
installées, l'empreinte initiale de `printer.cfg`, l'absence du profil cible et
du stockage Z, le socket Klipper, `standby` et les deux cibles de chauffe à
zéro. Il s'est ensuite arrêté sur les axes `xyz` encore référencés, conséquence
attendue des mesures. Le backup exact reste sur la K1 comme preuve privée.

## Conclusion bornée

La gate est KO et son GO est consommé. Les chiffres prouvent une répétabilité
insuffisante pour ce contrat, mais ne permettent pas encore d'attribuer la cause
aux `200 s`, à la mécanique ou au palpage. Aucune nouvelle action imprimante ne
doit être lancée avant analyse hors imprimante, protocole révisé et nouvelle
autorisation explicite.
