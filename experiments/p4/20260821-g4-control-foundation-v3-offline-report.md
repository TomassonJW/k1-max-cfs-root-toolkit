# G4-K1-CONTROL-FOUNDATION-V3 — rapport hors imprimante

Date : 2026-08-21
Statut : prepare localement, non autorise sur l'imprimante

## Decision appliquee

Thomas a choisi `CHOIX AUTH — NGINX`. La fondation V3 place donc
l'authentification devant Mainsail dans le nginx dedie, sans exposer Moonraker.
Moonraker reste sur `127.0.0.1:7125` et ne fait confiance qu'au proxy local.

Le compte est cree par une saisie PowerShell masquee. Seul un enregistrement
RFC 2307 `{SSHA}` avec un sel aleatoire de 16 octets est transmis puis stocke
avec le mode `0600`. Le mot de passe n'est ni accepte en argument de commande,
ni ecrit dans les preuves.

## Etats prevus

1. bootstrap anonyme, uniquement sur `127.0.0.1:4409` par tunnel SSH ;
2. creation et verification du compte nginx, toujours en boucle locale ;
3. ouverture de `0.0.0.0:4409` uniquement apres validation humaine, avec
   authentification obligatoire et filtrage des sources privees.

L'en-tete `Authorization` est consomme par nginx puis retire avant tout proxy
vers Moonraker. Un echec apres la premiere mutation declenche le rollback de la
fondation. Ce rollback ne retire le dossier distant que si le marqueur du meme
`CaptureId` prouve son absence initiale, puis controle la restauration complete
de cette absence.

## Preuves hors imprimante

- binaire nginx MIPS epingle : directives `auth_basic` et
  `auth_basic_user_file` presentes, module non desactive explicitement ;
- generation SSHA executee deux fois : format valide, empreinte recalculee,
  sels distincts de 16 octets ;
- analyse PowerShell : deployeur et saisie de compte valides ;
- syntaxe Buildroot : deux services valides par `bash -n` ;
- `python -m unittest discover -s tests -v` : `56/56` ;
- `python -m prototype.scenario_matrix` : `17/17` ;
- action locale `Plan` : V3, `printer_mutation_authorized=false`, aucun contact
  distant ;
- bundle reconstruit depuis les artefacts epingles : `11` fichiers, toutes les
  empreintes de `checksums.sha256` valides.

## Limite de transport

HTTP Basic ne chiffre pas les identifiants sur le reseau. Le port LAN 4409 est
donc reserve a un reseau prive de confiance. Sur un reseau non fiable, il faut
conserver le tunnel SSH. L'ajout de TLS n'appartient pas a cette tranche.

## Changements non effectues

Aucun contact avec l'imprimante n'a eu lieu pendant cette preparation. Aucun
fichier, service, port, G-code, mouvement, chauffe, calibration, extrusion,
impression ou redemarrage n'a ete cree ou lance sur l'imprimante.

## Gate suivante

Toute action distante reste fermee. La seule autorisation acceptee par le
deployeur est le texte exact :

`GO G4-K1-CONTROL-FOUNDATION-V3`
