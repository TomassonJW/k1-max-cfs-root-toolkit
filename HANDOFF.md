# HANDOFF — redirection vers la passation complète actuelle

La passation canonique de la session est désormais :

`docs/HANDOFF-CFS-OWNER-EXCLUSION-GUARD-2026-08-28.md`

Lire ce document en premier. Le contenu ci-dessous est conservé comme archive
des clôtures antérieures ; il ne décrit plus l'état live actuel et ne doit pas
piloter la prochaine action.

`GOAL-P4-OFFLINE-CYCLE-CFS-V1` est terminé hors imprimante et
`GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` est terminé en lecture seule. La capture
canonique de ce second Goal reste
`20260827-142853-goal-p4-k1-read-only-qualification-v1`. Le Goal 3 reste en
cours à `2/7` ; le nettoyage automatique est clos KO et le nettoyage manuel
est obligatoire.

`G4-K1-CONTROL-CFS-OWNER-CORE-OFFLINE-V1` reste clos avec `21/21` scénarios.
Son successeur `G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1` est
maintenant clos avec `25/25` scénarios et `15/15` tests ciblés. Le garde pur
sauvegarde la valeur stock, prépare au plus une désactivation non exécutable,
exige deux lectures qui prouvent l'effet puis restaure exactement la valeur
précédente. Un acquittement seul ne prouve rien et un résultat incertain n'est
jamais rejoué.

Les signatures S12 `BOX_ENABLE_AUTO_REFILL ENABLE=0/1` restent présentes comme
intentions `dispatchable=false`. Aucune impression, G-code, écriture distante,
connexion K1, chauffe, mouvement ou action CFS n'a été produit par cette
mission. Le Goal 3 reste à `2/7`.

La prochaine mission unique proposée est
`G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-READ-ONLY-V1`. Elle exige une
nouvelle autorisation explicite de connexion en lecture seule. Elle prendra
deux lectures fraîches et nettoyées pour vérifier la forme réelle, sans appeler
le garde ni envoyer de commande. L'essai réel, les primitives filament et la
production restent fermés, avec rollback exact obligatoire avant toute future
mutation.

## Archive historique — clôture initiale du Goal 2

Date de passation : 2026-08-27
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`
Nouvelle tâche créée : non
Goal actif : absent après clôture

## État à annoncer immédiatement à Thomas

- **`GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` est terminé.**
- La lecture réelle est qualifiée sans effet, mais la suite physique est
  bloquée : le mesh actif `default` diffère du profil robuste requis.
- Le profil robuste `k1_p001_t055_r001_n06x06` existe encore avec sa bonne
  empreinte ; il n'a pas été chargé, car le Goal 2 l'interdisait.
- Aucune impression, G-code, écriture distante, chauffe, mouvement, restart,
  action CFS ou reconnexion provoquée n'a eu lieu.
- La production reste fermée et le mode Précision reste caché.
- Cette session source doit rester visible et ne doit pas être archivée.

## État livré

La capture privée retenue est
`20260827-142853-goal-p4-k1-read-only-qualification-v1`. Le nettoyage a lieu sur
la K1 avant le retour local : aucun numéro de série, UUID, nom de fichier
d'impression ou contenu de configuration n'est exporté.

Deux lectures stables confirment Klippy prêt, l'imprimante en `standby`, les
cibles à zéro, les axes libérés, `T1/T2` connectés, `T3/T4` non configurés,
aucune route engagée, `t_command` vide, le capteur de tête actif et le Z accepté
à `−0,04 mm`. L'identité filament reste donc classée `engaged_unknown`.

Les lectures d'état ont pris `199,212 ms` et `235,525 ms`, sous le plafond de
`5 s`. La forme est identique entre les deux réponses. Les douze empreintes de
configuration, composants Moonraker et fichiers UI correspondent aux versions
revues et sont identiques avant/après.

Le seul écart bloquant est réel : le mesh actif `default` et le profil robuste
requis `k1_p001_t055_r001_n06x06` sont tous deux des matrices `6 × 6`, mais
leurs empreintes diffèrent. Le robuste existe toujours ; il n'est simplement
pas actif. Le statut fermé est `CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT`.

Le collecteur `GET`, la traduction pure, le délai et la règle d'invalidation du
mapping sont qualifiés. Une reconnexion très courte qui revient au même état
entre deux sondages reste invisible ; le futur composant Moonraker devra donc
prendre son époque dans les notifications.

Le pilotage macro est maintenant centralisé dans `GOALS.md` :

1. `GOAL-P4-OFFLINE-CYCLE-CFS-V1` — terminé hors imprimante ;
2. `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` — terminé en lecture seule avec KO
   borné du mesh actif ;
3. `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1` — installer et qualifier les
   fonctions physiques par petites tranches avec Thomas présent, après le
   chargement contrôlé du profil robuste ;
4. `GOAL-P4-DAILY-CUTOVER-V1` — basculer enfin vers le fonctionnement quotidien
   complet avant la campagne G5.

Ces noms sont des regroupements de pilotage. Ils ne remplacent pas les gates de
`GATES.md` et ne donnent aucune autorité d'installation ou de production.

## Git vérifié avant le commit de cette passation

- base de mission : `5927a7ff49b67dc52a9ae5af6f1a1193ff19003a` ;
- `main` local et `origin/main` étaient alignés sur cette base ;
- divergence : `0/0` ;
- checkout propre au départ ;
- un seul worktree ; travail réalisé sur `codex/k1-read-only-qualification-v1` ;
- aucune branche de mission ou ressource étrangère observée ;
- le SHA final contenant cette passation sera communiqué dans le compte rendu.

## Vérifications réutilisables

- preuve live nettoyée : **OK**, `2/2` lectures ;
- schéma réel : **OK**, stable et épinglé ;
- délai de lecture : **OK**, maximum observé `235,525 ms` sous `5 s` ;
- empreintes distantes : **OK**, exactes et inchangées ;
- CFS, Z et état au repos : **OK** pour la lecture seule ;
- mesh actif conforme au contrat quotidien : **KO borné** ;
- validation physique ou humaine : **non exécutée**, hors périmètre ;
- effet sur la K1 : **aucun** ;
- suite complète : **OK**, `488` tests exécutés, `485` verts et `3` ignorés ;
- scripts PowerShell : **OK**, `29` fichiers relus sans erreur.

## Prochaine mission unique

### Gate préalable au `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1`

Thomas doit être devant la K1. La prochaine gate vérifiera l'état sûr et les
empreintes, chargera uniquement `k1_p001_t055_r001_n06x06`, puis relira le nom
actif et la matrice sans lancer d'impression. Elle s'arrêtera au premier écart
et gardera un retour arrière exact.

Relire dans cet ordre : `HANDOFF.md`, `GOALS.md`, le document 41, le `RESULT.md`
et le contrat du paquet `k1-read-only-qualification-v1`, puis le plan futur.

Cette action modifie l'état d'exécution de la K1 et exige une nouvelle
autorisation explicite ; le Goal 2 clos ne l'autorise pas. Concrètement, le
prochain GO permettra seulement de charger le profil robuste déjà présent et
de vérifier sa matrice, pas d'imprimer ni de commencer toutes les tranches du
Goal 3.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`, car la tâche est petite
mais touche du matériel réel et doit distinguer précisément profil, matrice et
rollback. Option économique : `gpt-5.6-terra` en `medium`, avec un risque plus
élevé de reprise si un état transitoire ou une incohérence de preuve apparaît.
