# Fin réelle du 23 septembre : fausse absence de confirmation du retrait

## Demande et périmètre

Thomas a terminé une impression complète et confirme que le filament a été
correctement rembobiné. La relance est refusée avec « fin incomplète
(rewind_not_confirmed) ». Il demande de corriger ce dernier contrôle en
préservant le fonctionnement précédent. Aucun nouvel essai physique n'est demandé.

## Preuve collectée

Capture privée : `inventory/raw/20260923-cfs-rewind-confirmation/`.
Les heures ci-dessous sont celles du journal de la K1.

| Événement | Heure |
| --- | --- |
| Fin du fichier et sortie du lecteur SD | 05:33:44 |
| Coupe confirmée, puis capteur de cutter libéré | 05:33:50 |
| Départ du retrait T1B | 05:33:52,523 |
| Réponse CFS `f7 01 03 00 11 ca`, `OK[0x0]` | 05:34:06,358 |
| Échec logiciel `rewind_not_confirmed` | 05:34:26,387 |

La lecture fraîche donne `ready/standby`, températures cibles zéro, tête vide,
phase `failed`, aucune opération de fin en cours. T1B reste déclaré engagé et
`t_command=T0` est conservé. La position est X38 Y291,5 Z103,97, au retrait local
du cutter. L'état matériel et la mémoire de route divergent. Les 22 fichiers
protégés correspondent exactement à la version V2 attendue.

## Cause prouvée

Le binaire constructeur exact a été invoqué dans un processus séparé avec
de faux transports, moteurs, G-code et objets d'imprimante, sans initialiser
le pilote réel. Le transport `RETRUDE_PROCESS` renvoie un succès mais n'efface
pas `Tn_data.T1.filament`. Le chemin complet `BoxAction.box_retrude_material`
effectue ensuite :

1. `last_cmd_tmp = last_cmd` ;
2. `update_filament_pos(route, None)` ;
3. `last_cmd = None`.

La deuxième opération se réduit à
`modify_Tn_data(1, 'None', 'filament', 'B')` pour T1B. L'exécution isolée de
cette méthode ne fait aucun appel externe et remplace la valeur du dictionnaire.
`get_status` expose une copie de ce dictionnaire. V2 attendait donc le changement
spontané d'une mémoire qu'elle devait mettre à jour elle-même. Le test V2 simulait
à tort un effacement automatique après quelques secondes, ce qui masquait le bug.

## Correction

`packages/k1-control-v1/end-rewind-confirm-v3/kctrl_end.py` reprend V2 en
conservant exactement chargement, coupe, retrait local Y, températures, distances,
vitesses, chevauchement extrudeur/CFS, barrières et fin existante.
Après les trois acquittements strictement vrais et le dernier `M400`, V3 attend
une tête vide stable pendant 0,5 s, puis applique les trois écritures constructeur.
La route doit devenir vide et rester vide avec le capteur pendant encore 0,5 s.

Un autre slot, un CFS déconnecté, un capteur inconnu/actif, un acquittement faux,
une erreur console, une annulation, une modification concurrente de commande ou
une écriture d'état inefficace empêchent toujours la fin. Aucune relance moteur
n'est ajoutée. Le contrôle thermique existant est conservé.

La garde d'accès au prochain fichier n'est pas modifiée : elle redevient passante
lorsque la fin est `complete`, ou après le redémarrage à froid en `idle` pour
la récupération actuelle. Aucun contournement général du message d'échec.

## Validation et pose

Les 184 contrôles ciblés couvrent le cas réel, les erreurs, le chevauchement
moteur, la pose et le retour arrière. La suite complète obtient 1883 tests verts, 2 xfail et les deux échecs
délibérés déjà déclarés dans `.github/workflows/tests.yml` ; 55 sous-tests sont
verts. Aucun autre échec. La pose et sa validation indépendante sont vertes
(`INSTALLED_COLD_OK`, puis `VALIDATED_COLD_OK`). La pose remplace un seul fichier avec
sauvegarde et 22 empreintes protégées. Elle ne lance aucune impression,
chauffe, coupe, purge, rétraction ni déplacement d'axe.

La prochaine impression normale pourra valider le passage réel jusqu'au parc
final. Le succès physique du retrait précédent est confirmé par Thomas et par
l'acquittement CFS ; il ne devient pas une validation physique du nouveau code.

## État de clôture vérifié

La nouvelle révision est chargée et activée. La garde du prochain fichier lit
`phase=idle`, `pending=false`, `failure=''`, `thermal_failure=''`. Les deux
CFS sont connectés sans route, la tête est vide, `t_command=''`, les cibles
sont zéro. Klipper est prêt au repos. Le mesh `k1_p001_t055_r001_n11x11` et
les offsets observés juste avant la pose sont conservés exactement (l'offset
runtime de cette impression était nul, sans rétablir une ancienne valeur).
Les axes sont non référencés à la suite du redémarrage logiciel.

Sauvegarde : `/usr/data/k1-control-v1/backups/cfs-end-rewind-confirm-v3`.
Le retour arrière reposerait le fichier V2 exact ; il réintroduirait le défaut
de confirmation aux prochaines fins. Aucun redémarrage électrique, arrêt
d'urgence, chauffage ou essai physique n'a été demandé à Thomas.
