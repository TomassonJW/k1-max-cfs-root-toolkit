# Résultat

Statut actuel : `OFFLINE_CORRECTED_AND_TESTED_WAITING_FOR_T1A_AND_EXACT_PHYSICAL_GO`.

Le candidat privé est dérivé du G-code physique déjà qualifié. Sa différence
est uniquement la fin sûre. La stabilisation n'est plus placée dans le fichier
d'impression : le pilote l'exécute avant de créer le jeton humain, dans cet
ordre exact :

- `M140 S55` ;
- `M190 S55` ;
- `G4 P200000` ;
- `M140 S0` ;
- confirmation consommable « buse nettoyée » ;
- départ unique du fichier.

Cette correction évite que le jeton de cinq minutes expire pendant la montée
du plateau et les `200 s`. Elle normalise aussi un ancien état `complete` par
`SDCARD_RESET_FILE` avant tout chauffage, uniquement si nécessaire.

Le vérificateur du candidat, le plan hors imprimante et les sept tests ciblés
sont verts.
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

Une lecture fraîche de reprise sous la capture
`20260829-resume-read-only-z-thermal-preflight` a été refusée avant tout effet
avec `t1a_route_not_unique`. Elle confirme que le redémarrage a effacé la route
logique et que `T1A` doit être rechargé puis relu avant tout transfert ou essai.
