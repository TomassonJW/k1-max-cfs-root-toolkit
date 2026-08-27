# CLEAN-MOTION-V1 — première tranche physique du Goal 3

Statut : **plan hors imprimante ; aucune commande de mouvement préparée**.

## Pourquoi cette tranche vient en premier

Le contrat de cycle exige un nettoyage autonome, mais la position et la hauteur
réelles de la brosse ne sont pas encore qualifiées. Le PRTouch sait mesurer le
plateau ; il ne doit pas servir à enfoncer la buse dans la brosse. Avant toute
chauffe, purge ou recette de nettoyage, il faut donc mesurer la géométrie à
froid et observer un trajet sans collision.

Cette tranche ne commence qu'après
`G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1 = ACTIVATION_OK`.

## Ce que Thomas devra confirmer

Thomas devra être devant la K1 et confirmer concrètement :

1. le plateau est entièrement libre ;
2. la brosse et le réceptacle sont installés, immobiles et visibles ;
3. il peut arrêter immédiatement la machine ;
4. il voit directement la buse ou dispose d'une caméra sans angle mort ;
5. il valide chaque rapprochement lent avant le suivant.

Ces confirmations autoriseront seulement des déplacements à froid par petits
checkpoints. Elles n'autoriseront ni chauffe, ni extrusion, ni CFS, ni
impression.

## Déroulement prévu

1. Relire l'état sûr, les limites machine et le profil robuste actif.
2. Noter les limites visibles de la brosse et du réceptacle sans mouvement.
3. Référencer uniquement ce qui est nécessaire pour circuler, sous observation.
4. Se placer très au-dessus de la zone, puis approcher par checkpoints validés.
5. Déterminer à vitesse très faible le plan de premier contact à froid.
6. Revenir au-dessus de la zone, puis tester une trajectoire sèche et bornée.
7. Sortir par la direction sûre, parquer et relire l'état final.

Les coordonnées, vitesses, accélérations et commandes exactes restent absentes
tant que les faits physiques ne sont pas observés. Il n'existe donc encore
aucun script exécutable pour cette tranche.

## Verdict

La gate sera OK seulement si le trajet complet est observé sans collision,
contact inattendu, perte de visibilité, chauffe, extrusion, action CFS,
palpage, mesh ou modification Z. Le profil robuste devra rester actif et les
cibles thermiques devront rester à zéro.

Au premier doute, la gate s'arrête. Aucun passage n'est relancé automatiquement.
La gate suivante `G4-K1-CONTROL-CLEAN-AND-REFERENCE-V1` ne sera préparée avec
des commandes réelles qu'après ce verdict humain positif.
