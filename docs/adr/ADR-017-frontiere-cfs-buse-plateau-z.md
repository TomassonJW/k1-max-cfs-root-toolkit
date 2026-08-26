# ADR-017 — Protéger toute la frontière CFS : buse, plateau et Z

Date : 2026-08-26
Statut : décision hors imprimante ; aucun déploiement autorisé

## Contexte

Le passage physique `20260826-physical-cfs-insert-purge-v1` demandait une buse
à `190 °C`. La séquence CFS a bien engagé le filament et produit une purge
visible, mais elle a ensuite imposé `220 °C` et lancé un homing X/Y. Le plateau
était trop haut pour le mécanisme arrière, car la séquence ne l'avait pas placé
à la hauteur de purge stock `Z=30 mm`.

La cible du plateau est restée à `0 °C` pendant cet incident. Cela ne suffit pas
à autoriser le CFS à la commander : Thomas signale que certains chemins CFS
peuvent également modifier le plateau et, selon les séquences, le Z. Les macros
Creality publiques de la famille CFS combinent effectivement gestion filament,
chauffe et parfois géométrie. Le cœur exact `box_wrapper` de cette K1 reste un
module compilé.

Le Z persistant accepté de la machine reste `−0,04 mm`. Son invariance pendant
la frontière fautive n'a pas été capturée avec une preuve fraîche assez complète
pour conclure. Elle doit donc rester une condition à prouver.

## Décision

Une opération CFS devient une frontière à six invariants :

1. cible buse explicite de la phase ;
2. cible plateau explicite du travail ou de Thomas ;
3. Z accepté inchangé ;
4. origine Z courante inchangée ;
5. profil mesh inchangé ;
6. ensemble des axes référencés inchangé.

À l'intérieur de cette frontière, le CFS n'a pas le droit d'émettre ou de
provoquer une commande buse/plateau, un homing, un réglage de Z ou un
effacement/chargement de mesh. Les cibles thermiques sont fixées et stabilisées
avant l'entrée. Le déplacement vers la purge arrière appartient au pilote de
mouvement de K1 Control et doit être terminé avant l'entrée dans la frontière.

Le paquet local `K1-CONTROL-CFS-BOUNDARY-GUARD-V1` évalue des traces sans se
connecter à la K1. Il refuse le passage du 26 août sur deux preuves suffisantes :
la cible buse `220 °C` et le `G28 X Y`. Les champs Z/mesh inconnus restent
explicitement marqués comme tels ; ils ne sont pas transformés en preuve verte.

## Options refusées

### Remettre la bonne température après le CFS

Refusé. Cette correction arrive après une chauffe ou une purge déjà fausse. Elle
peut bloquer la reprise, mais ne possède pas la phase.

### Remplacer `220` par une autre constante dans `box.cfg`

Refusé. Une constante casse dès que le matériau, le profil ou la phase change.
Elle ne protège ni le plateau ni le Z.

### Restaurer automatiquement l'ancien Z après une différence

Refusé. Une différence peut provenir d'une nouvelle référence réelle, d'une
origine transitoire ou d'un incident. Restaurer une ancienne valeur à l'aveugle
peut créer une collision. La règle est arrêt, preuve, puis récupération dédiée.

### Remplacer immédiatement tout `box_wrapper`

Différé. Le remplacement complet touche la communication de deux CFS, l'écran,
les capteurs, le changement et le refill. Il devient nécessaire seulement si
aucune primitive étroite ne respecte les six invariants.

## Conséquences

- les commandes brutes utilisées le 26 août ne doivent pas être rejouées ;
- `BOX_LOAD_MATERIAL_WITH_MATERIAL` est exclu d'un changement pendant
  impression, car son macro lisible contient `IF_NEED_HOME`, déplacement,
  nettoyage et restauration ;
- `BOX_MATERIAL_FLUSH TEMP=...` n'est pas suffisant tant que les primitives
  précédentes peuvent écrire une autre cible ;
- un watchdog n'autorise jamais la reprise à lui seul ;
- une dérive thermique coupe les deux cibles et bloque la reprise ;
- une dérive géométrique bloque la reprise sans restauration Z automatique.

## Gate suivante

Avant tout nouvel essai physique :

1. récupérer en lecture seule le journal complet de l'incident et le binaire
   exact `box_wrapper` par une mission séparée en lecture seule ; la
   joignabilité n'est plus le blocage ;
2. chercher hors imprimante les paramètres et écritures des primitives
   `BOX_EXTRUDE_MATERIAL`, `BOX_EXTRUDER_EXTRUDE` et
   `BOX_MATERIAL_FLUSH` ;
3. préparer un adaptateur étroit qui place d'abord la K1 à `Z=30 mm` et à la
   position de purge validée, puis n'appelle que des primitives respectant les
   six invariants ;
4. si aucune primitive ne les respecte, préparer un propriétaire CFS minimal
   séparé au lieu d'un correctif tardif ;
5. figer fichiers, commandes, backup, rollback et critères OK/KO avant un GO de
   pose ou d'essai.

Aucune étape de cette ADR n'autorise actuellement chauffe, mouvement, purge,
restart, modification de configuration ou impression.

## Résultat de la gate

L'audit demandé est clos par ADR-018. `BOX_EXTRUDE_MATERIAL` est refusée sur
preuve thermique et géométrique ; les deux primitives suivantes restent non
qualifiées faute de frontière isolée. L'adaptateur étroit existe donc comme
contrat fail-closed sans primitive appelable, pas comme paquet de pose.
