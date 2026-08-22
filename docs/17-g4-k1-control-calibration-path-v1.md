# G4 — K1 Control calibration path V1

Statut au 2026-08-22 : **préflight réel corrigé et vert ; aucune pose ni
calibration effectuées ; nouveau GO exact obligatoire**.

## Préflight réel de la capture `20260822-113503`

Thomas a envoyé le GO exact. Le premier préflight a joint la K1 puis s'est
arrêté avant toute écriture : le candidat complet était placé en Base64 dans la
ligne de commande SSH et dépassait la taille acceptée par le Dropbear de cette
machine. La connexion a été fermée pendant le parse Jinja ; aucun fichier,
backup, service, G-code ou état Klipper n'a été modifié.

Le déployeur transmet maintenant le même programme et le même candidat sur
l'entrée standard de SSH. La commande distante reste courte, exécute
`/usr/share/klippy-env/bin/python -` et ne crée toujours aucun fichier. Les
tests hors imprimante restent verts.

Le préflight corrigé a ensuite obtenu
`PREFLIGHT_CALIBRATION_PATH_V1_OK`. Il confirme : machine exacte, `standby`,
chauffes demandées à zéro, deux CFS `1.1.3`, runtime `ready=1`, stockage
`empty`, aucun Z accepté, production fermée, overlay/include absents, hashes
attendus, fondation intacte et parse Jinja exact vert. Les axes étaient encore
référencés avant le futur restart, état admis par ce préflight. Les preuves
privées restent ignorées sous la capture complète
`20260822-113503-g4-k1-control-calibration-path-v1`.

La commande revue ayant changé après le GO, ce GO n'autorise plus la pose. Le
déploiement attend un nouveau texte exact
`GO G4-K1-CONTROL-CALIBRATION-PATH-V1` portant sur le commit corrigé.

Le nom `G4-K1-CONTROL-CALIBRATION-PATH-V1` choisit ce lot. Il ne vaut pas GO de
mutation. L'ouverture future exigera le texte exact
`GO G4-K1-CONTROL-CALIBRATION-PATH-V1` après revue de ce document et du commit
figé.

## Résultat visé

Ajouter à Klipper une voie originale, bornée et non extrusive pour évaluer le
premier Z provisoire. La pose de cette voie est séparée de son utilisation : le
déploiement ne chauffe pas, ne référence pas les axes, ne bouge rien et
n'enregistre aucune donnée Z ou mesh.

Cette gate ne rend pas encore l'interface autonome. Elle retire seulement le
blocage de sécurité qui empêchait de construire ensuite une première
calibration assistée sans commandes libres.

## État initial obligatoire

- K1 Max `CR4CU220812S12`, structure `0`, firmware `2.3.5.34` ;
- `printer.cfg` stabilisé :
  `a484e8d802d0ba1a1331ea2060ecc339bd2d1a607e3a0f9bbcca976c66709c6a` ;
- runtime Z/mesh :
  `dd7fa02a8b7b9bd46850c90cf2a85afa71ce2494df3bd1f686ff4ee8cbb8ede` ;
- module persistant :
  `696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede` ;
- runtime `ready=1`, stockage `empty`, aucun Z accepté, mouvements bas fermés ;
- imprimante en `standby`, chauffes demandées à zéro ;
- deux CFS connectés en `1.1.3` ;
- fichier et include calibration-path absents.

Une différence ferme le préflight avant toute mutation.

## Écriture exacte prévue

Source locale :
`packages/k1-control-v1/calibration-path-v1/k1-control-calibration-path.cfg`.

Empreinte SHA-256 :
`825aadac8679e0d0e9be140cc5ba4e7656b2bff0d197d1683a73d2b5be4e364e`.

Destination :
`/usr/data/printer_data/config/k1-control-calibration-path.cfg`.

`printer.cfg` reçoit exactement une ligne
`[include k1-control-calibration-path.cfg]` juste après
`[include k1-control-z-mesh.cfg]`. Son empreinte attendue devient :
`0d59dd656844c3198ee43a81056b06830dbe60779d558b71aaa8c28fa708d9ee`.

Le seul redémarrage prévu est un `RESTART` de l'hôte Klipper. Aucun firmware,
service CFS, profil Orca, `START_PRINT`, postprocesseur Z ou fichier constructeur
n'est modifié.

## Déployeur revu

Le déployeur est
`scripts/deploy-k1-control-calibration-path-v1.ps1`. Son action par défaut est
`Plan`, purement locale. `Preflight`, `Deploy`, `Validate` et `Rollback` exigent
à la fois `-Execute` et
`-Gate G4-K1-CONTROL-CALIBRATION-PATH-V1`.

Avant la première écriture, le préflight :

1. repointe toutes les empreintes ci-dessus ;
2. vérifie l'identité exacte, le repos, les deux CFS et la fondation réseau ;
3. vérifie que le runtime reste vide et fermé à la production ;
4. transmet le candidat uniquement comme argument Base64 au Python/Jinja exact
   de la K1 pour le parser en mémoire, sans fichier distant ;
5. refuse toute cible ou inclusion déjà présente.

La capture future doit respecter
`AAAAMMJJ-HHMMSS-g4-k1-control-calibration-path-v1` et rester sous
`inventory/raw/`, ignoré par Git.

## Backup et ordre de pose

Le déployeur crée, sous
`/usr/data/k1-control-v1/backups/<capture>/calibration-path-v1`, un backup exact
de `printer.cfg` et son `checksums.sha256`. Il transfère le candidat dans un
dossier de staging lié à la capture, recalcule les deux fichiers futurs, puis :

1. pose le nouvel overlay avec le mode `0600` ;
2. remplace `printer.cfg` par la copie dont l'empreinte est figée ;
3. synchronise le stockage ;
4. envoie uniquement `RESTART` à Klipper ;
5. exécute la validation à vide.

Le déployeur ne contient aucun appel à `KCTRL_CALIBRATION_PREHEAT`, homing,
mesure mesh, `KCTRL_CAL_PATH_BEGIN`, mouvement, ajustement ou commit.

## Validation sans mouvement

Après le restart, la validation exige :

- Klipper prêt, `standby`, chauffes demandées à zéro, axes non référencés ;
- les deux CFS et les services/ports de fondation inchangés ;
- les quatre empreintes exactes et une seule occurrence de chaque include ;
- le runtime existant toujours `ready=1`, `empty`, sans Z accepté ;
- le chemin `idle`, `ready=0`, `mesh_ready=0`, `motion_armed=0` et
  `commit_ready=0` ;
- `KCTRL_CAL_PATH_ASSERT_ARMED` refusé ;
- cibles de chauffe, position et origine Z strictement identiques avant/après
  ce refus.

## Rollback exact

Sur échec après la première mutation, ou sur action `Rollback`, le déployeur :

1. vérifie le checksum du backup ;
2. restaure ce `printer.cfg` et retire uniquement l'overlay ajouté ;
3. synchronise puis recharge Klipper ;
4. attend le déchargement du chemin, les axes non référencés et les deux CFS ;
5. préserve et revérifie le runtime Z/mesh existant ;
6. attend cinq secondes pour les écritures Creality différées ;
7. restaure une dernière fois le backup exact sans autre restart ;
8. attend trois secondes et repointe l'empreinte et l'absence des transitoires.

Le backup et le staging de capture restent comme preuve. Le rollback ne retire
ni le runtime installé ni son stockage.

## Gate suivante, après installation validée

`G4-K1-CONTROL-FIRST-CALIBRATION-V1` sera une autre autorisation. Elle devra
figer plaque, températures, stabilisation, matrice, interpolation et tolérance,
puis effectuer deux meshes transitoires comparables avant tout enregistrement.
Elle pourra ensuite charger le mesh qualifié et utiliser le chemin borné pour le
premier Z. Aucun de ces actes n'appartient à la présente gate.
