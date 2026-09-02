# ADR-041 — Le signal réel du capteur cutter est la console, pas `box.cut_pos`

Date : 2026-09-01

Statut : **acceptée**. Remplace la garde d'ADR-040 fondée sur `box.cut_pos`.

## Contexte

Le retrait intégré `T1A` était bloqué depuis plusieurs jours. La garde exigeait
d'observer `box.cut_pos : 0 → 1 → 0`. Trois fenêtres de surveillance manuelle
(`90 s`, une longue interrompue, puis `600 s`) n'ont capté aucune transition,
et un appui humain direct sur le levier n'a rien produit non plus.

Le handoff du 1er septembre affirmait que « les traces historiques de cette
même K1 prouvent qu'un cycle stock fonctionnel publiait `cut_pos=1` ».

## Constats

1. Cette affirmation n'est étayée par aucune preuve du dépôt. Dans tout
   `inventory/`, `cut_pos` vaut `0.0` sans une seule exception. Aucune
   occurrence de `cut_pos=1` n'existe.
2. Une souscription Klipper (`objects/subscribe`) tenue pendant l'exécution
   complète de `BOX_CUT_HALL_TEST` a reçu **zéro** notification de changement
   sur `box.cut_pos`, alors que le capteur s'est bien déclenché. Ce champ ne
   reflète pas l'état du capteur.
3. Le capteur du cutter est un capteur à effet **Hall**, pas un contact
   mécanique. Le firmware expose `BOX_CUT_HALL_TEST` et `BOX_CUT_HALL_ZERO`.
   Un appui manuel sur le levier ne constitue donc pas un test valide.
4. Le capteur est **fonctionnel**. `BOX_CUT_HALL_TEST`, machine froide et
   `X/Y` référencés, amène la tête à `Y304,5` et publie sur la console :

   ```
   // [box] cut sensor state:1
   // cut to return failed index: 3
   // [box] cut sensor state:0
   // cself.release_failed_num: 0
   ```

## Décision

Le signal canonique du capteur cutter est la ligne console
`[box] cut sensor state:N`, lue via `gcode/subscribe_output`. `box.cut_pos` est
déclaré **non fiable** et ne doit plus servir de garde, de préflight ni de
critère d'arrêt.

La qualification du capteur se fait par `BOX_CUT_HALL_TEST`, pas par un appui
humain. Cette commande déplace la tête et exige `X/Y` référencés ; elle
n'exige pas `Z`, ce qui évite tout contact buse/plateau à froid.

## Conséquences

- La garde d'ADR-040 fondée sur `cut_pos` est retirée.
- Le geste humain « appuyer sur le levier » est supprimé de la liste de reprise.
- Toute lecture d'état ponctuelle est insuffisante pour un signal transitoire :
  les gardes sur événements brefs doivent souscrire, jamais échantillonner.
- Une affirmation de preuve historique doit citer une capture existante ; à
  défaut elle est traitée comme une hypothèse et ne peut pas fermer une porte.
