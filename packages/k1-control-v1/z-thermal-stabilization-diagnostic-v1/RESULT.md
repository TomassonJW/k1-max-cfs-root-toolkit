# Résultat

Statut actuel : `OFFLINE_READY_WAITING_FOR_T1A_AND_EXACT_PHYSICAL_GO`.

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

Le propriétaire R2 est maintenant installé et validé à froid. Sa purge suit le
tracé constructeur `X0,1/X0,4`, `Y20..180`, à `F3000`, avec remontée `Z5`.
Le candidat local ajoute la fin sûre `Z50 / X203 Y273 / M84`.

Le pilote de l'essai attend désormais l'empreinte R2 exacte. Son arrêt
d'urgence baisse aussi le plateau à `Z50` et parque la tête à `X203 Y273` avant
de libérer les axes lorsqu'ils sont encore référencés. La validation terminale
exige réellement cette position, en plus des chauffes zéro et des axes libérés.

Aucun fichier n'a été renvoyé sur la K1. L'essai attend le rechargement et la
relecture de `T1A`, puis une autorisation physique distincte avec Thomas présent.
