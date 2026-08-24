# ADR-016 — Cycle de production orchestré et propriété des températures CFS

Date : 2026-08-24

Statut : architecture retenue pour simulation hors imprimante ; production
toujours fermée

## Contexte

La séquence stock observée sur cette K1 Max avec deux CFS ne constitue pas un
cycle cohérent :

- le G-code Orca actif exécute un `G28`, un `Tn`, puis `START_PRINT`, alors que
  `START_PRINT` possède déjà son homing et son appel CFS ;
- `START_PRINT` enchaîne `CX_ROUGH_G28`, `CX_NOZZLE_CLEAR`, `ACCURATE_G28` et
  éventuellement le nivellement, ce qui explique les références Z répétées ;
- la configuration CFS garde `Tn_extrude_temp: 220`, indépendamment de la
  température réelle demandée par le filament ;
- les traces exactes ont vu un démarrage PLA demander `190 °C` mais charger et
  purger à `220 °C`, puis une reprise traverser plusieurs cibles incohérentes ;
- la macro `RESUME` appelle toujours `BOX_RESUME_EXTRUDE`, même pour une pause
  simple, puis restaure un état G-code pouvant écraser le Z ajusté pendant la
  pause ;
- la séquence de fin appelle le cutter et le retrait CFS par le cœur compilé,
  puis coupe les chauffes et désactive les moteurs, sans contrat K1 Control
  observable de bout en bout.

Le composant CFS `box_wrapper` est compilé. Ses primitives, ses objets d'état et
ses effets sont observables, mais son code exact n'est pas présent en clair sur
la machine. Des projets communautaires montrent qu'une réorchestration est
possible, mais aucun n'est directement installable sur cette révision : l'un
réécrit tout `box.cfg` et réapplique la température après coup ; un autre expose
un pilote CFS ouvert mais précise que la famille K1 n'est pas testée et remappe
les fonctions de communication.

## Décision

K1 Control deviendra le propriétaire du **cycle de travail**, sans remplacer le
firmware entier en une fois. Le slicer envoie un contrat unique et les macros
stock de haut niveau ne sont plus composées entre elles au hasard.

Le premier contrat Orca cible est :

```text
KCTRL_JOB_BEGIN
  BED=<température première couche>
  NOZZLE=<température première couche>
  TOOL=<outil initial>
  PLATE=<identité plaque>
  MESH=<mode standard ou précision>
  MATERIAL=<identité ou unknown>
```

Orca n'envoie alors ni `G28`, ni `Tn`, ni `START_PRINT`, ni correction Z
post-traitée en dehors de ce contrat. Le retrait de l'ancien `+0,27 mm` est
atomique avec cette bascule ; il n'est jamais retiré avant que le nouveau
chemin soit installé, vérifié et prêt à rollbacker.

Le système reste un monolithe modulaire :

- macros Klipper très courtes pour les mouvements déterministes et les arrêts
  d'urgence ;
- composant Moonraker K1 Control pour l'état, les contrats, les vérifications,
  l'historique et l'interface ;
- primitives CFS stock conservées tant qu'elles sont bornées et observables ;
- remplacement d'une primitive compilée uniquement si une trace prouve qu'elle
  réécrit tardivement une température ou un état impossible à contrôler.

## Séquence de démarrage cible

### 1. Admission et snapshot

Avant tout mouvement, K1 Control vérifie : état non imprimant, pas de
calibration active, plaque/profil connus, Z accepté valide, outil CFS résolu,
températures dans les bornes du matériau et deux CFS dans un état cohérent. Il
enregistre les cibles, le profil, le Z, l'outil, les capteurs et l'état de
rollback.

Toute ambiguïté ferme le démarrage. `MATERIAL=unknown` n'autorise pas un `220 °C`
silencieux : l'interface doit demander ou utiliser un profil par défaut affiché
et explicitement choisi.

### 2. Chauffe du plateau immédiatement

`M140` est lancé dès l'admission, sans attendre. Les opérations suivantes
utilisent ce temps de chauffe. Il n'y a pas de pause fixe de cinq minutes à
chaque impression.

La V1 attend au minimum que le plateau atteigne sa cible avant la référence Z
finale. Une courte fenêtre de stabilité pourra être apprise par les traces ; un
temps fixe long n'est pas décidé sans preuve.

### 3. Référence grossière seulement si nécessaire

Si les axes sont inconnus, X et Y sont référencés, puis une référence Z
grossière permet de se déplacer vers la brosse sans collision. Cette étape
n'est pas considérée comme la référence d'impression et n'écrit aucun Z
accepté.

Si une référence sûre et encore valide est disponible, elle n'est pas répétée.
Le cycle ne doit jamais faire trois homings Z par habitude.

### 4. Nettoyage réellement contrôlé

La température de nettoyage est dérivée du **filament précédemment présent**,
enregistré à la fin du travail précédent, et non du nouvel outil seulement. Le
profil matériau définit une température de nettoyage bornée, typiquement
quelques degrés au-dessus de sa température de travail, avec un plafond
explicite pour protéger la plaque et la brosse.

Le mouvement de brosse devient une recette K1 Control : plusieurs allers-retours
courts et rapides dans les coordonnées validées, avec limites X/Y/Z,
accélération et vitesse restaurées après coup. La recette est d'abord testée à
froid et loin du plateau, puis avec extrusion absente, avant tout essai chaud.

Si le dernier matériau est inconnu, le système n'invente pas une température :
il utilise une recette `unknown` affichée ou demande une confirmation.

### 5. Référence Z finale unique

Après nettoyage, la buse revient à la température de palpage qualifiée. Le
plateau doit avoir atteint sa cible. Une seule référence Z précise est alors
effectuée avec la buse propre.

Une confirmation supplémentaire n'est déclenchée que si le premier résultat
diffère d'une référence grossière ou d'une mesure précédente au-delà d'un seuil
qualifié. Ce n'est ni un troisième passage systématique, ni une moyenne
silencieuse.

Le profil mesh choisi est chargé **après** toute commande susceptible de le
vider ou de le remplacer. Le Z accepté est ensuite appliqué et relu. Les
mouvements bas restent désarmés tant que profil et Z effectifs ne correspondent
pas au contrat.

### 6. Chargement et purge CFS à la bonne température

K1 Control possède une cible logique par outil et par phase. Avant toute poussée
vers la buse, il impose la cible du filament entrant, attend la fenêtre
thermique et vérifie le capteur de filament.

Le cycle CFS est décomposé en états observables : outil courant, coupe,
retrait, position de chargement, avance, détection, purge et sortie de zone.
Chaque étape possède un délai maximal et un critère capteur. Une commande
acceptée par Klipper ne vaut pas preuve de réussite mécanique.

Si une primitive stock contient déjà sa propre purge, K1 Control n'en ajoute
pas une seconde. Si le module compilé réécrit tardivement la cible, la gate
échoue ; une simple commande `M104` ajoutée après coup n'est pas considérée
comme une propriété fiable.

### 7. Ligne d'amorçage puis impression

La ligne d'amorçage est une macro K1 Control autonome. Elle s'exécute à la
température de première couche, avec le profil mesh et le Z final déjà actifs.
Elle ne porte aucun offset caché et reste dans une zone testée de la plaque.

La main est rendue au G-code seulement après vérification : buse/plateau dans
leur fenêtre, bon outil, capteurs conformes, bon mesh, bon Z et aucun état CFS
en attente.

## Pauses et reprises distinctes

Le mot `RESUME` stock mélange plusieurs intentions. K1 Control les sépare :

### Pause normale

`KCTRL_PAUSE_NORMAL` sauvegarde la position, le mode d'extrusion, les
températures et le Z effectif, puis parque. Il ne coupe pas le filament, ne
change pas d'outil et n'appelle pas `BOX_RESUME_EXTRUDE`.

`KCTRL_RESUME_NORMAL` restaure la température et la position sans purge par
défaut. Une reprise après pause longue peut proposer **Réamorcer avant reprise**
dans l'interface. Le Z modifié volontairement pendant la pause est conservé ;
un snapshot antérieur ne peut pas le remplacer silencieusement.

### Changement de filament voulu

`KCTRL_TOOL_CHANGE` exécute coupe, retrait, chargement et purge avec la cible du
nouveau filament. Il conserve l'identité du travail et la position de reprise,
mais ne se fait pas passer pour une pause ordinaire.

### Fin de filament et recharge automatique

`KCTRL_RUNOUT_RECOVERY` possède son propre état et ses propres délais. Il
vérifie le slot de secours, l'équivalence ou la politique matériau, puis reprend
seulement après preuve capteur et température.

### Reprise après erreur

Une erreur CFS ne déclenche jamais automatiquement le cycle complet. L'écran
montre la phase atteinte, les capteurs et les seules actions de récupération
compatibles avec cet état.

## Fin d'impression cible

La fin conserve d'abord le chemin mécanique sûr déjà observé : park, coupe,
retrait du filament et rembobinage, avec vérification des capteurs et du slot.
La séquence exacte du cutter stock doit être tracée avant toute substitution,
car elle peut effectuer un homing, vider le mesh ou modifier temporairement
l'accélération.

Après retrait confirmé, une recette de nettoyage de fin peut utiliser la chaleur
résiduelle du matériau sortant et la brosse accessible, puis couper la buse et
le plateau. Elle reste optionnelle tant que son efficacité n'est pas prouvée.
Le système enregistre le dernier matériau et sa température de nettoyage pour
le prochain démarrage.

La désactivation des moteurs clôt le travail. L'état final doit être explicite :
chauffes zéro, CFS inactif, outil connu ou `none`, profil et Z persistants
inchangés, aucune reprise armée.

## Machine d'états

Le cycle minimal est :

```text
idle
  -> admitted
  -> bed_heating
  -> coarse_reference (si nécessaire)
  -> nozzle_cleaning
  -> final_reference
  -> mesh_and_z_armed
  -> cfs_loading
  -> priming
  -> printing
  -> ending
  -> idle
```

Les branches `paused_normal`, `tool_changing`, `runout_recovery`, `cancelling`
et `failed_safe` sont distinctes. Chaque transition possède entrée, sortie,
délai, effets autorisés, preuve attendue et rollback.

## Pièges explicitement interdits

- cumuler `G28`, `Tn` et `START_PRINT` dans Orca ;
- laisser Orca et la machine appliquer chacun un offset Z ;
- traiter une pause simple comme un changement de filament ;
- restaurer une origine Z sauvegardée avant un réglage utilisateur plus récent ;
- appeler une primitive CFS complète puis refaire sa coupe ou sa purge ;
- utiliser `220 °C` comme valeur universelle ou comme repli invisible ;
- croire qu'une commande CFS terminée prouve la position du filament ;
- ignorer les écritures de température retardées du module compilé ;
- perdre le mapping `CFS/slot` entre les deux unités après reconnexion ;
- lancer un mouvement de brosse rapide avant validation géométrique à froid ;
- charger le mesh avant une macro qui peut le vider ;
- retirer le `+0,27 mm` Orca avant la bascule atomique ;
- déclarer la production autonome avant une vraie pause normale, un changement
  voulu, un runout, les deux CFS et trois démarrages consécutifs sans correction.

## Stratégie de réalisation

1. **AUDIT-CYCLE-V2** : traces passives et scénarios contrôlés du démarrage,
   d'une pause normale, d'un changement, d'un runout et de la fin ; aucun
   remplacement.
2. **LIFECYCLE-OFFLINE-V1** : machine d'états simulée, fausses horloges,
   capteurs et retards de température injectés.
3. **CLEAN-MOTION-V1** : géométrie et mouvements de brosse validés à froid,
   sans chauffe ni extrusion.
4. **START-REFERENCE-V1** : chauffe plateau, référence grossière conditionnelle,
   nettoyage et référence finale, sans CFS ni impression.
5. **CFS-TEMP-OWNER-V1** : un seul chemin de chargement/purge avec température
   dynamique, d'abord sur CFS 1 puis CFS 2.
6. **PAUSE-SEMANTICS-V1** : pause normale sans purge, reprise avec Z conservé,
   puis reprise avec réamorçage volontaire.
7. **END-SEQUENCE-V1** : cutter, retrait, rembobinage et nettoyage de fin.
8. **ORCA-CUTOVER-V1** : bascule atomique du profil sélectionné, suppression de
   l'ancien départ et du `+0,27 mm`, avec export et rollback exacts.
9. **G5** : trois impressions, changements/refill sur les deux CFS, pause,
   reprise, annulation et démarrage quotidien sans Codex.

Une seule famille d'action physique est testée par incrément. Une correction
logicielle reste couverte par l'objectif actif, mais elle doit repasser ses
tests et sa gate complète avant la suite.

## Alternatives refusées

### Garder la séquence stock et ajouter quelques commandes Orca

Refusé : les commandes sont déjà dupliquées et les écritures CFS tardives ont
été observées. Ajouter `M104` après chaque `Tn` masque le symptôme sans garantir
la cible pendant la purge.

### Remplacer immédiatement tout `box_wrapper`

Refusé comme première étape : les fonctions de communication K1 sont remappées,
deux CFS sont chaînés et les chemins de sécurité stock ne sont pas tous
reproduits. Le remplacement complet ne devient rationnel que si une primitive
compilée empêche une propriété bornée.

### Faire un mesh à chaque impression

Refusé : le profil qualifié représente la forme chaude de la plaque. Le départ
doit seulement établir la référence Z propre et charger le profil adapté. Une
nouvelle mesure reste une action de calibration explicite.

### Attendre systématiquement plusieurs minutes

Refusé sans preuve. La chauffe du plateau commence immédiatement et se déroule
en parallèle du référencement grossier et du nettoyage. La référence finale
attend la cible et une stabilité bornée mesurée.

## Références

- [Klipper — recommandations de G-code slicer](https://github.com/Klipper3d/klipper/blob/master/docs/Slicers.md)
- [Moonraker — API imprimante](https://moonraker.readthedocs.io/en/latest/external_api/printer/)
- [CrealityPrint — profil officiel K1 CFS](https://github.com/CrealityOfficial/CrealityPrint/blob/master/resources/profiles/Creality/machine/Creality%20K1_CFS-C%200.4%20nozzle.json)
- [Mod communautaire K1/K1 Max CFS avec chemin reconstitué](https://github.com/FrederickAlt/CREALITY-K1-AND-K1-MAX-CFS-RETRUDE-BEFORE-CUT-MOD)
- [Pilote CFS communautaire ouvert et limites K1 explicites](https://github.com/gitstonelabs/creality-cfs-klipper)
