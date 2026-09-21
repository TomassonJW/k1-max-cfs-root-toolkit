# 90 — Fin T1B : coupe confirmée, retrait non confirmé

21 septembre 2026. Deuxième essai de prise, après retrait officiel et buse
nettoyée à nouveau par Thomas. Ce document remplace le statut « R2 préparé »
du document 89. **Le candidat de fin reste désactivé et non qualifié.**

## Départ et fin réellement observés

Aucun réglage moteur ou routine de chargement modifié. Une seule réponse
`full`, puis `middle`, sans relance/coupe de chargement. Thomas confirme de
nouveau purge au bac et boule décrochée. La pause du fichier est atteinte,
T1B engagé, courant 0,562 A et températures 55/200 °C. Le message externe de
ventilateur ne réapparaît pas : sa correction est prouvée par tests et rejeu,
pas par une occurrence ignorée pendant ce second essai.

| Heure K1 | Preuve |
|---|---|
| 19:05:16 | `RESUME_BASE` unique, reprise de T1A logique vers T1B déjà engagé ; la carte termine son fichier avant les effets de fin. |
| 19:05:20 | Contact cutter. |
| 19:05:21 | Retour cutter et déclenchement confirmés ; la phase suivante cible bien T1B. |
| 19:05:24 | Capteur cutter relâché ; tête repartie vers le bac pendant la commande de retrait. |
| 19:05:27 | Requête CFS `RETRUDE_PROCESS`, case B, phase 1. |
| 19:05:39,581 | Réponse CFS état zéro, commande retournée. |
| 19:05:39,589 | Contrôle immédiat : tête libre mais route encore B → `rewind_not_confirmed`, cibles zéro. |
| Ensuite | Observateur externe M112 ; sortie de Klipper ; retour exact désactivé et reprise logicielle en 52 s. |

La tête était déjà détectée libre **avant** l'arrêt. Le retour d'état zéro du
CFS et ce capteur ne prouvent pas seuls que toute la bobine avait fini de
rembobiner. L'état B peut être encore ancien ; l'arrêt immédiat a empêché de
mesurer son délai éventuel de mise à jour. Cette hypothèse reste ouverte.

## Pourquoi le départ du cutter vers le bac

La lecture statique du binaire exact chargé (`af630c02…`, contrôlé par le
préflight) identifie `cmd_retrude_material_with_tnn` à `0xf0734`. Son premier
appel d'action est `box_action.go_to_extrude_pos` (référence `0xf0948`), avant
la rétraction de l'extrudeur et les commandes de rembobinage CFS. Ce n'est donc
pas une primitive qui ne ferait que rembobiner le slot indiqué.

Le candidat appelle cette commande juste après la coupe. **Notre hypothèse
sur sa portée était fausse.** L'observation de Thomas et les positions
capturées concordent avec ce déplacement intégré. L'identification du mouvement
ne justifie pas de le conserver dans la séquence souhaitée. Une temporisation
supplémentaire ne suffirait pas à corriger cet ordre.

## Correction viable retenue pour la préparation

Voir [ADR-070](adr/ADR-070-retrait-cfs-separe-des-deplacements-de-fin.md).
Ne pas promouvoir `BOX_RETRUDE_MATERIAL_WITH_TNN` comme retrait isolé. Le
successeur doit séparer : coupe, dégagement local du levier, rétraction de
l'extrudeur et rembobinage CFS, preuve de fin avec délai borné d'actualisation,
puis seulement parc. Aucun déplacement vers le bac ni mouvement Z caché dans
le retrait. Les primitives de ce successeur doivent être identifiées et
revues sur le binaire exact avant toute exécution ; aucun transport nouveau
n'est inventé ni installé pendant cette mission.

Les tests doivent simuler une route restant B après le retour de la commande,
une libération différée, une absence persistante de libération, une autre route,
un état inconnu, une erreur et un moteur/effet incertain. Les tests actuels qui
mettent immédiatement le capteur et la route à vide ne couvrent pas cette
frontière. Conserver le refus sûr jusqu'à preuve de fin ; aucune relance.

## État final et contrainte physique

Configuration du candidat restaurée depuis la sauvegarde exacte R2. Lecture
indépendante : prêt/en attente, aucune pause, chauffes zéro, tête détectée libre,
deux CFS connectés sans route et commande vide. Le G-code R2 est supprimé
après contrôle de son hash. Les coordonnées logiques sont perdues au restart.

Thomas signale la tête au bac et interdit de relever le plateau. **Aucun
mouvement de tête/plateau, homing, chauffe ou effet filament n'est commandé
pour la récupération.** La caméra conserve le même parc au bac. Aucun geste
manuel supplémentaire n'est demandé à cette clôture ; ne pas assimiler le
capteur libre à une buse nettoyée ni les zéros logiques à la position réelle.

[Preuve nettoyée](../inventory/redacted/20260921-cfs-startup-probe-r2/result.json).
Captures privées : deux essais, caméra et séries temporelles, journaux bornés,
retours exacts, binaire et lecture statique. `27` tests ciblés du surveillant et
du collecteur sont verts ; les deux départs réussis ne résolvent pas le défaut
intermittent de première prise. La fin après relève réelle reste non validée.

Prochaine action : corriger hors imprimante le retrait et sa preuve de fin,
puis revoir le parcours physique avant un nouvel essai. GPT-5.6 Sol / high est
conseillé pour le binaire, les états asynchrones et les contraintes mécaniques ;
Sol / medium suffit à l'extraction de journaux, avec revue plus poussée requise
avant tout déploiement. Aucun nouvel essai complet identique n'est utile.
