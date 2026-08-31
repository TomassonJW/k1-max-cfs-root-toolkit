# ADR-039 — Activation du cycle stock-derived et exclusion persistante d'auto_refill

## Statut

Acceptée et implémentée hors effet. Le candidat de pose active a obtenu son
préflight réel en lecture seule ; la pose n'est pas encore exécutée. Elle ne
lancera aucun cycle. Le premier bouton physique restera une gate caméra séparée.

## Contexte

Les composants stock-derived sont installés avec `enabled=false`. Le premier
essai direct a aussi montré que le firmware remet `box.auto_refill` à `1` au
redémarrage. Activer le propriétaire direct sans résoudre ce point laisse soit
deux propriétaires concurrents, soit une gate qui se referme au boot.

Le cycle final doit en outre survivre à un restart Moonraker sans rejouer un
effet incertain, terminer toute géométrie avant filament, commander le cutter
avant retrait, purger dans le bac, décrocher la boule, exiger la caméra et
prendre lui-même le roulement vers une bobine strictement identique.

La trace constructeur réelle
`inventory/raw/g3-production/20260819-215124-long/20260819-215124-long.raw.txt`
qualifie le déclenchement utile : `filament_sensor_2` émet un runout, le print
est mis en pause, le dernier segment avance de `30 mm`, puis
`BOX_CHECK_MATERIAL_REFILL` est appelé. Elle montre aussi le défaut à supprimer :
la cible G-code `195 °C` est abaissée à `140 °C`, puis remplacée par `220 °C`
pendant la relève stock.

## Options

1. Conserver le remplacement stock et déléguer les runouts au firmware.
   Refusé : températures, géométrie et reprise restent opaques.
2. Modifier directement l'état interne du binaire `box_wrapper`.
   Refusé : attribut non contractuel et non testable hors imprimante.
3. Capturer seulement le petit handler stock déjà qualifié
   `BOX_ENABLE_AUTO_REFILL`, fermer sa surface publique, puis l'appeler une fois
   au boot pour imposer `0`. Retenue.

## Décision

- Un composant Klipper `k1_control_cfs_startup_exclusion` est chargé juste
  avant le propriétaire direct. Il capture le handler stock de politique,
  puis le propriétaire direct bloque publiquement toutes les commandes
  `BOX_*` d'effet.
- À `klippy:ready`, le composant appelle au plus une fois le handler privé avec
  `ENABLE=0`, vérifie `box.auto_refill == 0`, `t_command == ""` et les deux CFS
  connectés. Il ne chauffe, ne bouge et n'envoie aucune trame CFS.
- Après l'exclusion générale, un verrou runout remplace uniquement le bloqueur
  public de `BOX_CHECK_MATERIAL_REFILL`. Le handler stock original reste
  inaccessible. Ce nouveau point d'entrée ne produit aucun effet : il mémorise
  un numéro d'événement monotone, la route et la température G-code sauvegardée.
- Un retrait intentionnel désarme ce verrou et désactive les deux capteurs avant
  le cutter. Ils sont réactivés et le verrou réarmé seulement après preuve du
  nouveau chargement. Un changement volontaire ne peut donc pas être confondu
  avec une fin de bobine.
- Tant que cette installation active existe, la valeur précédente logique du
  cycle est `0`, pas `1`. Le roulement de bobine est entièrement possédé par
  K1 Control. Un rollback redémarre la configuration stock, qui retrouve sa
  politique normale.
- Le composant Moonraker persiste chaque ticket **avant** son premier effet.
  Un ticket `claimed` retrouvé après restart devient `uncertain` et n'est
  jamais rejoué automatiquement.
- L'inventaire de bobines est explicite et approuvé par l'utilisateur. Le
  groupe `same_material` du firmware ne suffit pas : un spare doit être unique
  et identique sur référence, matière, couleur, diamètre et recette thermique.
- Une vraie bobine vide ne repasse pas au cutter : après preuve que les deux
  capteurs sont libres, la route épuisée est libérée logiquement, sans moteur,
  puis l'unique spare est chargé et purgé à la température G-code sauvegardée.
  Le cutter reste obligatoire pour un changement volontaire ou une fin normale.
- S'il n'existe pas exactement un spare strict, aucune bobine n'est essayée :
  le print est fermé sans cutter, la tête est garée, les chauffes et ventilateurs
  sont coupés et les moteurs sont libérés.
- Les commandes G-code du print ne possèdent ni home, ni mesh, ni offset, ni
  chargement/retrait. Le départ est ouvert seulement après les deux preuves
  caméra de purge/décrochage et de ligne d'amorce.
- La pose d'activation s'arrête en `idle`, sans fichier sélectionné et sans
  effet filament. Le premier `begin` reste une gate physique distincte.

## Conséquences

- Le firmware ne peut plus reprendre silencieusement un mouvement filament
  pendant que K1 Control est actif.
- Le remplacement automatique entre bobines identiques reste disponible et
  passe par pause, preuve de fin réelle, libération logique sans cutter,
  chargement direct, purge, caméra et reprise du contexte exact.
- L'activation impose un ordre de sections Klipper stable et vérifié.
- Une panne après revendication d'un ticket demande une décision de reprise ;
  aucun retry automatique n'est permis.
- Une panne entre l'avance constructeur des `30 mm` et la capture du nouvel
  événement reste volontairement fermée : le print demeure en pause et exige
  une reprise humaine. Cette fenêtre sera vérifiée pendant l'essai physique ;
  elle n'autorise jamais une relève déduite des seuls états de capteurs.

## Alternatives refusées

- Réactiver `BOX_CHECK_MATERIAL_REFILL` ou `BOX_START_PRINT`.
- Déduire une fin de bobine d'un simple capteur à `false`, sans événement
  runout possédé.
- Considérer matière/couleur seules comme identité suffisante.
- Relancer un ticket après timeout ou restart.
- Refaire un Z ou un mesh après chargement.
