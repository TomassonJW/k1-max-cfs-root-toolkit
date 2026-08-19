# Journal public de l’acquisition ciblée

Capture : `20260819-1726-k1max-targeted-sources`

Date : 2026-08-19

Mode distant : lecture seule

| Étape | Classe de commandes | Résultat | Écriture distante |
|---|---|---|---|
| Préflight local | état Git, règles, protocole, vérification du chemin ignoré | OK | aucune |
| Identité matérielle | lecture de la métadonnée OTA, de la partition d’identité via l’outil constructeur et des variantes de configuration | OK | aucune |
| Recherche des extensions | `find`, `grep`, `stat` et `sha256sum` sur l’arbre Klipper borné | OK | aucune |
| Lecture ciblée | sources Python CX, sauvegarde, homing et PR Touch | OK | aucune |
| Frontière binaire CFS | inventaire et empreintes du chargeur `box` et de son module compilé | OK | aucune |
| Analyse locale | comparaison S11/S12, cartographie des commandes et nettoyage | OK | aucune |

Deux sessions SSH ont été nécessaires, avec une authentification interactive chacune. Le mot de passe n’a été ni enregistré, ni écrit dans un script, ni ajouté au dépôt.

Aucune commande distante mutante, redirection vers un fichier distant, installation, commande de redémarrage, mouvement, chauffe ou calibration n’a été utilisée.
