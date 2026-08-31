# Résultat — installation désactivée V1

Statut : **INSTALLED_VALIDATED_DISABLED_ZERO_CFS_FRAME**

Le composant Klipper réel est installé sur la K1 sous la capture
`20260831-123137-g4-k1-control-cfs-direct-owner-install-disabled-v1`. Les
`16/16` scénarios locaux, la validation intégrée à la pose et deux validations
indépendantes prouvent notamment :

- l'état désactivé sans transport ni trame ;
- le refus des trois entrées d'effet avant leurs arguments ;
- la conservation intacte des commandes stock quand le composant est désactivé ;
- leur remplacement borné quand une simulation active le propriétaire ;
- le refus si l'auto-remplacement stock n'est pas à zéro ;
- le refus si une commande stock est active ou si un des deux CFS manque ;
- le chargement simulé par le coeur `24/24` sans chauffe, géométrie, mesh ou purge ;
- le retrait simulé avec une seule traction locale exacte et `M400` avant la
  seconde phase CFS.

La pose a ajouté les six fichiers exacts et l'include, redémarré Klipper une
fois, puis remis `k1_p001_t055_r001_n11x11`. Elle n'a produit aucune chauffe,
aucun mouvement, aucune extrusion, aucun effet filament et aucune trame CFS.

Une première tentative s'est arrêtée avant la copie du premier candidat parce
que le client Windows cherchait un serveur SFTP absent de la K1. Le rollback
automatique a restauré et revalidé la base exacte. La reprise séparée a forcé le
mode SCP compatible et s'est terminée normalement.

L'état final est `ready/standby`, cibles zéro, axes libérés, Z accepté
`−0,04 mm`, `11 × 11` actif, `T1/T2` connectés et aucune route logique. Le
propriétaire publie `enabled=false`, `phase=disabled`, transport non pris,
commandes stock non remplacées et `frames_sent_count=0`.

## Vérifications de clôture

- vérificateur du paquet : `16/16` ;
- tests ciblés de la pose désactivée : `5/5` ;
- moteur direct source : `24/24` ;
- JSON et script PowerShell modifiés : valides ;
- suite globale : `842` tests exécutés, `825` verts, `3` ignorés et `14` KO
  connus dans d'anciens contrats non réalignés, dont un import `pytest` absent
  du Python système. Les vérifications ciblées de cette gate restent vertes.

La prochaine action utile est une qualification physique unique `T1A` du
chargement et du retrait directs. Elle reste une nouvelle gate : l'activation,
la chauffe et toute trame filament sont encore interdites.
