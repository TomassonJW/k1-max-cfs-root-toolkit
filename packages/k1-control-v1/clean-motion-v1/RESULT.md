# Résultat actuel

Statut : **checkpoint D1 techniquement OK ; verdict humain attendu ; D2 non
lancé**.

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
physique prouvée de la brosse. Thomas a confirmé le plateau libre, la brosse
visible, la buse observable et l'arrêt immédiat possible. Les limites exactes,
la hauteur libre, le premier contact et les directions sûres seront encore
qualifiés par checkpoints. Le préalable corrigé du mesh est vert : le meilleur
profil observé `k1_p001_t055_r001_n11x11` est actif et a été confirmé par deux
lectures indépendantes. Tous les profils actuels ont des défauts de bord ; aucun
n'est qualifié robuste.

Vérifications locales actuelles : `22/22` tests ciblés CLEAN-MOTION verts,
suite complète de `535` tests dont `532` verts et `3` ignorés connus, interface
de l'éditeur `6/6` verte et `62/62` scripts PowerShell relus sans erreur.

Le préflight frais a obtenu `CHECKPOINT_C_PREFLIGHT_OK`. Une seule séquence a
ensuite référencé XYZ, rechargé le `11 × 11`, commandé `Z=50 mm` et attendu la
fin. Le premier validateur a comparé à tort la position physique compensée
`50,23 mm` à la consigne G-code et a rendu un faux KO. La récupération n'a fait
aucun mouvement : chauffes coupées et `11 × 11` rechargé.

La validation corrigée, strictement en lecture seule, observe la position
G-code `50,00 mm`, la position physique compensée `50,23 mm`, XYZ référencés,
le `11 × 11` exact actif, les cibles à zéro, les deux CFS sans route et les
configurations inchangées. Résultat technique :
`CHECKPOINT_C_TECHNICAL_OK_AWAITING_HUMAN_VERDICT`.

Thomas a ensuite confirmé `CHECKPOINT C OK`. Cette validation clôt le
checkpoint C sans le rejouer. Elle permet de préparer le prochain rapprochement
lent, qui conservera son propre préflight et son observation humaine.

Le préflight D1 a obtenu `D1_PREFLIGHT_OK`. Le mouvement unique a commandé
`G1 X81 Y280 Z50 F1200`, soit un point encore situé `24,5 mm` avant la zone Y
stock déclarée. L'état final est `standby`, consigne G-code
`X81 Y280 Z50`, position physique compensée `X81 Y280 Z50,23`, chauffes à zéro,
aucune route CFS, configurations inchangées et `11 × 11` exact toujours actif.
Résultat : `D1_TECHNICAL_OK_AWAITING_HUMAN_VERDICT`.

Le mouvement D1 ne sera pas rejoué. D2 reste fermé jusqu'au verdict visuel
explicite de Thomas sur D1.
