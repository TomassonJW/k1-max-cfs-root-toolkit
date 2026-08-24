# ADR-013 — Maillage composite réel et interface guidée par les capacités

Date : 2026-08-23

Statut : **accepté et qualifié sur la K1 réelle** ; amende l'ADR-012 ;
l'exposition UI reste conditionnée par la comparaison de premières couches

## Contexte

L'ADR-012 a correctement interdit un maillage PRTouch de plus de trente-six
contacts dans une seule séquence. L'essai réel `9 × 9` a atteint
`g29_cnt=36`, puis le module propriétaire `prtouch_v2_wrapper` a levé un
`IndexError` avant le point 37.

Cette preuve ne signifie toutefois pas que Klipper, un profil enregistré ou
l'interface sont limités à une matrice finale `6 × 6`. Elle prouve seulement
que le chemin d'acquisition PRTouch V2 de cette K1 Max est limité à 36 contacts
entre un début et une fin de séquence.

Les faits supplémentaires suivants changent la décision de produit :

- les 36 paires `tri_min_hold_1..36` et `tri_max_hold_1..36` de la machine
  exacte ont toutes les mêmes valeurs ; elles ne constituent pas une
  calibration spatiale propre à chacun des 36 emplacements ;
- FIRST-CALIBRATION-V2 a exécuté six maillages `6 × 6` consécutifs sans
  dépassement : le compteur propriétaire est bien réinitialisé entre deux
  séquences ;
- les deux médianes indépendantes de trois maillages diffèrent de
  `0,010788694 mm` en moyenne, `0,013996452 mm` RMS et `0,034352 mm` au pire ;
- Klipper distingue les points physiques de la matrice interpolée et sait
  charger des profils bicubiques plus denses que la grille utilisée par la
  configuration courante ;
- un maillage final dense peut être construit à partir de plusieurs
  sous-grilles réelles, chacune restant à 36 points ou moins.

## Options examinées

1. **Forcer `9 × 9` ou davantage dans une seule séquence PRTouch V2.**
   Refusé : panne réelle au point 37.
2. **Passer `pr_version: 1` et retirer les tables de seuil.** Refusé : cela
   remplace le chemin capteur qualifié, avec des retours communautaires
   contradictoires et des blocages après redémarrage.
3. **Présenter l'interpolation `16 × 16` actuelle comme 256 mesures.** Refusé :
   ce serait faux. Le profil `6 × 6` actuel contient 36 mesures et Klipper
   calcule ensuite une surface `16 × 16` avec `mesh_pps=2`.
4. **Installer immédiatement une sonde externe et remplacer le firmware.**
   Refusé comme réponse immédiate : les solutions modernes sont prometteuses,
   mais aucune pile publique n'est aujourd'hui qualifiée pour cette K1 Max
   exacte avec deux CFS chaînés, l'écran, Orca et la reprise après coupure.
5. **Composer une vraie matrice dense à partir de plusieurs acquisitions
   bornées.** Retenu comme voie de précision à qualifier.

## Décision

K1 Control devient guidé par les capacités réelles du backend et non par une
liste universelle de tailles.

### Backend PRTouch V2 stock

- **Réutilisation** : charger le profil déjà qualifié pour la même plaque et la
  même bande de température, sans nouvelle mesure.
- **Standard** : un maillage physique `6 × 6` complet, 36 contacts, pour un
  changement de plaque, de température, de buse, de firmware, de position de
  machine ou après un défaut de première couche.
- **Précision** : quatre sous-grilles carrées `6 × 6` dans une seule session
  chaude et un seul référencement, puis fusion en une vraie matrice physique
  `11 × 11` bicubique : nord-ouest, nord-est, sud-ouest et sud-est. Les
  quadrants partagent la ligne et la colonne centrales.
- **Diagnostic** : répétitions statistiques uniquement lorsqu'un écart ou un
  événement le justifie ; jamais six passages par défaut.

Pour une zone `5..295 mm`, le profil composite comporte des positions tous les
`29 mm`. Chaque sous-grille reste à 36 contacts maximum. La fusion porte 144
contacts et 121 positions distinctes. Les 23 contacts répétés couvrent 21
positions de jonction ; ils sont moyennés et l'écart maximal admis entre leurs
mesures est `0,05 mm`. Il n'y a aucune interpolation cachée entre les 121
positions finales.

Chaque quadrant peut recevoir un biais vertical constant différent du
post-traitement propriétaire. La fusion estime donc un unique décalage additif
par quadrant à partir des seules positions communes. Les quatre décalages sont
recentrés pour garder une moyenne pondérée nulle, puis les valeurs communes
sont moyennées. Aucun plan, courbe ou correction locale libre n'est ajusté :
si l'écart résiduel maximal dépasse `0,05 mm`, le profil reste refusé.

La recette initiale `6 × 6 + 5 × 6 + 6 × 5 + 5 × 5` est remplacée : l'essai
réel du 24 août 2026 a prouvé que `prtouch_v2_wrapper.bed_mesh_post_proc` lève
un `IndexError` après les 30 contacts d'une grille rectangulaire `5 × 6`.

La campagne carrée réelle a ensuite prouvé les quatre séquences `6 × 6` et 144
contacts. Les valeurs exposées par Klipper présentaient un écart brut maximal
de `0,147858 mm` aux jonctions, cohérent avec un biais constant nord/sud du
post-traitement. L'ajustement additif borné donne un écart maximal
`0,043745029 mm` et moyen `0,013871331 mm`. Ces valeurs restent sous la garde
`0,05 mm` et autorisent une reprise logique des mesures conservées, sans les
rejouer physiquement.

Les quatre acquisitions doivent partager le même identifiant de session, la
même plaque, les mêmes cibles thermiques, le même référencement des axes et
aucun redémarrage Klipper entre elles. Cette contrainte évite d'introduire un
décalage Z différent entre sous-grilles.

### Précision d'implémentation hors imprimante

L'endpoint Creality `update_mesh` ne change que `probed_matrix` dans le `ZMesh`
déjà actif. Il ne recrée pas ses bornes, sa taille ou son algorithme. Il ne doit
donc jamais recevoir directement la matrice `11 × 11` après le dernier passage
`5 × 5`.

Le candidat retenu prépare un bloc de profil Klipper complet uniquement après
la fusion des 121 valeurs. Il exige le profil robuste `6 × 6` unique et
l'absence du profil cible. Cette méthode reste hors imprimante : sa transaction
atomique, son parse avec le Python exact, son restart après coupure des chauffes,
sa relecture et son rollback bit à bit doivent encore être prouvés après la gate
SUBGRID-V1. Cette précision n'autorise aucune écriture de `printer.cfg`.

### Backends futurs

Une sonde Cartographer, Beacon ou Eddy pourra exposer un mode de scan rapide et
des matrices `15 × 15` ou supérieures uniquement si le backend installé les
mesure réellement. Une CR-Touch ou MicroProbe pourra exposer ses propres
tailles et durées. L'interface ne promet jamais une capacité absente.

## Pourquoi `11 × 11` et pas `15 × 15` sur le PRTouch stock

Un `11 × 11` composite demande quatre séquences carrées et 144 contacts. Un
`15 × 15` exigerait au minimum neuf sous-grilles de `5 × 5`, soit 225 contacts.
Les mesures réelles actuelles durent environ 4 min 20 à 4 min 30 par maillage
`6 × 6`. Le mode `15 × 15` dépasserait donc raisonnablement quarante minutes de
palpage, hors chauffe, nettoyage et validation, sans preuve qu'il améliorerait
la première couche d'une tôle PEI physiquement lisse. Ce mode est refusé sur le
backend stock ; il devient raisonnable avec une sonde de scan rapide.

## Interface cible

La page doit afficher séparément :

- le nombre de contacts physiques, la matrice finale et la matrice interpolée ;
- la plaque, la température, le temps de stabilisation et l'âge du profil ;
- la durée estimée avant lancement ;
- l'amplitude, la répétabilité, la dérive par rapport au profil de référence et
  les anomalies locales ;
- un mode quotidien simple et un mode expert replié ;
- les raisons qui rendent une nouvelle calibration nécessaire ;
- un journal lisible, l'état du backup, l'annulation, la restauration et la
  récupération après redémarrage ;
- l'état des deux CFS, sans leur attribuer la propriété des températures pendant
  une calibration.

## Gates de qualification obligatoires

1. Fusion et rejets testés entièrement hors imprimante sur données synthétiques.
2. Composant installé sans modifier `pr_version`, les 72 tables, les macros CFS
   ni la commande stock `BED_MESH_CALIBRATE`.
3. Pose sans mouvement du composant séparé, puis petite grille bornée prouvant
   l'appel dynamique au moteur Bed Mesh et le retour au repos. Le premier essai
   retenu est la partition impaire/impaire `5 × 5`, de `34` à `266 mm`, soit 25
   contacts. Un restart est permis uniquement après sa capture afin de nettoyer
   la session ; il ne prouve pas encore l'enchaînement sans restart.
4. Une sous-grille décalée de 36 points maximum, avec arrêt, chauffes à zéro et
   rollback automatique sur toute divergence. La future campagne de quatre
   sous-grilles interdira tout restart avant la quatrième capture.
5. Quatre sous-grilles carrées complètes dans la même session ; preuve de 144
   contacts, 121 positions uniques, recouvrements conformes et profil final
   `11 × 11` bicubique.
6. Comparaison du profil composite avec le robuste `6 × 6`, puis recette de
   première couche sur plusieurs zones.
7. Coupure complète et redémarrage : écran, Klipper, profil, Z accepté et deux
   CFS conformes.
8. Annulation à chaque frontière, reprise, restauration du backup exact et
   absence de profil partiel chargé.

Le mode précision ne devient visible dans l'interface qu'après ces gates. Il
reste derrière une indication claire de durée et n'est jamais lancé avant
chaque impression.

## Conséquences

- ADR-012 reste valide pour la limite de 36 contacts par séquence et pour le
  maillage quotidien unique ; sa conclusion « seule matrice finale `6 × 6` »
  est remplacée par la présente décision.
- Le paquet correctif `6 × 6 / 1 passage` demeure la base sûre à déployer en
  premier.
- La matrice composite est une mission séparée, préparée et testée hors
  imprimante avant toute nouvelle gate physique.
- Aucune modification de l'imprimante n'est autorisée par cet ADR.

## Sources principales

- [Klipper — Bed Mesh](https://www.klipper3d.org/Bed_Mesh.html)
- [Creality — configuration K1 Max S12_1](https://github.com/CrealityOfficial/K1_Series_Klipper/blob/main/config/K1_MAX_CR4CU220812S12_1/printer.cfg)
- [Creality — `probe.py` et le chemin spécial `prtouch_v2`](https://github.com/CrealityOfficial/K1_Series_Klipper/blob/main/klippy/extras/probe.py)
- [KAMP-K2 — restauration du moteur Bed Mesh standard](https://github.com/grant0013/KAMP-K2/blob/main/extras/restore_bed_mesh.py)
- [Discussion communautaire sur la limite de 36 points](https://www.reddit.com/r/crealityk1/comments/17tjiz9/max_36_probe_points_with_kamp/)
- [Creality Helper Script — contournement `pr_version: 1`](https://github.com/Guilouz/Creality-Helper-Script-Wiki/discussions/434)
