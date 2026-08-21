# K1 Control Z/mesh runtime V1

Statut : **candidat hors imprimante, déploiement interdit**.

Ce dossier est le candidat exact du futur gate
`G4-K1-CONTROL-Z-MESH-RUNTIME-V1`. Il ne devient déployable qu'après ajout et
revue de l'installateur, des sauvegardes, du contrôle sans extrusion et du
rollback.

Le fichier `k1-control-z-mesh.cfg` ajoute une couche originale sans modifier le
corps des macros constructeur et sans remplacer `START_PRINT` :

- état Z persistant en un seul enregistrement versionné ;
- valeur courante et valeur précédente avec leur contexte complet ;
- réglage provisoire borné et acceptation volontaire ;
- invalidation explicite après une opération changeant la référence ;
- préchauffe, stabilisation, homing et mesure mesh séparés ;
- matrices 3×3 à 25×25 et contrôle de la limite Lagrange 6×6 ;
- nom de profil déterministe par plaque, température, révision et matrice ;
- garde fermée avant tout futur mouvement bas, purge ou changement CFS.

La persistance mesh de ce Klipper exact passe par `SAVE_CONFIG`, donc redémarre
Klipper. `K1_MESH_COMMIT` est volontairement séparée de la mesure et ne doit
être proposée qu'après qualification de deux matrices par K1 Control.

Le `save_variables.py` constructeur a été écarté parce qu'il réécrit son fichier
directement. `k1_control_store.py` est un petit module original dédié : schéma
borné, somme SHA-256, permissions `0600`, synchronisation du fichier et du
dossier, remplacement atomique et copie précédente valide. Une corruption ne
charge jamais silencieusement l'ancienne valeur : le runtime démarre bloqué et
signale seulement qu'une récupération existe.
