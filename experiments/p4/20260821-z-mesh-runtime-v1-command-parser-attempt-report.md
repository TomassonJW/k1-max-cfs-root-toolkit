# Deuxième essai réel `G4-K1-CONTROL-Z-MESH-RUNTIME-V1`

Date : 2026-08-21

Capture privée : `20260821-224828-g4-k1-control-z-mesh-runtime-v1`

## Résultat

Le nouveau GO exact a ouvert uniquement la pose Z/mesh corrigée. Le préflight
immédiat était vert : machine `standby`, axes non référencés, chauffes à zéro,
profil persistant `default`, empreinte initiale exacte, runtime absent,
fondation intacte et deux CFS connectés en `1.1.3`.

Le backup a été vérifié avant la première écriture. Le déployeur a posé les deux
fichiers et l'inclusion, puis exécuté le seul `RESTART` hôte Klipper prévu. Les
objets runtime étaient chargés, mais leur état `ready` est resté à zéro pendant
le délai borné. La garde sans mouvement n'a donc pas été appelée.

Le rollback a retiré les deux fichiers, l'inclusion et les données runtime, puis
rechargé Klipper. Une sauvegarde automatique Creality tardive a ensuite
normalisé les espaces des blocs générés `bed_mesh default` et `auto_addr`.
Après comparaison locale et vérification des empreintes, le backup exact a été
restauré une dernière fois sans nouveau restart.

Le préflight final a obtenu :

- `printer.cfg` revenu à
  `272640237e20659cf01f3268ed4cb0282b098c3d613e94bf84a3b80caac3c3b0` ;
- runtime absent sur disque et dans Klipper ;
- Klipper `standby`, axes non référencés, chauffes à zéro ;
- profil persistant `default` actif ;
- deux CFS reconnectés en `1.1.3` ;
- fondation V3 + PATHS-V1 intacte.

Aucun mouvement, homing, chauffage, extrusion, ordre CFS, calibration,
impression, firmware restart ou reboot imprimante n'a été exécuté.

## Cause exacte

Le journal Klipper rapporte `Unknown command:K1` avec la valeur complète
`K1_CONTROL_LOAD_STATE`. La source `gcode.py` exacte de la machine découpe les
commandes étendues avec `([A-Z_]+|[A-Z*/])`. Un chiffre placé au milieu du nom
arrête donc la lecture : les commandes prévues `K1_*` étaient enregistrées mais
impossibles à invoquer correctement.

La correction hors imprimante renomme tous les points d'entrée concernés en
`KCTRL_*`, y compris la commande Python de stockage et les futurs contrats Orca.
Un test rejoue désormais le parseur exact sur chaque nom de commande. Les deux
nouveaux fichiers ont pour SHA-256 :

- configuration :
  `1590b918dcdfe70e801c0be40fee4f19ab6b1e2dfa93936975b88aed5d4b1c79` ;
- module :
  `696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede`.

Le rollback attend maintenant le déchargement du runtime, la reconnexion des
deux CFS et une fenêtre silencieuse avant sa restauration finale, puis revérifie
l'empreinte après trois secondes. La suite locale passe `98/98`. Le Python/Jinja
exact de la K1 compile le module, parse les 17 templates et valide 18 noms de
commandes uniquement en mémoire :
`K1_EXACT_RUNTIME_OK templates=17 commands=18`.

## Gate

Le runtime est absent et la baseline exacte est saine. Le payload, les commandes
et le rollback ont changé après le GO consommé. Toute nouvelle pose exige une
nouvelle revue puis le même texte exact :

`GO G4-K1-CONTROL-Z-MESH-RUNTIME-V1`
