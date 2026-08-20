# ADR-001 — Reprendre la température du CFS sans remplacer son pilote

Date : 2026-08-20
Statut : rejeté par Thomas le 2026-08-20 ; jamais déployé

## Problème confirmé

Le fichier de production observé demande `190 °C` au démarrage puis `195 °C`
pour l'impression. Il ne contient aucune commande demandant `220 °C`.

Le CFS choisit pourtant `220 °C` :

- au chargement et à la purge de démarrage ;
- après le remplacement automatique d'une bobine PLA par une autre bobine PLA.

La configuration active fixe `Tn_extrude_temp` à `220`. Le module CFS compilé
lit aussi une base de matériaux dont l'entrée PLA par défaut vaut `220`. Après
la commande de reprise, la couche interne de lecture du fichier rejoue le nouvel
outil physique et réapplique cette température. Une simple commande placée avant
la reprise arrive donc trop tôt.

La pression d'avance n'est pas la cause de cet incident : le fichier a repris
la main avec `0.03`, valeur restée active pendant le remplacement de bobine.

## Options étudiées

### 1. Ne modifier que le profil OrcaSlicer

Refusé. Le fichier observé contient déjà les bonnes températures et aucune
commande à `220 °C`. Le remplacement automatique se produit en dehors du G-code
normal du fichier.

### 2. Remplacer ou modifier le pilote CFS compilé

Différé. Ce serait la seule voie propre pour gérer immédiatement plusieurs
matériaux et une température différente pour chaque bobine. Elle augmente
fortement le risque sur l'écran, les deux CFS et la reprise après épuisement.
Les remplacements ouverts consultés ne déclarent pas encore cette K1 Max et ses
deux CFS comme une combinaison validée.

### 3. Contrat PLA étroit autour du pilote d'origine

Retenu comme premier candidat G4. Le pilote d'origine reste en place :

- sa température fixe passe de `220` à `195 °C` ;
- le démarrage exige explicitement le profil `GEEETECH_PLA`, `190 °C` pour la
  première couche et `195 °C` pour l'impression normale ;
- un changement automatique mémorise la cible en cours ;
- si le pilote rejoue `195 °C` après la reprise alors que Thomas avait demandé
  `190 °C`, une garde courte remet immédiatement la valeur mémorisée ;
- tout autre contrat est bloqué avant le premier appel au CFS.

## Rejet et portée historique

L'option 3 a été préparée localement puis rejetée avant tout déploiement. Son
couple fixe `190/195`, son profil Geeetech obligatoire et son refus des autres
matériaux sont incompatibles avec l'usage réel de la machine.

Le besoin corrigé est défini dans `docs/07-dynamic-cfs-temperature-requirements.md` :
pendant une impression, la dernière température explicite du G-code ou de Thomas
doit toujours gagner. Aucun couple de températures et aucun matériau ne sera
codé en dur dans le prochain candidat.

## Conséquences

- Un fichier sans les trois paramètres explicites est arrêté avant chargement.
- PETG, ABS, ASA, TPU et profils PLA à d'autres températures sont volontairement
  refusés tant qu'un autre contrat n'a pas été conçu et validé.
- La déclaration PLA des bobines dans le CFS doit correspondre au filament réel.
- Z, nivellement, pression d'avance, ironing et nettoyage de buse restent hors
  de ce changement.
- Aucun `G4-CFS-TEMP-PLA` ne sera ouvert ; ce candidat est retiré.

## Sources de comparaison

- Le dépôt officiel Creality contient un profil `K1_CFS`, ce qui confirme que
  cette combinaison est prise en charge par l'écosystème du constructeur :
  <https://github.com/CrealityOfficial/CrealityPrint/blob/master/resources/profiles/Creality/machine/Creality%20K1_CFS-C%200.4%20nozzle.json>
- Une rétro-ingénierie indépendante documente le paramètre optionnel `TEMP` de
  `BOX_MATERIAL_FLUSH`, mais aussi l'absence de réglage de `Tn_extrude_temp` dans
  l'interface de modification à chaud :
  <https://github.com/FrederickAlt/CREALITY-K1-AND-K1-MAX-CFS-RETRUDE-BEFORE-CUT-MOD/blob/083c5a5679d5f7d3f3cfff9a6303b6d224347c29/docs/klipper-macros.md>
  et
  <https://github.com/FrederickAlt/CREALITY-K1-AND-K1-MAX-CFS-RETRUDE-BEFORE-CUT-MOD/blob/083c5a5679d5f7d3f3cfff9a6303b6d224347c29/docs/configuration.md>.

Ces sources servent seulement de comparaison. La décision repose sur les
traces et les fichiers exacts de la machine de Thomas.
