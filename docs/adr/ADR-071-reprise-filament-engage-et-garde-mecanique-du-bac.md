# ADR-071 — Décider avant le homing et protéger mécaniquement le bac

Statut : conception autorisée par Thomas le 23 septembre 2026 ; candidat en
construction, **pas encore installé ni qualifié physiquement**.

## Besoin

Après `key837`, le filament peut être présent dans la tête alors que le
chargement n'est pas validé. Thomas demande une relance qui conserve ce
filament, chauffe, purge au bac et imprime. Il demande aussi la correction de
la prise initiale par l'extrudeur, sans masquer les défauts.

Le démarrage installé palpe puis appelle Tn avant son test de présence. Ce test
ne protège donc ni la référence ni le changement d'outil. La pause diminue le
courant E à environ 0,28 A ; le démarrage ne le restaure pas explicitement.
La cause exacte de l'incident initial n'est pas prouvée par ce seul constat.

## Décision

Un petit coordinateur de départ doit classifier l'état **avant** l'effacement
des caches du travail précédent, `BOX_START_PRINT`, les chauffes, les références
et Tn. Quatre chemins : tête vide ; bon filament conservé ; prise interrompue
à terminer sans réinsertion ; changement d'une route connue vers une autre.
Un souvenir de bobine sélectionnée n'est jamais une preuve de filament engagé.

Thomas a révisé la condition de palpation le 23 septembre : son nettoyage
manuel à 150 °C permet de garder le filament engagé. Le départ doit refaire
les références après confirmation fraîche de propreté, à la température de
contact configurée (100 °C actuellement). La présence de filament n'impose
aucun retrait. Aucun `SET_KINEMATIC_POSITION` ne transforme une ancienne
coordonnée en mesure. Une nouvelle extrusion invalide la confirmation de
propreté si une autre palpation doit suivre.

La classification du filament avant le homing ne donne aucun droit de
mouvement. Le contrôle XYZ de `decide_start` reste conservé et doit être appelé
après la nouvelle référence. La future intégration doit en plus vérifier que
le homing précis vient de terminer dans ce départ, pas seulement que les axes
sont déclarés référencés. Cette intégration complète n'est pas encore écrite.

Le courant E doit être restauré à la valeur configurée, puis relu avant toute
prise/purge et au début du changement d'outil. Aucun courant supérieur à la
configuration n'est inventé. L'enchaînement de la prise et du CFS doit être
vérifié contre le binaire exact et par observation physique, pas seulement par
les ordres E enregistrés.

La reprise après prise interrompue reste provisoire jusqu'à la confirmation du
trajet, de l'état CFS et du débit réel. L'erreur est effacée uniquement dans ce
chemin identifié ; aucun chargement, cutter ou retry caché n'y est permis.
Les états constructeur ne sont finalisés qu'après la preuve de prise.

## Invariant mécanique prioritaire demandé par Thomas

Le plateau doit être descendu d'au moins **30 mm** lorsque la tête actionne le
bac. Ce minimum vaut pendant l'entrée, la purge, les quatre mouvements de
décrochage, les erreurs et la sortie. Une commande de remontée du plateau est
refusée tant que la tête n'est pas sortie vers le couloir avant.

Le candidat vise 35 mm au minimum, sans remonter un plateau déjà plus bas.
Une garde contrôle les coordonnées physiques après mesh et offset, y compris
les segments diagonaux. L'entrée dans la zone arrière du bac verrouille la
protection jusqu'à une sortie distincte à Y <= 280. Le parcours retenu sort à
Y273 avant toute remontée. L'enveloppe initiale X175..220 / Y>=300 couvre le
bac installé. Le décrochage candidat suit les sorties/retours Y291,5/Y305 à
X185,5, observés dans le trajet constructeur. Aucun brossage fixe ni balayage
latéral. Sa validation physique reste due.

L'adaptateur candidat `kctrl_bin_motion.py` conserve le calcul constructeur de
la descente et de la hauteur de retour ; il augmente à 35 mm la seule consigne
absolue de l'entrée au bac. Avant le retour Z constructeur, il sort vers Y273
sans commande Z ou E. Les appels non reconnus sont refusés avant mouvement.
Les tests couvrent le retour exact depuis une couche basse et depuis un
plateau déjà descendu ; ils ne qualifient pas l'installation réelle.

Un refus de commande déclenche une erreur contrôlée et coupe les chauffes ;
il ne justifie pas un M112 automatique après chaque échec de départ.

## Installation et vérification

Le chargement du correctif doit préserver le filament. Le Klipper exact coupe
les moteurs au restart : les références seront explicitement perdues, puis
refaites après nettoyage confirmé. Aucune ancienne coordonnée ne sera restaurée.
La pose future exige sauvegardes, empreintes, rollback et vérification réelle.

Les tests doivent couvrir le parcours complet et les erreurs avant de poser :
ordre des décisions, tête conservée après échec, homing frais puis absence de
Tn de réinsertion, courant nominal rétabli, purge dédiée, alarmes réarmées,
sortie du bac avant remontée, changement ultérieur et fin existante préservés.
Les tests simulés ne prouvent ni le débit ni la sécurité physique du bac.

Le 23 septembre, 49 tests locaux de politique et de garde passent. Le contrôle
automatique a refusé l'ajout du coordinateur complet, jugé insuffisamment
validé même comme candidat local. Aucun module de démarrage complet n'a été
créé ni posé. Voir le document 98 pour les preuves et le périmètre restant.

## Convention de nettoyage

Thomas indique qu'une chauffe manuelle à 150 °C lui sert à nettoyer la buse en
préparation. Cette consigne est un indice d'intervention manuelle ; elle ne
prouve ni que le nettoyage est terminé, ni que la géométrie est valide, ni que
le filament a été retiré. Elle n'autorise aucun mouvement simultané.

## Alternatives écartées

- Un seul IF après Tn : trop tard pour éviter la coupe ou le homing.
- Capteur présent donc impression autorisée : ne prouve ni route ni prise.
- Effacement systématique des erreurs et nouvelle tentative : perd la cause
  et peut répéter les efforts mécaniques.
- Restaurer une position Z historique après restart : remplace une référence
  physique par une supposition.
- Refonte du protocole CFS complet : inutile pour ce correctif ; les primitives
  vérifiées restent utilisées avec un propriétaire clair par phase.
