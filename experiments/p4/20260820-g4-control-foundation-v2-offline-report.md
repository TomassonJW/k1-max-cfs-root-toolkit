# Rapport P4 — préparation hors imprimante FOUNDATION-V2

Date : 2026-08-20

Résultat : **paquet V2 prêt et contrôlé hors imprimante ; non autorisé**

## Correction apportée

V2 retire entièrement la dépendance `logrotate` qui a bloqué V1. nginx envoie
ses erreurs à la socket `/dev/log` du `syslogd` BusyBox stock. Moonraker garde
sa propre rotation quotidienne. Aucun paquet, cron ou service de journal n'est
ajouté.

L'archive nginx auditée contient nginx `1.17.7` et les marqueurs nécessaires au
transport syslog par socket Unix. L'environnement Moonraker contient un vrai
binaire Python 3 MIPS ; ses liens `python` et `python3.8` pointent vers ce
binaire interne et ne remplacent pas le Python constructeur.

## Déploiement préparé

`scripts/deploy-control-foundation.ps1` :

- ne contacte rien avec son action par défaut `Plan` ;
- refuse toute action distante sans `-Execute` et le texte exact V2 ;
- répète l'identité machine, l'inactivité, les deux CFS, les ports, les
  processus Creality, le syslog, la RAM, le swap et le stockage ;
- compare chaque archive, configuration et service avant démarrage ;
- teste nginx avant exécution ;
- attend les nouveaux services avec un délai borné ;
- garde Moonraker et Mainsail en boucle locale jusqu'au compte vérifié ;
- remplace la configuration LAN de façon atomique et restaure la précédente au
  premier KO ;
- rollback automatiquement la fondation locale au premier échec.

## Bundle reconstruit

Le bundle temporaire contient dix fichiers contrôlés. Archives tierces :

- Moonraker MIPS :
  `ca22e35a2773b3159b5023ace15e9abe305f1e5d01a01eef8fa1b6a3f9ce918a` ;
- nginx MIPS :
  `586d69ee2b61bf0a6b65e77bcd91bbee28e2b457019a7bcac65898f6f8d7f9f1` ;
- Mainsail `v2.18.2` :
  `df2ba7c301f7bfc8ac9f122741a6ba08356d679ecfa1f62f898d0337802d5de5`.

Les archives restent hors Git et seront reconstruites depuis leurs sources
figées au moment de la future pose.

## Vérifications vertes

- `python -m unittest discover -s tests -v` : `54/54` ;
- `python -m prototype.scenario_matrix` : `17/17` ;
- analyse PowerShell du futur déployeur : OK ;
- action locale `Plan` : OK, `printer_mutation_authorized=false` ;
- action `Validate` sans gate : refus attendu avant SSH ;
- syntaxe Buildroot des deux services avec Git Bash : OK ;
- reconstruction et inventaire SHA-256 du bundle : 10 fichiers, OK.

## Effet réel sur la K1 Max

Aucun. Les seules lectures distantes de cette reprise ont servi au préflight V1
et à prouver le syslog stock. Aucun fichier, dossier, service ou port n'a été
créé. Aucune chauffe, commande G-code, référence, calibration, extrusion,
impression ou relance n'a été demandée.

## Gate restante

V2 change l'architecture approuvée de V1 ; elle exige donc le nouveau texte
exact `GO G4-K1-CONTROL-FOUNDATION-V2` avant la première écriture distante.
