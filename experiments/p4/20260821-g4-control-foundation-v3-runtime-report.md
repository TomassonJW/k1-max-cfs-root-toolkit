# G4-K1-CONTROL-FOUNDATION-V3 — première exécution réelle

Date : 2026-08-21
Capture privée : `20260821-010616-g4-control-foundation-v3`

Résultat : **rollback complet ; aucune fondation active**

## Autorité et périmètre

Thomas a fourni le texte exact `GO G4-K1-CONTROL-FOUNDATION-V3`. La tentative
est restée limitée à Moonraker, nginx et Mainsail en observation. Aucun G-code,
mouvement, chauffe, calibration, extrusion, impression, redémarrage ou
changement Orca/Z/mesh/CFS/macro n'a été demandé.

## Étapes réelles

- reconstruction locale du bundle : 11 fichiers, empreintes valides ;
- préflight réel : conforme ;
- `InstallBootstrap` : OK ;
- `Validate` en exposition `Bootstrap` : OK ;
- création du compte nginx : écriture SSHA et activation authentifiée en boucle
  locale effectuées ;
- vérification automatique `401/200` : KO avant résultat HTTP ;
- rollback automatique : exécuté.

## Cause confirmée

Le test distant lançait le programme Python depuis stdin, puis ce programme
essayait de lire le JSON du compte sur le même stdin. Après lecture du programme,
le flux était vide et `json.load(sys.stdin)` retournait
`JSONDecodeError: Expecting value`.

Le mot de passe n'a pas été affiché, écrit dans les preuves ou ajouté à une
ligne de commande. Seul le SSHA salé a existé brièvement dans la fondation,
avant sa suppression par rollback.

## État après rollback

Vérifications distantes en lecture seule :

- `/usr/data/k1-control-v1` absent ;
- `S56k1_control_moonraker` et `S57k1_control_gateway` absents ;
- ports `7125` et `4409` fermés ;
- ports Creality `80`, `8080` et `9999` présents ;
- Klipper et les processus Creality nommés présents.

Les preuves brutes restent sous `inventory/raw/`, ignorées par Git.

## Correctif hors imprimante

Le programme de vérification passe désormais par Python `-c`; stdin est réservé
au JSON. Les 56 tests passent. Un JSON factice a traversé la même fonction SSH
et a été lu par le Python constructeur avec `REMOTE_STDIN_PROOF_OK`, sans
écriture distante.

## Reprises autorisées et causes suivantes

Thomas a renouvelé le GO V3 exact. Les reprises ont toutes utilisé le rollback
automatique au premier KO :

- le fichier `nginx.htpasswd` était d'abord illisible par le worker nginx ;
- `root:www-data 0640` ne suffisait pas car le dossier `state`, créé sous le
  `umask` de root, n'était pas traversable ;
- la pose a donc fixé `state` en `root:www-data 0710`, le fichier en `0640` et
  ajouté une lecture réelle sous `www-data` avant la saisie humaine ;
- la première activation LAN a prouvé qu'un reload nginx ne peut pas remplacer
  l'écoute `127.0.0.1:4409` par `0.0.0.0:4409` tant que l'ancien worker possède
  la socket ; seul le service nginx du projet est désormais redémarré après
  validation de la nouvelle configuration.

## Pose finale

Capture privée : `20260821-015722-g4-control-foundation-v3`

Résultat : **fondation installée et validation LAN verte**

- `INSTALL_BOOTSTRAP_OK` ;
- `SET_GATEWAY_ACCOUNT_OK username=TomassonJW` ;
- compte vérifié humainement dans le vrai tableau de bord Mainsail ;
- `ACTIVATE_LAN_OK` ;
- `VALIDATE_OK` ;
- Moonraker : `127.0.0.1:7125` uniquement ;
- Mainsail authentifié : `0.0.0.0:4409` ;
- ports Creality `80`, `8080`, `9999` intacts ;
- mémoire disponible après pose : 105292 Kio ; croissance swap : 36 Kio ;
- Klipper `standby`, chauffes à `0`, axes non homés ;
- deux CFS connectés, quatre emplacements chacun, version `1.1.3` ;
- aucun G-code, mouvement, chauffe, calibration, extrusion, impression ou
  redémarrage imprimante.

Le lanceur local à double-clic a été testé en arrêtant l'ancien tunnel : il a
créé automatiquement un nouveau tunnel SSH et obtenu HTTP `401` avant ouverture
du tableau de bord. Les preuves brutes restent privées et ignorées par Git.

L'acceptation durable nécessite encore huit heures d'observation incluant une
impression normale lancée manuellement par Thomas.
