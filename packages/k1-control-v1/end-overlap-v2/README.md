# Retrait coordonné V2 — correctif et pose à froid

Corrige l'attente fautive du candidat end-separated-v1. La primitive
constructeur Tn_Extrude attend la fin des 20 mm rapides ; les 15 mm lents
suivants sont en revanche seulement mis en file avant les appels CFS. Le
candidat V1 attendait aussi leur fin, supprimant ce chevauchement.

V2 garde la coupe, le relâchement local sans X/Z ni bac et la résolution fraîche
T1B. Il attend après E-20, programme E-15, lance les primitives CFS une fois,
puis attend la fin des mouvements avant les preuves de retrait et le parc.
Les ACK, les capteurs, les températures et les refus restent exigés.

170 tests ciblés verts, dont trois délais d'ACK sous une file de mouvements
simulée et trois témoins négatifs utilisant le code V1. Ces tests refusent
l'ancien ordre. Ils ne constituent pas une qualification physique.

Le paquet de pose remplace uniquement `kctrl_end.py`, depuis les octets exacts
de V1 installé. La configuration active reste inchangée ; le défaut de
coordination logiciel est confirmé, sa correction physique reste à qualifier.
La cause exacte de l'effort mécanique ne peut pas être prouvée par simulation.

## Pose et retour arrière

`build_manifest.py` fige 22 chemins, le fichier candidat et l'installateur.
`remote_install.py` reçoit par stdin le manifeste et le contenu encodé en
base64. Modes : `preflight`, `install`, `validate`, `rollback`. Le transport
local vérifie l'empreinte de l'installateur avant envoi ; aucun chemin distant
ou contenu non relu ne doit lui être substitué.

Le préflight exige deux états stables, machine au repos, cibles zéro,
températures réelles au plus 50 °C, aucune vitesse ni commande CFS, tête vide,
deux CFS connectés sans route, propriétaire V1 actif/idle. Les axes peuvent
être libres ou seulement X/Y référencés après le retrait manuel ; aucune
commande de mouvement ne sert à satisfaire ce contrôle. Après restart,
aucun axe ne doit rester référencé.

Sauvegarde exclusive : `/usr/data/k1-control-v1/backups/cfs-end-overlap-v2`.
Pose : sauvegarde exacte, arrêt Klipper et preuve de disparition de l'ancien
processus, remplacement atomique d'un fichier, redémarrage, contrôle de V2,
remise du profil réellement actif et des offsets avec `MOVE=0`, comparaison
de la matrice et des 22 empreintes, seconde lecture froide. Aucun chauffage,
mouvement, homing, palpage ou démarrage d'impression.

Tout échec après l'arrêt déclenche une tentative de retour exact vers V1,
avec redémarrage, remise de l'état logiciel et contrôle des empreintes. Une
erreur de rollback est propagée : jamais transformée en succès. Le rollback
restaure une version connue défectueuse, pas une autorisation de production.
Le mode explicite `rollback` exige aussi une machine froide au repos.

199 tests ciblés passent, dont 29 consacrés à cette pose et ses refus.
Voir le document 93 pour le résultat réel de l'installation et ses limites.

Pose réalisée : `INSTALLED_COLD_OK`, puis `VALIDATED_COLD_OK` indépendant sous
la capture `20260921-cfs-end-overlap-v2-install`. Version active `end-overlap-v2`,
idle, chauffes zéro, axes non référencés. Aucun mesh actif, offsets zéro
conservés depuis l'état réel après reboot. Validation physique toujours fausse.
