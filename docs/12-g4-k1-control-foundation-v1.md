# 12 — G4-K1-CONTROL-FOUNDATION-V1

Date : 2026-08-20

Statut : **préflight réel KO ; jamais déployé ; nom définitivement fermé**

## Arrêt définitif de V1

Thomas a autorisé exactement V1 le 2026-08-20. Le préflight réel a confirmé la
bonne machine, l'état `standby`, les chauffes à zéro, les deux CFS connectés,
les ressources attendues et l'absence de toutes les cibles. Il a aussi prouvé
que la machine ne possède ni `logrotate`, ni `/etc/logrotate.d`.

V1 exigeait explicitement ce programme avant toute copie. La pose a donc été
arrêtée à temps : aucun dossier, fichier, service, port ou profil n'a été créé
ou modifié sur l'imprimante. Ce nom ne peut plus recevoir de GO.

Le texte restant ci-dessous conserve le plan refusé comme preuve historique.
Son remplacement sans dépendance ajoutée est décrit dans le document 13 et
s'appelle `G4-K1-CONTROL-FOUNDATION-V2`.

## Ce que cette première pose apportera

Cette gate ajoute Moonraker et Mainsail sans changer le comportement de la K1
Max. Après validation, Thomas aura une interface experte propre pour voir les
températures, le mesh, les fichiers, les états, les macros et les erreurs.

Elle ne corrige pas encore le Z, le démarrage, la purge ou les températures CFS.
Ces règles restent dans le simulateur tant que leurs wrappers exacts ne sont pas
prêts. `K1 Control` reste donc local dans cette pose. L'écran, Creality Web,
Creality Print, le firmware `2.3.5.34` et les deux CFS restent en place.

Le profil Orca actif et son post-traitement `+0,27 mm` ne sont pas touchés.

## Composition figée

Le manifeste `packages/k1-control-v1/foundation-manifest.json` fixe :

- Moonraker MIPS au commit `fccffa96c63ed77dc3953e18615e9fe9cd3d69ea` ;
- son environnement Python 3.8 déjà construit pour la famille K1 ;
- nginx MIPS provenant du même paquet audité ;
- Mainsail `v2.18.2` ;
- les tailles, SHA-256, ports, chemins et plafonds de ressources.

Le script communautaire n'est jamais exécuté. Le script local
`scripts/prepare-control-foundation.py` vérifie les trois archives et prépare un
dossier inspectable. Il n'a ni code SSH ni destination imprimante.

## Préparation locale reproductible

Toutes les commandes ci-dessous restent sur le PC :

```powershell
git clone https://github.com/Guilouz/Creality-Helper-Script.git .codex-work\helper-script
git -C .codex-work\helper-script checkout b46787a61b3ce2f04ec04d115a73a46c26814057
python scripts\prepare-control-foundation.py --download-mainsail .codex-work\cache\mainsail-v2.18.2.zip
python scripts\prepare-control-foundation.py `
  --artifact moonraker-mips-bundle=.codex-work\helper-script\files\moonraker\moonraker.tar.gz `
  --artifact nginx-mips-bundle=.codex-work\helper-script\files\moonraker\nginx.tar.gz `
  --artifact mainsail=.codex-work\cache\mainsail-v2.18.2.zip `
  --output .codex-work\bundle
```

Résultat attendu : `status=OK`, trois archives conformes et un
`checksums.sha256` couvrant tout le dossier. Une archive de transport sera créée
seulement pendant le futur déploiement, puis son empreinte sera enregistrée.

## Chemins futurs exacts

Nouveaux chemins persistants :

- `/usr/data/k1-control-v1/releases/K1-CONTROL-V1.0.0` : version posée ;
- `/usr/data/k1-control-v1/current` : lien vers la version active ;
- `/usr/data/k1-control-v1/state` : base Moonraker et configuration active ;
- `/usr/data/k1-control-v1/logs` : journaux dédiés et bornés ;
- `/usr/data/k1-control-v1/backups/<UTC_CAPTURE_ID>` : preuve et rollback ;
- `/etc/init.d/S56k1_control_moonraker` : nouveau service Moonraker ;
- `/etc/init.d/S57k1_control_gateway` : nouvelle passerelle Mainsail.
- `/etc/logrotate.d/k1-control-v1` : rotation bornée du journal nginx.

Aucun fichier constructeur n'est remplacé. Les chemins interdits sont listés
dans le manifeste, notamment `printer.cfg`, `gcode_macro.cfg`, `box.cfg`, le
Klipper constructeur et `/etc/nginx/nginx.conf`.

## Sauvegarde obligatoire avant pose

Le futur opérateur doit enregistrer sous le dossier de backup daté :

1. processus, ports, RAM, swap et espace `/usr/data` ;
2. présence, type, cible de lien et SHA-256 de chaque chemin qui sera créé ;
3. copie de tout ancien service portant exactement les deux nouveaux noms ;
4. marqueur explicite `ABSENT` lorsqu'un chemin n'existe pas ;
5. SHA-256 de l'archive locale, de l'archive reçue et de chaque fichier extrait.

Un écart d'empreinte arrête la pose avant le démarrage d'un service.

## Ordre futur de pose

1. vérifier que l'imprimante est au repos et que son `logrotate` accepte, en
   mode diagnostic sans rotation, la politique préparée ; sinon arrêt ;
2. déposer l'archive dans un nouveau dossier `staging` sous
   `/usr/data/k1-control-v1` ;
3. vérifier toutes les empreintes ;
4. extraire la version sans modifier les fichiers Creality ;
5. créer l'état, les logs et la configuration nginx de démarrage, limitée à
   `127.0.0.1:4409` ;
6. poser les deux nouveaux services et la politique de rotation nginx déjà
   contrôlée ;
7. démarrer Moonraker, puis la passerelle locale ;
8. sur le PC, ouvrir un tunnel
   `ssh -N -L 4409:127.0.0.1:4409 k1max-root` ;
9. ouvrir `http://127.0.0.1:4409`, créer le premier compte et vérifier sa
   connexion ; cette action humaine garde le mot de passe hors des scripts ;
10. seulement après cette connexion, activer la configuration LAN sur le port
    `4409` et recharger la nouvelle passerelle ;
11. exécuter les contrôles ci-dessous.

Les étapes 2 à 7 et 10 modifient l'imprimante et restent interdites sans le GO
exact `G4-K1-CONTROL-FOUNDATION-V1`.

## Contrôles sans chauffe, mouvement ni extrusion

La validation initiale n'envoie aucune commande G-code :

- `7125` écoute uniquement sur `127.0.0.1` ;
- `4409` reste local jusqu'à la création du compte, puis devient le seul nouveau
  port LAN ;
- Mainsail exige une connexion et affiche la K1 comme prête ;
- les ports Creality `80`, `8080` et `9999` répondent encore ;
- l'écran, Klipper et les deux CFS restent présents ;
- Moonraker reste sous 45 Mio au repos ;
- il reste au moins 70 Mio disponibles et le swap n'augmente pas de plus de
  8 Mio ;
- les journaux restent ensemble sous 16 Mio et la rotation nginx est reconnue ;
- aucune chauffe, référence, calibration, purge, extrusion ou impression n'est
  lancée par Codex.

Après ce contrôle, une observation d'au moins huit heures incluant une
impression normale choisie et lancée par Thomas est requise. Cette impression
n'est pas autorisée automatiquement par la gate d'installation.

## OK, KO et rollback

**OK provisoire** : empreintes exactes, compte créé sans fenêtre LAN ouverte,
services stables, interfaces Creality intactes et ressources sous les limites.

**OK final** : mêmes résultats après l'observation longue, sans perte de CFS,
écran, réseau ou mémoire.

**KO immédiat** : empreinte différente, port imprévu, accès sans connexion,
service Creality manquant, RAM sous la limite, swap en hausse ou instabilité.

En cas de KO : arrêter seulement les deux nouveaux services, restaurer les deux
services ou leurs marqueurs `ABSENT`, restaurer l'ancien lien `current` ou son
absence, déplacer la version en échec dans le backup daté, puis comparer les
processus et ports avec le relevé initial. Aucun rollback Orca n'est nécessaire,
car Orca reste inchangé dans cette pose.

## Manuel et automatique

Automatisé plus tard : vérification des empreintes, préparation des dossiers,
pose des nouveaux fichiers, contrôles de ports/ressources et rollback borné.

Manuel : donner le GO exact, vérifier que la machine est au repos, choisir le
mot de passe initial dans le tunnel, lancer l'impression normale d'observation
et confirmer le résultat physique.

## Gate fermée

`G4-K1-CONTROL-FOUNDATION-V1` est définitivement non déployable. La seule
succession possible est le nouveau paquet V2, après sa propre validation et un
nouveau GO portant son nom exact.
