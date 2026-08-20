# Candidat G4-CFS-TEMP-PLA

Ce dossier contient un correctif original, local et **non déployé** pour le cas
mesuré : une bobine Geeetech PLA imprimée à `190/195 °C`, avec remplacement
automatique par une bobine équivalente.

Contenu :

- `cfs-temperature-contract.cfg` : validation du profil et garde de reprise ;
- `active-config.patch` : trois petites adaptations des fichiers actifs ;
- `orca-start-gcode.md` : paramètres obligatoires du fichier imprimé ;
- `DEPLOYMENT.md` : sauvegarde, installation, validation et retour arrière.

Le paquet ne gère pas PETG/ABS/ASA/TPU, ne remplace pas le pilote CFS compilé et
ne touche ni au Z, ni au mesh, ni à la pression d'avance, ni à l'ironing, ni au
nettoyage de buse.
