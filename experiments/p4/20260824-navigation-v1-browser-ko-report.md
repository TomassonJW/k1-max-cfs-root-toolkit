# NAVIGATION-V1 — KO navigateur et candidat R2

Date : 2026-08-24

## Faits confirmés

- capture de pose :
  `20260824-110936-g4-k1-control-calibration-ui-navigation-v1` ;
- préflight, déploiement et validation SSH indépendante : verts ;
- restart, chauffe, homing, mouvement, mesh et écriture Z : absents ;
- Chrome authentifié affiche le lien Mainsail `K1 Control` vers
  `/k1-control/` ;
- après clic, le navigateur affiche encore Mainsail ;
- le `sw.js` exact installé enregistre un `NavigationRoute` vers `index.html` ;
- sa denylist contient le préfixe `/access` ;
- le profil robuste, le Z accepté et l'état final sûr restent conformes selon
  les deux validations du déployeur.

## Cause

L'origine `localhost:4409` était historiquement réservée à K1 Control. Dès que
Mainsail est ouvert sur cette même origine, son service worker la contrôle et
intercepte aussi `/k1-control/`. Un lien normal, même affiché correctement, ne
peut pas forcer nginx à servir l'autre application.

## Correctif R2 validé

R2 ne modifie pas le service worker constructeur. Elle ajoute dans la racine
statique l'alias `access-k1-control -> k1-control` et change le lien Mainsail en
`/access-k1-control/`. Le préfixe est déjà exclu par le worker exact. Le rollback
restaure les deux fichiers de V1 et retire l'alias. Aucune action physique ni
aucun restart n'est présent dans le paquet.

La capture `20260824-112535-g4-k1-control-calibration-ui-navigation-v1-r2` a
obtenu le préflight, la pose et deux validations SSH vertes. Chrome a rechargé
Mainsail, confirmé le lien `/access-k1-control/`, puis rendu
`K1 Control — calibration` après le clic. Le texte final corrigé est visible,
sans nouvelle authentification, case physique cochée ou lancement de
calibration.
