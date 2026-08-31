# K1 Control — interface du cycle stock dérivé V1

Statut : **installé et validé statiquement, sans essai physique**.

Ce paquet remplace la page principale K1 Control par le parcours d’impression
possédé installé sous `stock-derived-cycle-activation-v1`. Le sous-dossier
`calibration/` déjà installé reste strictement inchangé et accessible depuis
l’en-tête.

## Parcours utilisateur

1. déclarer une fois les bobines réellement présentes dans `T1A..T2D` ;
2. choisir un G-code Orca et la bobine de départ ;
3. confirmer présence, caméra et volume libre ;
4. cliquer une fois sur `Préparer et lancer l’impression` ;
5. si demandé, nettoyer réellement la buse et le plateau puis confirmer ;
6. laisser K1 Control gérer géométrie, insertion, purge, ligne d’amorce,
   impression, changements, roulement de bobine et fin sûre.

Le roulement ne choisit jamais une bobine par matière seule. Il exige une seule
bobine disponible avec la même référence, matière, couleur, diamètre, recette
thermique et approbation utilisateur. Zéro ou plusieurs correspondances
ferment le chemin de reprise en sécurité.

## Limite caméra explicite

La page montre les arrêts caméra, mais ne propose aucun bouton `PASS`. Le pilote
local actuel sait capturer une image fraîche, contrôler son cadrage et sa
netteté. Il ne possède encore que la référence `SAFE_IDLE_PARK` : les références
de purge, de ligne d’amorce et de première couche doivent être acquises pendant
une campagne physique surveillée avant de rendre le verdict sémantique autonome.

Le déploiement de cette interface est purement statique : aucune chauffe,
mouvement, extrusion, trame CFS, palpation, recalcul de mesh, commande G-code ou
redémarrage de service.

La capture `20260831-215849-g4-k1-control-stock-derived-cycle-ui-v1` a obtenu la
pose puis une validation indépendante. Les trois fichiers racine correspondent
au manifeste, le sous-dossier `calibration/` est inchangé et le propriétaire
installé reste actif au repos sûr.
