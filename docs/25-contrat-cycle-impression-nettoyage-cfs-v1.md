# Contrat V1 — nettoyage, impression et cycle filament CFS

Date : 2026-08-28

Statut : **amendé après qualification physique ; nettoyage manuel obligatoire ;
aucune implémentation production ni mutation K1 autorisée par ce document**

Ce document fixe le comportement attendu de K1 Control pour :

- le nettoyage manuel obligatoire de la buse ;
- le démarrage d'une impression ;
- le maintien, le chargement et le remplacement du filament ;
- la pause, le changement volontaire, la fin de filament et la reprise ;
- la fin d'impression et le retrait manuel sur commande ;
- le choix du mesh et les calibrations qui nécessitent ou non du filament.

Il complète ADR-016 et ADR-030. En cas d'écart, la règle la plus sûre de ce
document ferme la phase. Il ne remplace pas une gate physique, un préflight
frais, un backup ou un rollback.

## 1. Invariants non négociables

1. Le CFS n'est jamais propriétaire d'une température de travail.
2. Le plateau suit seulement une cible explicite du contrat G-code ou de
   Thomas.
3. Pendant l'impression, la buse suit seulement la dernière cible explicite du
   contrat G-code ou de Thomas.
4. Une température de transition, de retrait, de purge, de nettoyage ou de
   palpage est une phase distincte et doit elle aussi être explicitement
   déclarée, bornée et visible. Une valeur interne CFS comme `220 °C` ne peut
   jamais servir de repli silencieux.
5. Le bon filament déjà engagé est conservé. Il n'est ni coupé ni retiré par
   habitude.
6. Une présence capteur ne prouve ni l'identité du filament ni son écoulement à
   travers la buse.
7. Toute impression commence par une purge de preuve. Son volume dépend du
   chemin réellement parcouru.
8. Une buse sale ne qualifie pas une référence Z précise.
9. Le mesh est chargé après toute commande susceptible de le vider ou de le
   remplacer.
10. Aucun `T0` ou autre outil physique n'est supposé. Un outil logique est
    résolu vers un CFS et un slot à partir de l'état réel.
11. Toute ambiguïté importante produit `bloqué`, jamais une supposition.
12. La production reste fermée jusqu'au cutover Orca atomique et à G5.

## 2. Contrat de travail envoyé par le G-code

Le slicer envoie un seul `KCTRL_JOB_BEGIN`. Il n'ajoute pas séparément `G28`,
`Tn`, `START_PRINT`, un offset Z post-traité ou une macro CFS complète.

Le contrat versionné contient au minimum :

- identifiant et version du contrat ;
- identité de plaque ;
- température plateau première couche et température plateau normale ;
- température buse première couche et température normale de chaque outil
  logique ;
- identité déclarée de chaque matériau ;
- outil logique initial, sans hypothèse sur son CFS ou son slot physique ;
- cibles explicites de retrait et de purge pour chaque transition de matière ;
- volume de purge demandé par le slicer pour chaque transition ;
- politique de mesh et profil attendu ;
- politique de fin : conserver engagé ou retrait explicite ;
- preuve que l'ancien `+0,27 mm` n'est pas appliqué.

Le mapping `outil logique -> CFS -> slot` est résolu au moment du travail. Une
reconnexion, un déplacement de bobine ou une intervention manuelle invalide un
ancien mapping non re-prouvé.

Si une transition ne fournit pas une température exploitable, elle s'arrête
avant coupe, avance ou extrusion. K1 Control n'invente aucune valeur.

## 3. Températures par phase

### 3.1 Impression et remplacement équivalent

- plateau : cible active du G-code ;
- buse en première couche : cible première couche du G-code ;
- buse en couches normales : dernière cible du G-code ou de Thomas ;
- bobine épuisée remplacée par une bobine réellement équivalente : conserver la
  cible active ;
- filament correct déjà engagé : conserver la cible prévue et ne pas exécuter
  de cycle de retrait.

### 3.2 Changement entre matières différentes

Le contrat distingue trois valeurs :

1. retrait de l'ancien filament à sa température explicite et acceptée ;
2. purge de transition à une température explicitement fournie et compatible
   avec les deux matières ;
3. retour à la température du nouveau filament avant l'amorçage ou la reprise.

La règle initiale proposée pour la purge de transition est la plus haute des
deux températures de travail, seulement si elle reste dans les bornes déclarées
des deux recettes. Cette règle doit être calculée par le contrat et affichée ;
elle ne devient pas une heuristique cachée dans le CFS.

### 3.3 Nettoyage et palpage

La recette de l'ancien matériau stocke séparément :

- température minimale de nettoyage ;
- température nominale de nettoyage ;
- plafond absolu ;
- température de palpage qualifiée ;
- durée maximale de maintien chaud.

Il n'existe pas de `+10 °C`, `+20 °C`, `−30 °C` ou `100 °C` universel. Ces
valeurs peuvent seulement apparaître dans une recette matière physiquement
qualifiée.

## 4. Modèle d'état du filament

K1 Control utilise les états suivants :

| État | Signification | Action autorisée |
|---|---|---|
| `absent_confirmed` | absence cohérente et chemin CFS inactif | chargement contrôlé |
| `engaged_known` | outil, CFS, slot, matière et capteurs cohérents | conserver ou changer selon le contrat |
| `engaged_unknown` | présence détectée mais identité ou route incertaine | confirmation ou retrait contrôlé ; jamais imprimer |
| `transitioning` | coupe, retrait, avance ou purge en cours | seulement l'étape suivante de la même transition |
| `fault` | capteurs contradictoires, timeout, CFS incohérent ou débit absent | arrêt sûr et récupération affichée |

L'enregistrement persistant du dernier filament contient :

- outil logique ;
- CFS et slot physiques ;
- matière, marque et couleur déclarées ;
- source de l'identité : RFID, saisie humaine ou inconnue ;
- dernière température explicite utilisée ;
- signature des capteurs avant et après la dernière transition ;
- résultat de la dernière purge visible ;
- date, travail et niveau de confiance ;
- état `engaged`, `absent` ou `unknown`.

Après un reboot, une reconnexion CFS, un changement manuel ou une contradiction,
l'identité n'est pas restaurée comme certaine sans nouvelle preuve.

Sur la K1 exacte, deux objets `filament_switch_sensor` ont déjà été observés,
mais leur correspondance physique et leur combinaison correcte ne sont pas
encore qualifiées. Le second a déjà été vu désactivé. Leur audit passif est une
condition de l'implémentation ; aucun des deux ne devient une preuve de débit.

## 5. Nettoyage de buse — politique manuelle obligatoire

### 5.1 Décision physique

Les essais automatiques sur les deux brosses sont clos. La brosse du bac a
recollé du filament sur la buse. La grande brosse a ensuite été testée jusqu'à
huit allers-retours diagonaux à `F12000`, sans résultat visuel convaincant.

Le nettoyage automatique est donc rejeté. Aucun brossage automatique ni aucune
référence finale issue de cette gate ne peut être lancé. Cette décision est
figée par ADR-030 et `design/manual-nozzle-cleaning-policy-v1.json`.

### 5.2 Séquence manuelle canonique

1. Mettre la machine dans un état où Thomas peut atteindre la buse sans danger.
2. Thomas nettoie lui-même la buse.
3. Thomas confirme visuellement `NOZZLE_VISIBLY_CLEAN`.
4. La référence Z finale peut seulement commencer après cette confirmation.
5. En cas de doute ou de verdict négatif, la référence et l'impression restent
   bloquées.

Cette gate ne commande ni chauffe, ni mouvement, ni CFS. Elle ne déduit jamais
la propreté d'un retour logiciel.

### 5.3 Géométries historiques des brosses

Les coordonnées, trajectoires froides et captures chaudes restent conservées
pour la traçabilité. Elles ne sont plus une recette exécutable. Un futur retour
au brossage demanderait une décision distincte et une nouvelle qualification
physique ; aucun V4 n'est implicite.

### 5.4 Calibration Z et mesh

Le nettoyage manuel avec contrôle visuel est obligatoire avant une référence Z
ou un mesh de métrologie. Aucun chargement ni aucune purge n'a lieu pendant la
mesure de contact. Le retrait préalable reste recommandé si l'absence de
suintement ne peut pas être garantie autrement.

## 6. Démarrage d'une impression

1. Valider le contrat et l'absence d'offset Z caché.
2. Interroger machine, deux CFS, mapping des slots et capteurs.
3. Classer l'état filament. Toute contradiction ferme le départ.
4. Lancer immédiatement la chauffe plateau à la cible du contrat.
5. Si nécessaire, faire la référence grossière permettant de circuler.
6. Obtenir la confirmation humaine que la buse a été nettoyée manuellement et
   est visiblement propre.
7. Attendre la cible plateau et la stabilité bornée requise, puis revenir à la
   température de palpage qualifiée.
8. Faire une seule référence Z précise avec la buse propre.
9. Charger le profil mesh qualifié après toute macro pouvant le vider, appliquer
   le Z accepté et relire les deux états effectifs.
10. Résoudre le filament : conserver, changer, charger ou bloquer.
11. Aller au réceptacle arrière et purger dans tous les cas.
12. Prouver le débit par capteurs cohérents, transition CFS finie et sortie
    réellement visible. Sans capteur de débit qualifié, cette dernière preuve
    reste humaine ou caméra.
13. Attendre les températures première couche exactes du contrat.
14. Faire la ligne d'amorçage dans une zone de plaque physiquement qualifiée,
    jamais sur une coordonnée mécanique `0` supposée sûre.
15. Vérifier outil, CFS, températures, mesh, Z, capteurs et absence de transition,
    puis seulement rendre la main au modèle.

## 7. Décision filament au démarrage

### Bon filament déjà engagé

- ne pas aller au cutter ;
- ne pas retirer ni rembobiner ;
- aller au réceptacle ;
- faire une petite purge de preuve ;
- bloquer si aucun débit ne sort.

### Mauvais filament engagé

- atteindre la température explicite de retrait de l'ancien matériau ;
- aller au cutter par une trajectoire qualifiée ;
- couper, retirer et vérifier la séparation ;
- aller au réceptacle ;
- charger le nouvel outil à sa cible explicite ;
- purger selon le volume et la température de transition du contrat ;
- revenir à la cible première couche du nouvel outil.

### Aucun filament

- aller au réceptacle ;
- charger le filament résolu ;
- vérifier les capteurs ;
- purger et prouver le débit.

### Présence ou identité inconnue

Le démarrage s'arrête. L'interface montre les capteurs, la dernière route connue
et les choix sûrs : confirmer, retirer ou annuler. Elle ne choisit jamais `T0`.

## 8. Changement pendant l'impression

Un changement voulu, une fin de filament et une pause normale sont trois chemins
différents.

Avant tout trajet arrière, K1 Control sauvegarde :

- position XYZ et position de reprise ;
- modes absolu/relatif et état E ;
- mesh, Z effectif et profil actif ;
- températures, ventilateurs, vitesses et débit ;
- pression d'avance ;
- outil logique, CFS, slot et état des capteurs.

Il calcule une levée Z dans la hauteur encore disponible et une trajectoire qui
ne traverse pas la pièce. Aucun homing n'est effectué pendant l'impression.

Le changement suit ensuite le même noyau : retrait éventuel, cutter, nouveau
chargement, purge arrière, preuve de débit et retour à la température du prochain
segment.

La purge arrière chasse l'ancien matériau. La tour de purge ou autre structure
prévue par le slicer stabilise ensuite la pression et essuie la buse. L'une ne
remplace pas silencieusement l'autre.

La reprise restaure l'état courant volontaire, pas un ancien Z. Elle est refusée
si mesh, Z, outil, température, capteurs ou trajectoire ne correspondent plus au
snapshot accepté.

## 9. Pause et fin de filament

### Pause normale

La pause normale parque et sauvegarde. Elle ne coupe pas, ne change pas d'outil
et ne purge pas par défaut. Une reprise longue peut proposer un réamorçage
explicite.

### Fin de filament

Un remplacement par bobine réellement équivalente conserve la cible active.
Le slot de secours, la matière et la compatibilité doivent être prouvés. Une fin
de filament ne lance jamais un cycle complet sans savoir à quelle phase la
matière s'est arrêtée.

## 10. Mesh

Le profil est sélectionné au minimum par :

- plaque ;
- plage qualifiée de température plateau ;
- révision de la référence de palpage ;
- identité et diamètre de buse ;
- famille de profil : robuste, source physique ou dérivé qualifié.

Le profil standard sûr reste le `6 × 6` Lagrange qualifié. Le composite physique
et ses dérivés restent cachés tant que leurs gates de bord ne sont pas passées.

Si la première couche et les couches normales utilisent des températures de
plateau différentes, le contrat nomme explicitement le profil qualifié. K1
Control ne devine pas le plus proche et n'interpole pas deux profils sans gate
scientifique séparée.

## 11. Calibration et filament

| Calibration | Politique filament |
|---|---|
| Z ou mesh par contact buse/plateau | nettoyage manuel obligatoire ; aucun chargement ni purge pendant la mesure ; retrait préalable recommandé si l'absence de suintement n'est pas autrement prouvée |
| débit, température, rétraction ou pression d'avance | filament requis et explicitement résolu |
| résonances et input shaper | filament sans rôle métrologique ; aucun changement automatique |
| géométrie historique de la brosse | conservée comme preuve, non exécutable sans décision future distincte |

Le retrait CFS ne prouve pas une buse vide : un résidu peut rester dans le bloc
de chauffe. La propreté extérieure et l'absence de suintement restent des
preuves distinctes.

## 12. Fin d'impression et bouton de retrait

La politique cible par défaut est **conserver le filament correct engagé**, sous
réserve de la qualification physique du CFS exact :

1. parquer ;
2. effectuer seulement la rétraction finale validée ;
3. ne pas aller au cutter ;
4. enregistrer outil, CFS, slot, matière, température et capteurs ;
5. demander les chauffes à zéro ;
6. libérer les moteurs seulement dans un état sûr ;
7. fermer toute reprise.

L'interface fournit un bouton séparé **Désengager et nettoyer**. Cette action :

- utilise la température explicite enregistrée de l'ancien matériau ;
- coupe, retire et vérifie le rembobinage ;
- ne lance aucun nettoyage automatique ; le nettoyage manuel reste une gate
  séparée si la buse doit être rendue propre ;
- finit avec cibles zéro, outil `none` ou état `unknown` clairement affiché.

Il n'existe pas de réchauffage automatique différé et sans présence humaine
plusieurs heures après la fin d'un travail.

## 13. Arrêt sûr et reprise après erreur

Chaque phase possède un délai maximal, une preuve d'entrée, une preuve de sortie
et les seuls effets autorisés. Toute erreur :

- arrête l'extrusion et les mouvements bas ;
- coupe les chauffes si leur maintien n'est pas requis pour une récupération
  humaine immédiate ;
- conserve mesh et Z persistants ;
- n'exécute pas automatiquement le cycle complet ;
- montre phase, capteurs, outil attendu, outil observé et actions sûres ;
- ne transforme jamais une commande Klipper terminée en preuve mécanique.

Les cas obligatoires incluent : capteurs contradictoires, cutter non confirmé,
retrait incomplet, chargement incomplet, débit absent, réceptacle indisponible,
température réécrite, mapping CFS perdu, pièce bloquant le trajet arrière,
reboot et coupure de courant.

## 14. Incident MESH-EDGE-DIAGNOSTIC-V1

Le premier motif source a chauffé, déplacé la tête et envoyé des commandes
d'extrusion, mais aucun filament n'a été déposé. Le paquet minimal avait retiré
le chemin stock `Tn/START_PRINT` sans le remplacer par une résolution filament,
un chargement ou une purge. L'hypothèse documentaire `T0` n'était pas un fait
fourni par Thomas et ne prouvait rien sur l'état physique.

Ce passage ne constitue ni une impression, ni une preuve de buse bouchée, ni une
qualification de mesh. Le rollback exact et sa validation finale sont verts
sous la capture `20260826-090956-mesh-edge-diagnostic-v1`. La gate physique
reste suspendue. Avant toute reprise :

1. ne pas répéter le rollback déjà clos et partir de la base sûre validée ;
2. conserver l'absence de `T0` supposé ;
3. exiger une route filament explicitement confirmée ;
4. exiger une purge visible fraîche avant chaque motif ;
5. repasser les tests hors imprimante et un nouveau préflight.

## 15. Ordre de réalisation

1. **PRODUCTION-SEQUENCE-AUDIT-V2** : trace passive des capteurs, cutter,
   retrait, chargement, purge, pause, runout et fin.
2. **JOB-LIFECYCLE-OFFLINE-V1** : machine d'états simulée avec erreurs,
   horloges, capteurs et réécritures thermiques injectés.
3. **CLEAN-MOTION-V1** : coordonnées et trajectoires de brosse à froid.
4. **CLEAN-AND-REFERENCE-V1** : essais automatiques clos KO, politique manuelle
   obligatoire et actions automatiques désactivées ; la référence finale prévue
   n'a pas été exécutée.
5. **CFS-TEMP-OWNER-V1** : cible par phase, démarrage avec filament correct,
   absent puis incorrect, d'abord CFS 1 puis CFS 2.
6. **TOOL-CHANGE-AND-RUNOUT-V1** : changement voulu, remplacement équivalent,
   changement de matière et trajet sûr autour d'une pièce.
7. **PAUSE-RESUME-SEMANTICS-V1** : pause sans CFS, reprise simple et
   réamorçage volontaire.
8. **END-SEQUENCE-V1** : conserver engagé par défaut, puis bouton Désengager et
   nettoyer.
9. **ORCA-CUTOVER-V1** : bascule atomique du profil sélectionné et retrait du
   `+0,27 mm` historique.
10. **G5** : trois travaux consécutifs, deux CFS, changement, runout, pause,
    annulation, fin et redémarrage sans Codex.

Une seule famille d'action physique est qualifiée par incrément.

État au 26 août 2026 : `G4-K1-CONTROL-CFS-DYNAMIC-TEMP-ROUTING-V1` a fermé
hors imprimante le contrat thermique préparatoire de l'étape 5. Le propriétaire
minimal séparé est choisi et 25 scénarios thermiques sont verts.

La gate suivante `G4-K1-CONTROL-CFS-MINIMAL-OWNER-PROTOCOL-V1` est close en
KO borné : les captures prouvent deux adresses de requête et seulement une
route d'effet `T1A`. Retrait, coupe, purge isolée, autres slots, effets du
second CFS, intégrité de trame et exclusion du propriétaire stock ne sont pas
qualifiés. La liste appelable, le transport, la pose et la qualification
physique de `CFS-TEMP-OWNER-V1` restent donc absents.

État au 27 août 2026 : `GOAL-P4-OFFLINE-CYCLE-CFS-V1` est terminé. Le transport
simulé du garde obtient `13/13`, la machine d'états exécute les `27/27` cas
canoniques et le plan futur épingle sources, destinations, sauvegardes et
rollback sans contenir de connecteur réel ni de commande distante. Cette
fermeture ne qualifie aucun mouvement, débit, délai réseau ou effet physique.
La prochaine étape est une comparaison en lecture seule avec un état K1 frais,
sous une autorité séparée.

## 16. Références

- [ADR-016 — cycle de production orchestré](adr/ADR-016-cycle-production-orchestre-et-propriete-cfs.md)
- [ADR-021 — protocole minimal fermé en KO borné](adr/ADR-021-fermer-le-protocole-minimal-cfs-en-ko-borne.md)
- [ADR-027 — cycle hors imprimante avant connecteur réel](adr/ADR-027-fermer-le-cycle-hors-imprimante-avant-tout-connecteur-reel.md)
- [ADR-030 — nettoyage de buse manuel obligatoire](adr/ADR-030-nettoyage-buse-manuel-obligatoire.md)
- [Audit mesh et cycle CFS](23-audit-mesh-manuel-et-cycle-production-cfs.md)
- [Klipper — capteurs filament](https://www.klipper3d.org/Config_Reference.html#filament-sensors)
- [Klipper — profils bed mesh](https://www.klipper3d.org/Bed_Mesh.html#profiles)
- [Klipper — sauvegarde et restauration d'état G-code](https://www.klipper3d.org/G-Codes.html#save_gcode_state)
- [Creality — kit CFS K1](https://wiki.creality.com/en/k1-flagship-series/CFSUK/user-manual)
- [Creality — chargement et identité CFS](https://wiki.creality.com/en/cfs/cfs-filament-loading-guide)
- [CrealityPrint — profil officiel K1 CFS](https://github.com/CrealityOfficial/CrealityPrint/blob/master/resources/profiles/Creality/machine/Creality%20K1_CFS-C%200.4%20nozzle.json)
