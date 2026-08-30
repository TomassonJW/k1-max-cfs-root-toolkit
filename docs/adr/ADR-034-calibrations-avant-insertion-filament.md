# ADR-034 — Terminer les palpations avant l'insertion du filament

## Contexte

Le 30 août 2026, Thomas a terminé les trois gestes demandés : buse nettoyée,
plateau nettoyé et libre, puis `T1A` réengagé avec la fonction officielle. Il a
ensuite renettoyé la buse, car une insertion laisse toujours un résidu sous la
buse. Sans ce second nettoyage, une nouvelle palpation aurait pu être faussée.

R3 faisait pourtant l'inverse de la règle cible déjà écrite dans le contrat du
cycle : il exigeait `T1A` engagé, purgeait `20 mm`, décrochait la boule, puis
appelait `ACCURATE_G28`. La caméra pouvait voir un gros filament restant, mais
elle ne pouvait pas garantir une surface de buse assez propre pour la mesure de
contact.

## Décision

Une insertion, un chargement ou une purge est désormais une frontière de
contamination. Dans la version finale :

1. classer l'état filament ;
2. si une palpation Z ou un mesh est nécessaire, exiger l'absence de route
   engagée et un nettoyage manuel consommable une fois ;
3. chauffer et stabiliser aux températures de mesure ;
4. terminer toutes les références et mesures par contact ;
5. charger puis relire le mesh et le Z acceptés ;
6. seulement ensuite résoudre et insérer le filament ;
7. purger, prouver le débit et vérifier la buse par caméra ;
8. amorcer hors zone utile puis commencer le modèle.

Un travail qui conserve un bon filament déjà engagé ne fait aucune nouvelle
palpation. Il réutilise une géométrie encore valide. Si la géométrie doit être
réétablie, ce travail quitte le chemin « conserver » : désengagement, nettoyage,
palpation, puis nouvelle insertion.

Le nettoyage humain après une insertion peut sécuriser un diagnostic ponctuel,
mais il ne valide pas l'ordre final et ne crée pas d'exception automatique. Une
image caméra ne remplace jamais la règle d'ordre ni la confirmation de
nettoyage.

## Conséquences

- ADR-033 est supersédée sur l'ordre purge/palpation.
- R3 est fermé avec `SUPERSEDED_NEVER_DEPLOY_OR_RUN_PROBING_AFTER_INSERTION`.
- Sa validation Jinja et ses deux arrêts caméra restent des preuves froides
  historiques, pas un candidat de pose.
- Le prochain candidat exécutable devra séparer la géométrie sans filament du
  chargement CFS qui suit ; aucun simple déplacement de `ACCURATE_G28` dans R3
  ne suffit.
- Toute insertion invalide le jeton « buse propre pour palpation », mais
  n'invalide pas à elle seule un mesh et un Z déjà acceptés.
- La machine observée après les gestes manuels reste sans essai chaud : le
  préflight a trouvé `T1A` engagé mais le mesh actif `default` en `6 × 6`, donc
  la gate est aussi fermée sur dérive de profil.

## Alternatives refusées

- **Purger puis juger la propreté à la caméra** : la caméra ne mesure pas le
  petit résidu qui peut modifier un contact Z.
- **Nettoyer systématiquement après insertion puis palper** : cela ajoute une
  action humaine fragile et conserve le mauvais ordre dans le produit final.
- **Garder R3 pour un seul essai chaud** : ce test qualifierait une séquence que
  le produit ne doit pas reproduire.
