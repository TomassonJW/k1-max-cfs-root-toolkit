# Résultat actuel

Statut : **sources live qualifiées en lecture seule ; aucune commande
candidate ; aucun essai physique**.

La capture privée `20260827-clean-motion-v1-read-only-sources-v3` confirme :

- limites logiques : X `−2…306,5 mm`, Y `−0,5…307,5 mm`, Z `−10…305 mm` ;
- zone de nettoyage déclarée par le `prtouch_v2` stock : X `68…94 mm`,
  Y `304,5…306,5 mm` ;
- trajet nominal X configuré : `20 mm` ;
- delta Z stock déclaré : `−0,15 mm` ;
- `CX_NOZZLE_CLEAR`, `CX_ROUGH_G28`, `NOZZLE_CLEAR`, `ACCURATE_G28` et
  `ACCURATE_HOME_Z` sont réellement enregistrées ;
- le code complet des macros n'a pas été exporté ;
- aucune commande G-code, lecture ou écriture de fichier distant, chauffe,
  mouvement, service ou action CFS n'a eu lieu.

Ces valeurs décrivent la configuration logicielle stock, pas la position
physique prouvée de la brosse. Thomas doit encore confirmer visuellement ses
limites, la hauteur libre, le premier contact et les directions sûres. Aucune
commande de mouvement ne sera préparée avant ces faits humains. Le préalable
du mesh est désormais vert : le robuste `k1_p001_t055_r001_n06x06` est actif
et a été confirmé par deux lectures indépendantes. Il manque uniquement la
présence de Thomas devant la K1, le plateau libre, la brosse visible et les
verdicts humains prévus.

Vérifications locales : `11/11` tests ciblés verts, suite complète de `513`
tests dont `510` verts et `3` ignorés connus, collecteur compatible Python 3.8
et script PowerShell relu sans erreur.
