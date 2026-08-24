# ADR-014 — Autorité par objectif et autonomie de l'agent

Date : 2026-08-24

Statut : accepté explicitement par Thomas

## Contexte

Les premières campagnes sur la K1 Max utilisaient des phrases `GO ...` exactes
pour séparer fortement la préparation, la pose et les actions physiques. Cette
discipline a aidé à établir les backups, les empreintes, les write-sets et les
rollbacks. Elle a ensuite produit un coût sans bénéfice : une mission déjà
autorisée pouvait rester bloquée parce que le nom littéral d'un delta corrigé
n'apparaissait pas dans le dernier message, même si son périmètre restait
strictement compris dans le Goal.

Thomas demande désormais beaucoup plus d'autonomie. Lorsqu'il formule un
objectif ou active un Goal, il délègue l'exécution complète de cet objectif
sans devoir confirmer chaque commande ou recopier un identifiant interne.

## Options examinées

1. **Conserver un `GO` exact pour chaque révision.** Refusé : cela confond une
   chaîne de caractères avec la maîtrise du risque et interrompt inutilement
   les missions déjà déléguées.
2. **Supprimer toutes les gates et gardes.** Refusé : l'imprimante reste du
   matériel de production ; les états frais, backups, hashes, validations et
   rollbacks restent indispensables.
3. **Faire porter l'autorité sur l'objectif et garder les gates comme preuves
   techniques.** Retenu.

## Décision

Un Goal actif ou une mission clairement décrite autorise Codex à accomplir les
actions normalement nécessaires dans le périmètre demandé. Une formule comme
« tu as les autorisations » confirme ce périmètre courant ; elle ne crée pas un
périmètre futur ou implicite.

Aucune phrase littérale supplémentaire n'est requise. Les identifiants `G4-*`
restent dans les scripts pour sélectionner le bon contrat et relier les preuves
au bon rollback ; Codex les fournit lui-même. Si un script change après une
revue, Codex le relit, le reteste et poursuit sous la même autorité.

Les limites suivantes restent fermes :

- une instruction plus récente et plus restrictive prime ;
- l'objectif ne peut pas être élargi silencieusement ;
- une action physique doit être explicitement comprise dans l'objectif actif ;
- l'état réel doit être revérifié avant une mutation risquée ;
- le write-set, le backup, les empreintes, la validation indépendante et le
  rollback restent proportionnés au risque ;
- une donnée physique non observable doit être confirmée comme un fait avant
  l'action qui en dépend ;
- les contrôles techniques imposés par la plateforme ne peuvent pas être
  désactivés depuis ce dépôt.

## Conséquences

- Thomas n'a plus à recopier de `GO` exact ni à renouveler une permission pour
  une correction qui reste dans la mission active.
- Codex pilote les gates, les scripts, les captures et les reprises jusqu'au
  résultat demandé.
- Les anciennes mentions `ATTENDRE_GO` restent uniquement dans l'historique ;
  elles ne gouvernent plus une roadmap active.
- Les confirmations humaines restantes décrivent un état physique réel, par
  exemple un plateau libre, et non une autorisation administrative.
- Une instruction explicite `stop`, `lecture seule` ou `ne touche pas à
  l'imprimante` ferme immédiatement l'autorité correspondante.

## Alternatives refusées

La confiance ne justifie ni la suppression des preuves ni une autorité sans
périmètre. L'autonomie retenue supprime les blocages administratifs tout en
conservant les protections qui ont une valeur technique mesurable.
