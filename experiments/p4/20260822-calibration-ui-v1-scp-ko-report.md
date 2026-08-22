# CALIBRATION-UI-V1 — rapport du premier déploiement KO

Date : 2026-08-22

Gate : `G4-K1-CONTROL-CALIBRATION-UI-V1`

Capture locale privée : `20260822-192821-g4-k1-control-calibration-ui-v1`

## Résultat

Le préflight réel a obtenu `PREFLIGHT_CALIBRATION_UI_V1_OK`. Le déployeur a
ensuite créé et vérifié le backup exact de `moonraker.conf`, puis créé son
répertoire de staging. Le premier transfert s'est arrêté avant tout payload :

```text
scp.exe: Connection closed
sh: /usr/libexec/sftp-server: not found
Transfert SCP KO : .../moonraker.conf
```

Cause confirmée : l'OpenSSH Windows actuel utilise SFTP par défaut pour `scp`,
mais le Dropbear de cette K1 ne fournit pas le serveur SFTP attendu.

## Rollback et état final

Le rollback automatique a :

- restauré le `moonraker.conf` du backup exact ;
- retiré les deux composants, les deux caches et les trois fichiers UI s'ils
  existaient ;
- redémarré uniquement le Moonraker dédié ;
- confirmé la K1 en `standby`, chauffes demandées à zéro, runtime fermé et
  chemin Z `committed` non armé.

Le préflight final a de nouveau obtenu `PREFLIGHT_CALIBRATION_UI_V1_OK`. Le
répertoire de staging de cet essai existe encore mais il est vide. Aucun
chauffage, homing, mouvement, mesh, réglage Z, extrusion, impression ou action
CFS n'a été exécuté.

## Correction hors imprimante

La fonction de transfert force maintenant le protocole SCP historique avec
`scp -O`. Le rollback nettoie aussi les six noms de staging exacts puis retire
le répertoire vide. Les tests épinglent cette option et ce nettoyage. Le hash du
déployeur est renouvelé dans le manifeste.

Une preuve sans écriture distante a ensuite copié le `moonraker.conf` courant
de la K1 vers un dossier local ignoré avec `scp -O`. Le transfert a réussi et le
hash obtenu est exactement la base revue
`fef837a1acaa59af400ac63c244df78dec6e70a71e1707d61f242f56cb1c7fba`.
Le dossier temporaire local a été supprimé après ce contrôle.

Le paquet corrigé complet a enfin repassé
`PREFLIGHT_CALIBRATION_UI_V1_OK` sur la K1, sans écriture ni redémarrage.

Le GO de ce premier essai est consommé. La version corrigée doit être intégrée,
revue puis recevoir un nouveau GO exact avant une seconde pose.
