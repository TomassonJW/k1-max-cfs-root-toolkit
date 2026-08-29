# Résultat

Statut : `OFFLINE_CANDIDATE_PHYSICAL_RUN_BLOCKED`.

Validation locale : vérificateur dédié vert, `4/4` tests propres au paquet et
`14/14` tests ciblés avec le diagnostic thermique. Le parse Jinja complet n'a
pas été exécuté car le Python local ne contient pas `jinja2`; il reste un
critère explicite de la prochaine validation froide.

Le défaut R5 est reproduit dans le contrat : R2 ne purgeait pas dans le bac, ne
décrochait pas la boule et ne disposait d'aucune preuve caméra. Les coordonnées
Klipper ne pouvaient donc pas exclure une référence Z faussée par du filament
sous la buse.

Le candidat R3 place deux arrêts caméra réels dans le chemin. Le premier bloque
avant la référence Z précise ; le second bloque avant la première commande du
modèle. La ligne finale reste hors zone imprimable grâce à la course mécanique
négative déjà présente sur cette K1.

Aucune pose, chauffe, extrusion, référence ou reprise physique n'est permise par
ce résultat. Le prochain travail est une revue hors imprimante du candidat et
de son futur pilote caméra, puis une validation à froid. Un nouvel essai chaud
restera bloqué tant que T1A n'est pas réellement réengagé et que le plateau et
la buse n'ont pas été remis propres après l'incident.
