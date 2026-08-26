# HANDOFF — preuves CFS enrichies, protocole toujours fermé

Date de passation : 2026-08-26 23:20 +02:00
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`
Mission terminée : `G4-K1-CONTROL-CFS-MINIMAL-OWNER-EVIDENCE-V1`

## État à annoncer immédiatement à Thomas

- **Autonomie calibration quotidienne standard : atteinte.**
- **Autonomie de création et d'édition hors ligne d'un profil dérivé : atteinte.**
- **Autonomie du mode Précision réellement installé : non atteinte.**
- **Autonomie production : non atteinte. Production fermée.**
- L'audit CFS apporte une preuve solide de retrait constructeur sur `T1A`, mais
  il ne démontre toujours pas un protocole minimal complet et sûr.
- Le verdict est **KO borné avec progrès** et `callable_messages=[]` reste vide.
- Aucun transport, déployeur, write-set ou candidat installable n'a été créé.
- Aucune connexion K1, SSH, série, API ou G-code n'a eu lieu pendant la mission.
- Le module MIPS a seulement été haché et lu comme structure ELF ; il n'a été
  ni chargé, ni importé, ni exécuté.
- `MESH-EDGE-DIAGNOSTIC-V1` reste suspendue. Son rollback exact est vert : le
  profil diagnostic et quatre G-code sont absents, le robuste reste la base.
- `VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK` reste le marqueur de fermeture valide.
- Les quatre G-code ne doivent pas être recréés depuis ce handoff.
- Toute future action physique exige que Thomas confirme le plateau réellement libre,
  ainsi qu'une route fraîche et une purge visible dans une gate revue.
- Aucun `GO` exact antérieur n'autorise une capture réelle, une pose ou une
  reprise physique.
- Autorisation de démarrage suivante : **ATTENDRE_GO**. La prochaine gate
  proposée est passive, distincte et doit recevoir son propre GO exact.

## État Git de départ

- SHA initial local et distant : `a90dc76a54851f80a8be10132fd9066a92c040e4`.
- Branche : `main`, propre et alignée avec `origin/main` au démarrage.
- Branche de mission séparée : aucune.
- Worktree de mission séparé : aucun.
- Autres worktrees observés : aucun.
- Le SHA final de cette passation doit être lu après son commit et son push.

## Résultat concret

La mission a repris toutes les preuves statiques locales autorisées, puis les a
recoupées avec deux documentations publiques de rétro-ingénierie et le dépôt
officiel Creality. Elle ferme quatre points :

1. Deux grands journaux locaux ne sont pas deux expériences indépendantes : le
   plus court est exactement le préfixe du plus long.
2. Une séquence constructeur de retrait est désormais qualifiée sur la route
   déjà connue `T1A`, adresse 1, slot A, numéro 1.
3. Cette séquence envoie successivement les requêtes visibles
   `[1,5,255,17,1,0]` puis `[1,5,255,17,1,1]`, avec une attente de `150 s` et
   deux réponses de succès `[247,1,3,0,17,202]`.
4. Le dernier octet `0xca` de la réponse est cohérent avec le CRC-8 public,
   polynôme `0x07`, calculé sur longueur, état, commande et données.

La transition locale du capteur de filament de `présent` vers `absent` encadre
les deux acquittements. Cela prouve un retrait constructeur réellement observé,
pas une simple chaîne trouvée dans le binaire.

## Pourquoi le protocole reste fermé

La preuve ne suffit pas pour exposer une commande appelable :

- le journal local n'affiche pas la trame sortante complète avec son en-tête et
  son CRC ; la transformation requête visible vers fil série reste inconnue ;
- la route `T1A` n'est pas résolue fraîchement dans le même événement ;
- le contrat terminal d'un chargement isolé n'est pas établi ;
- coupe, purge, arrêt et annulation ne sont pas isolés ;
- timeout réel, réponse tardive et reconnexion ne sont pas qualifiés ;
- les slots B/C/D et le second CFS ne sont pas prouvés ;
- surtout, la prise de propriété face au gestionnaire constructeur, son
  acquittement et sa restitution sûre restent inconnus.

La documentation communautaire confirme la forme générale du protocole et les
deux phases de retrait, mais sa table de commandes diffère de la capture locale.
Elle sert donc de recoupement sémantique, jamais de preuve exacte pour produire
une trame.

## Travail livré

### Paquet hors ligne

`packages/k1-control-v1/cfs-minimal-owner-evidence-v1/` contient :

- `contract.json` : verdict, limites et liste appelable vide ;
- `evidence-map.json` : preuves locales, publiques et manquantes ;
- `verify_private_evidence.py` : vérification statique des hashes, lignes,
  séquences, CRC de réponse et relation de préfixe ;
- `README.md` et `RESULT.md` : mode d'emploi et verdict ;
- `PASSIVE-CAPTURE-PROTOCOL.md` : candidat de capture passive préparé mais non
  autorisé.

Le vérificateur n'importe aucun module réseau ou série, ne lance aucun
processus, ne charge pas le `.so` et ne publie aucune identité privée.

### Contrat et décisions

- `docs/33-preuves-proprietaire-filament-minimal-cfs-v1.md` ;
- ADR-022 ;
- D-072 ;
- section `cfs_minimal_owner_evidence` dans
  `design/job-lifecycle-contract-v1.json` ;
- `AGENTS.md`, `STATE.md`, `GATES.md`, `ROADMAP.md`, `HANDOFF.md` et les index
  du paquet alignés.

### Tests

- `tests/test_cfs_minimal_owner_evidence_v1.py` ajoute 9 tests ;
- suite complète : `371` tests exécutés, `368` verts et `3` ignorés connus ;
- vérificateur privé : `VERIFY_CFS_MINIMAL_OWNER_EVIDENCE_V1_OK`.

## Gates matérielles

- connexion K1 : **non exécutée et interdite dans cette mission** ;
- écoute série réelle : **non exécutée** ;
- trame série envoyée : **non exécutée** ;
- filament, cutter, purge, chauffe, mouvement, restart ou impression :
  **non exécutés** ;
- exclusion puis restauration du propriétaire stock : **non validée** ;
- production : **fermée**.

## Fichiers privés

Les journaux et le binaire restent sous `inventory/raw/`, hors publication.
Seuls leurs hashes, leurs lignes techniques non identifiantes et les conclusions
bornées sont versionnés. Aucun numéro de série, identifiant unique ni payload
d'identité n'a été ajouté au dépôt.

## Prochaine mission unique

### `G4-K1-CONTROL-CFS-MINIMAL-OWNER-PASSIVE-CAPTURE-V1`

Cette gate est seulement préparée. Elle n'est ni autorisée ni exécutée.

But : observer passivement un cycle constructeur borné afin de relier les
actions de haut niveau, les octets réellement présents sur le fil, les réponses,
les changements d'état et la propriété stock, sans injecter aucune trame.

Conditions avant exécution :

1. revue du protocole passif figé ;
2. GO exact de cette nouvelle mission ;
3. confirmation humaine de la configuration physique et du filament ;
4. méthode d'écoute isolée qui ne peut pas écrire sur le bus ;
5. arrêt sûr et suppression des identités avant toute version Git.

Interdits maintenus :

- aucune commande série écrite par l'outil de capture ;
- aucune invention de trame à partir des tables communautaires ;
- aucun transport applicatif, déployeur ou paquet installable ;
- aucun redémarrage, chauffage, mouvement ou cycle filament lancé par Codex ;
- ne pas reprendre `MESH-EDGE-DIAGNOSTIC-V1` ;
- garder `callable_messages=[]` jusqu'à la qualification du cycle minimal
  complet et de l'exclusion du propriétaire constructeur.

Critère de fin : soit la capture remplit les champs manquants avec des preuves
répétables et nettoyées, soit elle ferme un nouveau KO borné sans élargir
l'autorité.

## Modèle conseillé pour la reprise

- Optimal : `gpt-5.6-sol`, raisonnement `high`, à cause du risque matériel, de
  la corrélation temporelle et de la séparation stricte observation/commande.
- Option économique : `gpt-5.6-terra`, raisonnement `high`, acceptable pour
  relire ou affiner le protocole hors imprimante ; compromis : plus de risque
  de manquer une ambiguïté de propriété ou de devoir reprendre l'analyse.

## Autorisation de démarrage

**ATTENDRE_GO.** La présente passation n'autorise aucune nouvelle action sur la
K1 et ne transforme pas la capture passive proposée en mission active.
