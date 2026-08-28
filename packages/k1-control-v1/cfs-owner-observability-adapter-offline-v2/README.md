# Adaptateur d’observabilité du propriétaire CFS V2

Ce paquet pur transforme deux observations continues Moonraker vers le contrat
fermé du garde d’exclusion. Il utilise l’identifiant réel de la connexion
Moonraker et la séquence des changements CFS notifiés. Une reconnexion de
l’observateur ou une transition CFS signalée invalide la paire.

Le Z accepté vient de `gcode_macro KCTRL_STATE.accepted_z_offset`. Le store
persistant doit conserver `integrity=ok` et la forme runtime `null` déjà
qualifiée sur cette K1. `homing_origin` n’est jamais utilisé.

La matrice obtient `12/12`. Le paquet n’a aucun transport et n’autorise aucun
effet. La lecture live V2 et l’effet réel ont ensuite été qualifiés par leurs
gates séparées.
