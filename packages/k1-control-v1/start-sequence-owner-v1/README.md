# START-SEQUENCE-OWNER-V1

Statut : **installé et validé à froid ; essai physique bloqué tant que `T1A`
n'est pas chargé et relu**.

Ce paquet reprend uniquement le demarrage quotidien deja observe avec le bon
filament `T1A` engage. Il remplace le point d'entree constructeur
`START_PRINT`; il ne l'enveloppe pas.

## Ordre retenu

1. Thomas nettoie visuellement la buse a la main, imprimante au repos, puis
   lance `KCTRL_CONFIRM_MANUAL_NOZZLE_CLEAN_V1`.
2. Le G-code exporte appelle seulement
   `KCTRL_JOB_BEGIN_KEEP_CORRECT_V1 BED=55 PROBE_NOZZLE=140 FIRST_NOZZLE=190`.
3. La route unique `T1A`, l'absence de commande CFS, le profil `11 x 11` et le
   Z accepte sont verifies avant le premier effet physique.
4. Le plateau et la buse commencent a chauffer. X/Y sont references pendant la
   montee en temperature.
5. Une fois `140/55 degC` atteints, une seule reference Z precise est faite avec
   `ACCURATE_G28`. Il n'y a ni brossage ni reference Z grossiere.
6. Le profil persistant et le Z accepte sont armes et relus.
7. `T1A` est conserve sans commande CFS. La buse atteint les `190 degC`
   explicites de la premiere couche.
8. Une ligne de purge visible est deposee seulement apres une derniere
   verification mesh/Z, puis le G-code du modele prend la suite.

## Protections ajoutées

- La confirmation du nettoyage manuel expire après cinq minutes et reste
  consommable une seule fois.
- Un surveillant vérifie toutes les cinq secondes que le démarrage reste dans
  l'état d'impression attendu et dans le délai de sa phase. Une perte d'état ou
  un dépassement demande immédiatement l'arrêt des chauffes et bloque la suite.
- Les délais maximaux sont `600 s` pour la chauffe de référence, `120 s` après
  la référence, `180 s` pour la chauffe de première couche et `60 s` pour la
  purge.
- Le test froid volontairement expiré a prouvé ce surveillant sans chauffe,
  mouvement ni extrusion avant que le fichier soit retenu.

Le seul temps d'attente volontaire avant la reference Z sert a retrouver la
meme fenetre thermique que celle du Z accepte. Une reference faite a une
temperature variable recreerait un decalage difficile a distinguer d'un residu
sur la buse.

## Preuves obtenues

La capture réelle
`20260828-220525-g4-k1-control-start-sequence-owner-v1` a confirmé :

- les treize templates Jinja passent dans le Python et le Klipper exacts de la
  K1 ;
- la ligne de purge `X15 / Y20..180 / Z0,3..5` reste dans les courses lues ;
- le `11 × 11`, le Z `−0,04 mm`, les cibles à zéro, les axes libérés et les
  empreintes des configurations sont conformes ;
- le backup exact, l'ajout du fichier et de l'include, puis le restart Klipper ;
- une vraie transition du socket avant la reprise des contrôles ;
- la restauration unique et la relecture du `11 × 11` après restart ;
- le propriétaire et son surveillant chargés, le test froid vert et la phase
  finale `idle` ;
- aucun chauffage, mouvement, extrusion ou ordre CFS.

L'export sacrificiel Orca 2.4.2 contient deux couches et mesure `0,4 mm` de
haut. Le profil temporaire retire l'ancien post-traitement, vide le G-code de
filament et active `manual_filament_change=1`. L'export final contient exactement
un appel du propriétaire et aucun `Tn`, `START_PRINT`, brossage, recalibration,
`220 °C` caché ou ancien `+0,27 mm`. Il n'a pas été imprimé.

## Limites actuelles

- La lecture réelle a trouvé zéro route engagée : `T1A` est absent. La branche
  physique `KEEP_CORRECT_T1A` est donc bloquée avant tout effet.
- Le chargement de `T1A` ne fait pas partie de cette gate.
- Une panne complète du processus Klippy reste couverte par la sécurité hôte/MCU
  de niveau inférieur, pas par le surveillant Klipper lui-même.
- Le fichier de macros est posé et inclus ; seul son test froid a été appelé.

## Fichiers

- `contract.json` : contrat ferme et ordonnancement attendu ;
- `k1-control-start-sequence-owner-v1.cfg` : candidat de macros Klipper ;
- `orca-start.gcode` : unique ligne de demarrage a placer dans Orca ;
- `watchdog_model.py` et `watchdog-scenarios.json` : huit cas déterministes ;
- `remote_admin.py` et `remote_jinja_validate.py` : lectures et parse exacts
  envoyés par entrée standard, sans fichier distant ;
- `deployment-manifest.json` : fichiers, empreintes, backup, pose et rollback ;
- `sacrificial-gcode-inspection.json` : preuve de l'export Orca non imprimé ;
- `verify_candidate.py` et `verify_sacrificial_gcode.py` : contrôles locaux ;
- `scripts/deploy-k1-control-start-sequence-owner-v1.ps1` : plan, préflight,
  pose, validation et rollback fermés par gate exacte.

La pose est close et son autorisation est consommée. La gate suivante doit
rétablir puis relire une route unique `T1A`, sans lancer d'impression. L'essai
physique viendra ensuite sous une autre gate, avec Thomas présent devant la K1.
