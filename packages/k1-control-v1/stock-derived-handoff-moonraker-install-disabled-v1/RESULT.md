# Résultat

État courant : pose froide désactivée close `OK` sous la capture
`20260831-173114-g4-k1-control-stock-derived-handoff-moonraker-install-disabled-v1`.

- Les `12/12` scénarios du handoff et du composant Moonraker sont verts.
- Les `14/14` scénarios des primitives Klipper et les `19/19` scénarios du
  cœur persistant restent verts, soit `45/45` sur la chaîne appelée par cette
  pose.
- Le plan du déployeur, ses empreintes locales et sa syntaxe PowerShell sont
  verts.
- La base K1 a été lue une fois sans effet ; les deux configurations futures et
  les six destinations sont absentes.
- Aucune chauffe, aucun mouvement, aucune extrusion, aucune trame CFS et aucun
  redémarrage n'ont été produits pendant la préparation.
- La pose a ensuite ajouté les six fichiers, les deux includes et la section
  Moonraker, redémarré seulement le Moonraker dédié et Klipper, puis remis le
  même `11 × 11`.
- La validation intégrée et une validation indépendante confirment les trois
  composants `enabled=false`, zéro commande ou demande d'effet, aucun fichier
  d'état et six endpoints Moonraker refusés.
- L'état final est `ready/standby`, chauffes zéro, axes libérés, aucune route
  CFS, deux CFS connectés, Z `-0,04` et meilleur `11 × 11` actif.
- L'activation et l'essai physique restent deux étapes séparées ; cette
  révision ne peut pas être activée par une simple modification de config.
