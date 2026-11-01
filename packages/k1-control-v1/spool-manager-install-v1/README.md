# Spool manager install V1 - pose du gestionnaire de bobines

Statut : **préparé hors imprimante, non posé**. ADR-075, document 102.

- `remote_install.py` : relevé, préflight, pose, validation et retour arrière.
  Le repos est prouvé par deux lectures identiques de Klipper, avant l'arrêt et
  à la fin. Aucun G-code, chauffe, mouvement, écriture CFS, changement de
  `printer.cfg` ni redémarrage de Klipper.
- `build_manifest.py` : écrit `manifest.json` avec les douze fichiers (quatre
  composants, quatre pages Bobines remplacées, quatre nouvelles), la section
  `[kctrl_spools]` de `moonraker.conf`, le bloc de la passerelle, le budget
  mémoire et les fichiers épinglés.
- `deploy.py` : vérifie chaque fichier contre le manifeste, envoie l'installateur
  par `ssh k1max-root python3 -` et range le reçu dans `inventory/raw/`, hors
  Git.

Déroulé :

1. `survey`, en lecture seule au repos : empreintes de `moonraker.conf` et de
   `nginx-active.conf` avant et après insertion, fichiers à épingler. Les
   recopier dans `SURVEY` de `build_manifest.py` puis reconstruire le
   manifeste ; d'ici là, tout autre mode est refusé.
2. `preflight` : tout est vérifié sans rien écrire, dont l'import réel des
   quatre composants dans le Python de Moonraker et la base matériaux.
3. `install`, verrou de la machine pris, repos revérifié juste avant, Thomas
   présent : sauvegarde, arrêt du Moonraker de K1 Control, pose, `nginx -t` puis
   rechargement de la passerelle, redémarrage. Ensuite : composant chargé, aucun
   nouvel avertissement, bibliothèque saine, pages et API servies par la
   passerelle, Moonraker sous 45 Mio, au moins 70 Mio libres, swap +8 Mio au
   plus. Le moindre écart remet tout en place.
4. `validate` relit le tout. `rollback`, au repos, remet les fichiers exacts,
   range l'état des bobines dans la sauvegarde et redémarre.

Seuls le Moonraker de K1 Control et la passerelle sont touchés. Le bloc de la
passerelle persiste : `S57k1_control_gateway` ne régénère pas
`nginx-active.conf`. Après une nouvelle version de K1 Control, recopier
composants, pages et section.

Après un retour arrière ou un échec remis en place, la sauvegarde est rangée
sous un nom daté. `ROLLBACK_INCOMPLETE`, `INSTALL_FAILED_RECOVERY_INCOMPLETE` et
`INSTALL_STOPPED_NOT_AT_REST` la laissent en place. Dans ce dernier cas, la K1 a
quitté le repos après l'arrêt : plus aucun service n'est touché, `validate` ou
`rollback` se lance quand elle est revenue au repos.

La pose ferme les préflights et retours arrière des paquets qui épinglent les
anciennes pages : `end-overlap-v2`, `end-rewind-confirm-v3`,
`end-separated-v1`, `retained-start-v1` et `end-after-refill-install-disabled-v1`.

Validation : **125 tests ciblés verts** (`tests/test_spool_manager_install_v1.py`),
avec un faux Klipper, de faux services, un faux Moonraker et une fausse
passerelle dans un arbre temporaire, plus l'import réel des quatre composants.
**Pas de pose sans le verrou de la machine.**
