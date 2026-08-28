# Résultat

Statut actuel : `PREFLIGHT_AND_UPLOAD_OK_AWAITING_HUMAN_PHYSICAL_CHECKPOINT`.

Le candidat privé est dérivé du G-code physique déjà qualifié. La seule
différence fonctionnelle avant `KCTRL_JOB_BEGIN` est l'ajout exact de :

- `M140 S55` ;
- `M190 S55` ;
- `G4 P200000`.

Le vérificateur du candidat est vert et les six tests ciblés sont verts.
L'essai conserve `T1A`, ne permet aucun réglage Z avant le verdict visuel et
n'autorise aucun retry automatique.

Le premier préflight a bloqué sans effet sur le statut terminal sûr `complete`,
puis une double lecture seule a prouvé l'état stable. Le garde corrigé accepte
désormais seulement `standby` sans fichier ou `complete` avec fichier. Le
préflight R2 est vert. Le G-code a été envoyé sous un nouveau nom et son
empreinte distante est exacte. Aucune chauffe, extrusion, mesure, impression
ou action CFS n'a eu lieu.

Le prochain effet reste bloqué jusqu'à la confirmation humaine du plateau
libre, de la buse nettoyée et de la possibilité d'arrêter immédiatement.
