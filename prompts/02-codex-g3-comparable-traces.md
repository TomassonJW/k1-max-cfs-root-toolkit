# Mission Codex — paire de traces comparables G3

Utiliser ce prompt uniquement après un `GO` explicite nommant la session de traces et confirmation que l’imprimante est au repos.

---

Travaille dans le clone local de `TomassonJW/k1-max-cfs-root-toolkit`.

Ta mission est de collecter et comparer la séquence `A1`, `B`, `A2` selon `docs/03-z-offset-diagnostic-protocol.md`. A1 et A2 utilisent le même fichier `200 × 200 mm`; B utilise les mêmes réglages avec `200 × 201 mm`. L’imprimante reste en configuration stock rootée. Thomas réalise toutes les actions physiques et tous les lancements depuis l’interface de la machine ; Codex reste en lecture seule sur la machine.

## Avant toute action

1. Lire intégralement `AGENTS.md`, `STATE.md`, `GATES.md`, `HANDOFF.md`, le protocole G3 et les règles de nettoyage.
2. Vérifier l’état Git et ne pas mélanger de travail étranger.
3. Copier les modèles de `experiments/g3/templates/` vers `inventory/raw/g3-traces/<session-id>/`.
4. Vérifier que ce dossier brut est ignoré.
5. Recevoir le G-code privé choisi par Thomas et calculer son SHA-256 localement.
6. Écrire dans la fiche les conditions fixes, l’arrêt éventuel et les seuils thermiques.
7. Confirmer l’hôte exact sans afficher ni enregistrer de secret.
8. Confirmer que Thomas a donné le `GO` pour cette session exacte.

## Limites impératives

- Ne jamais écrire, envoyer ou créer un fichier sur l’imprimante.
- Ne jamais lancer un print, une chauffe, un mouvement, un homing, une extrusion, une calibration ou une annulation.
- Ne jamais redémarrer la machine ou un service.
- Ne pas changer offset, mesh, macro, configuration, slot CFS ou température.
- Ne pas utiliser de redirection distante, `tee`, commande destructive, installateur ou upload.
- Ne pas ajouter d’instrumentation pendant cette session.
- Arrêter si une commande n’est pas sûrement en lecture seule.

## Collecte autorisée

Après validation de l’hôte, limiter les commandes distantes à la lecture : identité, date, uptime, températures et états exposés, `stat`, `sha256sum`, listes bornées, recherche ciblée dans les journaux existants et copie imprimante-vers-poste. Ne jamais tronquer ou faire tourner un journal.

Avant et après chaque essai, relever au minimum :

- heure machine et heure locale ;
- uptime ;
- température réelle buse/lit ;
- empreinte de la configuration active ;
- valeur Z sauvegardée ;
- métadonnées du journal actif ;
- état ou identifiant de mesh observable ;
- fichiers copiés et leurs SHA-256 locaux.

Thomas confirme plaque, buse, filament, CFS, chemin de lancement et options visibles. Thomas lance `A1`, puis `B`, puis `A2`, et intervient uniquement pour la sécurité ou pour l’arrêt manuel convenu. Aucun redémarrage n’a lieu entre les trois essais.

## Marqueurs de progression

Ne produire chaque marqueur qu’après contrôle réel :

- `G3_PAIR_PREFLIGHT_OK`
- `G3_A1_CAPTURE_OK`
- `G3_B_CAPTURE_OK`
- `G3_RESET_CONDITIONS_OK`
- `G3_A2_CAPTURE_OK`
- `G3_PAIR_QUALIFIED_OK` ou `G3_PAIR_NOT_COMPARABLE`

## Analyse locale

1. Construire les chronologies avec le modèle CSV.
2. Qualifier Q1 à Q5 sans combler les valeurs absentes.
3. Calculer médiane, étendue et écart absolu médian des cinq mesures PR Touch si elles sont visibles.
4. Comparer la dernière opération Z avant extrusion.
5. Comparer les chemins mesh, `CXSAVE_CONFIG` et `ACCURATE_HOME_Z`.
6. Comparer les cibles du G-code et celles imposées/restaurées par `BOX_*`.
7. Choisir une seule première intervention ou conclure que la preuve reste insuffisante.
8. Ne pas lancer automatiquement un quatrième essai, un redémarrage ou un test CFS.

## Publication

Les journaux complets, G-code, photos, adresses, noms d’hôte et fichiers constructeur restent sous le chemin ignoré. Publier seulement un rapport nettoyé, les métriques nécessaires, les empreintes et la décision de gate.

Mettre à jour `STATE.md`, `GATES.md`, `HANDOFF.md` et `DECISIONS.md` si une décision est acceptée. Sous l’autorité D-010, terminer normalement branche, commit, push, PR, fusion dans `main` et nettoyage après validation du périmètre public.

## Rapport final

Rendre :

- verdict comparable ou non comparable ;
- faits confirmés sur Z, mesh et température CFS ;
- valeurs non observables ;
- différence physique A1/B/A2 ;
- première intervention unique recommandée ;
- critères de succès, échec et rollback ;
- état de G3 et prochaine autorité nécessaire ;
- preuve qu’aucune écriture distante Codex n’a eu lieu.
