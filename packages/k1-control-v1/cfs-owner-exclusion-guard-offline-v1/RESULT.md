# Résultat — garde d’exclusion du propriétaire stock hors imprimante V1

Statut : `OFFLINE_EXCLUSION_GUARD_CLOSED_GREEN_EFFECTS_UNQUALIFIED`

La matrice canonique obtient `25/25`, les tests ciblés `15/15` et la suite
complète exécute `669` tests, dont `666` réussis et `3` ignorés connus. Le garde
sauvegarde exactement `0` ou `1`, prépare une seule désactivation si nécessaire,
attend sa preuve avant d’ouvrir le propriétaire, puis exige le retour exact à la
valeur sauvegardée.

Un acquittement seul ne prouve jamais l’effet. Une issue incertaine ne relance
pas la désactivation. Si des lectures ultérieures montrent que la valeur est
passée à `0`, le propriétaire reste fermé et une unique restauration inerte est
préparée. Une restauration incertaine mais observée à la valeur initiale ferme
le cycle en sécurité, sans qualifier le transport.

Toutes les autres valeurs sont comparées : état machine, deux CFS, commande
active, routes, cartographie, époque de connexion, politique d’impression,
mesh, Z, axes et cibles thermiques. Toute dérive ferme le chemin.

Les trois sources de décision sont épinglées par SHA-256. Aucun réseau,
connecteur, G-code, chauffage, mouvement, effet CFS, fichier distant, service,
pose ou qualification physique n’a été exécuté. Les commandes restent
`dispatchable=false` et la production demeure fermée.

La prochaine gate proposée est
`G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-READ-ONLY-V1`. Elle pourra
seulement relire deux états frais et nettoyés pour vérifier la compatibilité de
l’adaptateur. La première mutation réelle exigera encore une gate distincte.
