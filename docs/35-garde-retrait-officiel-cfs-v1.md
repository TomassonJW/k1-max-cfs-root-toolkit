# Garde du retrait officiel CFS V1

Date : 2026-08-27

Mission : `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-V1`

Verdict : **OK hors imprimante ; aucun accès K1 ; aucune action physique ;
aucun candidat de pose**.

## Le problème résolu

Le retrait officiel `BOX_QUIT_MATERIAL` a réellement libéré `T1A`, mais il a
laissé la buse demandée à `220 °C`. Une commande mal encodée a aussi prouvé que
la réponse HTTP `ok` ne garantit pas l'effet demandé.

Le garde V1 transforme ces constats en règles exécutables et testables. Il
réutilise la commande Creality au lieu d'inventer des messages série.

## Fonctionnement

Avant toute commande, le garde exige :

- une machine `standby` ;
- l'état CFS `connect` ;
- les deux unités `T1` et `T2` visibles ;
- aucune commande CFS active ;
- exactement une route engagée, identique à celle demandée.

Si une de ces preuves manque, il refuse sans envoyer de commande. Il ne coupe
pas les chauffes à ce stade, car cela pourrait interrompre une impression ou
une opération étrangère déjà active.

Après le premier effet, il :

1. envoie au maximum une fois `BOX_QUIT_MATERIAL` ;
2. attend le retour de la requête, la libération réelle de la route et la
   disparition de la commande CFS active ;
3. refuse tout changement vers une autre route, toute déconnexion, tout échec
   stock ou toute sortie de `standby` ;
4. n'effectue aucun second essai automatique ;
5. envoie une fois `TURN_OFF_HEATERS`, succès ou échec du retrait ;
6. exige ensuite les deux consignes réellement à zéro.

Le résultat rappelle toujours que le segment situé après le cutter peut rester
présent dans la tête. L'absence de ce segment n'est pas exigée pour qualifier le
désengagement côté CFS.

## Vérifications hors imprimante

La fausse API couvre neuf scénarios : succès, retrait sans effet malgré HTTP
`ok`, arrêt thermique sans effet malgré HTTP `ok`, perte de transport pendant le
retrait, perte de transport pendant le nettoyage, échec stock, changement de
route, déconnexion CFS et sortie inattendue de `standby`.

Les tests unitaires ajoutent les refus avant effet : impression en cours, route
ambiguë, mauvaise route, commande CFS déjà active, second CFS absent et route
invalide.

Le code du paquet n'importe aucun module réseau, série, SSH ou de lancement de
processus.

Le préflight live suivant a prouvé que la K1 n'expose aucun champ direct de fin
de retrait et que `box.t_command` reste vide pendant le cycle stock. Le contrat
a donc été corrigé : la fin est déduite du retour sans erreur de la requête et
de la route réellement libérée. HTTP `ok` seul reste insuffisant.

## Limites

- les noms et le sens exacts des champs live doivent encore être confirmés sur
  la K1 ;
- aucun adaptateur Moonraker réel n'existe ;
- aucune commande de ce paquet ne peut atteindre l'imprimante ;
- les autres slots et le second CFS ne sont pas physiquement qualifiés ;
- le propriétaire série indépendant reste fermé avec `callable_messages=[]` ;
- la production reste fermée.

## Prochaine action

En langage courant : se connecter ensuite uniquement en lecture pour vérifier
que la K1 expose bien chaque information utilisée par le garde, avec le sens
attendu. Cette étape ne lancera pas le retrait, ne chauffera pas et n'installera
rien.

Nom proposé :
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-LIVE-PREFLIGHT-V1`.

Cette connexion demandera un nouveau GO exact. Un nouvel essai réel demandera
encore une autorisation distincte après revue.
