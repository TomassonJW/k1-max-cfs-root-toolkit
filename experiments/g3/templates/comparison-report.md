# Comparaison G3 — <session-id>

## Verdict de comparabilité

| Gate | Verdict | Preuve ou écart |
|---|---|---|
| Q1 — intégrité | OK / KO / inconnu | |
| Q2 — conditions initiales | OK / KO / inconnu | |
| Q3 — chemin d’exécution | OK / KO / inconnu | |
| Q4 — observabilité | OK / KO / inconnu | |
| Q5 — pouvoir discriminant | différent / identique_correct / identique_mauvais / inconnu | |

Paire comparable : oui / non

## Résultat physique

| Run | Classe première couche | Gravité | Photo privée | Intervention |
|---|---|---:|---|---|
| R1 | | | | |
| R2 | | | | |

## PR Touch et référence Z

| Mesure | R1 | R2 | Différence |
|---|---:|---:|---:|
| échantillon 1 | | | |
| échantillon 2 | | | |
| échantillon 3 | | | |
| échantillon 4 | | | |
| échantillon 5 | | | |
| médiane | | | |
| étendue | | | |
| écart absolu médian | | | |
| Z sauvegardé avant | | | |
| Z sauvegardé après | | | |
| Z après homing final observable | | | |

Dernière opération capable d’établir ou remplacer Z avant extrusion :

## Chemin d’exécution

| Événement | R1 ordre/heure | R2 ordre/heure | Équivalent |
|---|---|---|---|
| `START_PRINT` | | | oui / non / inconnu |
| `BOX_START_PRINT` | | | oui / non / inconnu |
| `CX_ROUGH_G28` / `G28` | | | oui / non / inconnu |
| `CX_NOZZLE_CLEAR` | | | oui / non / inconnu |
| `ACCURATE_G28` / `ACCURATE_HOME_Z` | | | oui / non / inconnu |
| mesh / `G29` / `CXSAVE_CONFIG` | | | oui / non / inconnu |
| `BOX_START_PRINT_EXTRUDE_MATERIAL` | | | oui / non / inconnu |
| première extrusion | | | oui / non / inconnu |

## Température et CFS

| Mesure | R1 | R2 | Différence |
|---|---:|---:|---:|
| cible G-code buse | | | |
| cible maximale imposée par `BOX_*` | | | |
| écart maximal | | | |
| durée de l’écart | | | |
| cible restaurée avant première couche | | | |

## Hypothèses

| Hypothèse | Confirmée | Réfutée | Non observable | Preuve |
|---|---|---|---|---|
| dispersion PR Touch | | | | |
| remplacement Z après mesure | | | | |
| chemin de préparation variable | | | | |
| état thermique / nettoyage | | | | |
| remplacement de cible par CFS | | | | |

## Décision

- fait confirmé principal :
- limite principale :
- première intervention unique proposée :
- effet attendu :
- critère de succès :
- critère d’échec :
- sauvegarde nécessaire :
- rollback prévu :
- Gate G3 : passer / rester ouverte
- Gate G4 à préparer pour :
- installation customisée large : non justifiée / ADR nécessaire

## Publication

- données privées supprimées : oui / non
- contenu constructeur brut absent : oui / non
- adresses, hôtes, identifiants et photos sensibles retirés : oui / non
- rapport public prêt : oui / non
