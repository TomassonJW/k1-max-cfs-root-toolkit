# Garde d’exclusion du propriétaire CFS hors imprimante V1

Date : 2026-08-28

Mission : `G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1`

Statut : **close OK hors imprimante ; effets et pose non qualifiés**.

## Pourquoi ce garde existe

Le cœur propriétaire ne doit jamais travailler en même temps que
l’auto-remplacement Creality. Avant de lui donner le cycle, il faut conserver
la valeur stock, la désactiver si elle vaut `1`, prouver le résultat, puis
restaurer exactement l’ancienne valeur à la fin ou après un incident.

Cette tranche ne commande rien. Elle rend seulement cette règle précise,
testable et fermée en cas de doute.

## Contrat retenu

Deux lectures nettoyées, identiques à l’exception d’un numéro croissant, sont
requises avant et après chaque futur effet. L’état doit rester `standby`, les
deux CFS doivent être connectés, aucune commande stock ne doit être active et
une seule route au maximum peut être engagée. Le mesh, le Z accepté, les axes
et les cibles thermiques sont protégés valeur par valeur.

Si la valeur initiale vaut `0`, le verrou peut être donné sans désactivation et
se ferme sans restauration. Si elle vaut `1`, le garde prépare une seule
intention `BOX_ENABLE_AUTO_REFILL ENABLE=0`, non exécutable. Il n’accorde le
verrou qu’après deux lectures à `0`. À la fermeture, il prépare une seule
restauration à `1` et exige sa preuve.

Un retour « accepté » sans changement observé ferme le chemin. Un retour
inconnu n’est jamais rejoué. Si une lecture de récupération montre que la
désactivation a pourtant eu lieu, le propriétaire reste fermé et le garde ne
prépare que la restauration. Si la valeur initiale est retrouvée après une
restauration incertaine, le système est classé sûr mais la commande reste non
qualifiée.

## Résultat local

La matrice obtient `25/25`. Les `15/15` tests ciblés couvrent les valeurs `0/1`,
les doubles lectures, les acquittements trompeurs, les résultats inconnus, le
refus des secondes tentatives, la récupération sans nouvel effet et les dérives
d’état. Ils vérifient aussi les empreintes du cœur propriétaire, du contrat S12
et de sa carte de preuve.

La suite complète du dépôt exécute `669` tests : `666` réussissent et les `3`
ignorés connus restent inchangés.

Le paquet est dans
`packages/k1-control-v1/cfs-owner-exclusion-guard-offline-v1`. Il contient un
contrat, un adaptateur pur, le garde, la matrice, un plan de rollback inerte et
leurs preuves locales.

## Limites

Aucune connexion K1, commande, chauffe, mouvement, action CFS, écriture
distante, restart ou pose n’a eu lieu. La signature S12 de la commande est
connue ; son effet réel n’est pas qualifié. L’adaptateur n’a encore jamais reçu
une lecture live de cette gate. Ce vert ne modifie pas le Goal 3, qui reste à
`2/7`, et n’ouvre pas la production.

## Suite bornée

La prochaine mission proposée est
`G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-READ-ONLY-V1`. Elle devra seulement
prendre deux lectures fraîches, retirer les identifiants privés avant retour
local et vérifier que leur forme entre dans l’adaptateur sans l’appeler sur un
chemin d’effet. Elle exigera une autorité distincte de connexion en lecture
seule. Toute désactivation réelle, même unique, restera une autre gate avec
Thomas devant la K1.
