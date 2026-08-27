# ADR-029 — Nomenclature des profils mesh et référence actuelle 11 × 11

Date : 2026-08-27

Statut : **acceptée ; corrige la nomenclature courante sans réécrire les
identifiants historiques**

## Contexte

Le projet appelait `robuste` le profil quotidien
`k1_p001_t055_r001_n06x06`. Ce mot a fini par être interprété comme un verdict
de qualité générale. Cette interprétation est fausse : tous les profils actuels
ont des défauts visibles aux bords.

La comparaison physique disponible montre que le composite
`k1_p001_t055_r001_n11x11` est largement le meilleur résultat global et le
moins mauvais aux bords. Il reste pourtant imparfait et ne mérite pas lui-même
le qualificatif `robuste`.

Une activation du `6 × 6` a été exécutée sur la base de cette mauvaise
nomenclature. Elle a été corrigée par
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1`, qui a remis le `11 × 11` actif
sans mouvement, chauffe, fichier distant ni restart.

## Décision

La nomenclature courante devient :

| Objet | Nom métier courant | État réel |
| --- | --- | --- |
| `default` | profil stock historique | défauts de bord, non qualifié globalement |
| `k1_p001_t055_r001_n06x06` | profil quotidien historique `6 × 6` | défauts de bord, ancien repli, pas robuste |
| `k1_p001_t055_r001_n11x11` | meilleur profil observé `11 × 11` | meilleur résultat global, défauts de bord persistants, source immuable |
| `k1_p001_t055_r001_n11x11_tuned_vNNN` | candidat dérivé corrigé | éditable point par point, non robuste avant validation complète |
| `robuste` | état de qualification futur | aucun profil actuel ne le possède |

Le mot `robuste` devient un **verdict obtenu après validation physique sur toute
la zone utile**, pas le surnom permanent d'une taille de matrice.

Les identifiants historiques de gates, fichiers et captures contenant
`ROBUST-*` ne sont pas renommés : les changer casserait la traçabilité des
preuves déjà closes. Chaque document courant doit toutefois signaler que cette
nomenclature est obsolète et pointer vers la présente ADR.

## Édition point par point

`MESH-EDITOR-OFFLINE-V1` fournit déjà le socle demandé :

- sélection d'un point unique, d'une ligne, d'une colonne ou d'une zone bornée ;
- pas explicites de `0,005` et `0,010 mm` ;
- source, correction demandée, correction normalisée et matrice finale séparées ;
- historique, annulation, restauration et exports déterministes ;
- source `11 × 11` immuable et profil dérivé versionné ;
- aucun transport K1 ni mélange avec le Z global.

La suite ne recrée donc pas un second éditeur. Elle rend cette capacité plus
explicite dans l'interface, puis utilise le `11 × 11` comme source des
corrections de bord. Chaque candidat reste `draft` jusqu'à une comparaison
physique complète et répétée.

## Conséquences

### Positives

- la taille `6 × 6` n'est plus confondue avec une preuve de robustesse ;
- le meilleur profil réellement observé reste actif pendant le travail ;
- les corrections de bord partent de la meilleure source disponible ;
- l'historique et les preuves existantes restent récupérables.

### Négatives

- plusieurs documents historiques utilisent encore l'ancien mot dans leur
  identifiant ;
- aucun profil ne peut actuellement être présenté comme pleinement robuste ;
- la qualification demandera plusieurs motifs physiques comparables.

## Alternatives refusées

### Renommer immédiatement tous les identifiants historiques

Refusé : cela casserait les liens entre captures, contrats, scripts et commits.

### Déclarer le `11 × 11` robuste parce qu'il est le meilleur

Refusé : `meilleur actuel` ne signifie pas `sans défaut de bord`.

### Repartir d'un nouvel éditeur

Refusé : le moteur existant couvre déjà l'édition point par point, la
traçabilité, les gardes et les exports. Le dupliquer augmenterait le risque et
la maintenance sans bénéfice.
