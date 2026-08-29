# Résultat — BEST-CURRENT-MESH-RESTORE-AFTER-POWER-CYCLE-V1

Statut actuel : `OFFLINE_PREPARED_AND_TESTED_WAITING_FOR_T1A_REENGAGEMENT_AND_EXACT_LIVE_GATE`.

Le paquet corrige quatre défauts de l'ancienne gate historique :

- il épingle les empreintes réellement installées, dont le propriétaire R2 ;
- il accepte le profil `default` observé après extinction ;
- il exige et conserve la route logique unique `T1A` sans action CFS ;
- son retour de sécurité restaure le profil exact présent avant l'essai au lieu
  de forcer systématiquement le `6 × 6`.

Aucune connexion K1, commande G-code, chauffe, mouvement, extrusion, action CFS,
écriture distante ou relance de service n'a eu lieu pendant la préparation.

Prochaine gate : après réengagement stock de `T1A` et nettoyage visible de la
buse, autoriser exactement
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-AFTER-POWER-CYCLE-V1` sur le commit
figé. Cette gate ne couvre toujours pas l'essai chaud de deux couches.
