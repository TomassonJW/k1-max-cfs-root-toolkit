# Handoff — START-SEQUENCE-OWNER-V1 — 2026-08-28

État de reprise : **ATTENDRE_GO**.

## État livré

La mission `G4-K1-CONTROL-START-SEQUENCE-OWNER-V1` est close au niveau
préparation et préflight. Elle livre un candidat de pose surveillé, réversible
et fermé par défaut pour le seul démarrage quotidien déjà prouvé : conserver
une route unique `T1A`, sans commande CFS, sans brossage, sans recalibration de
mesh et sans ancien offset Orca.

Le fichier Klipper possède maintenant une confirmation de nettoyage manuel
valable cinq minutes, un surveillant toutes les cinq secondes et des délais
bornés pour chaque phase. Une perte de l'état d'impression ou un dépassement
demande `TURN_OFF_HEATERS`, bloque la suite et n'effectue aucun retry. Le chemin
garde une seule référence Z précise à `140/55 °C`, arme le `11 × 11` et le Z
accepté, atteint explicitement `190 °C`, puis purge seulement après une seconde
vérification de la géométrie.

Le déployeur prépare une pose additive unique : un fichier, un include dans
`printer.cfg` et un restart de l'hôte Klipper. Il sauvegarde le
`printer.cfg` exact, épingle toutes les empreintes, valide le candidat par un
test froid volontairement expiré, puis sait restaurer le fichier de base et
retirer l'ajout. Il ne lance jamais le démarrage physique pendant la pose.

Les documents canoniques sont le
`packages/k1-control-v1/start-sequence-owner-v1/contract.json`, le
`deployment-manifest.json`, ADR-031 et la cartographie CFS du document 43. Le
registre Goal 3 reste à `2/7` : cette preuve technique ne remplace aucune
validation physique humaine.

## Preuves et limites réelles

La capture privée
`20260828-203739-g4-k1-control-start-sequence-owner-v1` a exécuté seulement le
préflight. Les treize templates Jinja passent dans l'environnement exact de la
K1 ; la ligne de purge proposée reste dans les courses lues ; le `11 × 11`, le
Z `−0,04 mm`, les cibles zéro, les axes libérés et les empreintes des
configurations sont conformes. Aucun fichier distant, restart, chauffage,
mouvement, extrusion ou ordre CFS n'a été produit.

Le point bloquant est matériel et honnête : `route_count=0`, donc `T1A` n'est
pas engagé. Aucun démarrage physique ne peut être tenté avec la V1 dans cet
état.

Un export OrcaSlicer 2.4.2 privé de deux couches et `0,4 mm` a été inspecté.
L'ancien démarrage, l'ancien post-traitement et le G-code filament ont été
neutralisés dans la copie. `manual_filament_change=1` retire le `T0` que le
slicer ajoutait autrement. L'export final contient un seul appel propriétaire
et aucun ordre interdit. Il n'a pas été imprimé ni envoyé à la K1.

Vérifications : candidat `OK`, surveillant `8/8`, tests ciblés `9/9`, suite
complète `703` exécutés dont `700` réussis et `3` ignorés connus, parse
PowerShell `OK`, plan local et empreintes `OK`. Validation humaine de couche :
non exécutée. Installation : non exécutée.

## Prochaine mission unique

Attendre un nouveau GO exact
`G4-K1-CONTROL-START-SEQUENCE-OWNER-V1` sur le paquet figé. Concrètement, ce GO
autorisera seulement : refaire le préflight, sauvegarder `printer.cfg`, ajouter
le fichier et l'include, redémarrer l'hôte Klipper, exécuter le test froid du
surveillant, puis retenir la pose si toutes les preuves restent identiques. Au
premier écart, le rollback exact doit s'exécuter.

Critères de fin : empreintes attendues, include unique, Klipper prêt, cibles
zéro, axes libérés, `11 × 11` et Z acceptés inchangés, test froid terminé sans
effet physique, backup vérifié et rollback disponible. Cette mission de pose
n'autorise toujours ni chargement, ni chauffe, ni mouvement, ni extrusion, ni
impression.

Après cette pose seulement, une gate distincte devra charger puis relire une
route unique `T1A`. Le premier démarrage réel constituera encore une gate
séparée avec Thomas présent devant la K1.

Modèle conseillé pour la pose : `gpt-5.6-sol`, raisonnement `high`, car la
mission combine état live, empreintes, restart et rollback sur du matériel de
production. Option économique acceptable : `gpt-5.6-terra`, raisonnement
`high`, avec le même protocole ; elle est suffisante si le préflight reste
strictement conforme, mais offre un peu moins de marge en cas de rollback ou de
dérive inattendue.

La tâche source reste visible et ne doit pas être archivée.
