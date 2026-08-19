# G4-SSH-KEY — rapport de déploiement

Date : 2026-08-19
Portée : accès SSH root sans mot de passe uniquement

## Résultat

`G4-SSH-KEY` est déployé et validé. La K1 Max accepte une clé publique ECDSA P-256 dédiée. Deux connexions finales indépendantes ont réussi alors que l'authentification par mot de passe était explicitement désactivée.

L'alias local `k1max-root` sélectionne automatiquement cette clé, vérifie l'identité déjà connue de la machine et refuse tout retour au mot de passe.

## État final distant

- fichier : `/root/.ssh/authorized_keys` ;
- propriétaire et groupe : root ;
- droits : `600` ;
- clé active : exactement une ;
- empreinte SHA-256 finale du fichier : `eae61f0314dbcdfaa9a02a42352592e3b175a5d35a0d501cb909b365697eb6af` ;
- aucun service redémarré ;
- aucun mouvement, chauffage, calibrage, print ou changement Klipper/CFS.

Les sauvegardes distantes et leurs empreintes sont conservées dans la preuve privée ignorée. La configuration SSH Windows a elle aussi été sauvegardée avant l'ajout de l'alias.

## Incident rencontré et correction

Le premier essai utilisait Ed25519. Deux problèmes ont été observés et conservés dans les preuves privées :

1. le premier transport de commande a découpé la clé sur plusieurs lignes ; le fichier raté a été reconnu par son empreinte exacte puis remplacé ;
2. une fois correctement formée, la clé Ed25519 restait refusée car le serveur observé est Dropbear `2019.78`. La prise en charge Ed25519 dans `authorized_keys` apparaît seulement dans Dropbear `2020.79`.

Une clé ECDSA P-256 compatible a donc été créée et installée. La clé Ed25519 distante a été retirée après sauvegarde, puis ses fichiers privés locaux inutilisés ont été supprimés définitivement.

## Validation

- installation ECDSA : `G4_SSH_KEY_INSTALL_SESSION_OK` ;
- clé active trouvée exactement une fois ;
- deux connexions explicites sans mot de passe : OK ;
- deux connexions après nettoyage : OK ;
- connexion par alias `k1max-root` : OK ;
- droits et propriétaire : OK.

## Retour arrière

L'état initial ne contenait ni dossier `/root/.ssh` ni fichier `authorized_keys`. Le retour complet consiste donc à supprimer uniquement la ligne ECDSA dédiée, puis le fichier et le dossier seulement s'ils sont vides. Les sauvegardes intermédiaires privées permettent aussi de revenir à chaque état observé pendant le déploiement.

Une fois le retour arrière effectué, la configuration SSH Windows peut être restaurée depuis sa sauvegarde `config.pre-k1max-g4-20260819-2135.bak`, et les deux fichiers locaux `id_ecdsa_k1max_codex` peuvent être supprimés.
