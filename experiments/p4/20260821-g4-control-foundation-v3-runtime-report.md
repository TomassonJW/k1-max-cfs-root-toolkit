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

Le correctif n'a pas été redéployé. Une nouvelle tentative exige un nouveau
texte exact `GO G4-K1-CONTROL-FOUNDATION-V3`.
