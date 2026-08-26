# Audit — correction manuelle du mesh et cycle de production CFS

Date : 2026-08-24

Périmètre : photos de la comparaison V2, matrices `6 × 6` et `11 × 11`,
implémentation Klipper/Mainsail exacte, macros K1 Max + deux CFS, sources
officielles et retours communautaires ciblés.

Aucune connexion ni mutation de la K1 n'a été effectuée pour cet audit.

## Conclusion opérationnelle

Les deux familles demandées sont réalisables, mais pas par un petit réglage
unique :

1. **Mesh** : le composite `11 × 11` améliore réellement la grande zone
   centrale, mais il échoue encore aux bords. L'interpolation bicubique n'est
   pas la cause principale. Un éditeur de corrections locales dans K1 Control
   est faisable et constitue la bonne suite, à condition de produire des profils
   dérivés réversibles au lieu d'écraser la mesure physique.
2. **Production** : la séquence stock peut être remplacée à son niveau de
   pilotage. Les macros lisibles, le profil Orca, Moonraker et les primitives
   CFS sont accessibles. Le cœur CFS interne reste compilé ; il faut donc
   reprendre le cycle par étapes, tracer chaque effet et ne remplacer ce cœur
   que si une primitive empêche réellement la propriété des températures.

L'autonomie de calibration quotidienne standard reste atteinte avec le profil
robuste. L'autonomie du mode Précision et l'autonomie de production ne sont pas
atteintes.

## Verdict sur les trois photos

Les photos ne montrent pas un simple Z global faux :

- une large zone centrale est nettement plus homogène que lors du passage
  robuste ;
- les lignes restent soudées sur une grande surface ;
- les défauts graves se concentrent dans des bandes proches des bords ;
- on voit des zones froissées, arrachées ou déplacées, avec des défauts très
  localisés, notamment près du bord arrière et sur les côtés ;
- certaines zones voisines restent acceptables, ce qui exclut une seule
  correction Z uniforme comme solution complète.

La valeur temporaire `−0,24 mm` a bien été observée pendant l'impression, mais
elle n'est pas une nouvelle calibration persistante. Le stock `RESUME` a déjà
montré qu'il pouvait restaurer une origine sauvegardée et écraser un réglage
fait pendant la pause. Le Z persistant `−0,04 mm` doit rester inchangé tant que
le futur démarrage propre n'a pas qualifié le Z absolu.

Le résultat V2 se classe donc ainsi :

- **gain composite central : oui** ;
- **gain global sur toute la plaque : non** ;
- **exposition du mode Précision dans l'UI : refusée pour l'instant** ;
- **profil `11 × 11` à supprimer : non**, il reste une source physique utile ;
- **rejouer le même carré `260 × 260` sans correction : inutile**.

## L'interpolation n'explique pas les bords

Le calcul a été exécuté avec le `bed_mesh.py` exact capturé sur cette K1, pas
avec une approximation externe.

### Validation du calcul local

La matrice calculée du profil robuste actif est reproduite à
`0,000000499 mm` près. Le banc local suit donc bien les formules et l'ordre de
la machine.

### Composite `11 × 11`

Comparaison du bicubique actif (`tension=0,2`, deux points intermédiaires) avec
la surface directe issue des 121 points :

| Mesure | Résultat |
|---|---:|
| écart maximal sur toute la plaque | `0,009877883 mm` |
| écart maximal dans la bande extérieure de 29 mm | `0,009712808 mm` |
| dépassement maximal de l'enveloppe locale | `0,000689867 mm` |
| dépassement de la plage globale mesurée | aucun |

Le bicubique peut contribuer de quelques microns à environ un centième de
millimètre. Il ne peut pas créer seul les défauts visibles de plusieurs bandes.

Après retrait d'une constante globale, la différence de forme entre le robuste
et le composite atteint environ `−0,086850 .. +0,085271 mm`. Le point le plus
écarté est proche de `(X=34, Y=266)`, donc dans la bande extérieure. Le changement
vient bien des valeurs spatiales du composite, pas seulement du rendu entre
elles.

Klipper avertit par ailleurs que Lagrange peut osciller sur de grandes matrices
et le limite à six points par axe. Le `11 × 11` doit donc rester bicubique ou
direct ; revenir à Lagrange n'est pas une option valide. La documentation
officielle décrit aussi `mesh_pps=0` comme la façon de supprimer les points
interpolés, utile comme comparaison mais insuffisante ici.

## Pourquoi une mesure peut être fausse alors que « mesuré » et « calculé » se ressemblent

Mainsail affiche deux objets cohérents entre eux :

- `probed_matrix`, les valeurs fournies par la machine ;
- `mesh_matrix`, la surface calculée à partir de ces mêmes valeurs.

Si un effort mécanique fausse une valeur au moment du contact, la surface
calculée suivra fidèlement cette mauvaise valeur. La proximité des deux vues ne
prouve donc pas que la hauteur physique a été bien mesurée.

La K1 exacte utilise quatre canaux de pression `pres0..pres3`. Le calcul de
contact est dans `prtouch_v2_wrapper`, distribué sous forme compilée. Les 36
tables de seuil par acquisition sont visibles, mais pas la façon complète dont
les quatre canaux sont combinés selon la position.

### Causes classées

1. **Effort dépendant de la position pendant le contact** : tube PTFE/CFS trop
   tendu, faisceau ou chaîne qui tire la tête près d'un bord.
2. **Réponse des quatre capteurs de charge** : contrainte, entretoise, câble ou
   précharge du plateau donnant une précision différente selon la zone.
3. **Biais résiduel de composition** : les quatre quadrants ont déjà exigé des
   corrections constantes importantes ; leur recouvrement résiduel maximal
   reste `0,043745029 mm`.
4. **Z de travail contaminé par la séquence** : il explique une erreur globale
   ou une reprise incorrecte, mais pas à lui seul les formes spatiales répétées.
5. **Première couche elle-même** : débit, plaque, contamination ou traction du
   filament peuvent amplifier localement un défaut déjà présent.
6. **Interpolation** : contribution secondaire, bornée ici à environ `0,01 mm`.

Un retour communautaire K1 Max + CFS décrit précisément un tube PTFE qui tire
la tête vers le haut aux coins avant et crée une lecture faussement haute. Ce
n'est pas une preuve sur notre machine, mais c'est une hypothèse prioritaire car
elle correspond à un effet de bord et au matériel CFS présent. Un autre projet
sur les capteurs de charge K1 rapporte que des fils ou entretoises mal disposés
peuvent dégrader la répétabilité et créer une précision différente selon les
zones. Là encore, ce sera testé, pas présumé.

## Peut-on modifier les points à la main ?

Oui.

Klipper persiste chaque profil sous forme d'une matrice de points. Le code exact
de la K1 ajoute la valeur calculée à la coordonnée Z commandée pendant la
première couche. On peut donc construire une nouvelle matrice, la valider, la
persister sous un nouveau nom et la charger comme n'importe quel autre profil.

Ce que Mainsail `v2.18.2` sait faire aujourd'hui :

- afficher les points et la surface calculée ;
- charger, renommer et supprimer un profil.

Ce qu'il ne sait pas faire : sélectionner un point pour en changer la valeur,
le glisser en 3D ou créer un profil dérivé. Son code source confirme que la
carte est un rendu ECharts sans gestion d'édition.

La bonne solution n'est pas de forker Mainsail. Le bouton Mainsail ouvre déjà
K1 Control sans nouvelle authentification ; l'éditeur sera une section
**Maillage > Ajustement local** de cette application.

### UX retenue

- grille 2D `11 × 11` avec orientation physique explicite ;
- clic sur un point ou une petite zone ;
- boutons `Rapprocher` et `Éloigner` par `0,005` ou `0,010 mm` ;
- valeur source, correction et résultat visibles ;
- vue 3D de contrôle, mais pas de glisser vertical en V1 ;
- comparaison avant/après et historique des versions ;
- activation et retour au robuste en un clic ;
- aucune console et aucune intervention Codex dans l'usage final.

### Pourquoi un profil dérivé

Le profil physique source et le profil robuste ne doivent jamais être écrasés.
Une correction manuelle peut être fausse, inversée ou adaptée à une plaque
particulière. Le système crée donc :

```text
k1_p001_t055_r001_n11x11
  -> corrections locales versionnées
  -> k1_p001_t055_r001_n11x11_tuned_v001
```

La correction est normalisée à moyenne nulle pour ne pas devenir un nouvel
offset Z global. L'éditeur n'écrit jamais le stockage Z accepté.

### Sens des corrections

Dans la mécanique Klipper :

- **Éloigner** ajoute une correction positive au mesh local ;
- **Rapprocher** ajoute une correction négative.

Le premier test ne fera confiance ni au vocabulaire ni à une intuition. Une
seule cellule sera changée de `0,010 mm` et réimprimée pour prouver le sens dans
la chaîne réelle avant toute correction générale.

## Motif physique recommandé

Un carré plein `300 × 300` consomme beaucoup, masque les coordonnées et arrive
trop près des limites mécaniques. La zone mesurée va de `5` à `295 mm` ; le
motif couvrira donc effectivement toute cette zone utile de `290 × 290 mm`.

Le motif `MESH-EDGE-DIAGNOSTIC-V1` contiendra :

- un cadre continu de plusieurs lignes sur `X/Y=5..295` ;
- 121 petites pastilles ou cellules centrées sur la grille réelle `11 × 11` ;
- des bandes continues dans les quatre zones de bord ;
- une croix centrale de référence ;
- une carte affichée dans K1 Control associant chaque cellule à `(ligne,
  colonne, X, Y)`.

Il doit tenir en une première couche et utiliser nettement moins de matière
qu'une feuille pleine. Les premières itérations ne changent qu'une région.

## Tests physiques avant correction généralisée

### E1 — Répétabilité chaude

Deux acquisitions bornées d'une petite zone de bord dans la même session, sans
changer plaque, vis, tube ni chauffe. Si la différence dépasse la tolérance du
profil, aucune correction manuelle n'est qualifiée.

### E2 — Effort du tube PTFE

Comparer une disposition normale et une disposition où le tube garde un mou
neutre et reproductible vers les quatre bords. Aucun démontage du CFS ni
changement de firmware. Si l'erreur suit la tension, la correction est
mécanique avant d'être logicielle.

### E3 — Point témoin

Créer un profil dérivé qui ne change qu'une petite région de `0,010 mm`,
imprimer le motif diagnostic, puis revenir au profil source. Le centre doit
rester identique.

### E4 — Ajustement par petits lots

Corriger au maximum une famille de bords par passage. Une photo et un verdict
sont liés à chaque version. Aucun algorithme ne déduit automatiquement des
valeurs depuis la photo.

### E5 — Qualification

Deux feuilles complètes consécutives, sans défaut grave ni correction Z en
direct. Seulement alors le profil peut devenir `qualified` et apparaître comme
mode Précision dans l'interface.

## Accès réel à la séquence de démarrage

### Ce qui est garanti

Nous avons accès et pouvons remplacer ou envelopper :

- le G-code de départ, changement et fin du profil Orca sélectionné ;
- les macros `START_PRINT`, `PAUSE`, `RESUME` et `END_PRINT` ;
- les macros Creality lisibles de préparation et de purge ;
- le composant Moonraker K1 Control et ses endpoints ;
- le chargement du mesh, le Z accepté et l'armement des mouvements bas ;
- les commandes publiques `BOX_*`, les objets `box.state` et `box.t_command` ;
- la cible de température Klipper et sa vérification continue.

Il est donc réaliste de remplacer **le pilotage complet du travail** par notre
propre cycle.

### Ce qui n'est pas encore garanti

Le cœur `box_wrapper` est compilé. Nous ne pouvons pas affirmer sans essais que
toute primitive :

- respecte la température reçue pendant toute sa durée ;
- ne lance pas un mouvement ou une purge interne ;
- remonte immédiatement un échec mécanique ;
- conserve exactement les mappings des deux CFS après reconnexion.

Nous pouvons soit utiliser ses primitives basses et vérifier leur état, soit
remplacer plus tard leur propriétaire. Nous ne devons pas promettre un
remplacement monolithique sans ces preuves.

## Séquence stock réellement observée

| Phase stock | Effet | Défaut |
|---|---|---|
| Orca `G28` | référence avant le contrat machine | doublon |
| Orca `Tn` | engage le CFS | température et purge CFS prématurées |
| `START_PRINT` | appelle encore préparation et CFS | second propriétaire |
| `CX_ROUGH_G28` | référence grossière | utile seulement si axes inconnus |
| `CX_NOZZLE_CLEAR` | chauffe/nettoyage stock | brossage inefficace observé |
| `ACCURATE_G28` | nouvelle référence | utile après nettoyage, mais répétée |
| nivellement optionnel | nouvelle mesure/état | inutile avec profil quotidien valide |
| `BOX_START_PRINT_EXTRUDE_MATERIAL` | charge/purge | valeur stock `220 °C` |
| ligne de purge stock | amorce | exécutée avant notre maîtrise Z/mesh historique |
| `RESUME` | `BOX_RESUME_EXTRUDE` + restore | pause simple transformée en reprise CFS ; Z écrasable |
| `END_PRINT` | cutter/retrait/chauffes zéro/M84 | effets internes pas encore tous tracés |

## Séquence cible

Cette section historique a été précisée et figée le 26 août 2026 dans
[`docs/25-contrat-cycle-impression-nettoyage-cfs-v1.md`](25-contrat-cycle-impression-nettoyage-cfs-v1.md).
Le contrat détaillé ajoute notamment : absence de `T0` supposé, état filament à
cinq valeurs, conservation du bon filament engagé, purge visible obligatoire,
températures distinctes de retrait/transition/reprise, calibration humaine de
la brosse et bouton séparé `Désengager et nettoyer`.

1. Orca envoie un seul `KCTRL_JOB_BEGIN` avec plateau, buse, outil, plaque,
   mesh et matériau.
2. K1 Control vérifie l'état et lance immédiatement la chauffe plateau.
3. Si les axes sont inconnus, référence grossière minimale pour atteindre la
   brosse sans danger.
4. Nettoyage à la température du matériau précédent, par mouvements courts et
   rapides validés d'abord à froid.
5. Retour à la température de palpage ; attente du plateau à sa cible et d'une
   courte stabilité bornée.
6. Une référence Z finale avec buse propre ; confirmation seulement si écart
   anormal.
7. Chargement du profil mesh choisi, application et relecture du Z accepté.
8. Chargement/purge CFS à la température du filament entrant, avec capteurs et
   délais vérifiés.
9. Ligne d'amorçage à la température première couche, sans offset caché.
10. Impression.

Cette séquence utilise la chauffe du plateau en parallèle. Elle n'impose pas
une attente longue arbitraire et ne refait pas un mesh à chaque travail.

## Pause, changement, refill et reprise

Quatre événements différents deviennent quatre chemins :

| Événement | Coupe/charge | Purge | Z |
|---|---|---|---|
| pause normale | non | non par défaut | conserve le réglage le plus récent |
| reprise avec réamorçage choisi | non | petite purge bornée | conserve le Z |
| changement d'outil voulu | oui | volume calculé | restaure la position, pas un ancien Z |
| fin de filament/refill | selon slot et état | oui, contrôlée | conserve le Z du travail |

Une pause n'est plus un changement de filament implicite. L'interface propose
l'intention et montre la conséquence avant exécution.

## Propriété des températures CFS

Les données de matériau renseignées dans le CFS stock ne suffisent pas à prouver
la cible de travail. La source principale devient le contrat du G-code :

- température première couche ;
- température normale ;
- température du prochain outil ;
- température de nettoyage du matériau sortant ;
- bornes de sécurité par famille de matériau.

K1 Control conserve la cible logique pendant toute la phase et surveille les
écritures tardives. Si le stock redemande `220 °C`, la phase s'arrête avant de
reprendre l'impression. Une commande correctrice envoyée après la purge ne
suffit pas : la purge elle-même doit se faire à la bonne température.

La recherche communautaire confirme deux points utiles :

- un mod K1/K1 Max a dû réimplémenter le changement et réappliquer `M104` parce
  que Creality écrase la température Orca ; cela corrobore notre trace, mais ne
  résout pas la propriété pendant l'opération ;
- un pilote CFS ouvert décrit les phases capteur, coupe, chargement, purge et
  les deux axes `BOX/TOOL`, mais déclare la famille K1 non testée à cause de
  fonctions remappées. Il sert de référence de protocole, pas de paquet à
  installer.

## Séquence de fin

Avant de la modifier, un audit passif doit identifier :

- la position exacte avant cutter ;
- les mouvements d'extrudeur autour de la coupe ;
- le capteur qui confirme la séparation ;
- le retrait et le rembobinage par slot ;
- les changements temporaires de mesh, homing, vitesse et accélération ;
- le moment où la température est coupée.

La cible est : terminer, parquer, couper, retirer, vérifier le rembobinage,
nettoyer éventuellement avec la chaleur résiduelle, enregistrer le dernier
matériau, puis chauffes zéro et moteurs libérés. Le nettoyage de fin reste une
option tant qu'un essai ne prouve pas qu'il retire mieux le résidu sans créer de
filament sur la plaque.

## Registre des erreurs à éviter

### Mesh

- confondre la surface calculée et la justesse de la mesure ;
- écraser le seul profil physique `11 × 11` ;
- utiliser la correction locale comme un Z global ;
- corriger une erreur non répétable ;
- ignorer l'orientation physique de la matrice ;
- changer plusieurs bords à la fois et perdre l'attribution ;
- rendre le mode Précision visible après un simple gain central ;
- imprimer exactement sur les limites mécaniques `0/300` au lieu de la zone
  mesh qualifiée `5/295`.

### Démarrage et Z

- laisser Orca et la K1 faire chacun leur homing et leur `Tn` ;
- prober précisément avec une buse sale ou suintante ;
- charger le mesh avant une commande qui le vide ;
- croire que `−0,24 mm` est déjà un Z persistant qualifié ;
- laisser `RESUME_BASE` restaurer une ancienne origine ;
- retirer le `+0,27 mm` avant la bascule atomique Orca.

### CFS

- utiliser `220 °C` comme température universelle ;
- ajouter une seconde purge après une primitive qui purge déjà ;
- considérer une réponse G-code comme preuve que le filament est arrivé ;
- oublier les délais et erreurs remontés après la fin apparente de la commande ;
- confondre numéro de CFS et numéro de slot ;
- tester les deux CFS dans le même premier incrément ;
- installer un pilote RS485 communautaire explicitement non testé sur K1 ;
- remplacer tout `box.cfg` sans préserver les paramètres exacts de cette
  machine.

### Interface

- patcher directement le bundle Mainsail ;
- autoriser une écriture pendant l'impression ;
- cacher la normalisation ou le signe d'une correction ;
- ne pas conserver de profil de repli et de rollback ;
- dépendre de Codex pour l'usage quotidien final.

## Roadmap arrêtée

L'ordre recommandé termine d'abord le mesh, puis reprend le cycle de
production. Les développements hors imprimante peuvent préparer la suite, mais
une seule famille physique est active à la fois.

### M1 — MESH-EDITOR-OFFLINE-V1

Livrables : modèle de profil dérivé, moteur de corrections, normalisation,
bornes, historique, grille 2D et fausse API. Tests mathématiques sur les 121
valeurs exactes. Aucune pose K1.

Sortie : création, undo/redo, preview et export Klipper bit à bit reproductibles.

### M2 — MESH-EDGE-DIAGNOSTIC-V1

Livrables : G-code première couche `5..295`, carte des 121 cellules et protocole
PTFE/répétabilité. Lancement uniquement quand Thomas est devant la machine.

Sortie : sens `Rapprocher/Éloigner` prouvé sur une cellule et erreur de bord
classée stable ou mécanique.

### M3 — MESH-DERIVED-PROFILE-V1

Pose de l'API et de l'écran au repos. Création d'un profil dérivé après backup,
restart Klipper et relecture, puis retour automatique au robuste. Aucune
impression dans cette gate.

Sortie : `failed_components=[]`, `warnings=[]`, source et robuste intacts,
rollback prouvé.

### M4 — MESH-TUNING-CAMPAIGN-V1

Ajustements par petits lots et motifs diagnostic. Deux feuilles finales sans
défaut grave ni correction Z en direct.

Sortie : profil dérivé `qualified` ou mode Précision définitivement refusé sur
ce matériel. Seulement en cas de succès, exposition dans K1 Control.

### P1 — PRODUCTION-SEQUENCE-AUDIT-V2

Traces ciblées du démarrage, pause normale, reprise, changement, runout et fin,
avec températures, `box.state`, `box.t_command`, capteurs, outil et Z. Aucune
substitution.

### P2 — JOB-LIFECYCLE-OFFLINE-V1

Machine d'états complète et simulations : commandes retardées, CFS absent,
température réécrite, capteur bloqué, pause longue, changement entre deux CFS,
annulation et rollback.

### P3 — CLEAN-AND-REFERENCE-V1

Mouvements de brosse à froid, puis nettoyage chaud séparé, puis référence finale
et chargement mesh/Z. Aucun CFS ni impression dans le premier essai.

### P4 — CFS-TEMP-OWNER-V1

Chargement/purge dynamique sur un slot du CFS 1, puis gate séparée pour le CFS
2. La température logique doit rester propriétaire pendant toute l'opération.

### P5 — PAUSE-RESUME-SEMANTICS-V1

Pause normale sans purge, reprise conservant le Z, reprise avec réamorçage
volontaire, puis chemin runout séparé.

### P6 — END-SEQUENCE-V1

Cutter/retrait/rembobinage qualifiés, puis éventuel nettoyage de fin.

### P7 — ORCA-CUTOVER-V1

Export du profil actif, remplacement atomique des G-code machine par le contrat
K1 Control, retrait du `+0,27 mm`, impression témoin et rollback complet.

### P8 — G5 PRODUCTION

Trois démarrages consécutifs, pause, reprise, changement voulu, refill, passage
entre les deux CFS, fin propre et usage quotidien depuis l'interface sans
Codex.

## Critères d'autonomie finale

### Calibration

- refaire le composite `11 × 11` depuis l'écran ;
- créer, éditer, comparer, qualifier et restaurer un profil dérivé ;
- visualiser les valeurs brutes, corrections et valeurs finales ;
- lancer le motif diagnostic et associer le résultat à une version ;
- aucun fichier à demander à Codex.

### Production

- Orca n'envoie qu'un contrat versionné ;
- K1 Control possède démarrage, nettoyage, référence, mesh, Z, CFS et purge ;
- pause simple distincte d'un changement ;
- température correcte pendant toute transition ;
- fin, cutter et rembobinage observables ;
- aucune correction manuelle par impression ;
- erreurs récupérables depuis l'écran.

## Sources externes

Sources officielles :

- [Klipper — Bed Mesh](https://www.klipper3d.org/Bed_Mesh.html)
- [Klipper — Slicers](https://github.com/Klipper3d/klipper/blob/master/docs/Slicers.md)
- [Moonraker — composants](https://moonraker.readthedocs.io/en/latest/components/)
- [Moonraker — API imprimante](https://moonraker.readthedocs.io/en/latest/external_api/printer/)
- [Mainsail v2.18.2 — carte](https://github.com/mainsail-crew/mainsail/blob/v2.18.2/src/components/charts/HeightmapChart.vue)
- [Mainsail v2.18.2 — profils](https://github.com/mainsail-crew/mainsail/blob/v2.18.2/src/components/panels/Heightmap/HeightmapProfilesPanelRow.vue)
- [Creality — configuration K1 Max PRTouch](https://github.com/CrealityOfficial/K1_Series_Klipper/blob/main/config/K1_MAX_CR4CU220812S12_1/printer.cfg)
- [CrealityPrint — profil officiel K1 CFS](https://github.com/CrealityOfficial/CrealityPrint/blob/master/resources/profiles/Creality/machine/Creality%20K1_CFS-C%200.4%20nozzle.json)

Retours communautaires utilisés uniquement comme hypothèses ou exemples :

- [K1 Max + CFS, tension PTFE et macros](https://github.com/DieDutchman/K1-Max-KAMP-CFS-Fix)
- [Réimplémentation communautaire du changement CFS K1/K1 Max](https://github.com/FrederickAlt/CREALITY-K1-AND-K1-MAX-CFS-RETRUDE-BEFORE-CUT-MOD)
- [Pilote CFS ouvert, K1 explicitement non testé](https://github.com/gitstonelabs/creality-cfs-klipper)
- [Capteurs de charge K1 et influence des câbles/entretoises](https://github.com/cryoz/K1_tenso_manual/blob/main/README_ENG.md)
