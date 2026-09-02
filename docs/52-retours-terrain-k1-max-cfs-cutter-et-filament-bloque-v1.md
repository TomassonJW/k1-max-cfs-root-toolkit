# 52 — Retours terrain K1 Max + CFS : cutter et filament bloqué

Date : 2026-09-01. Sources publiques, matériel identique ou proche (K1 Max +
kit CFS classique). À confirmer sur notre machine avant d'en faire une règle.

## 1. Procédure officielle Creality — filament bloqué dans la tête

Source : wiki Creality, K1 Max, « Filament Feed Issue/Clog Handling Procedure ».

1. Page de contrôle de l'imprimante → **`OFF`** pour libérer le moteur
   d'extrudeur.
2. Retirer le **clip de verrouillage bleu** en haut de l'extrudeur.
3. Sortir doucement le tube PTFE par le haut de l'extrudeur.
4. Chauffer la buse à la température d'impression du matériau et attendre la
   stabilisation.
5. Tirer le filament **franchement et d'un coup**, à la main.
6. Inspecter l'extrémité du filament : une déformation **en parapluie** signifie
   que le tube PTFE est à remplacer.
7. Si le filament est coincé *dans* le tube, le pousser avec une tige ou une
   clé Allen en L. Retirer la tige rapidement pour éviter que la matière fondue
   ne colle à la paroi du throat et à la roue d'entraînement.

Conséquence pour nous : l'accès manuel au filament **passe par le clip bleu**,
pas par un démontage de la tête. C'est la réponse au blocage « tube PTFE coincé,
plus d'accès au filament ».

## 2. Cutter CFS — défauts connus sur ce matériel

Source : forum Creality, « K1max cfs upgrade cutter issue ».

- Symptôme fréquent : le cutter **n'atteint pas le bloc de coupe**, avec
  l'erreur `Tc2841`, alors que la calibration est déclarée réussie.
- Causes rapportées : désalignement mécanique, `cut_pos_*` mal réglés,
  compatibilité logicielle CFS incomplète selon les versions.
- Correctifs réellement utilisés :
  - ajouter **deux petites rondelles derrière le bloc de coupe** — résout le cas
    de plusieurs utilisateurs ;
  - ajuster `cut_pos_y` **par pas de `0,1 mm`** jusqu'à ce que le levier soit
    **complètement** enfoncé ;
  - contournement manuel entre deux changements de couleur : relâcher la tension
    du tube, retirer le filament, réinsérer, rétracter depuis l'écran ;
  - un cas résolu par remplacement de la carte mère via le support.

Notre situation : `cut_pos_y = 303,2` plus `cut_pos_offset = 1,3`, soit
`304,5`. `BOX_CUT_HALL_TEST` y déclenche le capteur proprement, donc notre
géométrie de coupe est correcte. Ce point n'est pas notre problème.

## 3. Réglages que la communauté considère obligatoires

- `cut_pos_x` / `cut_pos_y` : régler jusqu'à enfoncement complet du levier.
- `Tn_extrude_temp` : température de buse par défaut pour charger/changer le
  filament. Chez nous elle vaut `220` en dur dans `box.cfg` — c'est la source
  du « parasitage de température » constaté, et elle ignore le G-code.
- `extrude_pos_x` / `extrude_pos_y` / `extrude_pos_z` : position du bac de
  purge déployé.

## 4. Primitive de rembobinage documentée

Le mod `FrederickAlt/CREALITY-K1-AND-K1-MAX-CFS-RETRUDE-BEFORE-CUT-MOD`
— déjà cité par notre cartographie — implémente une rétrusion avant coupe et
documente notamment :

- `variable_pre_cut_retrusion` : longueur rétractée avant coupe, de l'ordre de
  `37 mm`, soit la longueur du heatbreak ;
- `variable_pre_cut_retrusion_speed` : environ `33 mm/s` ;
- `BOX_RETRUDE_PROCESS ADDR=<boîtier, base 0> NUM=<bobine, base 0>` pour
  remplir le buffer.

Cette dernière commande est une piste sérieuse pour un rembobinage piloté,
puisqu'elle adresse explicitement le boîtier et la bobine. Elle reste une
commande `BOX_*` : elle est donc bloquée tant que le propriétaire direct
K1 Control est actif.

## 5. Ce que ça change pour le projet

- Le blocage du jour n'est **pas** matériel et **pas** firmware : c'est notre
  propre composant `k1_control_cfs_direct_owner`, posé `enabled: true` avec
  `stock_commands_blocked: true`, qui refuse toute commande `BOX_*` sans offrir
  de retrait de remplacement.
- Toute prise de propriété du CFS doit désormais livrer, **dans la même
  tranche**, un chemin de retrait et de rembobinage fonctionnel. Poser un garde
  d'exclusion avant d'avoir son remplaçant crée un verrou sans clé.
- Le `220 °C` de `Tn_extrude_temp` est confirmé comme réglage attendu du kit :
  le respect des températures du G-code passe par sa neutralisation explicite.

Sources :

- <https://wiki.creality.com/en/k1-flagship-series/k1-max/troubleshooting/filament-feed-issue>
- <https://forum.creality.com/t/k1max-cfs-upgrade-cutter-issue/39088>
- <https://forum.creality.com/t/filament-stuck-in-print-head-of-k1-max/4245>
- <https://github.com/FrederickAlt/CREALITY-K1-AND-K1-MAX-CFS-RETRUDE-BEFORE-CUT-MOD>
