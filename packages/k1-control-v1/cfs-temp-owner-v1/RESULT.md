# Résultat actuel

Statut : **observateur qualifié hors imprimante et baseline live en lecture
seule verte ; transitions physiques non commencées**.

Aucune exigence physique CFS n'est déclarée réussie par ce paquet. Il prépare
seulement une preuve fiable des futures actions manuelles, sans pouvoir les
déclencher ni remplacer le verdict de Thomas.

Les `8/8` scénarios synthétiques sont verts. La baseline réelle contient huit
lectures stables sur cinq secondes : aucune route, aucune commande CFS, cibles
zéro, deux unités connectées, profil `11 × 11`, Z `−0,04 mm` et configurations
inchangées. Aucun G-code, mouvement, chauffage, fichier distant ou service.

Une première fenêtre réelle `EMPTY_LOAD` de 120 secondes destinée à `T1A` n'a
vu aucune action stock : 160 lectures, route toujours vide, aucune commande,
aucune chauffe et aucune transition. Elle est non probante et ne qualifie pas
le chargement. Il faut savoir si l'action n'a pas été lancée ou si l'interface
l'a refusée avant toute nouvelle tentative.

Le manifeste physique fixe désormais quatre checkpoints couvrant `T1A`, `T2C`,
la conservation du bon filament et le blocage d'une identité ambiguë. Son
vérificateur retourne `CFS_PHYSICAL_CAMPAIGN_READY_INCOMPLETE` avec `0/4` : le
plan est prêt, mais aucune preuve humaine n'est inventée.

Le décideur local est également prêt et testé. Une capture live fraîche de huit
lectures a retrouvé le segment détecté dans la tête, aucune route engagée,
cibles zéro et configurations inchangées. Le décideur renvoie
`BLOCK/SEGMENT_PRESENT_WITHOUT_UNIQUE_ROUTE` avec zéro effet. La confirmation
humaine d'absence d'effet reste nécessaire pour passer le quatrième checkpoint.
