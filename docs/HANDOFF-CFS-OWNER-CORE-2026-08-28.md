# Handoff — cœur propriétaire CFS hors imprimante

Date de clôture : 2026-08-28

État de reprise : **ATTENDRE_GO**

Nouvelle tâche créée : non

Goal Codex créé : non

## État livré

La mission `G4-K1-CONTROL-CFS-OWNER-CORE-OFFLINE-V1` est close OK. Le paquet
`packages/k1-control-v1/cfs-owner-core-offline-v1` contient un moteur pur, son
contrat, une matrice de 21 scénarios, un lanceur local et sa preuve de résultat.
Le document canonique est `docs/45-coeur-proprietaire-cfs-hors-imprimante-v1.md`.

Le moteur rend exécutable la décision d’ADR-032 sans parler à la K1. Il exige un
seul propriétaire, mémorise la valeur précédente de l’auto-remplacement stock,
refuse d’activer le travail tant que cette politique n’est pas prouvée à `0`,
puis exige sa restitution exacte à la fermeture. Il sépare les départs
conserver/charger/changer et chaque future phase reste une intention abstraite,
ordonnée, consommable une fois et `dispatchable=false`.

La fin de bobine est modélisée entre les deux CFS. Un remplacement doit avoir
la même référence approuvée, le même type, la même couleur, le même diamètre et
la même recette thermique. Le scénario positif choisit `T2A` après l’épuisement
de `T1A`. Zéro candidat, deux candidats ou une couleur seulement proche restent
bloqués en pause. Une reprise K1 Control n’est admissible qu’après vérification
complète, sans commande de reprise stock, homing, référence Z ou mutation du
mesh.

Une cartographie périmée, une nouvelle époque de connexion, plusieurs routes
engagées, une commande CFS active ou un rappel du propriétaire stock ferment le
cycle. Un effet au résultat inconnu n’est jamais rejoué. La relecture finale a
aussi remplacé les déclarations « état complet » par une comparaison directe du
mesh, du Z, des axes, des cibles thermiques et du contexte structuré de pause
avant toute reprise.

Les sources restent celles déjà épinglées : préflight S12 nettoyé, carte
canonique, contrat de cycle et ADR-032. Le paquet conserve le fait réel que la
capture S12 ne contenait aucune paire identique. Les paires de la matrice sont
explicitement synthétiques.

## Limites réelles

Aucune connexion à la K1, commande, chauffe, mouvement, effet CFS, écriture
distante ou action de service n’a eu lieu. Le paquet ne contient ni connecteur,
ni encodeur de commande, ni script de pose, ni candidat de déploiement. Il ne
qualifie aucune coupe, aucun retrait, aucun chargement, aucune purge et aucune
fin de bobine physique.

Le Goal 3 reste à `2/7`. Ce vert logiciel n’ajoute aucune exigence physique
passée et n’ouvre pas la production. Le mesh conserve ses défauts de bord et le
nettoyage manuel reste obligatoire.

## Git et vérifications

La base de mission était `ad265692f3664a8cc73f14ff5f66cf8240c9697c`, avec
`main` et `origin/main` alignés, divergence `0/0` et checkout propre. Le travail
a été réalisé sur `codex/cfs-owner-core-offline-v1`. Aucun autre worktree ni
travail étranger n’a été touché. Le SHA final intégré sera communiqué dans le
compte rendu.

- matrice du cœur propriétaire : **OK**, `21/21` ;
- tests ciblés du nouveau paquet : **OK**, `21/21` ;
- tests ciblés élargis propriétaire/source/pilotage : **OK**, `36/36` ;
- suite complète : **OK**, `654` tests, dont `651` verts et `3` ignorés connus ;
- comparaison directe des états protégés et refus des booléens ambigus : **OK** ;
- effet sur la K1 : **non exécuté** ;
- validation physique : **non exécutée**, hors périmètre.

## Prochaine mission unique

La reprise proposée est
`G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1`. Elle préparera encore
uniquement sur le PC le garde exact qui encadrera l’auto-remplacement Creality :
lecture et sauvegarde de la valeur actuelle, au plus une intention de
désactivation, preuve avant de donner le verrou à K1 Control, puis restauration
exacte à la fin ou lors du retour arrière. Un retour incertain devra fermer la
suite sans seconde tentative.

Cette prochaine mission n’autorisera toujours aucune connexion K1, commande,
pose ou action physique. Son résultat attendu est un contrat, un adaptateur pur,
une matrice de fautes et un plan de rollback inerte. La connexion et l’essai
réel du garde resteront une gate distincte avec Thomas devant l’imprimante.

Documents à relire : `HANDOFF.md`, `GOALS.md`, les documents 43, 44 et 45,
ADR-032, `design/cfs-control-source-map-v1.json` et le contrat du nouveau paquet.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`, car la tranche est
petite mais doit borner précisément une mutation future et son rollback. Option
économique acceptable : le même modèle en `medium`, avec davantage de risque de
reprise si un retour ambigu ou une valeur stock inattendue est mal classé.

Ce clavardage source est conservé et ne doit pas être archivé.
