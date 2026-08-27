# CLEAN-MOTION-V1 — première tranche physique du Goal 3

Statut : **checkpoint C techniquement et humainement vert ; meilleur profil
actuel `11 × 11` actif ; prochain rapprochement pas encore lancé**.

## Faits déjà qualifiés sans mouvement

La capture privée `20260827-clean-motion-v1-read-only-sources-v3` a obtenu
`CAPTURE_OK` uniquement par requêtes GET. Elle confirme les limites logiques
X `−2…306,5 mm`, Y `−0,5…307,5 mm`, Z `−10…305 mm`.

Le `prtouch_v2` actif déclare une zone de nettoyage X `68…94 mm`,
Y `304,5…306,5 mm`, un trajet X de `20 mm` et un delta Z de `−0,15 mm`.
Les commandes stock de nettoyage et de référence sont réellement enregistrées.
Leur code complet n'a pas été exporté.

Ces valeurs prouvent la configuration logicielle, pas la position physique de
la brosse. Elles servent seulement à préparer l'observation humaine et ne sont
pas encore des coordonnées autorisées de mouvement.

## Pourquoi cette tranche vient en premier

Le contrat de cycle exige un nettoyage autonome, mais la position et la hauteur
réelles de la brosse ne sont pas encore qualifiées. Le PRTouch sait mesurer le
plateau ; il ne doit pas servir à enfoncer la buse dans la brosse. Avant toute
chauffe, purge ou recette de nettoyage, il faut donc mesurer la géométrie à
froid et observer un trajet sans collision.

Le préalable corrigé est maintenant satisfait :
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1 = RESTORE_OK`, avec le meilleur
profil observé `k1_p001_t055_r001_n11x11` confirmé actif par deux lectures
indépendantes. Tous les profils actuels ont des défauts de bord ; aucun n'est
qualifié robuste.

## Ce que Thomas devra confirmer

Thomas a confirmé concrètement :

1. le plateau est entièrement libre ;
2. la brosse et le réceptacle sont installés, immobiles et visibles ;
3. il peut arrêter immédiatement la machine ;
4. il voit directement la buse ou dispose d'une caméra sans angle mort ;
Les prochains verdicts humains porteront sur chaque rapprochement lent avant le
suivant.

Ces confirmations autoriseront seulement des déplacements à froid par petits
checkpoints. Elles n'autoriseront ni chauffe, ni extrusion, ni CFS, ni
impression.

## Déroulement prévu

1. Relire l'état sûr, les limites machine et le meilleur profil actuel actif.
2. Noter les limites visibles de la brosse et du réceptacle sans mouvement.
3. Référencer uniquement ce qui est nécessaire pour circuler, sous observation.
4. Se placer très au-dessus de la zone, puis approcher par checkpoints validés.
5. Déterminer à vitesse très faible le plan de premier contact à froid.
6. Revenir au-dessus de la zone, puis tester une trajectoire sèche et bornée.
7. Sortir par la direction sûre, parquer et relire l'état final.

Le premier checkpoint a pris en compte que le `G28` stock recharge
automatiquement `default` : il a remis aussitôt le `11 × 11` exact et commandé
une hauteur libre de `Z=50 mm`. Le premier validateur a confondu la position
G-code `50,00 mm` et la position physique compensée `50,23 mm`, puis a produit
un faux KO. Aucun mouvement n'a été rejoué. La validation corrigée en lecture
seule est verte. Les coordonnées de contact et de brossage restent absentes
jusqu'au verdict humain sur ce checkpoint. Thomas a depuis confirmé
`CHECKPOINT C OK` ; le mouvement ne sera pas rejoué.

## Verdict

La gate sera OK seulement si le trajet complet est observé sans collision,
contact inattendu, perte de visibilité, chauffe, extrusion, action CFS,
palpage, mesh ou modification Z. Le meilleur profil actuel `11 × 11` devra rester actif et les
cibles thermiques devront rester à zéro.

Au premier doute, la gate s'arrête. Aucun passage n'est relancé automatiquement.
La gate suivante `G4-K1-CONTROL-CLEAN-AND-REFERENCE-V1` ne sera préparée avec
des commandes réelles qu'après ce verdict humain positif.
