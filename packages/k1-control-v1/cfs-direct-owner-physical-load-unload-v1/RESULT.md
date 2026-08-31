# Résultat — qualification physique directe T1A

Statut : **CLOSED_KO_BEFORE_FILAMENT_EFFECT — V1 interdite de rejeu**

Capture :
`20260831-132914-g4-k1-control-cfs-direct-owner-physical-load-unload-v1`.

Le préflight initial était vert et les deux capteurs indiquaient un filament
engagé. La caméra montrait une tête au parc et un plateau libre. L'activation a
ensuite été refusée par `stock_auto_refill_invalid` après le restart, avant la
première trame CFS et avant toute chauffe.

Le rollback automatique est vert : propriétaire désactivé, transport non lié,
commandes stock non remplacées, `0` trame, cibles buse et plateau à zéro, axes
libérés, `11 × 11` actif, Z accepté `−0,04`, deux CFS connectés. Les deux
capteurs sont toujours actifs, ce qui prouve seulement que le filament initial
est resté engagé. Le dernier `final_validate` est KO sur
`final_filament_path_not_clear` pour cette raison ; ce n'est pas un retrait
échoué, car aucun retrait n'a été tenté.

La revue déclenchée par Thomas ferme aussi le concept V1 : un retrait sans
position cutter et un chargement sans purge bac ne correspondent pas au besoin
physique. Le successeur doit intégrer le cutter avant retrait, puis la purge
dans le bac et `3 à 4` allers-retours de décrochage après chaque chargement,
avec preuve caméra et sans palpage après insertion.
