# Résultat — propriétaire CFS direct hors imprimante V1

Statut : `CLOSED_OK_OFFLINE_24_OF_24`

Le propriétaire direct encode les trames exactes observées sur cette K1 et
garde seulement `auto_addr`/`serial_485` comme infrastructure stock. Les
macros et méthodes `BOX_*` ne sont plus des candidates du cycle final.

Le validateur indépendant obtient `24/24` scénarios : `T1A`, `T2D`, la reprise
logique sans mouvement d'une route `T1A` perdue, deux cycles
complets successifs, capteurs, température explicite, statuts CFS, timeouts,
CRC, limite de poussées, retrait en deux phases et identifiants consommables
une fois. Toutes les trames partent avec `retry=False`; un nettoyage de tension
de sécurité est tenté au plus une fois par adresse.

Le retrait ne confond plus la route amont libérée avec le segment déjà coupé
qui peut rester dans la tête. Le capteur après cutter doit être libre pour
valider le retrait ; l'état `retained_head_segment` est alors exposé et peut
être consommé uniquement par le chargement possédé suivant du même runtime.

Le paquet ne chauffe pas, ne référence pas, ne bouge pas, ne touche ni au mesh
ni au Z, ne purge pas et ne se connecte pas à la K1. Il n'est pas un candidat
de pose.

La prochaine gate est
`G4-K1-CONTROL-CFS-DIRECT-OWNER-INSTALL-DISABLED-V1` : fabriquer une pose
réversible, propriétaire encore désactivé, et prouver l'exclusion du
propriétaire stock avant toute trame d'effet. La qualification physique
chargement/retrait restera une gate suivante sous caméra.
