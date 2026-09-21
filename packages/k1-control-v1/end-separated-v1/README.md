> Historique clos KO le 21 septembre : key849, chevauchement extrudeur/CFS
> supprimé par une attente fautive. Ne pas poser ni rejouer V1. Voir document 92
> et end-overlap-v2, actuellement hors imprimante.

# Fin séparée CFS V1 — ADR-070

Ce paquet remplace uniquement `kctrl_end.py` et sa configuration incluse.
Le candidat historique ADR-069 reste conservé dans son paquet, non rejouable.

## Comportement

La fin attend la sortie réelle du contexte de reprise SD, résout la case
physiquement engagée, conserve la cible de température du travail, puis :

1. coupe et vérifie les événements réels du cutter ;
2. depuis X38 / Y303..306, dégage localement le levier à Y291,5 à 30 mm/s,
   sans X, Z ou E, et exige le relâchement du capteur ;
3. rétracte E−20 à F5000 puis E−15 à F120, avec extrusion relative,
   facteur 100 %, attente M400 et restitution de l'état G-code sans mouvement ;
4. appelle une fois les méthodes élémentaires du firmware : mode IDLE,
   moteur de liaison STOP, puis retrait MATERIAL de la case physique ;
5. exige `True` comme retour de chacune, puis tête vide et aucune route CFS,
   stables pendant 0,5 s, dans une attente bornée de 20 s après le retrait ;
6. autorise seulement alors `END_PRINT_NO_M84`, libère les moteurs et vérifie
   les chauffes à zéro.

L'ancien état de la même case est toléré pendant cette attente. Une autre case,
une ambiguïté, une déconnexion, une annulation ou une erreur arrête la fin,
coupe les chauffes et interdit tout retry/reprise automatique. Le surveillant
thermique global reste indépendant du verrou G-code, avec plafond de 180 s.
Aucune référence Z, aucun mesh ou homing n'est ajouté. Aucun trajet au bac
n'est présent dans le retrait séparé. Le parc final conserve la macro existante
et ne peut être appelé qu'après confirmation du retrait.

## Preuves des primitives

Binaire installé et capturé : SHA256
`af630c02ccdb51b57585114e5be2be7fcf91fdb10d88872eb6a0c65f048de777`.
Analyse statique, puis exécution des méthodes non liées dans un processus
Python isolé, avec faux propriétaires, faux capteurs et faux transport.
Aucun objet de l'imprimante active n'est utilisé par ces essais.

- `communication_set_box_mode(1, 'IDLE')` : commande 0x04, délai 2 s.
- `communication_ctrl_connection_motor_action(1, 'STOP')` : 0x07, délai 2 s.
- `communication_retrude_process(1, 'B', 'MATERIAL')` : 0x11,
  données `02 01`, délai constructeur 150 s.
- Le décodeur exact, alimenté par l'ACK historique simulé `f7 01 03 00 11 ca`,
  renvoie le booléen `True`. Les wrappers G-code jettent cette valeur : le
  successeur appelle donc les mêmes méthodes élémentaires et la contrôle.
- La commande combinée rejetée commence effectivement par `go_to_extrude_pos`.
- `BOX_GET_BOX_STATE` possède un délai constructeur de 3600 s : aucun nouvel
  appel n'est ajouté. L'attente observe les mises à jour périodiques existantes.
- L'adresse constructeur est basée sur **1**, et la case est la lettre **B**,
  contrairement à l'ancienne piste communautaire consignée au document 52.

## Pose réversible

`manifest.json` fige les 22 fichiers de référence, les deux remplacements et
le déployeur. `build_manifest.py` les reconstruit sans réseau.
`remote_install.py` s'exécute dans le Python Klipper avec une entrée JSON
contenant manifeste, payloads base64 et mode `install` ou `rollback`.
Le connecteur local de session utilise SSH et conserve les captures en privé.

Préflight : aucune impression/pause, chauffes zéro, axes libérés, tête vide,
aucune route CFS, ancien candidat désactivé et toutes les empreintes exactes.
Sauvegarde exclusive : `/usr/data/k1-control-v1/backups/cfs-separated-end-v1`.
Arrêt du service avec preuve de disparition de l'ancien processus, remplacement
atomique des deux fichiers, redémarrage et validation du nouveau propriétaire.
Le profil de mesh et les offsets sont restitués exclusivement avec `MOVE=0`.
Le rollback restaure les deux sauvegardes exactes, redémarre et vérifie le retour
au candidat désactivé. Toute dérive du préflight interdit l'écriture.

L'installation n'envoie aucun mouvement, chauffe, extrusion, retrait ou départ.
La configuration du successeur est active après pose réussie. Ce fait ne vaut
pas qualification mécanique : `physical_validation` reste `false`.

## Validation et limites

142 tests ciblés verts au gel initial : candidat historique, successeur,
paquet historique et déploiement/rollback séparés. Retards, contradiction de
route, absence de relâchement, panne de commande, température, annulation et
retours ACK ambigus sont injectés hors imprimante.

La nouvelle chorégraphie n'a pas encore été exécutée physiquement. La prise du
filament au démarrage, intermittente sur les essais antérieurs, n'est pas
corrigée ni déclarée qualifiée par ce paquet. Aucun réglage moteur de démarrage
n'est modifié. Un rembobinage interrompu exige une récupération contrôlée ;
il n'est jamais automatiquement relancé.
