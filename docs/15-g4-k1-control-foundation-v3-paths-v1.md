# 15 — G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1

Date : 2026-08-21

Statut : **GO renouvelé ; installé et validé le 2026-08-21**

## But exact

Corriger uniquement les deux avertissements de chemins du Moonraker V3 sans
déplacer les chemins actifs de Creality et sans changer le comportement
d'impression.

État avant attendu :

- `/usr/data/k1-control-v1/state/config` est un dossier réel vide ;
- `/usr/data/k1-control-v1/state/gcodes` est un dossier réel vide ;
- `/usr/data/printer_data/config` contient la configuration Creality active ;
- `/usr/data/printer_data/gcodes` reste le répertoire G-code actif ;
- le `moonraker.conf` installé a le SHA-256
  `7e9cc023da9addc62f492f6cddf6ab901dbc9e97821e8306b05cfbd1b6e576f7`.

État après attendu :

- `state/config` est un lien vers `/usr/data/printer_data/config` ;
- `state/gcodes` est un lien vers `/usr/data/printer_data/gcodes` ;
- `enable_config_write_access: False` expose `config` en lecture seule ;
- `gcodes` reste exposé en lecture/écriture par le gestionnaire de fichiers ;
- seuls le service Moonraker dédié et son PID changent ;
- les deux avertissements de chemins disparaissent.

## Écriture restante sur les G-codes

Le Moonraker épinglé enregistre toujours la racine `gcodes` avec accès complet.
Un utilisateur authentifié dans Mainsail peut donc encore téléverser, renommer
ou supprimer un G-code et demander le démarrage d'une impression. PATHS-V1 ne
prétend pas supprimer ce pouvoir : il le rend explicite et conserve la barrière
nginx existante.

La validation automatisée n'appelle aucun point d'API d'écriture. Elle lit
`/server/files/roots` et exige exactement :

- `config.permissions = r` ;
- `gcodes.permissions = rw`.

Pendant la validation et l'observation, ne pas utiliser les actions de fichier,
la console, les macros, les mouvements, les chauffes ou le démarrage
d'impression de Mainsail. Une impression d'observation éventuelle reste choisie
et démarrée manuellement par Thomas avec le flux Creality/Orca déjà approuvé.

## Préflight obligatoire

Le script refuse la pose si un seul point diffère :

- architecture, carte, structure ou firmware ;
- imprimante hors `standby`, fichier actif, chauffe demandée ou axes homés ;
- l'un des deux CFS absent, différent de `1.1.3` ou incomplet ;
- service, PID, port ou processus Creality/V3 absent ;
- racine Creality absente ou remplacée par un lien ;
- racine Moonraker déjà liée, non vide ou d'un autre type ;
- empreinte du `moonraker.conf` V3 initial différente.

## Backup et mutation

Le déployeur crée un dossier propre à la capture sous
`/usr/data/k1-control-v1/backups/<capture>/paths-v1` et y place :

- une copie du `moonraker.conf` avant changement ;
- une archive `tar` préservant les deux dossiers vides et leurs métadonnées ;
- leurs empreintes enregistrées dans les preuves locales ignorées par Git.

Après vérification des backups, il arrête uniquement
`S56k1_control_moonraker`, retire les deux dossiers avec `rmdir`, crée les deux
liens, remplace atomiquement `moonraker.conf`, puis redémarre seulement ce
service. Il n'appelle jamais nginx, Klipper, Creality, le CFS ou une API G-code
en écriture.

## Validation sans G-code

La pose est verte seulement si :

1. les deux liens ont leurs cibles exactes ;
2. le fichier installé a l'empreinte revue ;
3. Moonraker revient uniquement sur `127.0.0.1:7125` ;
4. nginx reste sur `0.0.0.0:4409`, garde le même PID et répond `401` sans compte ;
5. les ports Creality `80`, `8080` et `9999` restent présents ;
6. `config` est déclaré `r` et `gcodes` `rw` par l'API en lecture seule ;
7. les deux avertissements ciblés sont absents de `/server/info` ;
8. Klipper reste `standby`, chauffes à zéro, axes non homés ;
9. les deux CFS `1.1.3` et les processus Creality restent présents ;
10. au moins 64 Mio de RAM restent disponibles.

## Rollback

Au premier KO après le début d'une mutation, le déployeur :

1. arrête uniquement le Moonraker dédié ;
2. refuse d'enlever un lien dont la cible ne correspond pas au candidat ;
3. retire les deux liens attendus ;
4. restaure les dossiers d'origine depuis l'archive ;
5. restaure atomiquement le `moonraker.conf` d'origine après contrôle SHA-256 ;
6. redémarre Moonraker ;
7. exige le retour des deux dossiers réels vides, du hash initial et de toute la
   pile de sécurité.

Les backups et preuves restent conservés. Aucun redémarrage de l'imprimante
n'est permis.

## Commandes opérateur prévues

Plan local, sans connexion :

```powershell
pwsh -File .\scripts\deploy-control-foundation-paths-v1.ps1 -Action Plan
```

Les actions distantes exigent toutes `-Execute` et le gate exact. Leur exécution
reste interdite tant qu'un GO renouvelé n'a pas été donné après la revue de ce
paquet :

```powershell
pwsh -File .\scripts\deploy-control-foundation-paths-v1.ps1 `
  -Action Deploy `
  -Gate G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1 `
  -CaptureId <YYYYMMDD-HHMMSS-g4-control-foundation-v3-paths-v1> `
  -EvidenceDirectory <dossier-local-ignore> `
  -Execute
```

Rollback explicite :

```powershell
pwsh -File .\scripts\deploy-control-foundation-paths-v1.ps1 `
  -Action Rollback `
  -Gate G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1 `
  -CaptureId <capture-deployee> `
  -EvidenceDirectory <dossier-local-ignore> `
  -Execute
```

## Pourquoi le premier GO n'est pas consommé

Le texte exact a été reçu alors que le dépôt réel ne contenait encore aucun
fichier, aucune commande, aucun test, aucun backup ni rollback PATHS-V1. Les
conditions G4 exigeaient ces éléments avant l'autorisation. La préparation
locale a donc été réalisée sans mutation distante. Thomas a ensuite renouvelé le
texte exact après revue, ce qui a autorisé la capture réelle
`20260821-111001-g4-control-foundation-v3-paths-v1`.

## Résultat réel

Le déploiement a vérifié les backups suivants avant l'arrêt de Moonraker :

- `moonraker.conf.before` :
  `7e9cc023da9addc62f492f6cddf6ab901dbc9e97821e8306b05cfbd1b6e576f7` ;
- `empty-roots.before.tar` :
  `7bd189adecdd54f40013a9ee1b247825fd75c76e9fc48b5195757f12f40a4e83`.

L'état final vérifié est :

- `state/config -> /usr/data/printer_data/config` ;
- `state/gcodes -> /usr/data/printer_data/gcodes` ;
- `moonraker.conf` :
  `fef837a1acaa59af400ac63c244df78dec6e70a71e1707d61f242f56cb1c7fba` ;
- API Moonraker : `config=r`, `gcodes=rw`, `warnings=[]` ;
- Klipper prêt et `standby`, chauffes à zéro, axes non homés ;
- deux CFS `1.1.3` connectés avec quatre emplacements chacun ;
- environ 108 Mio de RAM disponibles et 40 Kio de swap utilisés.

Le wrapper local a perdu son dernier message après deux heartbeats. La mutation
n'a pas été relancée : ses preuves finales étaient complètes, puis une validation
distante séparée en lecture seule a obtenu `VALIDATE_PATHS_V1_OK`. Aucun rollback
n'a été nécessaire.
