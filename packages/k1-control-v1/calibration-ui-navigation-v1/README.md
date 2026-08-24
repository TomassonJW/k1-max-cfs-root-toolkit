# CALIBRATION-UI-NAVIGATION-V1

Ce delta statique ferme les deux défauts d’usage observés pendant la première
campagne quotidienne complète :

- pendant `starting_z`, l’écran annonce explicitement la préparation en cours au
  lieu de demander à tort de qualifier le mesh déjà enregistré ;
- après confirmation et après acceptation, le texte décrit l’action réellement
  disponible ;
- Mainsail charge `.theme/navi.json` et affiche un accès `K1 Control` vers
  `/access-k1-control/` dans la même fenêtre. Ce chemin est un alias symbolique
  original vers l'interface et commence par `access`, préfixe déjà exclu de la
  route de navigation du service worker Mainsail installé.

Le lien reste sur l’origine `http://localhost:4409`. L’authentification HTTP
déjà détenue par le navigateur est donc réutilisée pendant la même session. Ce
paquet ne retire ni ne modifie la protection nginx et ne stocke aucun mot de
passe.

La révision R2 remplace `app.js` par les mêmes octets déjà validés, remplace
`.theme/navi.json` et crée seulement l'alias statique
`access-k1-control -> k1-control`. Elle ne modifie pas le service worker
constructeur, ne redémarre aucun service et ne contient aucune commande de
chauffe, homing, mouvement, mesh, Z, extrusion, impression ou CFS. Le rollback
restaure les backups exacts de `app.js` et `navi.json`, puis retire l'alias.
