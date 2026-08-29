# Résultat

Statut actuel : `BLOCKED_CORRECTIVE_R2_REQUIRED_BEFORE_NEW_UPLOAD`.

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
préflight R2 était vert. Après le retour humain sur la mauvaise fin et le filet
de purge, ce fichier a été invalidé puis supprimé de la K1 sous contrôle de son
empreinte exacte.

Le candidat local R2 ajoute maintenant la fin sûre `Z50 / X203 Y273 / M84`,
mais il reste bloqué tant que la macro de purge corrigée n'est pas posée et que
son trajet inversé vers `X5 Y20` n'a pas reçu de verdict humain.
