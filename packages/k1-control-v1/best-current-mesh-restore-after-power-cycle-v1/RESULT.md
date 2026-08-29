# Résultat — BEST-CURRENT-MESH-RESTORE-AFTER-POWER-CYCLE-V1

Statut actuel : `LIVE_PREFLIGHT_KO_AXES_STILL_HOMED_NO_EFFECT`.

Le paquet corrige quatre défauts de l'ancienne gate historique :

- il épingle les empreintes réellement installées, dont le propriétaire R2 ;
- il accepte le profil `default` observé après extinction ;
- il exige et conserve la route logique unique `T1A` sans action CFS ;
- son retour de sécurité restaure le profil exact présent avant l'essai au lieu
  de forcer systématiquement le `6 × 6`.

Aucune commande G-code, chauffe, mouvement, extrusion, action CFS, écriture
distante ou relance de service n'a eu lieu pendant la préparation.

Le préflight en lecture seule du 29 août a joint la K1 puis s'est arrêté sur
`axes_still_homed`, avant même de pouvoir accepter la route logique `T1A`. Il
n'a produit aucun effet sur l'imprimante. La prochaine tentative exige donc un
redémarrage électrique humain qui efface la référence des axes, suivi d'une
unique action stock `Extrusion T1A` pour recréer explicitement la route logique.

Prochaine gate : après le nouveau préflight vert, autoriser exactement
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-AFTER-POWER-CYCLE-V1` sur le commit
figé. Cette gate ne couvre toujours pas l'essai chaud de deux couches.
