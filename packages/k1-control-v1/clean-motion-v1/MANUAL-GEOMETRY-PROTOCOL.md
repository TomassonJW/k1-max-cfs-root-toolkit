# Protocole manuel — cartographie réelle de la brosse

La capture est strictement en lecture seule. Thomas commande lui-même les
déplacements depuis l'écran ou l'interface de la K1. Codex n'envoie aucun
G-code pendant cette phase.

## Règles de sécurité

- buse et plateau froids ; aucune extrusion ni action CFS ;
- conserver la vue directe sur la buse et l'arrêt immédiat disponible ;
- près de la brosse, descendre par pas de `0,1 mm` maximum ;
- arrêter au premier effleurement visuel, sans déformer ni comprimer la brosse ;
- avant tout déplacement X/Y entre deux coins, remonter Z d'au moins `2 mm` ;
- au moindre bruit, contact dur, déplacement de la brosse ou doute : arrêter et
  annoncer `CAPTURE KO`.

## Ordre à suivre pendant la capture active

À chaque point, rester complètement immobile pendant **10 secondes** :

1. coin `A` : bord `X− / Y−`, Z au premier effleurement visuel ;
2. remonter Z d'au moins `2 mm`, aller au coin `B` : `X+ / Y−`, redescendre au
   premier effleurement, tenir 10 secondes ;
3. remonter, aller au coin `C` : `X+ / Y+`, redescendre, tenir 10 secondes ;
4. remonter, aller au coin `D` : `X− / Y+`, redescendre, tenir 10 secondes ;
5. remonter Z d'au moins `10 mm`, revenir devant la zone à une position sûre et
   tenir 10 secondes.

Les arrêts intermédiaires courts sont permis. L'analyseur ne retient que les
positions stables pendant au moins six secondes. Les quatre coins restent à
confirmer humainement après analyse ; ils ne deviennent pas automatiquement une
recette de brossage.
