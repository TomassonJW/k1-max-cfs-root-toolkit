# ADR-027 — Fermer le cycle hors imprimante avant tout connecteur réel

Date : 2026-08-27

Statut : **accepté pour le Goal 1 ; production et connexion K1 fermées**

## Contexte

Le garde du retrait stock, la traduction de la réponse K1 et leur validation
live en lecture seule sont fermés. Il manquait encore deux choses : la frontière
qui gère les délais et l'unicité des deux commandes, puis la machine d'états du
cycle complet.

Le vieux prototype de 17 scénarios est officiellement remplacé par le contrat
de cycle V1 à 27 scénarios. L'étendre aurait mélangé deux contrats différents.
Créer directement un connecteur réel aurait ajouté une surface d'effet avant
que les erreurs, reprises et retours arrière soient déterministes.

## Options

### 1. Ajouter tout de suite un connecteur Moonraker réel

Refusé. Les délais réels, l'encodage, la forme exacte des réponses et le point
d'intégration doivent d'abord être qualifiés en lecture seule. Un connecteur
d'effet dans le Goal 1 contredirait sa limite hors imprimante.

### 2. Continuer le prototype historique de 17 scénarios

Refusé. Il ne porte pas le nouveau modèle de filament, les trois températures
de transition, la conservation du bon filament, le retrait séparé ni les 27
scénarios canoniques.

### 3. Séparer transport simulé, cœur de cycle et future pose inerte

Retenu. Le transport simulé expose seulement `snapshot()` et `run_gcode()` au
garde. Il accepte uniquement `BOX_QUIT_MATERIAL` et `TURN_OFF_HEATERS`, une fois
chacun. Le cœur du cycle consomme des preuves synthétiques et n'importe aucun
transport. Le plan de pose épingle les sources et le futur périmètre de fichiers,
mais contient zéro commande distante et aucun script de déploiement.

## Décision

Le Goal 1 est représenté par deux paquets séparés :

- `cfs-stock-unload-guard-transport-offline-v1` pour les délais, coupures,
  réponses trompeuses et doubles envois ;
- `job-lifecycle-offline-v1` pour le démarrage, le nettoyage, le filament, les
  changements, le runout, la pause, la reprise, l'annulation et la fin.

Chaque effet CFS possède une cible explicite avant le premier effet, un
identifiant unique, une preuve de route fraîche consommée une fois, un délai et
une preuve de sortie. Une incertitude coupe les deux cibles simulées et ferme la
reprise. Aucun retry automatique n'existe.

La machine d'états reste un monolithe modulaire : modèle de contrat, moteur pur,
transport injecté et adaptateurs séparés. Aucun service ou framework nouveau
n'est ajouté.

## Conséquences

- les 13 scénarios du transport et les 27 scénarios du cycle sont exécutables
  sans K1 ;
- le retrait séparé réutilise le vrai garde simulé au lieu de dupliquer ses
  règles ;
- le plan futur connaît trois fichiers, leurs empreintes, les sauvegardes et le
  rollback, mais n'est pas déployable ;
- la géométrie, le débit visible, les délais réels, les autres slots et le
  second CFS restent des preuves futures ;
- le prochain Goal peut seulement commencer par une qualification K1 en lecture
  seule, avec une autorité distincte ;
- aucune production, pose, commande réelle ou modification Orca n'est ouverte.

Voir `docs/39-transport-hors-ligne-garde-retrait-cfs-v1.md`,
`docs/40-cycle-complet-hors-imprimante-v1.md` et
`packages/k1-control-v1/job-lifecycle-offline-v1/`.
