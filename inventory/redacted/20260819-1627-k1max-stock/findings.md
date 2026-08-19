# Résultats de l’acquisition P1

## Faits confirmés

- Firmware : `2.3.5.34`, compilé le 12 juin 2025.
- Système : Buildroot 2020.02.1, Linux 4.4.94, architecture MIPS.
- Identité de carte déclarée par le firmware : `CR4CU220812S11`.
- En-tête de la configuration active : `CR4CU220812S12`.
- Configuration active : `/usr/data/printer_data/config/printer.cfg`.
- Racine constructeur en squashfs, modifications via overlay ext4, données persistantes sous `/usr/data`.
- Klipper et la pile Creality sont actifs ; Moonraker n’a pas été observé.
- Deux CFS sont déclarés par l’opérateur en version `1.1.3`.
- Le CFS est relié par une liaison série 485 et possède ses propres commandes de coupe, chargement, retrait, nettoyage et purge.
- Les journaux Klipper utilisent environ 1,6 GiB.
- Aucune écriture distante n’a été effectuée.

## Résultats mesurés pertinents

- Le bloc `SAVE_CONFIG` actif contient `z_offset = 0.000`.
- Un seul instantané historique contient `-0.025`; les suivants reviennent à zéro.
- La température `Tn_extrude_temp` du CFS est fixée à `220 °C` dans la configuration active.
- `START_PRINT` déclenche des opérations firmware après les consignes issues du trancheur.

## Hypothèses à tester, pas encore des conclusions

1. La remise à zéro du Z-offset pourrait provenir d’une sauvegarde ou migration de configuration, d’une commande `CX_*`, de `CXSAVE_CONFIG` ou d’un chemin applicatif Creality.
2. L’écrasement de température pourrait provenir du module CFS utilisant `Tn_extrude_temp` ou une température de purge interne.
3. L’écart S11/S12 pourrait être un simple en-tête constructeur obsolète, une migration incorrecte ou une configuration réellement inadaptée. Il faut lire le code de sélection et comparer les variantes avant toute décision.

## Limites connues

- aucun mouvement, chauffage, homing, nivellement ou test d’impression n’a été lancé ;
- aucune comparaison de deux exécutions identiques n’est encore disponible ;
- les versions CFS viennent de l’écran, pas d’un fichier distant identifié ;
- la carte des ports n’a pas été capturée correctement ;
- l’image de récupération disponible en ligne n’a pas encore été vérifiée ni copiée localement ;
- les fichiers constructeur bruts restent privés et ne sont pas publiés.

## Prochaine gate

G2 peut être considérée atteinte pour l’acquisition stock ciblée. La suite autorisée commence par l’analyse locale G3 et la préparation d’un protocole de traces reproductibles. Les sources Python des extensions `BOX_*`, `CX_*`, `ACCURATE_HOME_Z` et `CXSAVE_CONFIG` n’ayant pas été copiées, une acquisition ultérieure limitée à ces modules pourra être nécessaire. Aucune modification de l’imprimante n’est autorisée.
