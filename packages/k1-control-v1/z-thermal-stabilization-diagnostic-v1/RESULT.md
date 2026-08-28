# Résultat

Statut actuel : `CANDIDATE_PRIVATE_BUILD_AND_OFFLINE_VALIDATION_OK`.

Le candidat privé est dérivé du G-code physique déjà qualifié. La seule
différence fonctionnelle avant `KCTRL_JOB_BEGIN` est l'ajout exact de :

- `M140 S55` ;
- `M190 S55` ;
- `G4 P200000`.

Le vérificateur du candidat est vert et les cinq tests ciblés sont verts.
L'essai conserve `T1A`, ne permet aucun réglage Z avant le verdict visuel et
n'autorise aucun retry automatique.

Aucune connexion K1, chauffe, extrusion, mesure ou écriture distante n'est
encore produite par cette gate. Le prochain effet reste bloqué jusqu'au
préflight frais, à l'envoi contrôlé du fichier et à la confirmation humaine du
plateau libre et de la buse nettoyée.
