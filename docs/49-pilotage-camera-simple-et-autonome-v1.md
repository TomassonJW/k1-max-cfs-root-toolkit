# Pilotage caméra simple et autonome V1

Statut : **règle canonique de reprise ; bibliothèque d'images à construire**.

## Principe

La caméra locale de la K1 est désormais un capteur obligatoire du projet. Son
image fixe `1280 × 720` est accessible sans mouvement sur le service caméra
existant, via `http://<adresse résolue par k1max-root>:8080/?action=snapshot`.
L'adresse n'est pas écrite en dur : le pilote la récupère avec la configuration
SSH locale.

La télémétrie dit ce que Klipper croit avoir fait. La caméra dit si la tête, le
bac, la purge et le filament sont réellement là où ils doivent être. Une phase
logicielle comme `visible_purge` ne vaut plus jamais preuve physique.

## Bibliothèque minimale à apprendre

Une seule session courte et surveillée doit capturer quelques références :

1. `SAFE_IDLE_PARK` : plateau descendu, tête haute et garée, aucun mouvement ;
2. `ROUGH_HOME_READY` : position sûre après la référence grossière ;
3. `BIN_PURGE_ACTIVE` puis `BIN_RELEASED_CLEAN` : purge dans le bac, boule
   décrochée et rien sous la buse ;
4. `PRIME_OUTSIDE_BED` : ligne continue à gauche, entièrement hors plateau ;
5. `FIRST_LAYER_GOOD` : une petite première couche connue comme correcte.

La première image `SAFE_IDLE_PARK` existe déjà dans l'inventaire brut privé de
l'incident R5. Les autres références n'existent pas encore et ne doivent pas
être inventées.

Le contrôle reste volontairement simple : même cadrage, petites zones fixes
autour de la buse, du bac et du plateau, comparaison avec la référence, puis
lecture visuelle par Codex. Si l'image est absente, floue, masquée ou différente
sans explication, le pilote arrête la séquence. Il ne suppose pas que tout va
bien.

## Répartition du travail

Codex prend en charge : état Moonraker/Klipper, captures caméra, comparaison des
images, commandes techniques déjà cadrées, arrêt immédiat, preuves, tests et
clôture Git. Une mission active sous `$session-tas` ne redemande pas de texte
d'autorisation pour chaque lecture ou commit, ni pour continuer une séquence
déjà cadrée lorsque les conditions physiques n'ont pas changé.

Thomas intervient seulement pour les actes réellement manuels : nettoyer la
buse ou le plateau, placer la plaque, lancer une séquence officielle nécessaire
dans l'interface constructeur, insérer ou retirer un filament/CFS, et corriger
le Z pendant une impression lorsque la caméra n'offre pas encore une preuve
suffisante. Codex décrit alors l'acte concret à faire ; aucun identifiant de gate
à recopier n'est demandé.

## Z offset

La caméra peut déjà repérer un défaut grossier : impression dans le vide,
filament non déposé, ligne écrasée ou traînée par la buse. Après constitution de
`FIRST_LAYER_GOOD`, elle pourra comparer largeur, continuité et écrasement de la
ligne, proposer un petit pas de Z, reprendre une image et converger sous limites
strictes.

Elle ne fournit pas encore une mesure fiable au centième de millimètre depuis
une vue oblique en `720p`. L'autonomie complète du Z sera donc qualifiée par une
campagne dédiée avec motif court, pas borné, maximum de corrections et arrêt au
doute. Le LiDAR n'est ni requis ni recommandé à ce stade.

## Règles bloquantes

- image fraîche avant tout essai physique et aux deux pauses caméra de R3 ;
- purge dans le vrai bac, mouvement E4 de décrochage, puis image propre avant
  la référence Z précise ;
- seconde image après la ligne hors plateau et avant le modèle ;
- surveillance caméra de la première couche avec annulation immédiate au défaut ;
- aucun retry automatique après un effet incertain ;
- aucun nouvel essai chaud tant que la buse, le plateau et la route filament ne
  sont pas réellement remis en état après R5.

Les détails du correctif sont figés par ADR-033 et le paquet
`start-sequence-owner-camera-purge-r3`.
