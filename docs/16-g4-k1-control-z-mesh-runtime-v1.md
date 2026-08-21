# 16 — Préparation de `G4-K1-CONTROL-Z-MESH-RUNTIME-V1`

Date : 2026-08-21

Statut : **construction hors imprimante ; aucun déploiement autorisé**

## Décision opérateur

Une impression utile réussie ne suffit pas à exclure les défauts aléatoires
rapportés. Thomas refuse une nouvelle campagne d'impressions sacrificielles et
demande la mise en œuvre des protections. L'observation de la fondation peut
continuer comme preuve de coexistence, mais elle ne bloque plus la construction
hors imprimante.

Le prochain lot fonctionnel traite ensemble la propriété du Z, le choix du
mesh et l'ordre sûr de démarrage. Le retrait de l'actuel post-traitement Orca
`+0,27 mm` reste interdit tant que son remplacement complet n'est pas prouvé et
prêt à être activé atomiquement.

## Fait nouveau issu de Mainsail

Thomas a lancé manuellement une calibration depuis Mainsail après avoir référencé
les axes. La lecture Moonraker postérieure a confirmé :

- état machine `standby`, axes `xyz` référencés et chauffes à zéro ;
- profil actif `Base` couvrant `5–295 mm` sur X et Y ;
- matrice mesurée `6 × 6`, interpolation Lagrange et `mesh_pps=2,2` ;
- amplitude des 36 points mesurés d'environ `0,446 mm` ;
- profil `Base` absent de `printer.cfg`, donc non persistant ;
- seul l'ancien profil `default` reste enregistré dans `printer.cfg`.

Ce résultat prouve que le bouton générique de Mainsail ne fournit ni orchestration
Creality sûre, ni choix explicite de densité, ni qualification, ni persistance
compréhensible du profil.

## Contrat du planificateur mesh

Le premier composant codé est volontairement hors imprimante. Il transforme un
contexte explicite en plan borné et ne transmet aucun G-code.

Presets :

| Nom | Matrice | Points | Usage |
|---|---:|---:|---|
| `quick` | `6 × 6` | 36 | équivalent à la configuration capturée |
| `standard` | `9 × 9` | 81 | compromis courant |
| `precise` | `11 × 11` | 121 | référence complète recommandée |
| `expert` | `15 × 15` | 225 | diagnostic ou besoin local confirmé |

Le mode expert accepte de `3` à `25` points par axe. La zone reste obligatoirement
dans la plage revue `5–295 mm`. Jusqu'à `6 × 6`, l'algorithme reste Lagrange ;
au-delà, il devient bicubique pour éviter la limite d'oscillation documentée de
Lagrange.

Un profil de référence est identifié par plaque, plage de température, révision
de la référence capteur et matrice. Un mesh adaptatif reçoit une zone de travail,
reste transitoire et ne peut jamais être réutilisé comme profil global.

## Qualification avant acceptation

Une matrice plus dense ne suffit pas. Deux mesures comparables doivent avoir les
mêmes dimensions et rester dans une tolérance point par point. La tolérance
initiale hors imprimante est `0,025 mm` ; elle devra être confirmée pour le PR
Touch exact avant la gate de déploiement. Une matrice vide, non rectangulaire,
non finie, hors zone ou trop dense est refusée.

## Suite de construction

1. raccorder le planificateur au vrai adaptateur Moonraker en lecture seule ;
2. ajouter l'état persistant Z/mesh indépendant des fichiers constructeur ;
3. produire les macros originales de garde et le contrat Orca atomique ;
4. préparer sauvegardes, empreintes, installation, contrôle sans extrusion et
   rollback ;
5. seulement alors présenter tous les fichiers et commandes pour un GO exact
   `G4-K1-CONTROL-Z-MESH-RUNTIME-V1`.

Le lot suivant, séparé pour le rollback, portera la propriété dynamique des
températures pendant les opérations des deux CFS.
