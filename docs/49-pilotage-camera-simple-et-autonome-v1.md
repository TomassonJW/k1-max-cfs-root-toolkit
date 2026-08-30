# Pilotage caméra simple et autonome V1

> Mise à jour du 30 août 2026 : la caméra ne peut pas rendre sûre une palpation
> après insertion. Toute insertion est présumée laisser un résidu ; les
> calibrations et références par contact doivent être terminées avant le
> chargement. Voir ADR-034. R3 reste une preuve froide historique et ne doit
> jamais être posé ni exécuté.

Statut : **règle canonique ; pilote minimal validé, bibliothèque limitée à
`SAFE_IDLE_PARK`**.

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
l'incident R5. Son empreinte, le cadrage et les zones buse/bac/plateau sont
figés dans le paquet
`camera-reference-library-and-r3-cold-validation-v1`. Une image fraîche du
30 août a été nette et visuellement cohérente avec cet état sûr. Le pilote
conserve toutefois `semantic_state_confirmed=false` : une proximité de pixels
ne confirme jamais seule une gate. Les autres références n'existent pas encore
et ne doivent pas être inventées.

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

- image fraîche avant tout essai physique et à chaque arrêt caméra du futur
  candidat ;
- toutes les palpations terminées avec buse propre avant toute insertion ;
- purge dans le vrai bac et mouvement E4 de décrochage seulement après les
  références et mesures de contact ;
- seconde image après la ligne hors plateau et avant le modèle ;
- surveillance caméra de la première couche avec annulation immédiate au défaut ;
- aucun retry automatique après un effet incertain ;
- aucun essai chaud avec R3, même après remise en état.

Les détails du correctif sont figés par ADR-034 et le paquet
`calibration-before-insertion-v1`. ADR-033 et R3 sont conservés comme preuves
historiques de l'ordre rejeté.

## Validation froide acquise

Le pilote minimal et R3 sont validés sans effet. Le pilote résout l'adresse par
la configuration locale de `k1max-root`, fait uniquement un `GET` caméra,
contrôle `1280 × 720`, la netteté et les trois zones, puis écrit dans
`inventory/raw`. Il ne connaît aucune route Moonraker ou G-code.

Les deux pauses R3 bloquent avant `ACCURATE_G28` et avant `RESUME_BASE`.
`PAUSE_BASE/RESUME_BASE` évitent les macros CFS stock ; le timeout appelle
`TURN_OFF_HEATERS` sans confirmer d'image. Les `16` blocs Jinja ont été parsés
par le Python existant de la K1 via stdin, sans fichier distant.

Cette validation ne permet pas de poser R3 ou de chauffer. Les gestes manuels
ont ensuite été confirmés, puis le préflight sans effet a fermé R3 et constaté
le retour du profil actif à `default` en `6 × 6`.

Thomas a ensuite remis le `11 × 11` en un clic dans Mainsail. Une seule lecture
passive a confirmé le résultat et l'état sûr, sans transformer ce clic en
nouvelle campagne. Le successeur R4 est validé hors imprimante et par le Python
Jinja exact de la K1 : ses `20` blocs choisissent entre réutiliser sans mesure
une géométrie encore valide avec `T1A` conservé, ou palper sans filament avant
l'insertion officielle. Les deux chemins rejoignent ensuite la purge, le
décrochage E4 et les deux arrêts caméra. La partie exécutée avec filament engagé
ne contient aucun homing, aucune palpation et aucune calibration de mesh. Sa
pose et son essai restent deux étapes distinctes.
