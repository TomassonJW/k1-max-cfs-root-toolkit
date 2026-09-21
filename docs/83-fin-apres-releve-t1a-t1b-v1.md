# 83 — Fin après relève T1A → T1B : ancienne bobine retenue, coupe refusée, retrait poursuivi

Date de l'audit : 21 septembre 2026. Diagnostic en lecture seule demandé par Thomas ; correction proposée, non implémentée et non posée. Révision examinée : `be7d34c`.

## Conclusion

Le fichier `10h37m` passe réellement de T1A à T1B le **18 septembre à 16:29:48**, puis atteint `END_PRINT` à **19:50:07**. Notre fin d'impression choisit encore T1A dans `kctrl_tool_change.last`. Le CFS refuse aussi la coupe : `if_in_resume: True`, puis `In resume, can not cut material now`. Notre macro continue malgré cela et demande le rembobinage de T1A. Le CFS répond `RETRUDE_ERR4`, puis la tête reste chargée. La fin constructeur est appelée malgré cet échec. Ce n'est donc pas une simple mauvaise déclaration de matière ni la preuve d'une panne mécanique.

Deux défauts de notre séquence sont démontrés : l'emplacement mémorisé ne suit pas la relève stock ; appeler la coupe ne prouve pas qu'elle a eu lieu. Remplacer seulement T1A par T1B laisserait le second défaut intact.

Le fichier est arrivé à sa commande de fin : cela établit la fin du parcours G-code, pas la qualité physique des dernières couches. Thomas confirme avoir terminé manuellement et rembobiné **T1B** (T2B était une faute de frappe).

## Preuves et chronologie

Les heures ci-dessous sont celles de la K1, Europe/Paris. Captures privées ignorées par Git : `inventory/raw/20260921-cfs-end-incident/`.

| Moment | Observation |
| --- | --- |
| 17 septembre 20:52:26 → 18 septembre 07:10:21 | Le fichier `12h34m` est enregistré `completed`. À 07:09:45, notre fin nomme T1A ; à 07:10:11, le capteur de tête est vide. |
| 18 septembre 09:28 et 10:22 | Deux essais du `10h37m`, annulé puis en erreur de chargement (`key836`). Le départ de 10:22 est arrêté avant la ligne d'amorce par ADR-066. |
| 18 septembre 10:38:08 | Départ du dernier `10h37m`. Les commandes de 10:40 et 10:41 résolvent encore T1A → T1A. |
| 16:29:41 | `filament_sensor_2 pause`, suspension à la position de fichier 26 531 551. |
| 16:29:48,155 | `material_auto_refill: BOX_MODIFY_TN T1A -> T1B`. |
| 16:29:48,185 | Le module stock résout explicitement `Tnn_map[T1A] = T1B`. Il est appelé depuis `gcode:<lambda>`, contrairement aux changements enveloppés tracés depuis `kctrl_tool_change:run_stock`. |
| 16:30:20 | Chargement T1B : `extrude_process_stage7 ret: True,OK`. |
| 16:32:18 | Reprise à la même position de fichier ; T1A logique résout encore T1B physique. |
| 19:50:07,155 | `K1 Control: retrait (fin) de T1A (dernier changement d'outil) : coupe, puis rembobinage`. |
| 19:50:07,214–216 | `if_in_resume: True`, puis `In resume, can not cut material now`. La coupe est refusée, pas confirmée. |
| 19:50:12,237 | Trame de retrait `01 05 ff 11 01 01` : CFS 1, commande `0x11`, masque de case `0x01` = A, déclenchement 1. Le décodeur local `cfs-direct-owner-offline-v1/protocol.py` fixe A=1 et B=2. |
| 19:50:12,255–278 | Réponse `RETRUDE_ERR4[0x16]`, erreur `key839`, puis `error: printing to pause`. Le message d'erreur rapporte `[1, B]` alors que la demande précédente visait A : ne pas prendre le libellé d'erreur comme preuve de la case commandée. |
| 19:50:24,423 | Notre contrôle dit que la tête contient encore du filament. |
| 19:50:24,435 | `box_end` s'exécute néanmoins, avec `last_err=key839`. |
| 19:50:25,977 | La fin stock remet la correspondance T1A → T1A. Une table lue après l'incident ne permet plus de reconstituer la relève. |
| 19:50:33 | Sortie du traitement G-code à la position 38 073 844, proche de la fin du fichier de 38 098 793 octets (le reste comprend la configuration Orca). |
| 21 septembre 09:19:48–09:21:27 | Commandes manuelles enregistrées : `BOX_CUT_MATERIAL`, puis `BOX_RETRUDE_MATERIAL`, deux réponses de retrait. Thomas identifie la bobine comme T1B. |
| 09:22:37–40 | L'annulation constate la tête déjà vide ; l'historique clôt le travail `cancelled`. |

L'historique retient 9 h 06 min 59 s de temps d'impression pour le dernier essai ; le temps total jusqu'à l'annulation du 21 dépasse 70 h. Ce total ne signifie pas que la machine a imprimé pendant trois jours.

La relève observée appartient bien au dernier fichier `10h37m`, pas seulement à une impression antérieure. L'ancien `12h34m` n'est plus présent sous le chemin exact fourni : son historique et sa fin au journal ont été lus, son contenu G-code n'a pas été vérifié. La capture `context.txt` est partielle à cause de cette absence, après acquisition réussie des états, des événements et des limites du `10h37m`.

## Mécanisme dans le code installé

Les SHA-256 de ces trois fichiers distants correspondent exactement aux fichiers du dépôt :

- `k1-control-owned-start-print-v2.cfg` : `f8562cbf36116e977c46f914e1af77ba16b384297ffaf0c58009ad4ea9b86503` ;
- `kctrl_tool_change.py` : `a203b0ec4bcbf42508daa5d2905542f6fc890740c7d1cc08bb5936d01b34b414` ;
- `kctrl_slot_map.py` : `041de62865702148ec796ea9a502a9067bf11252ffd678ea8886732c48e8c134`.

`_KCTRL_UNLOAD` privilégie `kctrl_tool_change.last.slot`, puis `START_PRINT.active_tool`. Elle ne relit ni la route engagée dans `box`, ni la correspondance modifiée par la relève. `KctrlToolChange.run_stock` ne met `last` à jour que lorsqu'il est traversé. Le passage stock de 16:29 ne le traverse pas ; la lecture du 21 trouve encore `last={tool:T0, outcome:done, slot:T1A, temp:200}` et `active_tool=T1A`.

Deux autres faiblesses de ce choix ont été reproduites : une ancienne valeur peut gagner sur le départ d'un nouveau travail, et un changement `paused_by_firmware` ou `empty` est accepté comme source de bobine alors qu'il ne prouve pas son engagement.

Après `BOX_CUT_MATERIAL`, la macro ne vérifie aucun résultat de coupe. `M400` termine les mouvements en attente mais ne transforme pas un refus stock en coupe réussie. `_KCTRL_UNLOAD_CHECK` ne fait qu'afficher un message ; `END_PRINT_NO_M84` tourne dans tous les cas.

Le `pause_resume.py` lu sur la K1 met `virtual_sdcard.do_resume_status=True` à la reprise. `virtual_sdcard.py` le remet à False après la sortie du traitement du fichier (ligne 1132). Cela explique une piste précise pour le refus tardif « in resume ». **Le prédicat exact du module compilé `if_in_resume` reste à qualifier** : ne pas affirmer qu'un simple `CLEAR_PAUSE` le résout, ni forcer arbitrairement un attribut interne. Les chaînes historiques du binaire confirment l'existence de la méthode et du message, pas son implémentation actuelle.

## Correction proposée

Voir [ADR-069 proposée](adr/ADR-069-fin-cfs-apres-releve-route-fraiche-et-coupe-confirmee.md).

1. Résoudre la bobine effectivement engagée juste avant la fin, avant toute remise à zéro stock. Garder séparés le filament logique du fichier et la case physique. Une route absente ou contradictoire arrête la partie filament avec un message utile, sans choisir la première bobine ni reprendre un cache ancien.
2. Qualifier la sortie du contexte de reprise, puis exiger une coupe réellement terminée avant un unique rembobinage de la case résolue. Si nécessaire, différer la finalisation après la sortie du traitement G-code, avec attente bornée. Ne pas contourner aveuglément le refus du firmware.
3. Relire l'état après chaque étape. Si coupe ou retrait échoue, couper les chauffes et annoncer une fin incomplète ; ne pas appeler automatiquement `BOX_END` tête chargée. Séparer les opérations de fin sans filament des opérations stock qui peuvent extruder. Conserver une annulation utilisable et les états d'erreur utiles au diagnostic.

La relève automatique reste disponible. La désactiver supprimerait la continuité demandée par Thomas et masquerait seulement le cas déclencheur.

## Vérifications et limites

- Collecte uniquement GET, lectures de fichiers et empreintes ; aucun G-code envoyé, aucun fichier distant écrit, aucun service redémarré.
- Journal du 18 lu au repos par blocs de 32 Mio, `nice -n 19`, lignes bornées avant filtrage ; contexte complémentaire du 18 et fenêtre de récupération du 21. Aucune lecture `tail -n N` du journal distant.
- 21 assertions existantes de fin d'impression : **21/21**, exécutées directement avec leur module de rendu Jinja. Elles ne couvrent pas la relève ni le refus de coupe. Le lanceur pytest est absent du Python accessible ; la suite `test_kctrl_tool_change_v1.py` n'a pas été exécutée dans cet audit.
- Trois reproductions synthétiques du mauvais choix : **3/3 défauts reproduits**, sans connexion K1. Cela valide le diagnostic, pas un correctif.
- Sept tests unittest de bornage des lectures : **7/7**.
- Six empreintes de configuration/modules identiques avant/après, dont les trois fichiers ci-dessus et `printer.cfg`, `box.cfg`, `gcode_macro.cfg`.
- État final observé : `cancelled`, aucune pause active, chauffes à zéro, axes libérés, capteur de tête `filament_sensor_2=false`. L'autre capteur reste vrai : ne pas convertir cela en preuve visuelle de tout le chemin filament. Aucun geste physique supplémentaire n'a été demandé.
- Ni photo de l'écran d'erreur ni preuve caméra historique ; la qualité des dernières couches et le texte précis affiché ne sont pas établis. Le journal donne `key839 [1,B]`, tandis que notre macro et la trame de retrait visent A.

## Suite

Construire et vérifier hors imprimante le correctif de l'ADR-069, avec essais synthétiques de relève, reprise, changement raté, ancien travail et retrait incomplet. Avant une pose, résoudre le prédicat `if_in_resume` et la preuve de coupe sur le firmware exact, préparer sauvegarde et retour arrière. La présente mission autorise le diagnostic et la proposition ; elle ne qualifie aucune nouvelle séquence physique.
