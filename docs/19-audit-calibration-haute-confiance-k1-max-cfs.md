# Audit calibration haute confiance — K1 Max CFS

Date : 2026-08-23

Portée : K1 Max structure S12, firmware `2.3.5.34`, PRTouch V2, plaque
`PEI_TEXTURED_A`, deux CFS `1.1.3` chaînés et K1 Control.

État de la machine pendant cet audit : éteinte. Toute l'étude et tous les
changements sont hors imprimante.

## Verdict

Oui, une excellente interface de calibration est réaliste dans ce cas. Elle ne
doit pas confondre une jolie sélection `15 × 15` avec une vraie capacité du
capteur. La solution robuste est une interface unique qui adapte ses fonctions
au backend réellement installé :

- immédiatement, PRTouch stock avec profil qualifié, maillage standard `6 × 6`
  et diagnostic statistique à la demande ;
- après qualification dédiée, un mode précision composite produisant 121
  mesures réelles par quatre séquences PRTouch bornées ;
- plus tard seulement, une sonde de scan externe si la vitesse ou la résolution
  justifie le coût, le montage et la reprise complète du chemin Z.

Le choix `15 × 15` dans une seule séquence PRTouch stock n'est pas raisonnable :
la machine exacte s'arrête au point 37. Un `15 × 15` composite stock serait
possible en théorie, mais demanderait au moins neuf séquences lentes et
n'apporte aujourd'hui aucun gain démontré. Une sonde de scan est le backend
raisonnable pour cette densité.

## Ce qui s'est précisément passé

1. L'interface a bien demandé `9 × 9` bicubique.
2. L'adaptateur a bien chargé cette configuration.
3. PRTouch a mesuré exactement 36 points.
4. À la préparation du 37e, `prtouch_v2_wrapper` a levé
   `IndexError: list index out of range`.
5. Le message « nombre de lignes inattendu » provenait ensuite de la matrice
   incomplète ; ce n'était pas la cause initiale.
6. L'arrêt a coupé les chauffes et la restauration a conservé le profil robuste
   `6 × 6`, le Z accepté `−0,04 mm` et les deux CFS.
7. Le XS3002 `nozzle_mcu` observé plus tard appartenait au redémarrage de
   restauration. Klipper a récupéré ; ce XS3002 n'a pas causé l'arrêt du mesh.

Le module binaire contient un compteur `g29_cnt`, des accès indexés
`tri_min_hold_%d` / `tri_max_hold_%d` et l'exception `IndexError`. Le fork
Creality de `probe.py` appelle en plus `run_to_next()` spécialement pour
`prtouch_v2`, au lieu du déplacement Klipper générique. La panne est donc bien
dans le chemin propriétaire exact.

## Qualité déjà démontrée

FIRST-CALIBRATION-V2 a comparé deux lots indépendants de trois maillages
`6 × 6` à `55/140 °C` après `200 s` :

| Mesure | Résultat |
|---|---:|
| différence moyenne absolue | `0,010788694 mm` |
| RMS | `0,013996452 mm` |
| pire point | `0,034352 mm` |
| amplitude du profil robuste | environ `0,532 mm` |
| espacement des contacts `6 × 6` | `58 mm` |
| matrice calculée par Klipper (`mesh_pps=2`) | `16 × 16` |

Le PRTouch de cette machine est donc répétable. Sa faiblesse prouvée est la
densité d'une séquence et son logiciel fermé, pas une absence générale de
précision. Une carte `6 × 6` corrige correctement une déformation globale
lisse ; elle peut manquer une bosse locale entre deux contacts.

## Cas d'usage et comportement attendu

| Cas | Action raisonnable | Ce que l'interface doit bloquer ou expliquer |
|---|---|---|
| même plaque, même température, impression déjà réussie | charger le profil qualifié | ne pas imposer dix minutes de calibration |
| petite pièce centrale, conditions inchangées | profil existant ou vérification courte | un mesh complet n'est pas automatiquement meilleur |
| plaque retirée, retournée ou remplacée | nouveau `6 × 6` ; profil distinct par face | refuser un profil d'une autre plaque/face |
| changement PLA/PETG/ABS ou température plateau | profil de la bonne bande thermique ou nouveau mesh chaud | ne pas réutiliser silencieusement un profil froid |
| changement de buse, hotend ou nettoyage important | revérifier Z puis première couche ; mesh si la géométrie a changé | ne pas confondre Z, débit et forme du plateau |
| imprimante déplacée, firmware changé ou axe Z entretenu | maillage standard et contrôles mécaniques | invalider les anciennes garanties |
| première couche mauvaise sur toute la surface | vérifier Z, débit, propreté et température avant de densifier le mesh | plus de points ne corrige pas un mauvais Z global |
| défaut local récurrent entre points | mode composite `11 × 11` après qualification | ne jamais appeler interpolation « mesure » |
| plateau très incliné ou amplitude importante | diagnostic mécanique puis mesh | le logiciel ne répare pas vis desserrée, axe contraint ou tôle sale |
| annulation, erreur ou navigateur fermé | couper les chauffes, garder le dernier profil validé, proposer reprise/rollback | ne jamais charger un profil partiel |
| coupure électrique | redémarrer sur une base connue et vérifier profil/Z/CFS | aucune reprise aveugle d'une session chaude |
| deux CFS actifs | observer `T1` et `T2`, laisser la calibration propriétaire des températures | aucune commande filament durant le mesh |
| Creality Print en LAN | vérifier le chemin réel de démarrage | KAMP peut être contourné par ce chemin selon un bug ouvert |
| OrcaSlicer | transmettre plaque/température/objets de façon atomique | supprimer l'ancien `+0,27 mm` avant autonomie production |
| besoin de `15 × 15` rapide à chaque impression | sonde de scan externe | PRTouch stock serait beaucoup trop lent |

Creality recommande elle-même une nouvelle calibration après changement de
matériau, déplacement ou firmware, mais pas pour la répétition du même modèle ni
une petite pièce centrale. Klipper rappelle qu'un maillage adaptatif est un
nouveau maillage propre au fichier et qu'il devient risqué si la variation du
plateau dépasse une hauteur de couche.

## Solutions étudiées

| Solution | Qualité potentielle | Double CFS / stock | Risque et maintenance | Décision |
|---|---|---|---|---|
| PRTouch `6 × 6` qualifié | bonne sur forme lisse ; répétabilité déjà mesurée | conservé | faible | base immédiate |
| PRTouch composite `11 × 11` | 121 vraies positions, 29 mm d'espacement | conservé en principe | moyen, qualification physique nécessaire | voie précision retenue |
| `pr_version: 1`, tables retirées | grandes grilles possibles chez certains | incertain | démarrages bloqués rapportés, protections changées | refusé |
| KAMP-K2 / bypass du handler | adaptatif et dense sur K2 | K1 Max annoncé non testé | dépend encore du chemin spécial PRTouch V2 | source d'inspiration, pas installable tel quel |
| CR-Touch / MicroProbe sur firmware CFS | maillage Klipper standard | un montage personnel CFS existe | câblage, support, Z, macros stock et un seul retour public | candidat secondaire |
| BTT Eddy sur firmware CFS | scan rapide dense | projet ciblé `2.3.5.34` CFS | auteur : recalibrages fréquents, Z bêta, wipe et fin d'impression à corriger | expérimental, assurance insuffisante |
| Cartographer + SimpleAF | scan rapide, écosystème mature | SimpleAF ne prend pas en charge le CFS propriétaire | factory reset, montage, firmware de sonde, reprise complète | excellent sans CFS, inadapté aujourd'hui |
| Beacon + SimpleAF | scan/contact rapide | même blocage CFS | firmware fermé ; `SCREWS_TILT` reproduit un crash sur K1 Max | non retenu ici |
| charge cells Klipper ouvertes | garde le principe de contact buse | CFS à réintégrer | soudure, flash MCU, calibration en force ; matériel K1 jugé limité | R&D, pas production actuelle |
| Klipper moderne + sonde + CFS ouvert | contrôle maximal | projet CFS ouvert encore bêta et surtout simple CFS | migration système complète | horizon long terme |

## Architecture recommandée

### Mode quotidien

L'écran commence par identifier plaque, face et température. Il affiche le
profil compatible, son âge et les événements depuis sa création. Par défaut :

- **Utiliser le profil** si rien n'a changé ; démarrage quasi immédiat.
- **Recalibrer standard** si un événement l'impose ; un seul `6 × 6`.
- **Diagnostiquer** si la première couche est mauvaise ; séparer Z, débit,
  température, propreté, mécanique et mesh.

Les six passages restent un outil de qualification ou d'enquête, jamais le
bouton quotidien.

### Mode précision

Le mode composite suit l'ADR-013 : une chauffe, un référencement, quatre
sous-grilles de 36 points maximum, fusion stricte de 121 positions, profil
`11 × 11` bicubique, validation et persistance atomique. Durée prévisible :
environ 18 minutes de palpage, plus la préparation thermique. Il est destiné à
la création ou à la requalification d'un profil plaque/température, pas à
chaque impression.

### Mode expert

Il montre les données brutes, les écarts entre profils, l'amplitude, les pentes,
les points suspects et les journaux. Il peut exporter une preuve et restaurer
un backup. Il ne permet pas de dépasser une capacité sans protocole qualifié.

### Évolution matérielle

L'interface interroge les capacités. Si une sonde de scan qualifiée remplace un
jour PRTouch, elle active les scans rapides et `15 × 15+` sans refaire toute
l'UX. La couche d'acquisition change ; les profils, diagnostics, sauvegardes et
écrans restent.

## Blocages restants avant « beaucoup d'assurance »

1. Le composant de sous-grilles doit être testé hors imprimante puis installé
   comme ajout isolé, sans remplacer la commande stock.
2. Il faut prouver sur la K1 que quatre commandes bornées restent dans la même
   référence Z et que `g29_cnt` repart de zéro à chaque fois.
3. Il faut comparer une vraie première couche `6 × 6` et `11 × 11`; sans gain
   visible ou mesurable, le mode composite restera diagnostic.
4. Il faut tester annulation, erreur au passage 1/2/3/4, rollback, coupure puis
   démarrage complet avec les deux CFS.
5. L'autonomie production reste séparée : Orca/`START_PRINT`, retrait du
   `+0,27 mm`, températures CFS et gate G5.

## Sources externes vérifiées

### Officielles et primaires

- [Creality — configuration usine K1 Max S12_1](https://github.com/CrealityOfficial/K1_Series_Klipper/blob/main/config/K1_MAX_CR4CU220812S12_1/printer.cfg)
- [Creality — chemin spécial PRTouch dans `probe.py`](https://github.com/CrealityOfficial/K1_Series_Klipper/blob/main/klippy/extras/probe.py)
- [Creality — recommandations de calibration](https://wiki.creality.com/en/k1-flagship-series/k1-max/quick-start-guide/printing-parameter-settings)
- [Creality — diagnostic officiel du nivellement](https://wiki.creality.com/en/k1-flagship-series/k1-max/troubleshooting/leveling-trouble-shooting)
- [Klipper — Bed Mesh, interpolation, adaptation et scan](https://www.klipper3d.org/Bed_Mesh.html)
- [Klipper — sécurité des sondes à cellules de charge](https://github.com/Klipper3d/klipper/blob/master/docs/Load_Cell.md)
- [BTT Eddy — guide officiel](https://github.com/bigtreetech/Eddy)
- [Cartographer — K1/K1 Max](https://docs.cartographer3d.com/cartographer-probe/installation-and-setup/creality-k1-and-k1-max-specific)
- [Beacon — documentation Contact](https://docs.beacon3d.com/contact/)

### Projets et retours communautaires

- [Limite 36 points sur K1/K1 Max](https://www.reddit.com/r/crealityk1/comments/17tjiz9/max_36_probe_points_with_kamp/)
- [Contournement `pr_version: 1` et retours contradictoires](https://github.com/Guilouz/Creality-Helper-Script-Wiki/discussions/434)
- [KAMP-K2 et restauration du handler Klipper](https://github.com/grant0013/KAMP-K2)
- [Bug Creality Print LAN contournant KAMP](https://github.com/CrealityOfficial/CrealityPrint/issues/560)
- [SimpleAF — sondes prises en charge](https://pellcorp.github.io/creality-wiki/)
- [SimpleAF — refus documenté des cellules de charge K1](https://pellcorp.github.io/creality-wiki/faq/)
- [SimpleAF — contraintes Cartographer K1 Max](https://pellcorp.github.io/creality-wiki/cartographer/)
- [SimpleAF — limitation Beacon reproduite sur K1 Max](https://pellcorp.github.io/creality-wiki/beacon/)
- [BTT Eddy sur K1 Max CFS `2.3.5.34`](https://github.com/mikeinredding/K1Max-Klipper-Eddy)
- [CR-Touch, KAMP et CFS sur une configuration personnelle](https://github.com/DieDutchman/K1-Max-KAMP-CFS-Fix)
- [Conversion ouverte des cellules de charge K1](https://github.com/cryoz/K1_tenso_manual)
- [Pilote CFS ouvert, encore bêta](https://github.com/gitstonelabs/creality-cfs-klipper)
- [Ellis — incohérences de première couche](https://ellis3dp.com/Print-Tuning-Guide/articles/troubleshooting/first_layer_squish_consistency_issues/first_layer_inconsistency.html)
- [Ellis — dérive thermique](https://ellis3dp.com/Print-Tuning-Guide/articles/troubleshooting/first_layer_squish_consistency_issues/thermal_drift.html)
