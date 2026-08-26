# HANDOFF — garde hors imprimante du retrait officiel CFS

Date de passation : 2026-08-27
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`
Mission terminée : `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-V1`

## État à annoncer immédiatement à Thomas

- **Le garde du retrait officiel est terminé et vert hors imprimante.**
- Il n'a établi aucune connexion K1 et n'a lancé aucun retrait réel.
- Il refuse sans effet une machine occupée, un CFS incomplet, une commande déjà
  active ou une route ambiguë.
- Après une tentative, il lance au maximum une fois `BOX_QUIT_MATERIAL`, exige
  la vraie libération de la route et ne fait aucun retry automatique.
- Il envoie ensuite une seule fois `TURN_OFF_HEATERS` et exige les deux
  consignes réellement à zéro, même si le retrait a échoué.
- Une réponse HTTP `ok` n'est jamais considérée seule comme une réussite.
- Le segment situé après le cutter peut toujours rester présent dans la tête ;
  le message opérateur l'indique explicitement.
- Aucun transport, déployeur ou candidat de pose n'a été créé.
- Le propriétaire série reste fermé avec `callable_messages=[]`.
- La production reste fermée.
- `MESH-EDGE-DIAGNOSTIC-V1` reste suspendue. Son rollback et son audit CFS
  n'autorisent aucune reprise : le profil diagnostic et quatre G-code sont absents.
- `VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK` reste son marqueur de fermeture valide.
- Les quatre G-code ne doivent pas être recréés depuis ce handoff.
- Toute future action physique exige une route fraîche et, si le plateau est
  concerné, la confirmation « plateau réellement libre ».
- Aucun `GO` exact antérieur ne couvre une nouvelle connexion ou action K1.
- Autorisation suivante : **ATTENDRE_GO**.

## État Git

- SHA initial local et distant :
  `6fe0f0a0d4f2ef4aa2b703e0c184c8efd642b9f7`.
- Branche de mission séparée : aucune.
- Worktree de mission séparé : aucun.
- Autre worktree observé : aucun.
- Le commit de mission et le SHA final doivent être lus après le commit et
  l'envoi de cette passation.

## Travail livré

Le nouveau paquet
`packages/k1-control-v1/cfs-stock-unload-guard-v1/` contient :

- `controller.py` : le garde indépendant du transport ;
- `fake_api.py` : une fausse K1 déterministe sans réseau ;
- `scenarios.json` et `run_scenarios.py` : neuf déroulés succès/panne ;
- `contract.json` : autorité, préconditions, preuves de succès et limites ;
- `README.md`, `RESULT.md` et `NEXT-LIVE-PREFLIGHT.md` : utilisation, résultat
  et prochaine étape en langage courant.

Le contrôleur attend seulement une API injectée capable de lire un état et
d'envoyer une commande. Aucun module réseau, série, SSH ou de processus externe
n'est présent dans le paquet.

## Décision de sécurité

Avant le premier effet, un refus n'envoie aucune commande, y compris aucune
coupure de chauffe : cela évite d'interrompre une impression ou une opération
étrangère déjà active.

Dès que le retrait a été tenté, même si le transport devient ambigu, le garde
tente une fois la coupure globale des chauffes. Le succès final demande :

1. fin stock observée ;
2. route demandée libérée ;
3. commande CFS active redevenue vide ;
4. consignes buse et plateau à zéro ;
5. exactement une commande de retrait et une commande de nettoyage.

Un timeout ou une perte de transport produit un KO lisible et aucune relance.

## Documentation et contrats

- `docs/35-garde-retrait-officiel-cfs-v1.md` ;
- ADR-024 ;
- D-074 ;
- section `cfs_stock_unload_guard` dans
  `design/job-lifecycle-contract-v1.json` ;
- `AGENTS.md`, `STATE.md`, `GATES.md`, `ROADMAP.md`, les index du paquet et des
  tests alignés.

## Vérifications

- matrice hors imprimante : `CFS_STOCK_UNLOAD_GUARD_V1_OK 9/9` ;
- tests ciblés : `18/18` verts ;
- suite complète : `400` tests exécutés, `397` verts et `3` ignorés connus ;
- conflit de nom de fausse API découvert puis corrigé par des noms de modules
  uniques ;
- aucune connexion K1, requête réseau, chauffe, mouvement, retrait, restart ou
  fichier distant ;
- contrôle Git final à compléter après la passation.

## Limites et risques

- Les noms et le sens des champs live ne sont pas encore reliés à une vraie API
  K1.
- Le délai entre deux lectures sera la responsabilité du futur adaptateur ; la
  simulation actuelle avance sans attendre réellement.
- Les slots B/C/D et le second CFS ne sont pas physiquement qualifiés.
- La coupe n'a toujours pas de preuve capteur indépendante.
- Le segment après cutter peut rester dans la tête.
- Chargement, purge, changement complet et reprise après reconnexion restent
  hors périmètre.
- Aucun comportement de production n'est autorisé.

## Prochaine mission unique

### `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-LIVE-PREFLIGHT-V1`

En langage courant : se connecter à la K1 uniquement pour lire son état et
vérifier où se trouvent réellement les informations utilisées par le garde :
machine au repos, deux CFS présents, commande inactive, slot engagé, fin stock
et consignes de chauffe.

Cette étape est utile pour éviter de brancher le garde sur un champ mal compris
ou incomplet. Elle ne lancera aucun retrait, n'enverra aucun G-code, ne chauffera
rien, ne déplacera rien et n'installera aucun fichier.

Le prochain GO exact autorisera uniquement cette connexion en lecture seule.
Il n'autorisera pas un retrait réel. Un futur essai du garde demandera encore
une autorisation distincte après revue des données live.

Critères de fin :

1. chaque champ requis possède une source K1 exacte et stable ;
2. la route engagée se résout sans hypothèse de slot ;
3. les états actif, terminé et en faute sont distinguables ;
4. les deux consignes thermiques sont lisibles ;
5. aucune commande ou écriture n'apparaît dans la capture ;
6. l'adaptateur de lecture peut ensuite être figé hors imprimante.

## Modèle conseillé pour la reprise

- Optimal : `gpt-5.6-sol`, raisonnement `high`, car les champs Creality sont peu
  documentés et une mauvaise interprétation pourrait rendre la future sécurité
  inefficace.
- Option économique : `gpt-5.6-terra`, raisonnement `high`, acceptable pour la
  capture en lecture seule ; compromis : davantage de risque de devoir reprendre
  la correspondance des états avant l'essai réel.

## Autorisation de démarrage

**ATTENDRE_GO.** La mission hors imprimante est close. Rien dans cette
passation n'autorise une connexion K1, un G-code, un retrait, une chauffe, une
pose ou un restart.
