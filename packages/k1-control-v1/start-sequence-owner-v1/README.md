# START-SEQUENCE-OWNER-V1

Statut : **candidat hors imprimante, non installable en l'etat**.

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

Le seul temps d'attente volontaire avant la reference Z sert a retrouver la
meme fenetre thermique que celle du Z accepte. Une reference faite a une
temperature variable recreerait un decalage difficile a distinguer d'un residu
sur la buse.

## Limites volontaires

- Une route vide, differente ou ambigue est bloquee. Le chargement et le
  changement attendent encore leur transport CFS a temperature explicitement
  possedee.
- La confirmation manuelle est consommable une seule fois, mais ce candidat ne
  lui associe pas encore d'horodatage persistant.
- Les erreurs de garde prévues coupent les chauffes avant de bloquer. Une panne
  Klipper inattendue au milieu d'une macro exige encore un surveillant borné ;
  son absence interdit la pose de ce candidat.
- Les coordonnees de purge sont une proposition hors imprimante. Elles devront
  etre revues dans le preflight de pose.
- Le Python local ne fournit pas Jinja2. La structure est contrôlée hors
  imprimante, mais chaque template devra être parsé avec l'environnement exact
  de la K1 avant toute demande de pose.
- Le fichier de macros n'est pas inclus, deploye ou appele sur la K1.

## Fichiers

- `contract.json` : contrat ferme et ordonnancement attendu ;
- `k1-control-start-sequence-owner-v1.cfg` : candidat de macros Klipper ;
- `orca-start.gcode` : unique ligne de demarrage a placer dans Orca ;
- `verify_candidate.py` : verification hors imprimante du candidat.

Une future pose exige une gate separee
`G4-K1-CONTROL-START-SEQUENCE-OWNER-V1`, avec fichiers figes, backup, rollback
et commandes exactes. Ce paquet ne donne aucune autorisation de connexion ou
d'effet sur la K1.
