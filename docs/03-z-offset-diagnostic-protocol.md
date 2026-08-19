# Protocole G3 — traces comparables avant installation customisée

Statut : **A1/B/A2 exécuté mais non qualifié ; observation passive de production en cours**

Périmètre : firmware stock rooté `2.3.5.34`, K1 Max S12 structure 0, deux CFS `1.1.3` déclarés par l’écran

Décision visée : identifier le premier changement minimal justifié avant de choisir une installation customisée

## 1. Questions auxquelles la paire doit répondre

La comparaison doit séparer cinq mécanismes possibles :

1. dispersion des cinq mesures PR Touch utilisées par `G28` ;
2. remplacement logiciel d’une bonne référence Z après le premier `G28` ;
3. différence de chemin dans `START_PRINT`, notamment autour de `ACCURATE_HOME_Z`, du mesh ou de `CXSAVE_CONFIG` ;
4. effet de l’état thermique ou de la propreté de la buse ;
5. remplacement d’une consigne de température par la chaîne CFS compilée `BOX_*`.

Les ressorts jaunes ne sont pas une hypothèse par défaut : le défaut existait avant et après leur installation.

## 2. Limite d’autorité

Ce document prépare une future expérience mais ne l’autorise pas.

La préparation locale peut :

- figer et hacher un G-code privé ;
- créer un dossier brut ignoré sous `inventory/raw/g3-traces/` ;
- préparer les fiches de session et les outils d’analyse locale ;
- analyser les captures déjà présentes.

Une exécution future exige un `GO` nommé pour la session. Thomas reste l’opérateur des actions physiques et de l’interface de l’imprimante. Codex pourra seulement collecter des états et copier des journaux en lecture seule, sauf nouvelle autorisation explicite ouvrant une autre classe d’action.

Le protocole n’autorise pas :

- une écriture SSH, une modification de configuration ou un ajout d’instrumentation ;
- un redémarrage de service, un reboot ou une extinction par l’agent ;
- un homing, une chauffe, une extrusion, un mouvement ou une annulation lancés par l’agent ;
- une installation Helper Script, Moonraker, Mainsail, Fluidd ou un firmware différent.

## 3. Unité expérimentale

La preuve primaire contient deux essais `A1` / `A2` réalisés avec **le même fichier G-code, octet pour octet**, dans une même session de démarrage et sans changement volontaire de configuration.

Pour la session préparée le 19 août 2026, un essai intermédiaire `B` utilise les mêmes 637 réglages et ne change que la géométrie de `200 × 200 mm` à `200 × 201 mm`. L’ordre est donc `A1`, `B`, `A2`. A1/A2 mesurent la répétabilité ; B teste si un seul millimètre supplémentaire déclenche un autre comportement.

Le fichier idéal est un petit reproducer de première couche qui se termine seul. Si un travail plus long doit être arrêté après la première couche, Thomas effectue manuellement la même action au même point sur les trois essais et cette intervention est enregistrée. Une annulation différente entre les essais invalide la comparaison d’état après impression.

Le G-code et les captures brutes restent privés. Seuls leur SHA-256, les événements nettoyés et les conclusions peuvent entrer dans Git.

## 4. Conditions fixes obligatoires

Avant `A1`, les valeurs suivantes sont choisies et copiées dans `session-record.md`. Elles ne changent pas avant la fin de `A2` :

| Domaine | Condition fixe |
|---|---|
| G-code | même fichier et même SHA-256 |
| Trancheur | aucune nouvelle génération entre les essais |
| Plateau | même plaque, même face, même orientation, non déplacée |
| Buse | même buse ; procédure de nettoyage manuel identique |
| Filament | même bobine, même emplacement CFS et même trajet |
| CFS | mêmes unités sous tension et même sélection de matériau |
| Interface | même chemin de lancement et mêmes options visibles de calibration |
| Configuration | aucun fichier, offset, mesh, macro ou paramètre modifié |
| Démarrage | même session de boot ; aucun reboot ni restart entre `A1`, `B` et `A2` |
| Intervention | aucune correction Z, extrusion ou commande manuelle pendant la première couche |

Avant chaque essai, le lit et la buse doivent revenir dans la même fenêtre thermique : écart entre les trois départs inférieur ou égal à `2 °C` pour chacun, avec une variation inférieure ou égale à `1 °C` pendant les cinq minutes précédant le lancement. Les valeurs réelles sont enregistrées ; elles ne sont pas remplacées par les seules consignes.

Si l’une de ces conditions n’est pas tenue, l’essai reste une observation utile mais la paire n’est pas déclarée comparable.

## 5. Preflight de session

La session reçoit un identifiant local de forme `YYYYMMDD-HHMM-g3-pair`.

Sous `inventory/raw/g3-traces/<session-id>/`, conserver :

- le G-code privé ou son emplacement local contrôlé ;
- `session-record.md` rempli à partir du modèle ;
- un `event-timeline.csv` par essai ;
- les journaux bruts copiés de l’imprimante ;
- les photos originales ;
- les sorties des commandes de lecture et leurs horodatages ;
- les SHA-256 de chaque artefact.

Avant connexion ou lancement :

1. confirmer que l’imprimante est au repos et qu’aucune autre tâche n’est en attente ;
2. confirmer l’hôte exact sans le recopier dans Git ;
3. calculer localement le SHA-256 du G-code ;
4. vérifier que le dossier de session est ignoré par Git ;
5. relever l’heure locale et l’heure de la machine sans les modifier ;
6. relever en lecture seule l’uptime, les fichiers de journaux actifs et leurs métadonnées ;
7. relever l’empreinte de la configuration active et la valeur Z sauvegardée ;
8. confirmer visuellement plaque, filament, CFS et options de lancement ;
9. consigner les températures réelles pendant cinq minutes ;
10. arrêter si une lecture risque d’écrire, de faire tourner les logs ou de modifier un service.

## 6. Exécution de `A1`

1. Thomas applique la procédure manuelle de nettoyage convenue.
2. Codex effectue uniquement le relevé de lecture avant essai explicitement prévu.
3. Thomas lance le fichier depuis l’interface choisie.
4. Aucune correction n’est appliquée pendant la première couche, sauf arrêt de sécurité.
5. Relever l’heure visible du lancement et photographier la première couche avec les mêmes cadrage et éclairage prévus pour `B` et `A2`.
6. Attribuer un résultat : `trop_haut`, `acceptable`, `trop_bas`, `contact_dangereux` ou `mixte`.
7. Si le travail ne se termine pas seul, Thomas l’arrête manuellement au point convenu.
8. Après l’arrêt ou la fin, copier les journaux existants vers le poste local sans les tronquer ni les faire tourner.
9. Relever de nouveau la valeur Z sauvegardée, le mesh actif identifiable, les températures et les métadonnées des fichiers concernés.

Un bruit anormal, un contact buse/plateau, une extrusion dangereuse ou une erreur machine impose l’arrêt manuel immédiat. L’essai est classé `sécurité`, pas `échec fonctionnel`.

## 7. Retour à l’état de départ

Avant chaque essai suivant :

1. ne pas redémarrer la machine et ne modifier aucun fichier ;
2. retirer seulement la pièce imprimée, sans déplacer la plaque ;
3. répéter exactement la procédure manuelle de nettoyage ;
4. attendre la fenêtre thermique définie à la section 4 ;
5. confirmer qu’aucun offset manuel, changement de slot ou nouveau mesh volontaire n’a été appliqué ;
6. enregistrer toute différence imprévue au lieu de la masquer.

Si le firmware a spontanément changé de mesh, de valeur sauvegardée ou de chemin de préparation, cette différence est une donnée importante. Elle n’est toutefois pas une raison pour prétendre que les conditions étaient identiques.

## 8. Exécution de `B`, puis de `A2`

Exécuter B avec le même opérateur, le même chemin de lancement, les mêmes observations et les mêmes bornes de collecte. B conserve tous les réglages de A et change seulement la dimension Y de `200` à `201 mm`.

Après le même retour à l’état de départ, exécuter A2 avec le fichier exact de A1. Vérifier son SHA-256 avant lancement. Ne pas redémarrer entre les trois essais.

Ne pas lancer automatiquement un quatrième essai ni un test CFS. La séquence A1/B/A2 est d’abord qualifiée et analysée. Un essai après redémarrage demande une nouvelle décision fondée sur le résultat obtenu.

## 9. Événements à extraire des journaux

L’analyse doit reconstituer, lorsqu’ils sont observables, les événements suivants :

| Domaine | Événements recherchés | Valeurs associées |
|---|---|---|
| Lancement | réception du travail, entrée dans `START_PRINT` | horodatage, paramètres transmis |
| CFS initial | `BOX_START_PRINT`, sélection du slot | unité, slot, matériau |
| Homing initial | `CX_ROUGH_G28`, `G28`, PR Touch | cinq mesures, médiane, étendue, `self_z_offset` |
| Nettoyage | `CX_NOZZLE_CLEAR` / `NOZZLE_CLEAR` | ordre, températures avant/après |
| Homing final | `ACCURATE_G28`, `ACCURATE_HOME_Z` | ordre, valeur Z observable avant/après |
| Mesh | `CX_PRINT_LEVELING_CALIBRATION`, `CHECK_BED_MESH`, `G29`, chargement ou génération | identifiant, état, heure |
| Persistance | `CXSAVE_CONFIG` ou changement du bloc sauvegardé | ancienne/nouvelle valeur, fichier concerné |
| CFS extrusion | `BOX_START_PRINT_EXTRUDE_MATERIAL` et transitions `BOX_*` | consigne avant, consigne imposée, restauration |
| Chauffe | `M104`, `M109`, lit et buse | cible, réel, durée, origine de la commande |
| Première couche | première extrusion et début de couche | heure, Z/offset observable, résultat visuel |

Une absence d’événement dans le log doit être notée `non_observable`, jamais transformée en preuve d’absence d’exécution.

## 10. Qualification de la paire

La comparaison passe successivement cinq gates locales :

### Q1 — Intégrité

- SHA-256 du G-code identique ;
- captures attribuables sans ambiguïté à `A1`, `B` ou `A2` ;
- horodatages suffisamment alignés pour reconstruire l’ordre.

### Q2 — Conditions initiales

- toutes les conditions fixes sont respectées ;
- températures dans les tolérances ;
- aucune intervention cachée ou modification de configuration.

### Q3 — Chemin d’exécution

- même suite de préparation, homing, nettoyage, mesh et CFS ;
- si les chemins divergent, la divergence est la conclusion principale et la comparaison numérique directe est suspendue.

### Q4 — Observabilité

- début de travail et première couche couverts ;
- événements Z et température suffisamment visibles pour tester au moins une hypothèse ;
- valeurs manquantes explicitement marquées.

### Q5 — Pouvoir discriminant

- A1 et A2 différents : la paire peut expliquer la variabilité si Q1–Q4 passent ;
- A1 et A2 équivalents mais B différent : la géométrie ou une couche informée de son contour devient la piste principale ;
- résultats identiques et corrects : la paire ne reproduit pas le défaut ;
- résultats identiques et mauvais : la paire confirme un défaut déterministe mais ne localise pas seule sa cause.

Seule une paire passant Q1 à Q4 est appelée **comparable**.

## 11. Mesures calculées localement

Pour chaque série PR Touch observable :

- les cinq valeurs brutes dans leur ordre ;
- médiane ;
- minimum, maximum et étendue ;
- écart absolu médian ;
- différence de médiane entre `A1` et `A2`.

Pour le Z effectif :

- valeur sauvegardée avant et après chaque essai ;
- valeur affichée ou journalisée après le premier `G28` ;
- valeur après `ACCURATE_HOME_Z` si observable ;
- dernière opération capable de changer la référence avant la première extrusion.

Pour les températures :

- cible issue du G-code ;
- cible imposée par chaque étape `BOX_*` observable ;
- écart maximal à la cible demandée ;
- durée de l’écart ;
- présence et moment d’une restauration.

Les calculs gardent la précision source. Aucun seuil d’acceptation mécanique n’est inventé sans série suffisante ou spécification applicable à cette révision.

## 12. Matrice de décision avant installation customisée

| Observation confirmée | Première intervention à préparer | Ce qui n’est pas encore justifié |
|---|---|---|
| PR Touch dispersé sous conditions stables | traiter propreté, contact, thermique ou répétabilité mécanique ; nouvelle série bornée | ajouter un offset logiciel permanent |
| PR Touch stable mais Z change après `ACCURATE_HOME_Z` | override minimal appliqué après la dernière remise à zéro, avec backup et rollback | remplacer toute la pile Klipper |
| Chemin de calibration différent entre essais | wrapper de démarrage explicite avec modes référence/rapide | modifier simultanément Z, mesh et CFS |
| `CXSAVE_CONFIG` persiste une valeur remplacée ailleurs | corriger le producteur de valeur ou l’ordre, pas le mécanisme de sauvegarde | supprimer aveuglément la persistance |
| `BOX_*` impose `220 °C` puis restaure mal | paramétrage ou wrapper CFS minimal autour de la transition | abandonner les deux CFS ou forker OrcaSlicer |
| Logs stock insuffisants pour localiser une frontière | instrumentation minimale et temporaire préparée sous G4 | installer une interface complète uniquement pour « voir plus » |
| Plusieurs correctifs minimaux échouent avec preuves et rollback | ADR comparant overlay stock, Klipper custom hybride et remplacement plus large | choisir immédiatement une installation communautaire générique |

La décision d’installation customisée n’est prise qu’après un rapport de comparaison accepté. Le choix par défaut reste un overlay minimal compatible écran et double CFS ; un remplacement large doit démontrer un meilleur rapport bénéfice/risque et une récupération validée pour S12 structure 0.

## 13. Critères de sortie vers G3

Le protocole produit une décision exploitable si :

- au moins une paire passe Q1 à Q4 ;
- le chemin final qui établit Z est observé ou sa dernière frontière non observable est précisément bornée ;
- dispersion de mesure et remplacement logiciel restent des hypothèses séparées ;
- la chronologie de température CFS est mesurée ;
- une seule classe d’intervention est proposée avec succès, échec et rollback mesurables ;
- les limites et données manquantes sont explicites.

G3 peut alors autoriser la **préparation** d’un patch et de son rollback. Le déploiement reste soumis à G4 pour ce changement nommé.
