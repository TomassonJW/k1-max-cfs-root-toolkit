# Résultat hors imprimante

Le candidat `START-SEQUENCE-OWNER-V1` possède maintenant le seul chemin
`KEEP_CORRECT_T1A` :

- `T1A` doit être l'unique route engagée et aucune commande CFS ne doit être en
  cours ;
- le nettoyage est une confirmation humaine consommable une seule fois ;
- X/Y sont référencés pendant la chauffe ;
- `ACCURATE_G28` est appelé exactement une fois à `140/55 °C` ;
- le `11 × 11` et le Z accepté sont chargés et relus avant tout mouvement bas ;
- `T1A` n'est ni coupé, ni retiré, ni rechargé ;
- la cible de première couche `190 °C` est explicite ;
- la purge visible est effectuée sur le mesh et le Z armés ;
- aucun `START_PRINT`, brossage, `Tn`, `220 °C`, `BED_MESH_CALIBRATE` ou offset
  `+0,27 mm` n'est présent.

Vérification locale du 2026-08-28 :

- vérificateur structurel : `START_SEQUENCE_OWNER_V1_OFFLINE_OK` ;
- suite complète : `613` tests, `610` réussis, `3` ignorés connus ;
- connexion ou effet K1 : aucun.

Ce résultat ne qualifie ni la syntaxe Jinja exacte de la K1, ni les coordonnées
de purge, ni l'arrêt des chauffes après une panne Klipper inattendue. Ces trois
preuves, avec backup et rollback, sont obligatoires avant toute future demande
de pose.
