# G4-SSH-KEY — accès SSH dédié sans mot de passe

## Décision et portée

Thomas a donné le `GO G4-SSH-KEY` le 19 août 2026. Cette autorisation concerne uniquement l'ajout d'une clé publique dédiée dans `/root/.ssh/authorized_keys` sur la K1 Max déjà identifiée.

Le changement ne modifie aucun service, firmware, macro, réglage d'impression, fichier Klipper ou composant CFS. Il ne demande ni redémarrage ni mouvement de la machine.

La clé privée reste uniquement dans le profil Windows de Thomas. Elle n'est jamais copiée dans le dépôt, sur GitHub ou dans les captures du projet.

## Préparation et sauvegarde

- clé locale dédiée : type Ed25519, sans phrase secrète pour supprimer les demandes interactives ;
- cible distante unique : `/root/.ssh/authorized_keys` ;
- sauvegarde distante si le fichier existe : `/root/.ssh/authorized_keys.codex-backup-<identifiant>` ;
- empreinte SHA-256 calculée avant et après la copie ;
- si le fichier n'existe pas, l'absence est enregistrée explicitement au lieu de fabriquer une fausse sauvegarde ;
- les preuves brutes, l'hôte privé et les chemins locaux personnels restent sous `inventory/raw/`, donc hors Git.

Le script refuse de continuer si `.ssh` n'est pas un dossier, si `authorized_keys` n'est pas un fichier normal, si la sauvegarde existe déjà ou si son empreinte diffère de l'original.

## Installation

Le script [install-ssh-public-key.ps1](../scripts/install-ssh-public-key.ps1) conserve les clés déjà présentes, ajoute la nouvelle clé une seule fois, puis impose les droits `700` au dossier et `600` au fichier. Le remplacement final du fichier est fait en une seule opération.

Une seule dernière saisie du mot de passe root est attendue pendant cette installation. Le mot de passe n'est ni affiché ni conservé.

## Validation attendue

Après installation, deux nouvelles connexions indépendantes doivent réussir avec :

- la clé privée dédiée explicitement sélectionnée ;
- l'authentification par mot de passe désactivée ;
- le contrôle strict de l'identité connue de la machine ;
- aucune écriture distante pendant les tests.

La première connexion vérifie l'accès, l'unicité de la clé et l'empreinte du fichier. La seconde confirme que le résultat ne dépend pas d'une session déjà ouverte.

Succès : les deux connexions retournent `SSH_KEY_AUTH_OK`, sans invite de mot de passe, et la clé apparaît exactement une fois.

Échec : toute invite, erreur d'identité, clé absente ou dupliquée, droits inattendus ou différence d'empreinte non expliquée.

## Retour arrière

Si `authorized_keys` existait avant le changement, recopier la sauvegarde vérifiée vers le fichier actif, remettre les droits `600`, puis confirmer que son empreinte correspond à l'empreinte d'avant.

S'il n'existait pas, retirer uniquement la ligne de la clé dédiée. Supprimer ensuite le fichier seulement s'il est vide, puis supprimer le dossier `.ssh` seulement s'il avait lui aussi été créé par ce changement et reste vide.

Le retour arrière doit être exécuté avec la clé encore fonctionnelle. En cas d'échec de la validation initiale, ne tenter aucun autre changement : conserver les preuves et utiliser l'accès root manuel pour restaurer seulement la sauvegarde prévue.

## Conditions d'arrêt

Arrêt immédiat si la cible est ambiguë, si l'identité SSH connue ne correspond plus, si la machine n'est pas au repos, si le fichier distant a une forme inattendue, si la sauvegarde ne peut pas être vérifiée ou si l'installation réclame plus d'une authentification.
