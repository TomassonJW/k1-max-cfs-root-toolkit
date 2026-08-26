# HANDOFF — audit CFS minimal clos en KO borné ; preuves suivantes à préparer

Date de passation : 2026-08-26 22:35 +02:00
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`
Mission terminée : `G4-K1-CONTROL-CFS-MINIMAL-OWNER-PROTOCOL-V1`

## État à annoncer immédiatement à Thomas

- **Autonomie calibration quotidienne standard : atteinte.**
- **Autonomie de création et d'édition hors ligne d'un profil dérivé : atteinte.**
- **Autonomie du mode Précision réellement installé : non atteinte.**
- **Autonomie production : non atteinte. Production fermée.**
- L'audit CFS de protocole minimal est clos en **KO borné** : les preuves
  disponibles ne suffisent pas à construire un propriétaire filament sûr.
- `callable_messages=[]`, aucun transport, aucun déployeur et aucun candidat de
  pose n'ont été créés.
- Aucune connexion K1, même en lecture seule, n'a eu lieu pendant la mission.
- Le module MIPS a été haché et inspecté par ses chaînes ; il n'a été ni chargé,
  ni importé, ni exécuté.
- `MESH-EDGE-DIAGNOSTIC-V1` reste suspendue. Son rollback exact est vert : le
  profil diagnostic et quatre G-code sont absents, le robuste reste la base.
- `VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK` reste la dernière validation de cette
  fermeture ; les quatre G-code ne doivent pas être recréés depuis ce handoff.
- Avant toute future action physique : plateau réellement libre confirmé par
  Thomas, route fraîche et purge visible dans une gate revue.
- Aucun `GO` exact antérieur n'autorise la prochaine mission, une connexion K1,
  une capture physique ou la reprise du diagnostic de bord.
- Autorisation de démarrage suivante : **ATTENDRE_GO**. Lire et vérifier est
  permis ; ne modifier aucun fichier avant une nouvelle demande non ambiguë.

## État Git vérifié

- SHA de départ : `49c5314e948a43785e6fae83eab405f0c8499766`.
- Commit de mission : `1fd5ab56cf9d95f541eb567d5fe259ebf45ba0ff`.
- Commit de mission publié sur `origin/main` : oui, vérifié par `ls-remote`.
- Branche cible locale avant le commit de cette passation : `main` au même SHA.
- Branche cible distante avant le commit de cette passation : `origin/main` au
  même SHA.
- Divergence observée avant la passation : `0/0`.
- Checkout cible : propre avant l'édition de ce fichier.
- Branche de mission séparée : aucune ; le travail a été intégré directement
  dans `main` conformément à l'autorité Git du projet.
- Worktree de mission séparé : aucun.
- Autres worktrees : aucun ; `git worktree list --porcelain` ne montre que le
  checkout principal.
- Le commit qui contient ce fichier est le commit documentaire de passation ;
  son SHA final doit être lu par `git log -1 --format=%H`.

## Résultat concret

La gate cherchait le plus petit protocole permettant au propriétaire filament
minimal de l'ADR-020 de charger, retirer, couper, purger, s'arrêter et se
resynchroniser sur deux CFS, sans température ni géométrie cachée et sans
collision avec le propriétaire constructeur.

Le verdict honnête est **KO borné**. La cartographie établit :

- requêtes observées : `0x04`, `0x05`, `0x08`, `0x0a`, `0x0d`, `0x0f`,
  `0x10`, `0x14` ;
- forme visible d'une requête : adresse, longueur, `0xff`, commande, payload ;
- forme visible d'une réponse : `0xf7`, adresse, longueur, état, commande,
  payload ou terminaison ;
- clé d'attente visible : `(adresse, commande)` ;
- identifiant de transaction : non observé ;
- adresses interrogées : 1 et 2 ;
- seule route d'action : `T1A`, adresse 1, slot A, numéro 1 ;
- seul effet filament visible : séquence `EXTRUDE_PROCESS` sur l'adresse 1 ;
- états vus sur cette séquence : `OK` et `EXTRUDE_ERR8`.

Ne sont pas prouvés :

- l'intégrité ou le checksum complet des trames ;
- retrait ou rétraction ;
- coupe isolée ;
- purge isolée ;
- arrêt ou annulation du propriétaire minimal ;
- slots B/C/D ;
- effets filament sur le second CFS ;
- distinction complète réponse/événement hors attente active ;
- resynchronisation sûre après perte ou reconnexion ;
- prise exclusive puis restitution au propriétaire stock.

Les chaînes Cython contiennent les noms de retrait, moteur de connexion et
`extrude2`, mais aucun nom ne devient une trame. Deux lignes `box heart process
not enable` ne prouvent pas l'exclusion du propriétaire constructeur.

## Travail livré

### Paquet exécutable hors ligne

`packages/k1-control-v1/cfs-minimal-owner-protocol-v1/` contient :

- `contract.json` : gate KO, liste appelable vide et règles de blocage ;
- `evidence-map.json` : carte nettoyée, hashes et lignes exactes ;
- `verify_private_evidence.py` : lecture statique, hashes, trames et absences ;
- `emulator.py` : automate déterministe sans réseau, série, SSH ou G-code ;
- `scenarios.json` : 25 cas de corrélation et de refus ;
- `README.md`, `RESULT.md` et `FUTURE-EVIDENCE-PLAN.md`.

L'émulateur refuse les doublons sur une clé en attente, met la clé en
quarantaine après timeout, ne transforme jamais une réponse tardive ou un
événement non corrélé en acquittement, et invalide routes et attentes lors
d'une reconnexion. Une révision de mapping rend aussi l'ancienne route caduque.

### Contrat et décisions

- `docs/32-protocole-proprietaire-filament-minimal-cfs-v1.md` ;
- ADR-021 ;
- D-071 ;
- nouvelle section `cfs_minimal_owner_protocol` dans
  `design/job-lifecycle-contract-v1.json` ;
- `AGENTS.md`, `STATE.md`, `GATES.md`, `ROADMAP.md`, les contrats CFS et les
  index du paquet alignés.

### Tests

- `tests/test_cfs_minimal_owner_protocol_v1.py` ajoute 12 tests ;
- la matrice interne compte 25 scénarios déterministes ;
- les tests vérifient aussi l'absence d'import réseau, série, processus ou
  chargeur binaire.

## Vérifications

### Preuves automatiques

- `verify_private_evidence.py` : **OK**.
  - quatre SHA-256 exacts ;
  - journal complet : `1 342 535` lignes ;
  - fenêtre d'incident : `12 800` lignes ;
  - chaînes statiques : `4 922` lignes ;
  - huit commandes sortantes classées ;
  - `EXTRUDE_PROCESS` vu seulement à l'adresse 1 ;
  - seule route d'action : `T1A` ;
  - aucune donnée d'identité privée émise par le vérificateur.
- `emulator.py` : **OK**, `25/25`.
- tests ciblés : **OK**, `12/12`.
- suite complète : **OK**, `362` tests exécutés, `359` verts et `3` ignorés
  connus pour dépendances ou sandbox locaux.
- `git diff --check` et `git diff --cached --check` du commit mission : **OK**.

### Git

- commit mission créé : **OK** ;
- push de `main` : **OK** ;
- égalité locale/distante du commit mission : **OK** ;
- commit et push de la présente passation : à vérifier après sa création.

### Gates humaines ou matérielles

- connexion K1 : **non exécutée, interdite dans cette mission** ;
- trame série réelle : **non exécutée** ;
- filament, cutter, purge, chauffe, mouvement ou impression : **non exécutés** ;
- exclusion du propriétaire stock : **non validée** ;
- mode Précision installé : **non validé** ;
- production : **fermée**.

## Fichiers privés

Le vérificateur dépend localement de :

`inventory/raw/20260826-cfs-box-wrapper-read-only-audit-v1/`

Ce dossier reste ignoré et hors Git. Il contient le module MIPS, les chaînes et
deux journaux. Ne jamais publier leurs identifiants uniques ou payloads
d'identité. Les seuls éléments versionnés sont les hashes, les lignes, les
trames non identifiantes nécessaires et les conclusions bornées.

Le script temporaire `.codex-work/analyze_cfs_protocol_evidence.py` n'appartenait
pas au livrable et a été supprimé avant la clôture finale.

## Limites et risques

- Un journal prouve ce qui s'est produit, pas toutes les variantes possibles.
- Les noms Cython ne définissent ni identifiant de commande ni payload.
- Sans identifiant de transaction, une réponse tardive reste dangereuse.
- La symétrie entre slots ou unités ne peut pas être supposée.
- Un heartbeat arrêté n'est pas un verrou exclusif.
- La bonne architecture cible de l'ADR-020 n'a toujours aucun protocole
  d'exécution qualifié.
- Le robuste et le Z accepté n'ont pas été revérifiés sur la K1 pendant cette
  mission, puisque toute connexion était hors périmètre.

## Prochaine mission unique

### `G4-K1-CONTROL-CFS-MINIMAL-OWNER-EVIDENCE-V1`

Résultat attendu : acquérir ou préparer les preuves exactes manquantes, sans
inventer de trame et sans modifier la liste appelable tant que le cycle minimal
complet et l'exclusion du propriétaire stock ne sont pas démontrés.

Autorité par défaut après un futur GO : **hors imprimante seulement**.

Ordre recommandé :

1. vérifier `main`, `origin/main`, le worktree et les quatre hashes privés ;
2. relire HANDOFF, ADR-020, ADR-021, D-070, D-071, docs 31/32 et le nouveau
   paquet ;
3. chercher d'abord une source lisible ou une spécification correspondant
   exactement au binaire capturé ;
4. inventorier uniquement les autres preuves statiques déjà locales ;
5. si elles restent insuffisantes, produire un protocole de capture passive
   séparé, revu et borné, sans l'exécuter ;
6. garder `callable_messages=[]` tant que chaque effet nécessaire n'a pas sa
   requête, sa réponse ou son événement, ses erreurs, son timeout, sa reprise et
   son exclusion stock exacts ;
7. fermer la mission OK seulement avec preuves complètes, sinon fermer un
   nouveau KO borné et lister ce qui manque.

Interdits :

- aucune connexion K1, SSH, série, G-code ou API sans autorité fraîche qui la
  nomme explicitement ;
- aucune chauffe, homing, coupe, avance, retrait, purge, restart ou impression ;
- ne jamais charger, importer ou exécuter le `.so` MIPS ;
- aucun transport, déployeur, write-set ou paquet installable ;
- aucun numéro de série, identifiant unique ou payload privé dans Git ;
- ne pas reprendre `MESH-EDGE-DIAGNOSTIC-V1`.

Critère de fin : la provenance de chaque conclusion est exacte, les inconnues
restent bloquées, les tests sont déterministes, le diff est relu et Git est
intégré proprement. Une future capture réelle formera une gate différente.

## Horizons différés

Après preuves complètes seulement : protocole V2 appelable, transport séparé,
qualification physique incrémentale, intégration du ticket thermique, bascule
Orca atomique, puis G5. Aucun de ces horizons n'est ouvert par cette passation.

## Modèle conseillé pour la reprise

- Optimal : `gpt-5.6-sol`, raisonnement `high`. Le travail mélange grands
  journaux, protocole partiellement observable, sécurité matérielle et preuves
  négatives ; une erreur de déduction coûterait plus qu'un passage approfondi.
- Option économique : `gpt-5.6-terra`, raisonnement `high`, acceptable pour un
  inventaire statique étroit ; compromis : davantage de risque de manquer une
  ambiguïté de corrélation ou de devoir reprendre la synthèse.

## Autorisation de démarrage

**ATTENDRE_GO.** Aucun nouveau Goal, aucune nouvelle tâche et aucune action sur
la K1 ne sont créés par cette passation.
