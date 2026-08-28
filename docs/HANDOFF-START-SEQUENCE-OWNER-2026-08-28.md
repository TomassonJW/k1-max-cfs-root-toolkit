# Handoff — START-SEQUENCE-OWNER-V1 — 2026-08-28

État de reprise : **POSE_CLOSE_OK — ATTENDRE_LA_GATE_T1A**.

## État livré

La mission `G4-K1-CONTROL-START-SEQUENCE-OWNER-V1` est installée et validée à
froid. Elle livre un départ surveillé, réversible et fermé par défaut pour le
seul démarrage quotidien déjà prouvé : conserver
une route unique `T1A`, sans commande CFS, sans brossage, sans recalibration de
mesh et sans ancien offset Orca.

Le fichier Klipper possède maintenant une confirmation de nettoyage manuel
valable cinq minutes, un surveillant toutes les cinq secondes et des délais
bornés pour chaque phase. Une perte de l'état d'impression ou un dépassement
demande `TURN_OFF_HEATERS`, bloque la suite et n'effectue aucun retry. Le chemin
garde une seule référence Z précise à `140/55 °C`, arme le `11 × 11` et le Z
accepté, atteint explicitement `190 °C`, puis purge seulement après une seconde
vérification de la géométrie.

Le déployeur a posé un fichier et un include dans `printer.cfg`, avec backup
exact et un restart de l'hôte Klipper. Sa correction exige maintenant une vraie
transition du socket avant d'accepter le nouveau runtime, restaure une fois le
`11 × 11` après chaque restart et applique la même règle au rollback. Le test
froid volontairement expiré est vert. Aucun démarrage physique n'a eu lieu.

Les documents canoniques sont le
`packages/k1-control-v1/start-sequence-owner-v1/contract.json`, le
`deployment-manifest.json`, ADR-031 et la cartographie CFS du document 43. Le
registre Goal 3 reste à `2/7` : cette preuve technique ne remplace aucune
validation physique humaine.

## Preuves et limites réelles

La capture privée
`20260828-220525-g4-k1-control-start-sequence-owner-v1` contient le préflight,
le backup, la pose et la validation. Les treize templates Jinja passent dans
l'environnement exact de la K1 ; la ligne de purge proposée reste dans les
courses lues ; le `11 × 11`, le Z `−0,04 mm`, les cibles zéro, les axes libérés
et les empreintes des configurations sont conformes. Le propriétaire et le
surveillant sont chargés, la phase finale est `idle` et le test froid est vert.
Aucune chauffe, aucun mouvement, aucune extrusion et aucun ordre CFS n'ont été
produits.

Le point bloquant est matériel et honnête : `route_count=0`, donc `T1A` n'est
pas engagé. Aucun démarrage physique ne peut être tenté avec la V1 dans cet
état.

Un export OrcaSlicer 2.4.2 privé de deux couches et `0,4 mm` a été inspecté.
L'ancien démarrage, l'ancien post-traitement et le G-code filament ont été
neutralisés dans la copie. `manual_filament_change=1` retire le `T0` que le
slicer ajoutait autrement. L'export final contient un seul appel propriétaire
et aucun ordre interdit. Il n'a pas été imprimé ni envoyé à la K1.

Vérifications : payload installé `OK`, surveillant `8/8`, tests ciblés `11/11`, suite
complète `705` exécutés dont `702` réussis et `3` ignorés connus, parse
PowerShell `OK`, pose `OK`, validation indépendante `OK` et deux lectures finales
concordantes. Validation humaine de couche : non exécutée.

## Prochaine mission unique

Préparer puis exécuter une gate séparée qui charge `T1A` une seule fois et relit
la route réellement engagée, sans lancer d'impression. C'est utile parce que le
propriétaire installé refuse correctement de démarrer avec zéro route. Cette
gate permettra ensuite seulement de présenter le vrai essai physique court.

Critères de fin : une seule route `T1A`, commande CFS vide, cibles zéro, aucun
mouvement d'impression, `11 × 11` toujours actif et configurations inchangées.
Le premier démarrage réel restera une gate distincte avec Thomas présent devant
la K1.

Modèle conseillé : `gpt-5.6-sol`, raisonnement `high`, car la prochaine gate
agit sur le filament réel et doit distinguer commande acceptée, effet observé et
état final. Option économique acceptable : `gpt-5.6-terra`, raisonnement
`high`, avec un peu moins de marge si la CFS répond de façon ambiguë.

La tâche source reste visible et ne doit pas être archivée.
