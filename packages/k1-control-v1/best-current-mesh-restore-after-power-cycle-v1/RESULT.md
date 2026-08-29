# Résultat — BEST-CURRENT-MESH-RESTORE-AFTER-POWER-CYCLE-V1

Statut actuel : `R2_OFFLINE_READY_AFTER_DIAGNOSTIC_SAFE_PARK_PROOF`.

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

Le préflight a depuis été renforcé hors imprimante : lors d'un prochain refus,
il restituera la projection sûre complète capturée avant la première garde en
échec. Aucune condition n'est retirée et aucune nouvelle action distante n'est
ajoutée.

La projection fraîche après `Extrusion T1A` montre une route unique `T1A`, le
profil `default`, les chauffes à zéro et une tête parquée à
`X210 / Y291,5 / Z66,8915`. R2 accepte désormais uniquement ce type de parc
haut borné, ou des axes non référencés. Le chargement du mesh reste sans
mouvement ; toutes les autres positions référencées sont refusées.

Prochaine gate : après le nouveau préflight R2 vert, autoriser exactement
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-AFTER-POWER-CYCLE-V1-R2` sur le commit
figé. Cette gate ne couvre toujours pas l'essai chaud de deux couches.
