# 102 - Gestion des bobines dans Mainsail : plan V1

Date : 31 octobre 2026. Statut : plan. Rien n'est installé, la K1 n'a pas été
touchée. Lieu des données : K1 Control, sur la K1, choisi par Thomas
([ADR-075](adr/ADR-075-les-bobines-vivent-dans-k1-control.md), acceptée).

## 1. La demande

Thomas veut, dans Mainsail :

- un bouton « Bobines » qui ouvre une fenêtre par-dessus Mainsail, pas une
  page à part, dans le style de la fenêtre de choix des bobines au départ ;
- éditer une bobine et que le CFS reçoive ses caractéristiques, et l'inverse :
  ce qui change au CFS apparaît dans la fenêtre ;
- le suivi de ce qui reste, que le CFS ne fait pas pour ses bobines :
  - saisir ce qu'il estime qu'il reste, ou un poids pesé ;
  - un calculateur qui déduit le filament net selon le type de bobine vide ;
  - une bibliothèque éditable des bobines vides par marque, avec leur poids
    (exemple : « Geeetech plastique fine : xxx g ») ;
  - pour une bobine entamée : poids restant → pourcentage et longueur ;
- après chaque impression, la consommation de chaque bobine déduite, purges et
  pertes comprises, en grammes et en mètres ;
- un stock : une bobine entamée retirée du CFS se retrouve dans une
  bibliothèque, sauf si elle est déclarée terminée ou jetée.

Il demande d'abord si ça existe et s'intègre sans rien casser, puis un plan de
A à Z, et si une seule tranche, servie officiellement, peut le livrer avec un
risque de panne proche de zéro.

## 2. Ce qui existe déjà

| Outil | Ce qu'il fait | Pourquoi il ne suffit pas ici |
| --- | --- | --- |
| [Spoolman](https://github.com/Donkie/Spoolman) | Serveur libre de stock : fabricants, filaments, bobines, lieux, archives, poids restant, étiquettes QR, plusieurs imprimantes. Docker ou Linux ([installation](https://github.com/Donkie/Spoolman/wiki/Installation)). | Ne tourne pas sur la K1 (209 Mo de mémoire en tout). Possible sur le Proxmox. Ne connaît ni le CFS ni ses emplacements. |
| [SpoolmanDB](https://github.com/Donkie/SpoolmanDB) (licence MIT) | Base des filaments et des bobines vides par marque. Geeetech 1 kg : bobine plastique de 180 g ([geeetech.json](https://raw.githubusercontent.com/Donkie/SpoolmanDB/main/filaments/geeetech.json)). eSUN : PLA en carton 170 g, PETG Basic en carton 160 g, PETG, ABS+, HIPS et TPU 240 g ([esun.json](https://raw.githubusercontent.com/Donkie/SpoolmanDB/main/filaments/esun.json)). | Des données seulement. Bon point de départ pour la bibliothèque des bobines vides. |
| Composant `spoolman` de Moonraker ([configuration](https://moonraker.readthedocs.io/en/latest/configuration/#spoolman), [source](https://raw.githubusercontent.com/Arksine/moonraker/master/moonraker/components/spoolman.py)) | Compte le filament poussé par l'extrudeur et l'envoie à Spoolman toutes les 5 s. Présent dans notre Moonraker, non configuré. | Une seule bobine active, à changer à chaque changement d'outil. Consommation en attente gardée en mémoire seulement : perdue si Moonraker redémarre pendant que Spoolman est injoignable. |
| [Gestion des bobines de Mainsail](https://docs.mainsail.xyz/features/spool-management/) | Panneau Spoolman : bobine active, choix d'une bobine. | Exige Spoolman et le composant ci-dessus. Une bobine active, pas huit emplacements. L'édition se fait dans la page de Spoolman. |
| [CFSync](https://github.com/koen01/CFSync) | Tableau de bord des emplacements CFS pour K1 et K2 Plus, relié à Spoolman. | Tourne sur un autre ordinateur (Python 3.10 ou plus) et lit la K1 par SSH. Répartit la consommation totale au prorata des emplacements, sans purge par bobine. Bobines sans puce reliées à la main. N'écrit rien au CFS. Aucune licence affichée. |
| [SpoolFID](https://github.com/mitt3n/SpoolFID), [creality-hi-spoolman-tools](https://github.com/pickmanmike/creality-hi-spoolman-tools), [SpoolmanScale PR #51](https://github.com/Niko11111/SpoolmanScale/pull/51) | Écrivent des puces RFID CFS reliées à une bobine Spoolman par son numéro de série. | Supposent des bobines à puce ; visent surtout les K2 et la Hi. |
| [creality-cfs-bridge](https://github.com/jscottdouglas/creality-cfs-bridge) | Pont CFS pour la famille K2 et un Orca non officiel. | Autre machine, pas de stock. |

Conclusion : rien n'est prêt pour ce besoin (huit emplacements, bobines sans
puce, purges comptées par bobine, fenêtre dans Mainsail, synchro dans les deux
sens). On reprend le modèle de données de Spoolman, les tares de SpoolmanDB et
la méthode de comptage du composant Moonraker, pas leur code serveur.

## 3. Ce que la K1 sait déjà faire

Faits du dépôt, vérifiés dans le code le 31 octobre :

- la fenêtre Bobines existe : `kctrl_print_gate` retient chaque départ ; la
  couche `/bobines/overlay.js`, injectée dans Mainsail par une seule balise
  reposée à chaque démarrage de la passerelle, dessine dans un shadow DOM et
  lit l'état toutes les 750 ms (ADR-063, document 78) ;
- un emplacement compte comme chargé quand son unité est connectée et que son
  matériau n'est pas `-1` (`kctrl_slot_map.slot_identities`). Matériau :
  identifiant Creality (`000003`). Couleur : `0rrggbb` ;
- écrire matériau et couleur au repos est déjà fait par
  `KCTRL_FILAMENT SLOT=T2C MATERIAL=000003 COLOR=0ffffff`
  (`BOX_MODIFY_TN_DATA`, puis `BOX_UPDATE_SAME_MATERIAL_LIST`) ;
- le reste `remain_len` vient du matériel CFS (`BOX_GET_REMAIN_LEN`, lecture
  RFID). Pour une bobine sans puce ce n'est pas une mesure ; la fenêtre de
  départ l'affiche pourtant en « reste 100 % » (`logic.js`, `remainingLabel`).
  On ne l'écrit jamais : relu du matériel, il touche aussi la logique de fin de
  bobine (prudence, non testé exprès) ;
- l'emplacement engagé est connu : `kctrl_tool_change.last` donne l'outil,
  l'issue (`start`, `done`, `empty`, `refuse`, `stock`, `paused_by_firmware`) et
  l'emplacement physique ; `kctrl_end.slot` donne la route gardée (ADR-074) ;
- les purges du module CFS passent par l'extrudeur (`G0` ou `G1 E…`) : elles
  sont visibles dans la position E. Longueur arrondie à 140 ou 280 mm
  (document 79). Tour de purge active (`prime_volume` 25), purge dans la tour
  inactive ;
- la roue de mesure du CFS tient un compteur par unité, trop dispersé pour un
  compte au gramme : 140 mm purgés lus entre 122 et 142 mm, 280 mm entre 258 et
  290 mm (document 79) ;
- le pied du fichier Orca donne la consommation prévue de chaque filament (mm,
  g, densité, diamètre). Rien ne le lit encore ;
- relève automatique (`auto_refill: 1`) : seulement entre bobines de même fiche
  et de même couleur, prouvée une fois le 5 septembre (`T1A` → `T1B`) ;
- le Moonraker dédié de K1 Control (Python 3.8.2) porte déjà un composant à
  nous, `calibration-ui-v1/k1_control.py`. Limites de ressources : Moonraker au
  repos sous 45 Mo, au moins 70 Mo libres après son démarrage ;
- mesuré le 31 octobre en lecture seule, pendant une impression : 95 Mo de
  mémoire disponibles sur 209, le Moonraker dédié à 22 Mo et 5 % d'un cœur,
  Klipper à 41 % d'un cœur, l'ensemble à 49 % des deux cœurs ; 5 Go libres
  sous `/usr/data`, dont 272 Ko pour tout l'état de K1 Control. La machine
  écrit déjà d'elle-même environ 40 Mo par minute sur sa mémoire flash (mesuré
  sur une minute), soit 8,5 Go en 3 h 43 depuis son démarrage, plus que la
  capacité de la flash (7,8 Go) : dans la minute, seuls les journaux de
  Creality et de Klipper et un petit fichier d'état de Creality changent, rien
  sous K1 Control. Le noyau n'expose pas l'usure de la flash. Le composant
  s'ajoute au Moonraker dédié, sans nouveau programme.

## 4. Architecture

Principe : rien ne change dans Klipper, aucun redémarrage de Klipper. Le neuf
vit hors du chemin de l'impression.

- Composant Moonraker `kctrl_spools` (Python 3.8, bibliothèque standard
  seulement), chargé par le Moonraker dédié comme `k1_control.py`. Il lit par
  abonnement `box`, `kctrl_tool_change`, `kctrl_end`, `print_stats` et
  `toolhead.position`, sans requête active pendant une impression. Il tient le
  stock et le décompte, et n'écrit au CFS que par `KCTRL_FILAMENT`, au repos.
  Il expose quelques points d'entrée à la fenêtre, sur le modèle de
  `k1_control.py`.
- Stockage sous `/usr/data/k1-control-v1/state/spools/`, en JSON :
  écriture atomique (fichier temporaire, synchronisation disque, renommage),
  trois copies tournantes, journal en ajout seul et borné, export et import
  complets depuis la fenêtre. La bibliothèque n'est réécrite que sur action de
  Thomas, quand le contenu d'un emplacement change et en fin d'impression.
  Pendant une impression, seul un petit fichier de reprise de taille fixe,
  quelques Ko (un total par emplacement et le segment en cours), est réécrit
  chaque minute et à chaque changement d'outil, plus une ligne de journal par
  changement. L'usure de la mémoire flash reste négligeable (section 3).
- Interface : un module séparé, `/bobines/spools.js`, chargé à part par
  `overlay.js`. Une erreur dans ce module laisse la fenêtre de départ intacte.
  Même feuille de style.
- Repli : si le composant ne répond pas, la fenêtre de départ garde son
  affichage actuel, sans le faux « 100 % ». La gestion des bobines ne bloque
  jamais un départ.

## 5. Modèle de données

Mêmes notions et mêmes unités que Spoolman, pour qu'un export futur ne
demande aucune ressaisie.

- **Fabricant** : nom.
- **Bobine vide** (le type) : fabricant, nom libre (« plastique fine »),
  matière de la bobine (plastique, carton, métal), tare en g, net nominal
  (1 000 g…), origine de la tare : SpoolmanDB, ou pesée de Thomas datée. Une
  pesée de Thomas remplace toujours la valeur de SpoolmanDB.
- **Fiche filament** : fabricant, matière (PLA, PETG…), couleur, diamètre,
  densité (SpoolmanDB ou Orca), identifiant matériau Creality pour l'écriture
  au CFS.
- **Bobine** : numéro court (`B-001`), fiche, bobine vide, net initial, reste
  en g avec sa source (pesée, estimation, décompte) et sa date, état,
  emplacement CFS ou lieu de rangement, notes.
- **Journal** : chaque événement ajouté sans réécriture (pesée, estimation,
  consommation d'une impression, changement d'état, écriture au CFS et sa
  relecture).

États d'une bobine :

- dans le CFS (`T1A` à `T2D`) ;
- à ranger : retirée du CFS, lieu non dit ;
- en stock : lieu en texte libre (« étagère 2 », « boîte sèche ») ;
- terminée ou jetée : archivées, cachées par défaut, retrouvables par un
  filtre.

## 6. Calculateur

- net = poids brut pesé − tare de la bobine vide ;
- pourcentage = net / net initial ;
- longueur = net / (densité × π × (diamètre / 2)²). PLA 1,75 mm à 1,24 g/cm³ :
  2,98 g par mètre.

Exemple : bobine Geeetech, tare SpoolmanDB 180 g, brut pesé 650 g → net 470 g,
47 % d'une bobine de 1 kg, environ 158 m.

Règles :

- poids brut, pourcentage et longueur sont liés : Thomas en tape un, les deux
  autres se recalculent aussitôt, sans bouton ;
- un pourcentage donné à l'œil est marqué « estimé », un poids pesé « pesé » ;
- un poids brut inférieur à la tare est refusé avec la raison ;
- tare inconnue : peser une bobine vide de ce type, ou prendre la valeur de
  SpoolmanDB, marquée comme telle. Pour « Geeetech plastique fine », les 180 g
  de SpoolmanDB valent pour la bobine plastique de 1 kg : à confirmer par la
  pesée d'une bobine vide.

## 7. Synchronisation avec le CFS

| Donnée | Où elle vit | Mainsail → CFS | CFS → Mainsail |
| --- | --- | --- | --- |
| Matière (identifiant Creality) | CFS et K1 Control | écrite au repos par `KCTRL_FILAMENT`, puis relue | lue en continu |
| Couleur | CFS et K1 Control | idem | lue en continu |
| Présence d'une bobine | CFS | sans objet | retrait → bobine « à ranger » ; arrivée → propose une bobine du stock de même fiche et couleur, ou d'en créer une |
| Marque, poids, reste, tare, lieu | K1 Control | non : le CFS n'a pas de champ pour ça | sans objet |
| Reste d'une bobine à puce | CFS | jamais écrit | affiché tel quel, marqué « puce » |

Règles :

- aucune écriture au CFS pendant une impression, même en pause : elle attend,
  et la fenêtre l'affiche (« sera envoyé au CFS à la fin de l'impression ») ;
- une écriture n'est faite qu'après relecture de la même valeur dans `box`.
  Sinon l'écart s'affiche, sans nouvelle tentative automatique ;
- conflit : la présence vient du CFS, l'identité de la bobine vient de K1
  Control. Si le CFS montre une autre matière ou une autre couleur que la
  bobine attendue à cet emplacement, l'emplacement passe « à vérifier » et
  Thomas tranche d'un clic : garder la bobine et réécrire le CFS, ou choisir
  une autre bobine ;
- écrire une matière ou une couleur change les paires de relève automatique
  (même fiche et même couleur) : la fenêtre montre la paire créée ou perdue
  avant d'écrire.

## 8. Décompte de la consommation

Source : la position E de la tête (`toolhead.position`), c'est-à-dire le
filament réellement poussé par l'extrudeur, facteur de débit compris. Les
purges du CFS et la tour de purge y passent.

Segments :

- un segment, c'est une bobine engagée entre deux bornes ;
- bornes : changement d'outil à l'issue `start` (la purge de la nouvelle bobine
  va au nouveau segment), fin d'impression (route gardée), chargement ou
  retrait manuel ;
- consommation d'un segment = E à la fin − E au début : les rétractations
  internes s'annulent, la dernière avant la coupe n'est pas comptée ;
- pendant le segment, l'affichage suit le plus haut E atteint, pour que le
  compteur ne recule pas ;
- emplacement non prouvé (relève automatique, état inattendu) : le segment va
  « à attribuer » et Thomas l'attribue d'un clic. Rien n'est deviné ;
- redémarrage de Moonraker pendant une impression : rien n'est perdu tant que
  Klipper tourne, le début du segment est sur disque. Redémarrage de Klipper :
  E repart de zéro ; le décompte s'arrête au dernier point de reprise et le
  reste du segment passe « à vérifier ».

En fin d'impression :

- bilan par bobine en grammes et en mètres, dont purges, à côté de la
  prévision Orca augmentée des purges comptées ;
- reste de chaque bobine mis à jour, source « décompte » ;
- une pesée plus tard corrige le chiffre et garde l'écart entre pesée et
  décompte : c'est la preuve de justesse au fil des impressions.

Pertes :

- la coupe laisse un bout de l'ancien filament entre la lame et l'extrudeur ;
  il sort avec la purge de la nouvelle bobine. Le total reste juste, mais la
  répartition décale de la longueur de ce bout (quelques centimètres). On la
  mesure, et on ne la corrige que si la mesure le justifie ;
- les chargements que le firmware relance (document 82) poussent du filament
  qui revient en partie : à observer pendant la qualification.

Au départ, la fenêtre de choix affiche le vrai reste de chaque bobine et
prévient sans bloquer si le fichier demande plus : « T2B : reste ~38 g, le
fichier en demande ~52 g ». Tant qu'aucune pesée n'a vérifié le décompte, elle
le dit : « décompte non encore vérifié par pesée ».

## 9. Interface

- Un bouton « Bobines » posé par-dessus la barre du haut de Mainsail, sans
  modifier le code de Mainsail. Une pastille signale une bobine basse ou un
  emplacement « à vérifier ». Si Mainsail change sa barre, le bouton se range
  en coin haut droit au lieu de disparaître.
- La fenêtre s'ouvre sous le bouton, en plein écran sur téléphone ; Échap ou un
  clic à côté la referme.
- Quatre onglets :
  - CFS : les huit emplacements (couleur, matière, marque, reste en g, %
    et m, état de la synchro) ;
  - Stock : bobines rangées, filtres par matière, couleur et lieu ;
    terminées et jetées derrière un filtre ;
  - Bobines vides : la bibliothèque des tares, éditable ;
  - Journal : impressions et événements, bobine par bobine.
- Fiche d'une bobine : les trois champs liés du calculateur, état, lieu,
  notes ; actions Ranger, Mettre au CFS, Terminée, Jetée.
- Mêmes styles que la fenêtre de départ, thème sombre de Mainsail, libellés en
  français courant.
- Pendant une impression, tout reste consultable ; stock et pesées restent
  modifiables (ils ne touchent pas la machine) ; les écritures au CFS attendent
  la fin.

## 10. Lots de développement

Tous hors imprimante, sauf L.

| Lot | Contenu | Fini quand |
| --- | --- | --- |
| A | Socle : composant vide, stockage atomique, trois copies, journal borné, export et import | une coupure simulée à chaque étape d'écriture laisse un état relu intact |
| B | Bibliothèque des bobines vides : extrait compact de SpoolmanDB (marques utiles, licence MIT jointe), édition, pesée prioritaire | tares Geeetech et eSUN retrouvées, pesée qui remplace la valeur importée |
| C | Fiches filament et correspondance avec les identifiants matériau Creality | chaque fiche retrouve son identifiant dans la base matériau de la K1 |
| D | Calculateur | mêmes vecteurs de test verts en Python et en JavaScript, mêmes arrondis |
| E | Bobines, états, stock, lieux, archives | chaque transition d'état testée, aucune bobine perdue |
| F | Synchro CFS : lecture continue, écriture au repos, relecture, attente pendant l'impression, « à vérifier » | refus prouvé pendant une impression, écart affiché si la relecture diffère |
| G | Décompte : segments, bornes, points de reprise, « à attribuer », bilan de fin | rejeux de la section 11 verts |
| H | Fenêtre de départ : vrai reste, avertissement non bloquant, plus de faux 100 %, repli. JavaScript seulement, `kctrl_print_gate.py` inchangé | tests existants verts, plus composant absent, reste insuffisant, bobine à puce |
| I | Bouton et fenêtre Bobines dans Mainsail | rendu réel bureau et téléphone, zéro erreur console |
| J | Laboratoire : faux Moonraker qui rejoue des états réels, rendu Chrome | tous les lots jouables sans la K1 |
| K | Paquet de pose : manifeste, empreintes, sauvegarde, liste exacte des fichiers écrits, déployeur, validateur, retour arrière exact | préflight réel vert en lecture seule |
| L | Qualification sur la vraie K1 | les deux gestes de la section 12 |

## 11. Preuves hors imprimante, avant toute pose

- Faux Moonraker qui rejoue des états `box`, `kctrl_tool_change`, `kctrl_end`,
  `print_stats` et `toolhead` de forme réelle.
- Rejeu des séquences réelles déjà auditées (ordre des changements, issues,
  purges journalisées) : multicouleur du 14 septembre (document 79), fin du
  15 septembre (document 82), reprise de nuit (document 100), annulation qui
  garde le filament (document 101), relève automatique (document 76), plus
  pause et reprise, redémarrage de Klipper, emplacement inconnu.
- Vecteurs du calculateur, identiques en Python et en JavaScript.
- Tests de la fenêtre de départ existants, plus : composant absent, reste
  insuffisant, bobine à puce.
- Rendu dans un vrai Chrome contre une fausse API locale, comme
  MESH-EDITOR-OFFLINE-V1 : bureau et largeur téléphone, zéro erreur console,
  captures envoyées à Thomas.
- Mémoire : composant chargé dans un Moonraker local avec 200 bobines, mesuré
  sous les limites de ressources.
- Écritures : sur une impression rejouée avec beaucoup de changements, seul le
  petit fichier de reprise est réécrit, à taille fixe ; la bibliothèque ne l'est
  qu'en fin d'impression.

## 12. Pose et qualification

Pose (lot K), au repos seulement, revérifié juste avant l'arrêt du service :

1. préflight réel en lecture : K1 au repos, aucune impression, empreintes
   attendues ;
2. sauvegarde exacte des fichiers remplacés (configuration du Moonraker dédié,
   `overlay.js`, styles) ;
3. copie des fichiers neufs, dossiers en 755 et fichiers en 644 (sinon nginx
   répond 403) ;
4. redémarrage du seul Moonraker dédié. Klipper n'est pas touché ;
5. validation : composant chargé, `failed_components` vide, points d'entrée qui
   répondent, Moonraker dédié sous 45 Mo et au moins 70 Mo libres, rendu réel
   dans Mainsail ;
6. retour arrière exact au premier écart.

Qualification (lot L), deux gestes de Thomas :

1. retirer puis remettre une bobine, au repos : la fenêtre la passe « à
   ranger », puis la reconnaît. Ce geste dit comment le CFS signale une bobine
   sans puce, inconnue aujourd'hui ;
2. sa prochaine vraie impression multicouleur, bobines pesées avant et après :
   l'écart entre pesée et décompte doit rester dans la précision de la balance
   plus la perte de coupe mesurée. Sinon, on trouve la cause avant de clore.
   Pendant cette impression, une lecture passive de la mémoire, du processeur
   et des écritures sur la flash est comparée aux mesures de la section 3.

## 13. Risques et parades

| Risque | Parade |
| --- | --- |
| Le nouveau module casse la fenêtre de départ | module séparé, chargé à part ; fenêtre de départ testée avec composant absent ou en erreur |
| Défaut du composant | `failed_components` vérifié à la pose ; le composant ne commande à Klipper que `KCTRL_FILAMENT`, au repos ; retour arrière exact |
| Écriture au CFS pendant une impression | refusée par le composant, état d'impression relu juste avant ; l'écriture attend la fin |
| Écriture qui ne prend pas | relecture obligatoire, écart affiché, pas de nouvelle tentative automatique |
| Bobine changée sans être vue | présence lue en continu ; autre matière ou couleur → « à vérifier » |
| Perte des données | trois copies, journal, export sur le PC |
| Usure de la mémoire flash | bibliothèque réécrite rarement ; en impression, un petit fichier de taille fixe (section 4) ; marge mesurée en section 3 |
| Moonraker redémarré pendant une impression | pose au repos seulement (règle du 24 septembre) ; un plantage n'arrête pas l'impression et le décompte reprend depuis le disque |
| Mémoire et processeur de la K1 | composant sans dépendance dans le Moonraker existant ; marge mesurée en impression (section 3), remesurée à la pose et pendant la première impression |

## 14. Hors V1

- Contrôle croisé par la roue de mesure du CFS.
- Étiquettes QR.
- Export ou synchro vers Spoolman, si Thomas l'installe un jour sur le Proxmox.
- Températures par bobine pour chargement, purge et retrait (demande du
  23 septembre, `ROADMAP.md`), bâties sur cette bibliothèque.
- Alertes de stock bas.
- Plusieurs imprimantes.

## 15. Verdict

- **Une seule tranche** : oui. Les lots A à K se construisent et se prouvent
  hors imprimante, puis viennent une pose au repos et deux gestes de
  qualification.
- **Servie officiellement** : oui, dans Mainsail, par le même chemin que la
  fenêtre de départ, sans redémarrage de Klipper.
- **Risque pour les impressions** : proche de zéro par construction. Pendant
  une impression le composant ne fait que lire ; il n'écrit au CFS qu'au repos,
  avec relecture ; s'il tombe, le départ fonctionne comme aujourd'hui.
- **Risque de panne de la fenêtre, du calculateur, de la bibliothèque et du
  stock** : proche de zéro après les preuves hors imprimante et le rendu réel.
- **Justesse des grammes et des mètres** : pas prouvée avant la pesée de la
  première impression. Les inconnues sont nommées (présence d'une bobine sans
  puce, perte de coupe, attribution après une relève automatique) et fermées
  par la qualification, jamais devinées.
