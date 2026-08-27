# HANDOFF — reprise propre du pilotage K1 Max CFS

Date de passation : 2026-08-27
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`
Nouvelle tâche créée : non
Goal actif : absent

## État à annoncer immédiatement à Thomas

- **`GOAL-P4-OFFLINE-CYCLE-CFS-V1` est terminé et fermé hors imprimante.**
- Le transport simulé, le cycle complet et le plan futur inerte sont intégrés ;
  aucune connexion à la K1, aucun G-code et aucune action physique n'ont eu lieu.
- La prochaine grande session est une qualification K1 en lecture seule. Elle
  exige une autorité séparée et ne doit envoyer aucune commande.
- La production reste fermée et le mode Précision reste caché.
- Cette session source doit rester visible et ne doit pas être archivée.

## État livré

La dernière grande mission close est `GOAL-P4-OFFLINE-CYCLE-CFS-V1`. Son
transport simulé accepte uniquement `BOX_QUIT_MATERIAL` et
`TURN_OFF_HEATERS`, une fois chacun, et obtient `13/13`. Le moteur pur couvre
les `27/27` scénarios canoniques et ses tests ciblés obtiennent `20/20`.

Le cycle traite admission, nettoyage, référence, mesh/Z, filament correct,
absent ou incorrect, changements, runout, pause, reprise, annulation, reboot,
fin et action séparée `Désengager et nettoyer`. Un timeout ou un effet ambigu
ferme la reprise et n'est jamais rejoué.

Le plan futur épingle trois sources, trois destinations, les sauvegardes, le
rollback et sept petites tranches physiques. Il contient zéro commande distante,
aucun connecteur réel et aucun script de pose.

La dernière observation K1 reste la capture privée `20260827-110102`. Elle est
potentiellement périmée : elle ne vaut ni état frais ni autorité de connexion et
n'autorise aucun retrait.

Le pilotage macro est maintenant centralisé dans `GOALS.md` :

1. `GOAL-P4-OFFLINE-CYCLE-CFS-V1` — terminé hors imprimante ;
2. `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` — prochaine étape, vérifier la K1 sans
   impression ni commande ;
3. `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1` — installer et qualifier les
   fonctions physiques par petites tranches avec Thomas présent ;
4. `GOAL-P4-DAILY-CUTOVER-V1` — basculer enfin vers le fonctionnement quotidien
   complet avant la campagne G5.

Ces noms sont des regroupements de pilotage. Ils ne remplacent pas les gates de
`GATES.md` et ne donnent aucune autorité d'installation ou de production.

## Git vérifié avant le commit de cette passation

- base de mission : `5c0e843dfec32625a42b3daeddc66e4c711b7dc7` ;
- `main` local et `origin/main` étaient alignés sur cette base ;
- divergence : `0/0` ;
- checkout propre au départ ;
- un seul worktree ; travail réalisé sur `codex/offline-cycle-cfs-v1` ;
- aucune branche de mission ou ressource étrangère observée ;
- le SHA final contenant cette passation sera communiqué dans le compte rendu.

## Vérifications réutilisables

- transport simulé : **OK**, `13/13` scénarios et `13/13` tests ciblés ;
- cycle complet : **OK**, `27/27` scénarios et `20/20` tests ciblés ;
- plan futur inerte : **OK**, trois sources, trois destinations, sept tranches,
  zéro commande distante ;
- suite complète : **OK**, `476` tests exécutés, `473` verts et `3` ignorés ;
- nouvelle validation physique ou humaine : **non exécutée**, hors périmètre ;
- connexion ou mutation K1 : **non exécutée**, interdite par le Goal.

## Prochaine mission unique

### `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1`

Résultat attendu : comparer le système local à un état K1 frais sans envoyer de
commande. Il faut confirmer les formes, valeurs, erreurs et délais observables,
puis préparer les futurs connecteurs sans créer de surface d'effet.

Concrètement, la future mission lira seulement les objets utiles, retirera toute
identité avant traitement, comparera deux lectures stables au contrat local et
s'arrêtera sur toute donnée nouvelle ou ambiguë. Aucun G-code, fichier distant,
restart, chauffe, mouvement, retrait ou impression ne sera permis.

Relire dans cet ordre : `HANDOFF.md`, `GOALS.md`, le document 40 sur le cycle
complet hors imprimante, ADR-027, les deux nouveaux contrats et le plan futur.

Critères de fin : forme réelle qualifiée, écarts documentés, futurs appels et
rollback préparés mais non exécutables, tests et Git clos. Le vert restera une
preuve de lecture seule, jamais une qualification physique.

Autorisation de démarrage : **ATTENDRE UNE AUTORITÉ DE CONNEXION LECTURE SEULE**.
Concrètement, Thomas autorisera uniquement l'ouverture d'une connexion pour lire
l'état courant et les empreintes nécessaires, sans aucune commande ni écriture.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`. Option économique : le
même modèle en `medium`, avec plus de risque de manquer une dérive de forme, de
délai ou d'état avant les qualifications physiques.
