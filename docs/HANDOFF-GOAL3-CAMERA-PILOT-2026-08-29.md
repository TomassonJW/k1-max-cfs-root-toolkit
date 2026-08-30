# Handoff — Goal 3, incident R5 et reprise par caméra

Cette passation est historique. La passation canonique actuelle est
`docs/HANDOFF-GOAL3-R3-COLD-VALIDATED-2026-08-30.md`.

Date : 2026-08-29
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Nouvelle tâche créée : non
Nouveau Goal Codex : absent
Reprise : `ATTENDRE_GO`

## État livré

Le Goal 3 reste en cours à `2/7`. Le run thermique R5
`20260829-goal3-thermal-r5-run-6174bcc` est définitivement clos KO, sans retry.
La stabilisation de `200 s` a fonctionné, mais Thomas a observé trois défauts
physiques décisifs : purge hors du bac, absence de l'aller-retour qui décroche
la boule, puis impression visuellement proche de `10 mm` au-dessus du plateau.
La télémétrie Z ordinaire ne corrige pas ce verdict : un morceau de filament
sous la buse peut fausser la référence physique tout en laissant des coordonnées
Klipper cohérentes.

L'arrêt est prouvé. Le dernier état frais est `cancelled`, cibles buse et
plateau à zéro, axes libérés, tête haute à droite, profil
`k1_p001_t055_r001_n11x11` actif et aucune route CFS engagée. Une image caméra
`1280 × 720` prise après l'annulation montre le plateau descendu et la tête
éloignée ; elle est conservée dans l'inventaire brut privé. Elle ne prouve pas
la purge passée.

ADR-033 remplace la partie « sans brosse » du départ possédé. Le candidat local
`start-sequence-owner-camera-purge-r3` impose désormais : référence grossière,
purge de `20 mm` dans le bac à `X185,5 Y305 Z30`, retour à `140 °C`, mouvement
E4 qualifié à `X203..206 / Y305 puis Y304 / Z32`, pause caméra, référence Z
précise, restauration du `11 × 11` et du Z accepté, ligne rapide hors plateau à
`X-1,7/-1,3`, seconde pause caméra, puis seulement reprise du modèle. Il reste
strictement hors imprimante : aucun déployeur et aucune autorité physique.

Le pilotage caméra est canonique dans le document 49 et dans `AGENTS.md`.
Codex prend les images, compare les états, pilote les commandes, l'arrêt et les
preuves. Thomas ne doit être sollicité que pour un vrai geste manuel : nettoyer
buse/plateau, placer la plaque, déclencher une fonction constructeur nécessaire,
insérer ou retirer le filament, ou aider au Z si l'image reste insuffisante. Il
n'a aucun texte de gate à recopier pendant une mission déjà cadrée. Le LiDAR
reste démonté : il n'est ni requis ni conseillé pour la prochaine tranche.

## Vérifications et limites

- état sûr réel après R5 : **OK** ;
- accès caméra local et capture fixe : **OK** ;
- observation purge/première couche R5 : **KO physique** ;
- retry R5 : **interdit** ;
- candidat R3 : **OK hors imprimante**, vérificateur dédié vert et `4/4` tests
  propres au paquet ;
- tests R3 + diagnostic thermique : **OK**, `14/14` ;
- registre Goal 3 : **OK en cours**, `2/7` et prochain effet bloqué ;
- parse Jinja complet : **non exécuté**, `jinja2` absent du Python local ; la
  prochaine validation froide doit utiliser le parseur Klipper disponible ;
- pose R3, chauffe, extrusion, homing ou impression : **non exécutés** ;
- autonomie Z par caméra : **non qualifiée**. La caméra sait déjà détecter un
  défaut grossier ; une convergence fine exigera une référence
  `FIRST_LAYER_GOOD`, un motif court et des pas Z bornés.

## Prochaine mission unique

`G4-K1-CONTROL-CAMERA-REFERENCE-LIBRARY-AND-R3-COLD-VALIDATION-V1`

Relire, dans cet ordre : ce handoff, le document 49, ADR-033, le contrat et le
verdict du paquet R3, puis la matrice du Goal 3.

La mission doit d'abord rester hors effet : terminer un petit pilote qui résout
l'adresse par `k1max-root`, prend une image, vérifie cadrage/netteté, extrait les
zones buse/bac/plateau et compare une image courante à une référence. Conserver
`SAFE_IDLE_PARK` comme seule référence réellement acquise ; ne pas inventer les
autres. Relire ensuite le Jinja R3 et prouver à froid que ses deux états caméra
bloquent la suite, que `PAUSE_BASE/RESUME_BASE` évitent les macros CFS stock et
que tout timeout coupe les chauffes sans confirmer l'image.

Critères de fin : tests ciblés verts, JSON et Jinja valides, aucun connecteur
d'effet dans le pilote caméra, aucun changement K1, prochaine gate chaude
préparée mais fermée. Le futur essai chaud ne pourra commencer qu'après trois
faits physiques réellement nouveaux : plateau nettoyé et libre, buse nettoyée,
T1A réengagé par la fonction officielle. Codex demandera uniquement ces gestes,
en clair, au moment utile.

Modèle optimal : `gpt-5.6-sol`, raisonnement `high`, pour combiner Klipper/Jinja,
analyse d'image et sûreté matérielle. Option économique : `gpt-5.6-terra` en
`high`, acceptable pour la partie hors ligne, avec plus de risque de reprise au
moment d'interpréter les images et les états transitoires.
