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
aucune chauffe et aucune transition. Thomas a ensuite confirmé qu'il n'avait
rien déclenché pendant cette fenêtre. Elle est donc classée non probante et ne
qualifie pas le chargement, sans indiquer un refus de l'interface.

Thomas a aussi confirmé que la dernière action réelle, pendant la préparation
manuelle du nettoyage, avait chargé puis retiré `T1A`. Le segment encore détecté
dans la tête est donc attribué explicitement à `T1A`. Le décideur accepte
maintenant un futur chargement de ce même `T1A`, mais bloque toujours si cette
origine n'est pas confirmée ou si la route demandée est différente.

Le manifeste physique fixe désormais quatre checkpoints couvrant `T1A`, `T2C`,
la conservation du bon filament et le blocage d'une identité ambiguë. Son
vérificateur retourne `CFS_PHYSICAL_CAMPAIGN_READY_INCOMPLETE` avec `0/4` : le
plan est prêt, mais aucune preuve humaine n'est inventée.

Le décideur local est également prêt et testé. Une capture live fraîche de huit
lectures a retrouvé le segment détecté dans la tête, aucune route engagée,
cibles zéro et configurations inchangées. Le décideur renvoie
`BLOCK/SEGMENT_PRESENT_WITHOUT_UNIQUE_ROUTE` avec zéro effet. La confirmation
humaine d'absence d'effet reste nécessaire pour passer le quatrième checkpoint.
