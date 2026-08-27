# HANDOFF — reprise propre du pilotage K1 Max CFS

Date de passation : 2026-08-27
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`
Nouvelle tâche créée : non
Goal actif : absent

## État à annoncer immédiatement à Thomas

- **Le travail de cette session est fermé proprement et prêt à reprendre plus
  tard dans une session neuve.**
- Les quatre grandes sessions futures sont enregistrées dans `GOALS.md` et
  reliées à `ROADMAP.md` et `STATE.md`.
- La prochaine grande session est entièrement hors imprimante. Elle ne doit ni
  se connecter à la K1, ni envoyer de G-code, ni produire d'action physique.
- La production reste fermée et le mode Précision reste caché.
- Cette session source doit rester visible et ne doit pas être archivée.

## État livré

La dernière gate technique close est
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-LIVE-READ-ONLY-V1`. Deux lectures
K1 stables ont confirmé `T1/T2` connectés, aucune route engagée, commande CFS
vide, cibles zéro et configurations inchangées. Les identités sont retirées
avant l'adaptateur. L'état fonctionnel reste `BLOCKED_NO_ENGAGED_ROUTE`.

Cette observation date de la capture privée `20260827-110102`. Elle devra être
considérée comme potentiellement périmée dans une future session ; elle ne vaut
pas préflight frais et n'autorise aucun retrait.

Le pilotage macro est maintenant centralisé dans `GOALS.md` :

1. `GOAL-P4-OFFLINE-CYCLE-CFS-V1` — terminer tout le système hors imprimante ;
2. `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` — vérifier ensuite la vraie K1 sans
   impression ni commande ;
3. `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1` — installer et qualifier les
   fonctions physiques par petites tranches avec Thomas présent ;
4. `GOAL-P4-DAILY-CUTOVER-V1` — basculer enfin vers le fonctionnement quotidien
   complet avant la campagne G5.

Ces noms sont des regroupements de pilotage. Ils ne remplacent pas les gates de
`GATES.md` et ne donnent aucune autorité d'installation ou de production.

## Git vérifié avant le commit de cette passation

- dernier commit de pilotage :
  `0a59107248f5517590828a2e4dd26ac56ced2a14` ;
- `main` local et `origin/main` alignés avant cette modification ;
- divergence : `0/0` ;
- checkout propre au départ ;
- un seul worktree, sur `main` ;
- aucune branche de mission ou ressource étrangère observée ;
- le SHA final contenant cette passation sera communiqué dans le compte rendu.

## Vérifications réutilisables

- dernière suite complète après changement du code CFS : **OK**, `443` tests
  exécutés, `440` verts et `3` ignorés connus ;
- validation live nettoyée de l'adaptateur : **OK** ;
- documentation des grands Goals : **OK**, `git diff --check` et contrôle
  staged verts lors de son commit ;
- nouvelle validation physique ou humaine : **non exécutée**, hors périmètre ;
- suite complète relancée pour cette passation documentaire : **non**, inutile
  puisque le code n'a pas changé.

## Prochaine mission unique

### `GOAL-P4-OFFLINE-CYCLE-CFS-V1`

Résultat attendu : terminer et intégrer tout le système hors imprimante du cycle
d'impression et du garde CFS, depuis le transport simulé jusqu'à la préparation
complète des futures étapes réelles.

Première mission interne :
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-TRANSPORT-OFFLINE-V1`.

Concrètement, il faut tester la lecture simulée, les deux commandes déjà figées,
les délais, coupures, faux succès, doubles envois, arrêt thermique, changements
de filament, pause, reprise, annulation et fin. Aucun accès K1, G-code réel,
chauffage, mouvement, retrait, fichier distant ou candidat de pose n'est permis.

Relire dans cet ordre : `HANDOFF.md`, `GOALS.md`, le début de `ROADMAP.md`, la
gate courante dans `GATES.md`, puis les contrats du garde et de l'adaptateur.

Critères de fin : cycle hors ligne déterministe, aucun retry automatique, erreurs
et délais fermés, tests ciblés et suite complète verts, documentation et Git
clos, puis nouvelle passation.

Autorisation de démarrage : **ATTENDRE_GO**. Dans la future session, Thomas peut
envoyer `GO GOAL-P4-OFFLINE-CYCLE-CFS-V1`. S'il veut retrouver l'autonomie de
session sans demandes répétées, il doit aussi invoquer explicitement
`$session-tas` dans ce nouveau clavardage.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`. Option économique : le
même modèle en `medium`, avec plus de risque d'oublier un cas de délai, de double
commande ou de reprise après erreur.
