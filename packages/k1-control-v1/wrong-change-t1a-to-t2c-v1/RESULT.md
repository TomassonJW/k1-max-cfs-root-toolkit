# Résultat

Statut : `OFFLINE_READY_BLOCKED_BY_PRIOR_R2_PHYSICAL_TRIAL`.

La gate passive attend désormais l'empreinte exacte du propriétaire R2 et
accepte les deux états terminaux sûrs réellement observés : `standby` sans
fichier ou `complete` avec fichier. Elle reste bloquée tant que la purge R2 et
sa fin sûre n'ont pas reçu leur verdict physique.

Aucun changement de filament, chauffage, mouvement, écriture distante ou
service n'a été produit par ce paquet.
