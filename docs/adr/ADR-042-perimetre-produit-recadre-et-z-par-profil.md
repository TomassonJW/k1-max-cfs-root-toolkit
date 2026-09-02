# ADR-042 — Périmètre produit recadré : Orca en V2, un Z par profil de mesh

Date : 2026-09-01

Statut : **acceptée**. Recadre `GOALS.md` et remplace le Goal 4 précédent.

## Contexte

Le pilotage plaçait `GOAL-P4-DAILY-CUTOVER-V1` — bascule atomique vers Orca,
demande de démarrage unique envoyée par le slicer, retrait du post-traitement —
comme objectif de clôture **obligatoire** du projet.

Thomas a corrigé ce périmètre le 1er septembre 2026.

## Besoin réel, dans ses mots

> J'utilise Orca pour slicer et exporter mes fichiers, pas forcément besoin de
> déclenchement auto. Si je peux envoyer mes fichiers directement depuis Orca,
> c'est top, mais ça me semble pas du tout prioritaire, à faire éventuellement
> en V2.

Le besoin prioritaire est machine-side :

1. des mesh calibrés **par température de plateau** ;
2. au lancement d'une impression, **le bon profil se charge automatiquement**
   selon la température de plateau lue dans le G-code ;
3. les températures filament du G-code sont respectées au chargement CFS et à
   l'impression, sans parasitage ;
4. une séquence de démarrage sans palpage Z parasite ;
5. le changement de filament — couleur, matière, ou fin de bobine avec relève
   automatique sur une bobine compatible détectée par le CFS ;
6. le nettoyage de buse reste **manuel** et assumé comme tel ;
7. le Z-offset se calibre en imprimant un grand carré (`280 × 280`), se règle à
   la main, et **s'enregistre dans le profil** pour être rechargé avec le mesh
   correspondant ;
8. l'édition **point par point** du mesh, notamment sur les bords.

## Décisions

### 1. La bascule Orca sort du chemin critique

Le Goal 4 est ramené à ce qui est réellement machine-side. L'envoi direct
depuis Orca et tout déclenchement piloté par le slicer deviennent un backlog
**V2**, hors définition de fin du projet.

Le déclenchement automatique du bon profil ne nécessite pas Orca : il se fait
côté machine, à partir de la température de plateau du fichier. Aucune
modification du slicer n'est requise pour cela.

Une seule dépendance Orca subsiste et reste obligatoire : le post-traitement
caché `+0,27 mm` doit être retiré du profil de Thomas, sous peine de double
correction du Z. C'est une suppression d'une ligne, pas une bascule.

### 2. Le Z accepté devient un attribut du profil de mesh

L'état persistant actuel ne contient qu'un enregistrement global :

```json
{"record":[1,1,-0.04,1,55, ...]}
```

Un seul Z accepté, pour un seul couple plateau/bande de température. Tant qu'un
unique profil `55 °C` existe, cela fonctionne par coïncidence. Dès la deuxième
bande calibrée, la valeur devient fausse pour l'une des deux.

Le Z accepté doit être stocké **par profil**, chargé avec lui et vérifié
ensemble. Ce correctif est un préalable à toute campagne multi-températures :
calibrer plusieurs bandes avant lui produirait des données à refaire.

### 3. Ordre contraint des travaux physiques

Les calibrations de mesh se font **sans filament inséré**, pour éviter qu'un
résidu en bord de buse ne fausse les mesures. `T1A` étant actuellement engagé,
tout retrait passe par le cutter. L'ordre est donc imposé :

retrait `T1A` → nettoyage manuel → correctif Z-par-profil → recalibration des
mesh par bande → carré `280 × 280` et réglage Z par profil → changement de
filament et relève automatique.

## Conséquences

- `GOAL-P4-DAILY-CUTOVER-V1` est réécrit et perd la bascule Orca.
- Le projet ne peut plus être déclaré terminé sur un critère Orca.
- La campagne multi-températures est bloquée derrière le correctif Z-par-profil.
- La limite de palpage `11 × 11` (arrêt observé à 36 points, contourné par
  ADR-011) redevient un prérequis actif de la recalibration.
