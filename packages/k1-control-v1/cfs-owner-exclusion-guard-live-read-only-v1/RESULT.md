# Résultat — validation live en lecture seule du garde d’exclusion CFS V1

Statut : `CLOSED_READ_ONLY_BLOCKED_CONNECTION_EPOCH_AND_EFFECTIVE_Z_SOURCE`

La capture privée `20260828-190631-g4-k1-control-cfs-owner-exclusion-guard-live-read-only-v1`
a exécuté exactement deux GET dans une seule session SSH. Le nettoyage a eu
lieu sur la K1 avant le retour local. Les deux états sont stables : imprimante
au repos, cibles à zéro, `T1/T2` connectés, aucune route engagée, commande CFS
vide, auto-remplacement stock à `1`, politique d’impression CFS à `1` et mesh
`k1_p001_t055_r001_n11x11`. Les trois empreintes de configuration sont
inchangées.

La gate reste fermée pour deux raisons. Les objets actuels ne fournissent aucune
époque de connexion capable de détecter une reconnexion invisible entre les
deux lectures. De plus, V1 a projeté `gcode_move.homing_origin[2]`, observé à
environ zéro, alors que le contrat du projet exige la valeur Z acceptée séparée
(`−0,04 mm` au dernier état qualifié). L’empreinte du stockage Z est stable,
mais sa valeur n’a pas été retournée ; elle ne peut donc pas être affirmée par
cette capture.

L’adaptateur pur a été appelé et a refusé l’entrée sur
`connection_epoch_invalid` et `effective_z_source_unqualified`. Le garde n’a
été ni importé ni appelé. Aucun G-code,
chauffage, mouvement, effet CFS, fichier distant, restart ou déploiement n’a eu
lieu. V1 ne doit pas être rejouée.

La suite correcte est
`G4-K1-CONTROL-CFS-OWNER-OBSERVABILITY-ADAPTER-OFFLINE-V2`, mission hors
imprimante distincte qui définit une époque de connexion observable et corrige
la projection du Z accepté avant toute nouvelle lecture live ou tout essai réel.
