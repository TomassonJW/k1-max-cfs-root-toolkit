# Paire de traces G3

Ce dossier contient uniquement les modèles publics du protocole G3.

Pour une session réelle :

1. créer localement `inventory/raw/g3-traces/<session-id>/` ;
2. copier les trois modèles dans ce dossier ignoré ;
3. conserver les G-code, journaux complets, photos et données réseau uniquement dans ce dossier brut ;
4. remplir un `event-timeline-R1.csv` et un `event-timeline-R2.csv` ;
5. produire ensuite un rapport nettoyé sans secret ni contenu constructeur brut.

Modèles :

- `templates/session-record.md` : invariants, autorité et conditions de chaque run ;
- `templates/event-timeline.csv` : chronologie normalisée ;
- `templates/comparison-report.md` : qualification Q1–Q5 et décision.

Le protocole de référence est `docs/03-z-offset-diagnostic-protocol.md`.
