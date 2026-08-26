# Protocole physique — MESH-EDGE-DIAGNOSTIC-V1

Ce protocole couvre une seule comparaison : source composite puis correction
locale. Il s'arrête au premier KO et ne qualifie ni un profil quotidien ni le
mode Précision.

## Incident et suspension

Le premier passage source a déplacé et chauffé la machine, mais n'a déposé
aucun filament. Il ne prouve pas une buse bouchée : le G-code minimal n'appelait
aucune sélection CFS, aucun chargement et aucune purge. La mention `T0` de la
première révision était une hypothèse de Codex, pas un fait fourni par Thomas.

Avant toute nouvelle action physique, exécuter le rollback exact, retirer le
profil diagnostic et les quatre G-code, revalider la base sûre, puis repasser
la gate hors imprimante corrigée. Aucun motif ne doit être relancé directement.

## Avant toute extrusion

- Thomas est présent devant la K1.
- Le plateau est libre, propre et porte `PEI_TEXTURED_A` correctement assise.
- Le filament est le même PLA Geeetech pour les deux variantes. Son outil
  logique, son CFS et son slot sont résolus depuis l'état frais ; aucun `T0`
  n'est supposé.
- La route filament est confirmée immédiatement avant chaque motif.
- Une petite purge fraîche sort réellement dans le réceptacle immédiatement
  avant chaque motif. Un capteur de présence seul ne suffit pas.
- Le tube PTFE et le faisceau ont un mou neutre reproductible sur tout le
  contour ; aucun démontage ni changement de fixation entre variantes.
- Le préflight prouve `standby`, cibles zéro, deux CFS, stockage Z `ok`, Z
  accepté `-0,04 mm`, profils robuste et source présents.
- Le fichier `PREPARE` se termine sans chauffe ni extrusion. Son état final doit
  montrer le profil attendu et le Z effectif `-0,04 mm` avant que le fichier
  `PATTERN` soit autorisé. Aucun réglage Z en direct n'est permis.

## Carte physique

La première ligne de la matrice est l'avant `Y=5`; la dernière est l'arrière
`Y=295`. La première colonne est la gauche `X=5`; la dernière est la droite
`X=295`. L'écart entre cellules vaut `29 mm`.

La zone témoin est `ligne 9 / colonne 1`, soit `X=34, Y=266`, près de
l'arrière-gauche. Le candidat applique `Éloigner +0,010 mm` à ce seul point,
puis la normalisation de surface déjà validée.

Les repères du motif sont asymétriques : triangle avant-gauche, deux traits
avant-droit, trois traits arrière-gauche, carré arrière-droit. La croix centrale
sert de témoin inchangé.

## Passage 1 — source

1. Exécuter `01A-SOURCE-PREPARE`, sans chauffe ni extrusion.
2. Relever le profil actif, le Z effectif et la disposition PTFE.
3. Résoudre et confirmer le filament réellement engagé, sans supposer un outil.
4. Faire une petite purge dans le réceptacle et confirmer visuellement le débit.
5. Lancer `01B-SOURCE-PATTERN` seulement si les preuves sont conformes.
6. Arrêter sur bruit, traction, absence de débit, décollement, frottement ou
   changement d'état.
7. Photographier le motif entier puis la zone `(34,266)` sans déplacer la
   plaque avant le verdict.

## Passage 2 — correction

Le passage 2 n'est permis que si le passage 1 est exploitable et si le plateau
est de nouveau confirmé libre et propre. Les paramètres et la disposition PTFE
restent identiques.

1. Exécuter `02A-CORRECTED-PREPARE`, sans chauffe ni extrusion.
2. Prouver le profil dérivé et le même Z effectif `-0,04 mm`.
3. Reconfirmer la même route filament et obtenir une nouvelle purge visible.
4. Lancer `02B-FARTHER-X034-Y266-PATTERN` une seule fois.
5. Photographier avec les mêmes vues et consigner seulement les faits visibles.

## Verdict humain

- `OK signe` : la cellule témoin est moins surcomprimée sans trou, sans transfert
  du défaut aux voisines et sans dégradation de la croix centrale.
- `KO signe` : la cellule est plus écrasée, trop haute, ouverte ou ses voisines
  se dégradent.
- `KO répétabilité` : le défaut source ne revient pas au même endroit ou change
  fortement sans changement volontaire.
- `KO mécanique/PTFE` : la traction varie avec la position, le mou neutre ne
  peut pas être conservé ou le défaut suit clairement cette traction.
- `Inconnu` : photo ou observation insuffisante. Ne pas promouvoir en `OK`.

## Fin obligatoire

Quel que soit le verdict, y compris le passage sans filament déjà observé :
cibles zéro, retour au robuste, profil diagnostic retiré par restauration exacte
de `printer.cfg`, G-code supprimés, axes libérés et état final relu. Ne pas
enchaîner `MESH-DERIVED-PROFILE-V1`.
