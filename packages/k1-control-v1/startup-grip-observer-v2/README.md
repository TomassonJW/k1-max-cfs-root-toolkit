# Observateur de chargement V2 — local, sans transport

Le précédent observateur déclarait un blocage de première accroche sur huit
`full` jusqu'à la pause, même après détection de tête. Cette version exige
deux observations fraîches et distinctes : présence dans la tête et route
cible déclarée engagée par le CFS. Leur conjonction ferme le compteur de
première insertion ; une erreur firmware reste toujours surveillée.

Avant cette conjonction, le plafond de huit observations est conservé :
`buffer_full_before_head` si la tête est vide, ou
`loading_unconfirmed_buffer_full` si le filament est arrivé mais le CFS n'a
pas validé la route. Ces raisons nomment la limite d'observation, pas une
preuve de blocage mécanique ou d'absence de débit.

Le rejeu de l'essai V2 arrêté doit donc encore demander l'arrêt : sa route
n'était jamais B. La correction ne cherche pas à rendre verte cette trace.
Les limites thermiques, la limite temporelle globale, la caméra et la preuve
humaine de purge restent obligatoires dans le pilote appelant. Une position
E interpolée n'est jamais prise comme preuve de débit physique.

Ce module ne redémarre pas Klipper, ne commande aucun moteur et ne charge
aucun filament. Il ne modifie aucun fichier installé sur l'imprimante.
