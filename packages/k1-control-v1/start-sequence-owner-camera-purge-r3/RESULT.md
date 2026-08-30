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
ce résultat. La revue hors imprimante, le pilote caméra minimal et la validation
froide sont maintenant clos dans
`camera-reference-library-and-r3-cold-validation-v1`. Les `16` blocs Jinja ont
été parsés par le Python de la K1 via stdin, sans fichier distant ni G-code. Les
deux pauses restent bloquantes et les timeouts coupent les chauffes sans
confirmer d'image.

Un nouvel essai chaud reste néanmoins bloqué tant que `T1A` n'est pas réellement
réengagé et que le plateau et la buse n'ont pas été remis propres après
l'incident. R3 reste sans déployeur et sans autorité physique.
