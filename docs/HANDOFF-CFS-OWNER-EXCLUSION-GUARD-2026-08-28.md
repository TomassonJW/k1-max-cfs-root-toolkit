# Archive — garde d’exclusion du propriétaire CFS hors imprimante

Cette passation est historique. La reprise canonique est désormais
`docs/HANDOFF-CFS-OWNER-EXCLUSION-LIVE-READ-ONLY-2026-08-28.md`.

Date de clôture : 2026-08-28

État de reprise : **ATTENDRE_AUTORITÉ_LECTURE_SEULE**

Nouvelle tâche créée : non

Goal Codex créé : non

## État livré

La mission `G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1` est close OK.
Le paquet `packages/k1-control-v1/cfs-owner-exclusion-guard-offline-v1`
contient le contrat strict, l’adaptateur pur, le garde à tentative unique, sa
matrice de fautes et un plan de rollback inerte. Le document canonique est
`docs/46-garde-exclusion-proprietaire-cfs-hors-imprimante-v1.md`.

Le garde sauvegarde la valeur d’auto-remplacement Creality. Si elle est déjà à
`0`, il n’émet aucune intention. Si elle vaut `1`, il prépare exactement une
désactivation non exécutable. Le propriétaire K1 Control reste fermé tant que
deux lectures successives ne prouvent pas la valeur `0`. À la fin, le garde
prépare au plus une restauration de la valeur sauvegardée et exige deux
lectures qui la confirment.

Un retour HTTP ou un acquittement « accepté » ne suffit jamais. Un résultat
incertain n’est pas rejoué. Si une lecture ultérieure prouve que la
désactivation a eu lieu malgré l’incertitude, le propriétaire reste fermé et
seule la restauration est préparée. Si la valeur sauvegardée est ensuite
observée, le cycle peut être déclaré sûr, mais le transport reste non qualifié.

Le garde compare aussi l’état `standby`, les deux CFS, la commande active, les
routes, la cartographie, l’époque de connexion, la politique d’impression, le
mesh, le Z, les axes et les chauffes. Toute autre dérive ferme le chemin. Les
signatures présentes sont exactement `BOX_ENABLE_AUTO_REFILL ENABLE=0/1`, déjà
liées à S12, et restent toujours `dispatchable=false`.

## Preuves et limites

La matrice synthétique obtient `25/25`, les tests ciblés `15/15` et la suite
complète exécute `669` tests, dont `666` réussis et `3` ignorés connus. Les contrats
du cœur propriétaire et du préflight S12 ainsi que la carte de preuve S12 sont
épinglés par SHA-256. Aucun module de réseau, processus ou transport n’est
importé par le paquet.

Aucune connexion K1, commande, G-code, chauffe, mouvement, effet CFS, écriture
distante, restart ou pose n’a eu lieu. La commande réelle et son rollback ne
sont pas qualifiés. Le paquet n’est pas un candidat de déploiement. Le Goal 3
reste à `2/7`, le nettoyage manuel reste obligatoire, le `11 × 11` reste le
meilleur mesh actuel sans être qualifié robuste, et la production demeure
fermée.

## Prochaine mission unique

La reprise proposée est
`G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-READ-ONLY-V1`. Concrètement, elle
prendra deux lectures fraîches et nettoyées de la K1, sans envoyer de commande,
pour vérifier que les champs réels sont compatibles avec l’adaptateur pur. Elle
est utile pour éviter de découvrir une forme différente au moment d’une future
mutation. Si elle passe, elle permettra de préparer séparément un essai humain
très borné de désactivation puis restauration ; elle ne l’autorisera pas.

Cette prochaine mission exige donc une autorité explicite de connexion en
lecture seule. Elle n’autorise ni G-code, ni chauffe, ni mouvement, ni action
CFS, ni fichier distant, ni restart. L’essai réel de la commande exigera encore
une gate différente avec Thomas devant l’imprimante.

Relire `HANDOFF.md`, `GOALS.md`, les documents 43 à 46, ADR-032,
`design/cfs-control-source-map-v1.json`, le contrat du paquet et son plan de
rollback.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`, car la lecture devra
préserver les données privées, comparer exactement les champs et maintenir une
frontière stricte entre observation et effet. Option économique acceptable :
`gpt-5.6-terra` en `medium`, avec plus de risque de manquer une ambiguïté de
forme ou de fraîcheur.

Ce clavardage source est conservé et ne doit pas être archivé.
