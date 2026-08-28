# Cartographie canonique du pilotage K1 Max + CFS — V1

Date : 2026-08-28

État : **architecture choisie et surface S12 confirmée en lecture seule ;
implémentation, effets physiques et production fermés**

Mise à jour du 28 août 2026 : la gate S12 est close dans le document 44. Le
chargeur et le binaire exacts n'ont pas dérivé, l'objet `box` est actif, les
commandes et rappels attendus sont présents et les deux CFS `1.1.3` répondent.
Cette preuve permet de préparer le moteur hors imprimante ; elle ne qualifie
encore aucune primitive d'effet.

## Réponse concrète

Nous ne repartons pas de zéro et nous n’installons pas un nouveau firmware
aveuglément.

La meilleure voie est de garder le pilote CFS Creality déjà présent pour
parler aux deux boîtiers, mais de lui retirer la direction du cycle
d’impression. K1 Control décidera de l’ordre, des températures, du seul palpage
Z autorisé, du mesh, de la purge, du changement de filament, du runout, de la
pause, de la reprise et de la fin.

HelixScreen a effectivement réalisé une cartographie très utile. Nous
réutilisons ses noms de commandes, ses effets cachés et ses pièges comme
preuves recoupées. Nous n’utilisons pas son cycle K1 tel quel, car il appelle
encore une purge stock et la brosse, et son équipe indique ne pas avoir validé
ce comportement sur une vraie K1 + CFS.

## Ce qui ne sera pas jeté

Les éléments suivants restent les premières sources de vérité :

- les captures réelles de notre K1 Max S12 ;
- le hash du `box_wrapper` exact installé ;
- les matrices, profils et états Z déjà qualifiés ;
- les routes `T1A`, `T1/T2` et états CFS déjà observés ;
- le garde de retrait, l’adaptateur d’état, le moteur hors ligne et ses
  scénarios ;
- ADR-030 pour le nettoyage manuel et ADR-031 pour le départ sans brosse ni
  recalibration.

Les sources publiques complètent seulement les trous. Elles ne remplacent
jamais une preuve contraire obtenue sur notre machine.

## Sources retenues

| Source | Ce qu’elle apporte | Décision |
| --- | --- | --- |
| Captures locales K1 Control | vérité exacte sur cette K1 Max, deux CFS, mesh, Z, températures et routes | autorité principale |
| `box_wrapper` local, hash `af630c02…` | ancre toute comparaison au binaire réellement installé | doit être recartographié en lecture seule avant effet |
| [HelixScreen — internes CFS](https://github.com/prestonbrown/helixscreen/blob/192eb3babd2946d3e868e9c259da8037262529d5/docs/devel/CREALITY_CFS_INTERNALS.md), révision `192eb3b…` | commandes K1 `BOX_*`, effets cachés, erreurs, reprise, tests | excellente carte ; séquence non installée |
| [HelixScreen — backend CFS](https://github.com/prestonbrown/helixscreen/blob/192eb3babd2946d3e868e9c259da8037262529d5/docs/devel/FILAMENT_BACKEND_CFS.md) et [issue 968](https://github.com/prestonbrown/helixscreen/issues/968) | différence K1/K2, load/unload/swap et limite de validation matérielle | concepts repris, cycle K1 rejeté |
| [FrederickAlt — macros](https://github.com/FrederickAlt/CREALITY-K1-AND-K1-MAX-CFS-RETRUDE-BEFORE-CUT-MOD/blob/083c5a5679d5f7d3f3cfff9a6303b6d224347c29/docs/klipper-macros.md), révision `083c5a5…` | décomposition du wrapper, arguments et effets | deuxième preuve indépendante |
| [FrederickAlt — auto-refill](https://github.com/FrederickAlt/CREALITY-K1-AND-K1-MAX-CFS-RETRUDE-BEFORE-CUT-MOD/blob/083c5a5679d5f7d3f3cfff9a6303b6d224347c29/docs/auto-refill.md) | règle type + couleur + capteur, remap et reprise stock | fonction recréée dans notre propriétaire |
| [Profil officiel CrealityPrint K1 CFS-C](https://github.com/CrealityOfficial/CrealityPrint/blob/24b9395c131a9849724c5bf098cba140a207e877/resources/profiles/Creality/machine/Creality%20K1_CFS-C%200.4%20nozzle.json), [incident K1 Max 561](https://github.com/CrealityOfficial/CrealityPrint/issues/561) | séparation imparfaite entre slicer, `START_PRINT` et outil, plus incidents réels de température | preuve officielle de contexte, pas profil exact S12 |
| [CFSTool](https://github.com/Lamar1007/CFSTool), révision `a207980…` | génération CFS classique, CH340/RS485, deux CFS réels sur K1 | diagnostic seulement, aucun flash |
| [gitstonelabs/creality-cfs-klipper](https://github.com/gitstonelabs/creality-cfs-klipper), révision `16309d8…` | idées de machine d’état, capteurs et multi-boîtiers | pas installé sur notre K1 |
| [SLICK1MAX](https://github.com/crazyslicster/SLICK1MAX), révision `9d96868…` | retour réel K1 Max + CFS, neutralisation possible de macros de brosse | confirme le problème, configuration non reprise |
| [Nik-oli Helper Script K1 CFS](https://github.com/Nik-oli/Creality-Helper-Script-K1-CFS), révision `6b92368…` | faisabilité Moonraker/Mainsail et bug de purge avant chargement | son `START_PRINT` reste incompatible |
| [OrcaSlicer issue 14191](https://github.com/OrcaSlicer/OrcaSlicer/issues/14191) | idée d’écran de correspondance filament/slot via Moonraker | utile pour l’UX, mais proposition non fusionnée |

Les projets sous GPL servent uniquement à établir des faits, des interfaces et
des idées de tests. Aucun code n’est copié. La carte structurée et les révisions
complètes sont dans `design/cfs-control-source-map-v1.json`.

## Ce que fait réellement le système stock

Le gros chemin stock mélange cinq responsabilités :

1. choisir un filament ;
2. déplacer le filament et parfois la tête ;
3. choisir ou remplacer une température ;
4. purger et brosser ;
5. gérer erreurs, retry et reprise du print.

Ce mélange explique pourquoi corriger la température après un `Tn` ne suffit
pas : le mauvais effet a déjà pu se produire.

La bonne découpe publique est la suivante :

| Commande ou famille | Effet connu | Verdict K1 Control |
| --- | --- | --- |
| `START_PRINT`, `BOX_START_PRINT`, `Tn` | cycle complet avec décisions cachées | interdit |
| `BOX_NOZZLE_CLEAN` | brossage/mouvements/fans | interdit |
| `BOX_MATERIAL_FLUSH` | chauffe, extrusion, brosse puis petite rétraction ; repli possible à `220 °C` | interdit |
| `BOX_MATERIAL_CHANGE_FLUSH` | purge dépendante des matières, effets et température internes | interdit tant que nous possédons la purge |
| `BOX_ERROR_CLEAR` | peut jeter une reprise différée | interdit en automatique |
| `BOX_TNN_RETRY_PROCESS` | peut rejouer une phase et reprendre le print | interdit en automatique |
| `BOX_CHECK_MATERIAL_REFILL`, `BOX_EXTRUSION_ALL_MATERIALS`, `BOX_RESUME_EXTRUDE` | traitement stock de fin de bobine, extrusion restante et reprise | interdits tant que K1 Control possède le runout |
| `BOX_RETRUDE_MATERIAL_WITH_TNN` | peut agir même pendant la reprise interne | interdit |
| `BOX_EXTRUDE_MATERIAL TNN=…` | avance côté CFS | candidate, pas encore appelable |
| `BOX_EXTRUDER_EXTRUDE TNN=…` | prise côté extrudeur de tête | candidate, pas encore appelable |
| `BOX_CUT_MATERIAL` | coupe, avec mouvements possibles | candidate après cartographie exacte |
| `BOX_RETRUDE_MATERIAL` | retire la route active | candidate après cartographie exacte |
| requêtes capteurs, buffer et objet `box` | lecture de présence et d’état | candidates de lecture seule |
| `BOX_ENABLE_AUTO_REFILL ENABLE=0/1` | active ou désactive la politique stock | utilisé seulement pour exclure/restaurer le propriétaire stock, après preuve |

Une commande candidate n’est pas une commande autorisée. Chaque commande
d’effet reste bloquée jusqu’à sa gate exacte sur la S12.

## Architecture retenue

Le trajet sera :

    Orca cloné
        -> une demande KCTRL versionnée
        -> K1 Control dans Moonraker : état, décisions, journal, rollback
        -> macros KCTRL petites et vérifiées
        -> soit Klipper natif : chauffe, mesh, Z, purge, pause/reprise
        -> soit une primitive BOX qualifiée : moteurs et capteurs CFS
        -> les deux CFS stock

Le `box_wrapper` reste donc un conducteur matériel limité. Il ne décide plus
du départ, du mesh, du Z, de la température, de la purge, de la reprise ni de
la fin.

Un verrou de propriétaire est obligatoire. Tant que K1 Control possède un job :

- aucun `Tn` ou cycle complet stock ne peut être appelé ;
- l’auto-remplacement stock est désactivé après sauvegarde de son ancien état ;
- une incohérence de propriétaire bloque avant tout effet filament ;
- aucun retry automatique n’est possible.

## Démarrage quotidien

Le départ prévu reste volontairement court :

1. Tu nettoies la buse à la main et confirmes une fois.
2. Plateau et buse commencent à chauffer.
3. X/Y sont référencés pendant la chauffe.
4. À `140/55 °C`, une seule référence Z propre est exécutée.
5. Le profil `k1_p001_t055_r001_n11x11` et le Z accepté sont chargés puis
   relus.
6. Le filament correct déjà engagé est gardé sans `Tn`.
7. La température de première couche est atteinte.
8. Une purge K1 Control explicite, sans brosse, confirme le débit.
9. Le modèle commence sans autre palpage, sans mesh neuf et sans offset caché.

Les branches « aucun filament » et « mauvais filament » utiliseront le même
départ, mais ne seront ajoutées qu’après qualification des petites phases CFS.

## Changement de filament pendant le print

K1 Control capture d’abord la position de reprise, le mesh, le Z, les modes
G-code, l’extrudeur, les températures, les ventilateurs et la route CFS. Il
lève la tête et choisit un chemin qui évite la pièce.

Le changement réalise ensuite une seule fois : température de retrait de
l’ancien filament, coupe, retrait, chargement du nouveau, purge explicite et
retour à sa température d’impression. La purge arrière retire l’ancienne
matière ; la tour de purge du slicer sert ensuite à stabiliser la pression avant
de revenir sur la pièce.

Il n’y a aucun homing, aucun palpage Z et aucune modification de mesh durant ce
cycle.

## Auto-remplacement d’une bobine vide

Oui, notre version gardera cette fonction.

Elle sera plus stricte que le choix stock. Le slot de remplacement doit être
référencé comme le même filament par l’utilisateur, avec même type, même
couleur, même diamètre et recette thermique compatible. Son capteur doit voir
du filament et la cartographie des deux CFS doit être fraîche.

Le déroulé cible est :

1. détecter la fin de bobine et mettre le print en pause ;
2. figer position, mesh, Z, températures et outil logique ;
3. exclure le slot vide pour ce job ;
4. trouver un unique slot identique disponible, y compris dans le second CFS ;
5. déterminer avec les capteurs où se trouve encore la fin de l’ancienne
   bobine ;
6. appliquer une seule recette qualifiée pour consommer ou retirer ce segment,
   puis charger le remplacement ;
7. purger sans brosse, à température et longueur explicites ;
8. revérifier route, capteurs, CFS, mesh, Z et température ;
9. reprendre exactement où le print s’était arrêté.

S’il n’y a aucun candidat ou plusieurs candidats contradictoires, l’impression
reste en pause. Elle ne choisit pas « au plus proche » et ne reprend pas seule.

La seule limite matérielle connue est l’absence actuelle de preuve directe du
débit en sortie de buse. Les capteurs CFS et tête prouvent le passage dans le
chemin, pas l’écoulement réel. La gate de runout devra donc qualifier la purge
et les erreurs de blocage avant d’autoriser le mode sans surveillance.

## Pilotage depuis Mainsail et Moonraker

La page K1 Control déjà accessible depuis Mainsail devient l’interface
quotidienne :

- état du filament et des deux CFS ;
- correspondance outil logique/slot physique ;
- mesh et Z réellement armés ;
- températures attendues et observées ;
- auto-remplacement activé/désactivé ;
- étape actuelle du cycle ;
- raison précise d’un blocage ;
- actions sûres : pause, reprise, annulation, désengagement.

Mainsail garde son rôle d’interface experte. L’écran stock reste installé. Nous
ne remplaçons ni le firmware CFS ni Moonraker.

## Rollback réel

Le rollback sera fonctionnel parce que nous ne remplaçons pas le pilote RS485
et ne réécrivons pas les grosses macros stock.

La future pose ajoutera seulement des fichiers nommés `KCTRL_*`, un include,
un composant Moonraker épinglé, une extension K1 Control et un profil Orca
cloné. Avant activation, les fichiers exacts, leurs hashes, le réglage
d’auto-remplacement stock, le mesh, le Z et le profil Orca précédent seront
sauvegardés.

Le rollback :

1. refuse de démarrer pendant un effet filament ;
2. place la machine dans un état sûr ;
3. bloque les nouveaux jobs K1 Control ;
4. restaure les fichiers et réglages exacts ;
5. redémarre seulement les services nécessaires ;
6. restaure l’ancien réglage d’auto-remplacement ;
7. revérifie chauffes, routes, mesh, Z et hashes ;
8. remet le profil Orca précédent.

Il restaure le fonctionnement stock d’avant, défauts compris. C’est un repli
technique fiable, pas une validation de la mauvaise séquence stock.

## Points de friction encore ouverts

| Point | Pourquoi il bloque | Comment on l’évite |
| --- | --- | --- |
| Helix a analysé une image K1 S11, notre machine est S12 | résolu pour la surface hors effet : binaire et chargeur exacts liés à la carte publique | garder chaque effet derrière sa gate physique |
| le runout stock peut lancer des callbacks internes | les noms et drapeaux S12 sont maintenant cartographiés, pas leurs effets physiques | construire l'exclusion à un seul propriétaire hors imprimante puis la qualifier séparément |
| une fin de bobine laisse encore un segment dans le tube et la tête | couper aveuglément ou relancer la grosse purge stock serait faux | qualifier séparément la recette « consommer ou retirer la fin » |
| la fin de print stock nettoie mappings et états de reprise | les chemins S12 sont repérés, mais appeler `BOX_END_PRINT` rendrait le cycle au stock | posséder explicitement ces nettoyages sans appeler la grosse fin stock |
| les petites phases peuvent échouer sans lever une erreur claire | un retour HTTP OK ne prouve rien | états avant/après, capteurs, une seule tentative |
| `BOX_CUT_MATERIAL` peut déplacer la tête | risque de collision avec la pièce | gate séparée avec position et trajet bornés |
| le changement entre deux CFS n’est pas prouvé localement | route ou reconnexion ambiguë | essai unitaire puis essai inter-boîtiers |
| les capteurs ne prouvent pas le débit en sortie | risque de reprendre avec buse bouchée | purge qualifiée et règle de blocage avant mode sans surveillance |
| retour au stock | réintroduit brosse/palpage/mesh stock | profil stock réservé au rollback, jamais présenté comme voie normale |

## Prochaine gate

Le préflight S12 est maintenant clos sans effet. La prochaine étape raisonnable
n'est toujours pas un chargement : c'est
`G4-K1-CONTROL-CFS-OWNER-CORE-OFFLINE-V1`.

Après un nouveau GO exact, elle construira le propriétaire pur hors imprimante
contre la réponse S12 enregistrée : un seul propriétaire, états avant/après,
auto-remplacement d'une bobine identique, refus des ambiguïtés, aucune reprise
automatique et journal explicite. Elle n'aura aucun transport K1 et n'autorisera
aucune pose. Les chargements, retraits, coupes et fins de bobine resteront des
gates physiques distinctes. Aucun ancien essai valable ne sera rejoué.
