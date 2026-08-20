# 08 — Audit système complet et trajectoire de stabilisation

Date : 2026-08-20

Statut : **recommandation d'architecture ; aucune installation ni modification de l'imprimante**

> Mise à jour du 2026-08-20 : le paquet Z fixe préparé après cet audit a été
> rejeté avant déploiement. La cible détaillée et active est désormais le
> système cohérent décrit dans `10-systeme-pilotage-perenne.md` et ADR-004. Le
> découpage en poses sert au rollback ; il ne découpe pas le produit quotidien
> en réglages indépendants.

## Décision recommandée

La prochaine installation ne doit être ni un lot générique du Helper Script, ni
un remplacement complet de firmware, ni une installation immédiate de BTT Eddy.

La voie recommandée est un **niveau A renforcé** :

- conserver le firmware Creality CFS `2.3.5.34`, l'écran, Creality Web/Print et
  les CFS ;
- conserver le root et l'accès SSH dédié déjà validé ;
- construire d'abord un analyseur local en lecture seule ;
- ajouter ensuite nos propres fichiers de configuration, séparés des fichiers
  constructeur et faciles à retirer ;
- donner à une seule séquence de démarrage la maîtrise du Z, du mesh, des
  températures, de la purge et de la valeur finale de pression ;
- faire d'OrcaSlicer la source des paramètres de matériau, sans scripts qui
  tentent de réparer tardivement le firmware ;
- installer Moonraker et une seule interface, Mainsail par défaut, uniquement
  quand leur compatibilité avec cette pile CFS a été vérifiée hors ligne ;
- ne passer au BTT Eddy que si une séquence stock propre et déterministe prouve
  que PR Touch reste dangereux ou insuffisamment répétable.

Cette voie répond au besoin de la semaine prochaine avec le moins de risques,
tout en préparant une évolution ouverte et durable. Elle ne promet pas que PR
Touch sera finalement conservé : elle évite seulement de remplacer le capteur
avant d'avoir isolé la cause.

## Ce que Thomas dépose maintenant

Le point d'entrée privé est :

`inventory/raw/user-inputs/20260820-full-system-audit/`

Ce dossier est ignoré par Git. Il contient un fichier
`README-DEPOSE-ICI.md` et six sous-dossiers.

### Export OrcaSlicer prioritaire

Dans OrcaSlicer :

1. ouvrir le profil K1 Max actuellement utilisé ;
2. utiliser `File > Export > Export Preset Bundle` ou son équivalent traduit ;
3. choisir `Printer config bundle` ;
4. enregistrer le fichier `.orca_printer` dans `01-orca-exports` ;
5. si plusieurs profils K1 Max différents sont réellement utilisés, refaire
   l'opération pour chacun.

L'export « Printer config bundle » contient le profil imprimante et les profils
de filament et de procédé qui lui sont liés. C'est préférable à la copie brute
du dossier de données Orca, qui peut contenir des informations de compte
inutiles. La fonction est documentée dans le
[wiki OrcaSlicer](https://github.com/OrcaSlicer/OrcaSlicer/wiki/import_export).

Déposer ensuite, sans nouvelle impression de test :

| Dossier | Copies demandées |
|---|---|
| `02-projects-3mf` | projets PLA, plateau chaud, multi-objets et multi-filament déjà existants |
| `03-gcodes` | travaux déjà générés : bon résultat, mauvais Z, purge dangereuse, changement CFS |
| `04-custom-gcode-text` | scripts start, end, changement de couche, changement de filament et correctif Z actuel |
| `05-photos-and-notes` | photos existantes du plateau, de la purge, de la brosse, de la buse et notes de correction Z |
| `06-firmware-recovery` | image ou procédure déjà disponible, ou un fichier texte contenant le lien exact |

Ne déposer aucun mot de passe, jeton, clé SSH, export de navigateur ou secret
réseau. Ne pas renommer ni déplacer les originaux. Quand le dépôt est fini, le
signal attendu est simplement `DEPOT_AUDIT_PRET`.

## Faits confirmés sur cette machine

### Z, purge et carte du plateau (mesh)

- `START_PRINT` exécute plusieurs opérations capables d'établir ou de changer la
  référence Z : prise de repère initiale, nettoyage, prise de repère précise et
  contrôle de la carte du plateau.
- PR Touch effectue cinq mesures, utilise leur médiane et applique son propre
  décalage interne.
- A1/B/A2 a montré plusieurs phases Z et un nombre variable de reprises ; A2 a
  atteint l'index de tentative 7 avec de gros résultats internes rejetés.
- le contrôle stock du lit choisit certains points avec une part aléatoire et
  peut recréer puis sauvegarder un mesh sans décision explicite de Thomas ;
- le correctif `+0,27 mm` des G-code privés arrive **après** le retour de
  `START_PRINT` ; la ligne de purge stock s'est donc déjà déplacée trop bas ;
- les corrections historiques allant jusqu'à `+0,8 mm` sont un incident de
  sécurité, pas une variation normale que le logiciel doit accepter en silence.

### Températures et CFS

- le fichier de production observé demandait `190 °C`, puis `195 °C` ; il ne
  contenait aucune demande à `220 °C` ;
- la chaîne CFS compilée a tout de même chargé et purgé à `220 °C` au démarrage ;
- lors d'un remplacement automatique équivalent, elle a produit la suite
  `195 -> 140 -> 220 -> 195 -> 220 °C` et a laissé l'impression à `220 °C`
  jusqu'à correction manuelle ;
- les emplacements CFS stockent notamment le type et la couleur, mais aucune
  température ou pression personnalisée par bobine n'a été trouvée ;
- le cœur `BOX_*` est compilé. Une enveloppe de macros ne sera acceptable que si
  chaque écriture de température peut réellement être interceptée.

### Pression du filament

- le démarrage stock a appliqué `0,044` ; le G-code a ensuite appliqué `0,03` ;
- pendant l'impression longue observée, `0,03` est resté actif pendant et après
  le remplacement automatique de bobine ;
- le CFS n'a donc pas écrasé la pression dans ce cas mesuré ;
- un défaut visible près des bords du plateau n'est pas automatiquement un
  défaut de pression : la ventilation, le débit, la température, le mesh, la
  mécanique, l'ordre des objets et les accélérations peuvent produire des
  symptômes ressemblants.

### Fin de travail et position connue

- aucun processus Moonraker n'a été observé lors de l'acquisition ; Mainsail ou
  Fluidd nécessitera donc une vraie installation de service, pas l'activation
  d'une fonction déjà présente ;
- le `END_PRINT` stock coupe les moteurs avec `M84` ;
- après cette coupure, après un redémarrage ou après un déplacement manuel, la
  machine ne peut pas garantir où se trouvent exactement ses axes ;
- les butées fournissent une référence lorsqu'elles sont recherchées, mais ne
  sont pas des règles absolues qui suivent la position machine hors tension ;
- supprimer toute prise de repère à chaque travail serait donc dangereux. Le bon
  objectif est de supprimer les doublons et les chemins aléatoires, pas toute
  prise de référence.

La documentation Klipper sépare bien l'état des axes référencés, le mesh et le
décalage G-code : [état machine](https://www.klipper3d.org/Status_Reference.html),
[commandes Z](https://www.klipper3d.org/G-Codes.html) et
[mesh](https://www.klipper3d.org/Bed_Mesh.html).

## Pourquoi le script Z actuel ne peut pas être la solution finale

Le script protège une partie de l'impression mais ne protège ni les mouvements
bas ni la purge exécutés dans `START_PRINT`. Il mélange aussi deux notions :

- la **référence Z**, qui dit où se trouve réellement la buse par rapport au
  plateau ;
- la **petite correction de première couche**, qui affine l'écrasement voulu.

Ajouter tardivement une valeur positive peut masquer une mauvaise référence,
mais ne peut pas rendre la séquence précédente sûre. Il ne faut toutefois pas
retirer ce script avant que son remplaçant machine ait passé une validation et
un retour arrière. Le retrait se fera dans la même livraison que la nouvelle
séquence Orca, jamais avant.

## Règle de sécurité centrale de la future installation

La future machine ne devra effectuer **aucun mouvement proche du plateau et
aucune extrusion** avant que ces quatre conditions soient vraies :

1. la buse a été nettoyée ou le contrôle court de propreté a réussi ;
2. une seule référence Z finale a été établie et ses mesures sont cohérentes ;
3. la politique de mesh est connue et le bon mesh est actif ;
4. la correction effective de première couche est déjà active.

Si une mesure est incohérente, si le matériau n'a pas de température exploitable
ou si le changement de référence dépasse la plage qualifiée, la machine
s'arrête en hauteur et explique pourquoi. Elle ne tente jamais de compenser
automatiquement `+0,8 mm` et ne purge jamais « pour voir ».

La plage chiffrée d'acceptation ne sera pas inventée dans ce document. Elle sera
calculée à partir des mesures de cette machine, puis conservée dans une règle
testée. Le premier essai de mouvement se fera sans extrusion et très au-dessus
du plateau.

## Séquence de démarrage cible

Le détail final dépendra des sources et des profils déposés, mais le contrat est
déjà précis :

1. recevoir d'Orca la température du plateau, la température initiale de chaque
   filament, l'outil initial et le mode demandé ;
2. refuser le travail si une donnée indispensable manque ;
3. placer la tête et le plateau dans une position sûre ;
4. établir X/Y et une référence Z grossière uniquement si nécessaire ;
5. amener le plateau à sa température réelle d'impression et attendre sa
   stabilisation lorsque le matériau l'exige ;
6. chauffer la buse selon la température du filament, sans valeur universelle
   PLA/PETG/ABS ;
7. exécuter un contrôle court de nettoyage ; le nettoyage principal aura déjà
   été fait à la fin du travail précédent ;
8. établir une fois la référence Z finale sur une buse propre ;
9. charger un mesh validé ou produire un mesh adapté à la zone utile selon une
   règle explicite ; ne jamais le sauvegarder silencieusement ;
10. activer la correction Z machine avant tout déplacement bas ;
11. charger le filament CFS à la température du premier outil ;
12. purger à une hauteur sûre et dans une zone contrôlée, idéalement près de la
    pièce, puis vérifier que la température n'a pas été écrasée ;
13. appliquer la valeur de pression finale du filament et commencer la pièce.

Le projet KAMP montre qu'un mesh limité à la zone imprimée et une purge près de
la pièce sont des briques possibles, avec une hauteur de purge configurable.
Nous réutiliserons les idées ou le code compatible, pas l'installateur tel quel,
et seulement après vérification de la vieille pile Klipper de cette K1 Max :
[KAMP](https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging).

## Deux démarrages, mais choisis par l'état réel

### Mode référence

Utilisé après démarrage, coupure des moteurs, changement de plaque, incident,
fort changement de température du plateau, configuration modifiée ou doute sur
la position. Il refait la chaîne complète et sûre.

### Mode rapide

Autorisé seulement si les moteurs sont encore fiables, la plaque n'a pas bougé,
le même domaine thermique est utilisé, aucune erreur n'a eu lieu et les
empreintes de configuration correspondent. Il conserve ce qui est prouvé encore
valide et fait au minimum les contrôles nécessaires avant la purge.

Le choix ne sera pas « tous les dix travaux » ou « toutes les deux heures » : il
sera fondé sur l'état réel. Tant que `END_PRINT` exécute `M84`, le prochain
travail doit refaire sa prise de repère. Modifier cette fin de travail est une décision
séparée, car maintenir les moteurs alimentés en permanence a aussi un coût et un
risque thermique.

## Nettoyage de buse cible

Le nettoyage demandé par Thomas est cohérent, mais doit être paramétré au lieu
d'utiliser une température fixe :

- après coupe ou retrait du filament, utiliser une température issue du
  filament sortant ;
- effectuer plusieurs traversées rapides et contrôlées de la brosse, avec un
  mouvement progressif plutôt qu'un lent aller-retour au même endroit ;
- refroidir selon une rampe bornée ;
- finir en s'éloignant pour laisser le résidu solidifié dans la brosse ;
- garer la buse en sécurité ;
- au démarrage suivant, faire seulement un contrôle court avant la référence Z.

Il faudra d'abord mesurer les limites physiques de la brosse, la zone accessible
et la position réelle de la buse. Le nettoyage de fin, le démarrage Z et la
température CFS resteront trois changements séparés pour conserver un retour
arrière clair.

## Contrat CFS durable, de 2 à 4 unités

La machine doit manipuler deux identités différentes :

- le filament logique demandé par le G-code ;
- l'unité et l'emplacement physiques qui fournissent ce filament.

Le contrat retenu est celui de
[`docs/07-dynamic-cfs-temperature-requirements.md`](07-dynamic-cfs-temperature-requirements.md) :

- démarrage : température initiale du filament logique ;
- remplacement par une bobine équivalente : conserver la cible active ;
- vrai changement : température du prochain filament fournie par le G-code ;
- réglage manuel : la dernière demande de Thomas gagne ;
- aucune constante matériau dans le firmware.

Creality vend bien des combinaisons K1 avec quatre CFS et annonce la possibilité
de quatre unités. La cible 16 bobines est donc légitime, mais elle n'est pas
encore validée sur cette machine et ce firmware :
[offre K1 quatre CFS](https://store.creality.com/mx/products/cfs-4-kit-de-actualizacion-multicolor-para-serie-k1).

Le projet ouvert
[`creality-cfs-klipper`](https://github.com/gitstonelabs/creality-cfs-klipper)
documente l'adressage de une à quatre unités et permet de transmettre une
température aux opérations. C'est une excellente référence pour notre modèle de
données. Son propre README indique cependant que la famille K1 et la séquence
matérielle de ce module ne sont pas encore validées. Il ne doit donc pas être
installé tel quel sur la machine de production.

## Pression adaptative et qualité près des bords

OrcaSlicer sait désormais produire une pression adaptative selon le débit et
l'accélération. La fonction reste avancée et demande plusieurs points de
calibration ; elle conserve aussi une valeur de secours pour les changements
d'outil et la purge :
[documentation OrcaSlicer](https://github.com/OrcaSlicer/OrcaSlicer/wiki/adaptive_pressure_advance_calib).

La bonne démarche est :

1. stabiliser d'abord température, débit, Z, mesh et ordre des changements CFS ;
2. vérifier dans l'analyseur quelle commande de pression gagne réellement ;
3. conserver d'abord une pression simple par profil de filament ;
4. comparer les défauts selon leur **position sur la pièce** et leur **position
   physique sur le plateau** ;
5. n'activer la pression adaptative que si les mesures montrent qu'une valeur
   unique est réellement insuffisante.

Si le défaut apparaît seulement près d'un bord physique du plateau, la pression
n'est probablement pas la seule cause. Il faudra vérifier flux d'air,
température, compensation du lit, tube PTFE/CFS qui tire la tête et mécanique.

## OrcaSlicer remis au propre

Orca ne doit plus reproduire l'implémentation interne de la machine. Il doit
seulement exprimer l'intention :

- le G-code de démarrage appelle une macro publique unique avec températures,
  outil et mode ;
- le G-code de fin appelle une macro publique unique ;
- le changement d'outil transmet l'outil suivant, sa température, sa pression et
  les données de purge nécessaires ;
- les zones « avant/après changement de couche » ne contiennent aucun correctif
  Z caché ;
- les profils filament possèdent température, pression, débit maximal,
  rétraction et ventilation ;
- les profils procédé possèdent qualité, vitesses, accélérations, ironing et
  stratégie multi-objets ;
- aucune commande `G28`, mesh, purge ou nettoyage n'est dupliquée dans plusieurs
  zones Orca.

L'analyseur produira d'abord une carte « qui écrit quoi et quand », puis un diff
entre le profil actuel et ce contrat. La bascule vers le profil propre sera
atomique avec la nouvelle séquence machine ; l'ancien export restera disponible
pour retour arrière.

## Outil local à construire

Le bon produit n'est pas un panneau qui envoie n'importe quelle commande en
direct. C'est une application locale, en lecture seule par défaut, composée de
modules simples :

1. inventaire de la machine, des versions et des empreintes ;
2. analyse des G-code et exports Orca ;
3. chronologie de toutes les écritures Z, mesh, température, pression et CFS ;
4. règles de sécurité qui refusent les ordres manquants ou contradictoires ;
5. générateur de nos fichiers de configuration et profils Orca ;
6. tests locaux avec des scénarios simulés ;
7. paquet de déploiement avec sauvegarde, empreintes, validation et retour
   arrière ;
8. vue simple pour Thomas, avec les détails experts repliés.

L'outil reste un seul projet modulaire, pas un ensemble de services complexes.
Il ne stocke ni mot de passe ni adresse réseau dans Git. Une future action
« appliquer » reste désactivée jusqu'à ce qu'un paquet G4 nommé soit approuvé.

## Comparaison des trois niveaux

| Voie | Bénéfices | Limites et risques | Avis |
|---|---|---|---|
| **A renforcé** : stock CFS + fichiers séparés contrôlés | conserve écran, Creality, deux puis quatre CFS ; retour arrière le plus simple ; corrige l'ordre, les températures et Orca | PR Touch peut rester insuffisant ; module CFS compilé à contourner ou remplacer partiellement | **choix actuel** |
| **B** : A + BTT Eddy | carte du plateau rapide, mesure sans contact, contrôle plus ouvert du capteur | installation physique, calibration thermique, intégration CFS non officielle, correction Z encore délicate | uniquement après échec prouvé de PR Touch |
| **C** : Klipper moderne/SimpleAF + MMU ouvert | contrôle maximal et code lisible | SimpleAF ne prend probablement pas en charge le CFS propriétaire ; migration MMU, écran et reprise deviennent une R&D | hors objectif de la semaine prochaine |

Mainsail ou Fluidd n'est qu'une interface de contrôle. L'installation officielle
Creality existe, mais elle ne corrige aucune macro à elle seule :
[K1 Series Annex](https://github.com/CrealityOfficial/K1_Series_Annex).

SimpleAF précise que son support CFS propriétaire est improbable :
[documentation SimpleAF et Eddy](https://pellcorp.github.io/creality-wiki/btteddy/).
Happy Hare est une base mûre pour plusieurs MMU ouverts, mais sa liste actuelle
ne comprend pas le CFS Creality comme matériel prêt à l'emploi :
[Happy Hare](https://github.com/moggieuk/Happy-Hare).

## BTT Eddy : réponse précise

**Non, BTT Eddy n'est pas obligatoire aujourd'hui.** Il devient justifié si,
après nettoyage fiable, stabilisation thermique, suppression des multiples
producteurs Z et référence finale unique, PR Touch reste incapable de produire
une référence sûre et répétable.

La variante communautaire la plus proche de cette machine vise exactement le
firmware `2.3.5.34` et le CFS, mais son auteur indique que le Z-offset est encore
en mode bêta, qu'il faut recalibrer souvent et qu'il utilise un plateau déjà
abîmé lors de ses essais :
[`K1Max-Klipper-Eddy`](https://github.com/mikeinredding/K1Max-Klipper-Eddy).

BTT lui-même demande une cartographie hauteur/capteur, une calibration thermique
pour la version USB et des macros spécifiques de prise de repère :
[documentation BTT Eddy](https://github.com/bigtreetech/Eddy).
Eddy peut devenir la meilleure solution, mais ce n'est pas un capteur magique
qui connaît automatiquement la pointe exacte de chaque buse et chaque plaque.

### Porte de décision Eddy

Le niveau B sera préparé seulement si les quatre points suivants sont réunis :

1. la séquence A renforcée est déterministe et la buse est propre ;
2. les mesures PR Touch continuent à diverger au-delà de la plage sûre calculée
   ou déclenchent des reprises dangereuses ;
3. le plateau, les fixations, la buse et la traction du trajet PTFE/CFS ont été
   exclus comme causes principales ;
4. l'image de récupération exacte, le câblage, le support, le firmware Eddy, le
   retour arrière et un essai en hauteur ont été validés.

Si cette porte passe, Codex pourra préparer presque tout. Thomas devra installer
physiquement le capteur et surveiller la calibration. Une heure peut suffire à
la pose mécanique si tout est préparé, mais il faut prévoir encore une à trois
heures fractionnées pour calibrer et valider sans risquer le plateau.

## Macro-étapes, temps et responsabilités

Les durées sont des fourchettes de travail, pas des promesses de calendrier.
Elles dépendent surtout de la lisibilité du module CFS compilé et de la qualité
des exports fournis.

| Étape | Travail Codex | Temps Thomas | Durée probable |
|---|---|---:|---:|
| 0. Dépôt des entrées | inventaire automatique, contrôle de secrets | 10–20 min | même jour |
| 1. Analyseur hors ligne | analyse Orca/G-code, carte des séquences, règles de sécurité, tests | 0 min | 1–2 jours |
| 2. Architecture A détaillée | fichiers originaux, contrats, simulation, ADR et retour arrière | 0 min | 1–2 jours |
| 3. Premier changement de sécurité | sauvegarde, déploiement G4 nommé, essai sans extrusion puis retour arrière vérifié | 30–60 min de surveillance | 0,5–1 jour après GO G4 |
| 4. Démarrage/température/CFS | changements séparés, traces et contrôle automatique | 5–15 min au début de chaque travail utile | 2–5 jours en profitant des impressions utiles |
| 5. Profil Orca propre | génération, comparaison, import et retrait du script Z | 15–30 min | 0,5–1 jour |
| 6. Pression et qualité | diagnostic par défaut, pression adaptative seulement si utile | selon calibration retenue | 1–3 jours différés |
| 7. Quatre CFS | extension du modèle 8 vers 16 outils, simulation puis passages réels utiles | branchements et surveillance | 3–7 jours après V1 à deux CFS |
| B. Eddy si porte passée | adaptation ouverte, fichiers séparés, installateur, retour arrière et validation | 1 h de pose + 1–3 h de calibration | 2–4 jours d'ingénierie |
| C. Reconstruction | Klipper moderne, écran, MMU, migration et validation complète | plusieurs sessions | plusieurs semaines |

Pour la semaine prochaine, la cible réaliste est une **base A de sécurité et
d'observation**, puis une ou plusieurs impressions utiles surveillées. La cible
n'est pas encore « 16 bobines parfaites + Eddy + pression adaptative + nouveau
firmware » : ce regroupement augmenterait fortement le risque et rendrait toute
panne impossible à attribuer.

## Ce que Codex peut prendre en charge

Codex peut réaliser environ 95 % du travail logiciel et documentaire :

- lecture et comparaison des profils ;
- analyse des G-code et sources ;
- code de l'analyseur ;
- fichiers de configuration originaux ;
- tests et simulations ;
- sauvegardes, empreintes, scripts de déploiement et de retour arrière ;
- déploiement SSH après G4 nommé ;
- observation, analyse, Git, GitHub, PR, fusion et publication ouverte.

Thomas reste indispensable uniquement pour ce que le logiciel ne peut pas voir
ou arrêter physiquement : confirmer la plaque et la buse, surveiller le premier
mouvement bas et la première couche, appuyer sur l'arrêt si nécessaire, et poser
un éventuel capteur.

## Risques principaux et protections

| Risque | Protection obligatoire |
|---|---|
| buse dans le plateau avant purge | aucune trajectoire basse avant Z final, offset actif et garde validée |
| mauvais Z compensé silencieusement | arrêt sur incohérence ; jamais de correction automatique massive |
| température CFS inventée | valeur explicite du G-code ou de Thomas ; arrêt si absente |
| firmware constructeur remplace une configuration au démarrage | fichiers séparés sous stockage persistant, empreintes avant/après démarrage, aucun fichier constructeur publié |
| interface ou helper casse le CFS | installation composant par composant, un seul changement G4, pas de lot aveugle |
| perte d'accès | sauvegarde locale, SSH testé, retour arrière avant déploiement, image S12 vérifiée avant changement profond |
| dérive après mise à jour | versions verrouillées, matrice de compatibilité, mise à jour volontaire seulement |
| secret publié | entrées brutes ignorées, rapport de nettoyage avant commit |
| traction des tubes avec 2–4 CFS | contrôle physique du routage, liberté de la tête, arrêt si effort anormal |

L'image de récupération et sa procédure doivent encore être rapprochées de la
carte S12 structure 0. Un fichier marqué S11 ne sera jamais supposé compatible
sur la seule foi de la métadonnée OTA incohérente.

## Niveau de confiance actuel

- **élevé** : le script Z agit trop tard ; la température CFS écrase le G-code ;
  l'ordre de démarrage et le contrat Orca peuvent être rendus explicites ;
- **moyen à élevé** : un niveau A renforcé corrigera la majorité des problèmes
  de séquence, de purge, de température et de maintenance ;
- **moyen** : PR Touch pourra être rendu assez fiable. Les traces sont
  inquiétantes mais pas encore discriminantes ;
- **moyen** : quatre CFS fonctionneront avec la pile Creality annoncée, mais la
  stabilité de cette révision et notre contrôle dynamique restent à valider ;
- **faible pour un délai d'une semaine** : reconstruction SimpleAF/Happy Hare
  avec conservation directe des CFS ;
- **aucune promesse sérieuse possible** de « zéro incident pour toujours » ; la
  bonne cible est une machine qui détecte l'incertitude, s'arrête sans dommage,
  explique la cause et revient facilement à l'état précédent.

## Prochaine porte

Après `DEPOT_AUDIT_PRET`, Codex doit produire sans connexion imprimante :

1. l'inventaire nettoyé des entrées ;
2. la chronologie de chaque séquence Orca et G-code ;
3. la liste de toutes les commandes Z, température, mesh, pression et CFS ;
4. le contrat Orca cible ;
5. la décision « macros suffisantes » ou « propriétaire compilé à remplacer » ;
6. le premier paquet G4 de sécurité, sans le déployer.

La première mutation ne sera décidée qu'après revue de ce paquet précis. Aucun
test physique supplémentaire n'est demandé maintenant.
