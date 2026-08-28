# Résultat actuel

Statut : **observateur qualifié ; `EMPTY_LOAD_T1A` et le départ possédé
`KEEP_CORRECT_T1A` clos OK ; campagne CFS à `2/4`**.

L'observateur ne déclenche aucune action et ne remplace jamais le verdict de
Thomas. Le premier chargement physique est toutefois maintenant qualifié par
les deux preuves complémentaires.

La capture `20260828-goal3-cfs-empty-load-t1a-r2` contient 240 lectures. Elle a
vu une seule transition de route vide vers `T1A`, une cible de buse à `220 °C`,
les deux capteurs passer dans l'état attendu, puis les deux cibles revenir à
zéro. Les configurations, le profil `11 × 11` et le Z `−0,04 mm` sont restés
inchangés. Thomas a confirmé une purge visible sans bruit anormal ni blocage et
`T1A` reste engagé. `EMPTY_LOAD_T1A` est donc `PASSED`.

Les `8/8` scénarios synthétiques sont verts. La baseline réelle contient huit
lectures stables sur cinq secondes : aucune route, aucune commande CFS, cibles
zéro, deux unités connectées, profil `11 × 11`, Z `−0,04 mm` et configurations
inchangées. Aucun G-code, mouvement, chauffage, fichier distant ou service.

Une première fenêtre réelle `EMPTY_LOAD` de 120 secondes destinée à `T1A` n'a
vu aucune action stock : 160 lectures, route toujours vide, aucune commande,
aucune chauffe et aucune transition. Thomas a ensuite confirmé qu'il n'avait
rien déclenché pendant cette fenêtre. Elle est donc classée non probante et ne
qualifie pas le chargement, sans indiquer un refus de l'interface.

Thomas a aussi confirmé que la dernière action réelle, pendant la préparation
manuelle du nettoyage, avait chargé puis retiré `T1A`. Le segment encore détecté
dans la tête est donc attribué explicitement à `T1A`. Le décideur accepte
maintenant un futur chargement de ce même `T1A`, mais bloque toujours si cette
origine n'est pas confirmée ou si la route demandée est différente.

Le manifeste physique fixe quatre checkpoints couvrant `T1A`, `T2C`,
la conservation du bon filament et le blocage d'une identité ambiguë. Son
vérificateur retourne encore `CFS_PHYSICAL_CAMPAIGN_READY_INCOMPLETE`, désormais
avec `2/4`.

Le décideur local est également prêt et testé. Une capture live fraîche de huit
lectures a retrouvé le segment détecté dans la tête, aucune route engagée,
cibles zéro et configurations inchangées. Le décideur renvoie
`BLOCK/SEGMENT_PRESENT_WITHOUT_UNIQUE_ROUTE` avec zéro effet. La confirmation
humaine d'absence d'effet reste nécessaire pour passer le quatrième checkpoint.

Le premier essai réel `KEEP_CORRECT_T1A` est clos KO avec arrêt sûr. `T1A` est
resté sélectionné sans transition pendant la capture, mais l'ancien préfixe
Orca `G28/T0/START_PRINT` a remplacé le profil `11 × 11` par `default` et la
capture s'est terminée pendant un `T0` encore actif, avant verdict de première
couche. Thomas a annulé depuis l'interface stock. Les chauffes sont revenues à
zéro, mais la dernière lecture avant extinction restait `cancelled`, sans route,
avec `T0` résiduel et mesh `default`. Aucun restart n'a été envoyé.

Le successeur possédé est clos sous la capture
`20260829-goal3-start-owner-physical-keep-correct-t1a-v1-run`. T1A n'a jamais
changé, aucune commande CFS n'a été active, la purge est confirmée et les deux
couches sont bonnes après intervention humaine à `−0,19 mm`. Le checkpoint CFS
passe et la campagne atteint `2/4`. Le Z accepté `−0,04 mm` n'est cependant pas
qualifié sans intervention ; la stabilisation thermique doit être isolée avant
la suite imprimée.

Un fichier corrigé `…PLA_4h6m` est présent sur la K1 mais n'a pas été lancé. Son
ordre vérifié retire les `G28/Tn` préalables et place
`KCTRL_PRODUCTION_ARM … X_COUNT=11 Y_COUNT=11` après `START_PRINT`. La reprise
doit commencer après démarrage à froid par une lecture seule fraîche ; elle ne
doit pas supposer que le cœur Klipper est fautif ni rejouer automatiquement.
