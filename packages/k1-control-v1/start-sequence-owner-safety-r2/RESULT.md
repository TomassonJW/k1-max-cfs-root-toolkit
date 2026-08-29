# Résultat actuel

Statut : `OFFLINE_CANDIDATE_OK_LIVE_INSTALL_AND_PHYSICAL_PURGE_NOT_STARTED`.

La récupération d'accès est terminée et confirmée par deux lectures stables :
`standby`, chauffes à zéro, axes libérés, tête `X203 Y273`, plateau à `Z50,23`
physique, mesh `11 × 11`, Z accepté `−0,04` et `T1A` conservé.

Le premier appel a dépassé son délai HTTP après huit secondes. Il n'a pas été
rejoué. Une lecture intermédiaire a observé le `G28` terminé ; une continuation
distincte a ensuite bloqué avant effet parce que l'appel initial avait continué
en arrière-plan. Les deux lectures finales prouvent que toute la récupération
s'est terminée.

Le G-code thermique invalide a été supprimé de la K1 après vérification exacte
de son empreinte. Le correctif R2 est uniquement local : purge constructeur
aller-retour `X0,1/X0,4`, de `Y20` à `Y180`, `F3000`, rétraction `1,2 mm`,
remontée `Z5`, puis fin sûre à `Z50` et `X203 Y273` avant `M84`.

La pose live et la qualification physique de la nouvelle purge restent
fermées. Le déployeur de remplacement exact, son backup, son restart surveillé,
la restauration du `11 × 11`, sa validation froide et son rollback sont prêts
hors imprimante. Aucun nouveau fichier d'impression n'est présent sur la K1.
