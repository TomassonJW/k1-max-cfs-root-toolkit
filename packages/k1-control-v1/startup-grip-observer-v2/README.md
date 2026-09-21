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

## Arrêts et attente humaine

`stop_policy.py` prépare la politique commune des futurs pilotes d'essai :
`shutdown` déjà observé ne commande pas un second arrêt ; une fin déjà en
échec, sans mouvement en file et chauffes coupées, reste un échec maîtrisé.
Une pause d'attente arrivée à sa limite demande seulement de couper les
chauffes puis exige une nouvelle lecture prouvant l'immobilité et les cibles
zéro avant de rendre `cold_hold`. Une alerte physique caméra conserve l'arrêt.

Tous les émetteurs manuels et automatiques doivent utiliser le même
`StopOnce` et le même dossier de reçu. La création exclusive réserve l'unique
envoi, y compris lorsque sa réponse est incertaine. Un reçu `requested` ne
prouve jamais la réception par la machine. Ces fonctions n'ont aucun transport ;
leur intégration complète à un futur pilote reste à faire et à valider avant
usage physique. Ne pas rejouer les pilotes privés V2/V3 archivés.

`TrialSupervisor` relie ces décisions aux adaptateurs de lecture, de coupure
thermique et d'arrêt : la coupure est envoyée une seule fois, puis son effet
est relu avant de déclarer la pause froide. Les adaptateurs réels du prochain
pilote devront appeler ce propriétaire commun, y compris pour un arrêt manuel.

106 tests ciblés passent, incluant le refus de masquer une alerte caméra,
la pause chaude/froide, les mouvements encore en file, le double arrêt et la
réponse réseau incertaine. Aucune nouvelle séquence moteur installée.
